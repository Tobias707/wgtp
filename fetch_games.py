"""
fetch_games.py – Erweitert games_data.json mit neuen Spielen aus der SteamSpy API.
Inklusiv Reparatur von sekundären Feldern und Software-Tool-Flagging.

Quellen (in Reihenfolge abgefragt):
  1. top100in2weeks  – gerade trending
  2. top100forever   – Langzeit-Klassiker
  3. top100owned     – nach Besitzerzahl

Workflow:
  1. Fetch neue Games via SteamSpy Top-100
  2. Repariere sekundäre Felder (difficulty, story, session) für Games mit numerischen Tags
  3. Flagge Software-Tools (Utilities, Dev Tools, etc.)

Edge Cases:
  - Spiel already in Liste → wird übersprungen (per appid)
  - Kein review_score / zu wenige Reviews → wird übersprungen
  - Spiel ist shut down (z.B. 0 positive reviews) → wird übersprungen
  - API-Fehler / fehlende Felder → Spiel wird übersprungen, Error geloggt
  - Dry-run-Modus: --dry-run zeigt nur was hinzugefügt würde

Usage:
  python fetch_games.py                  # fetch + repair (one-shot)
  python fetch_games.py --dry-run        # zeigt Kandidaten ohne zu schreiben
  python fetch_games.py --limit 20       # max. 20 neue Spiele hinzufügen
  python fetch_games.py --min-score 80   # min. review_score (Standard: 60)
"""

import argparse
import json
import time
import sys
import io
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    sys.exit("requests nicht installiert. Bitte: pip install requests")

# ── Konfiguration ──────────────────────────────────────────────────────────────

DATA_FILE = Path(__file__).parent / "games_data.json"

STEAMSPY_SOURCES = [
    "top100in2weeks",
    "top100forever",
    "top100owned",
]

DETAIL_URL        = "https://steamspy.com/api.php?request=appdetails&appid={appid}"
LIST_URL          = "https://steamspy.com/api.php?request={source}"
STEAMSPY_ALL_URL  = "https://steamspy.com/api.php?request=all&page={page}"
SEEN_IDS_FILE     = Path(__file__).parent / "seen_appids.json"

# Spiele die generell rausgefiltert werden (Valves eigene Tools, Soundtracks etc.)
BLOCKLIST_APPIDS = {
    228980,  # Steamworks Common Redistributables
    250900,  # The Binding of Isaac: Rebirth Demo
    1070560, # Steam Linux Runtime
}

# Tags die auf DLC/Soundtrack/Tool hinweisen → überspringen
SKIP_TAG_KEYWORDS = {"soundtrack", "dlc", "demo", "playtest", "beta"}

# ── Quiz-Mapping ───────────────────────────────────────────────────────────────

GENRE_TAG_MAP = {
    "action":      {"FPS","Action","Action-Adventure","Action RPG","Hero Shooter","Battle Royale","Melee","Fighting"},
    "rpg":         {"RPG","Action RPG","CRPG","MMORPG","Hack and Slash","Dungeon Crawler","Rogue-like"},
    "strategy":    {"Strategy","Turn-Based Strategy","4X","Grand Strategy","City Builder","RTS","Management","Real-Time with Pause","Tower Defense"},
    "puzzle":      {"Puzzle","Logic","Physics Puzzle","Point & Click"},
    "adventure":   {"Adventure","Action-Adventure","Exploration","Narrative"},
    "shooter":     {"FPS","Third-Person Shooter","Hero Shooter","Extraction Shooter","Looter Shooter"},
    "simulation":  {"Simulation","Driving","Automobile Sim","Farming Sim","Life Sim","Economy","Transportation","Flight"},
    "horror":      {"Horror","Survival Horror","Psychological Horror","Gore","Supernatural"},
    "roguelike":   {"Rogue-like","Rogue-lite","Action Roguelike","Roguelike Deckbuilder"},
    "platformer":  {"Platformer","2D Platformer","Platform Fighter","Metroidvania"},
    "sports":      {"Sports","Racing","Football (Soccer)","Basketball","Football (American)","Golf"},
    "sandbox":     {"Sandbox","Open World Survival Craft","Building","Base-Building","Crafting","Survival"},
}

MULTIPLAYER_TAGS = {"Multiplayer","Co-op","Online Co-Op","Local Co-Op","MMO","MMORPG","Team-Based","PvP","PvE"}
SINGLEPLAYER_TAGS = {"Singleplayer","Single-player","Story Rich","Atmospheric","Walking Simulator"}

DIFFICULTY_MAP = {
    "hard":   {"Difficult","Dark Souls-like","Souls-like","Rogue-like","Competitive","Hardcore","Permadeath"},
    "chill":  {"Relaxing","Cozy","Casual","Family Friendly","Cute","Atmospheric","Walking Simulator"},
}

STORY_MAP = {
    "core":       {"Story Rich","Choices Matter","Multiple Endings","Visual Novel","Narrative","Interactive Fiction"},
    "irrelevant": {"Multiplayer","PvP","Competitive","Sports","Racing","E-sports"},
}

SESSION_MAP = {
    "short": {"Casual","Quick","Short","Arcade","Match 3"},
    "long":  {"Open World","MMO","4X","Grand Strategy","CRPG","Long","Deep","MMORPG","Massively Multiplayer"},
}

PLATFORM_TAG_MAP = {
    "steamdeck": {"Steam Deck Verified","Steam Deck Playable"},
}

STEAM_GENRE_TO_PLATFORM = {
    # keine direkte API-Abbildung, aber wir können via appdetails schauen
}


def infer_quiz_genres(tags: list[str]) -> list[str]:
    tag_set = set(tags)
    genres = [g for g, keywords in GENRE_TAG_MAP.items() if tag_set & keywords]
    return genres or ["action"]  # fallback


def infer_quiz_players(tags: list[str]) -> list[str]:
    tag_set = set(tags)
    has_multi  = bool(tag_set & MULTIPLAYER_TAGS)
    has_single = bool(tag_set & SINGLEPLAYER_TAGS)
    if has_multi and has_single:
        return ["solo","2","3-4","5+"]
    if has_multi:
        return ["2","3-4","5+"]
    return ["solo"]


def infer_quiz_online(tags: list[str]) -> str:
    tag_set = set(tags)
    has_online  = bool(tag_set & {"Multiplayer","Online Co-Op","MMO","PvP","PvE","MMORPG","Co-op"})
    has_offline = bool(tag_set & {"Singleplayer","Single-player","Local Co-Op","Offline"})
    if has_online and has_offline:
        return "both"
    if has_online:
        return "online"
    return "offline"


def infer_quiz_difficulty(tags: list[str]) -> str:
    tag_set = set(tags)
    if tag_set & DIFFICULTY_MAP["hard"]:
        return "hard"
    if tag_set & DIFFICULTY_MAP["chill"]:
        return "chill"
    return "medium"


def infer_quiz_story(tags: list[str]) -> str:
    tag_set = set(tags)
    if tag_set & STORY_MAP["core"]:
        return "core"
    if tag_set & STORY_MAP["irrelevant"]:
        return "irrelevant"
    return "nice"


def infer_quiz_session(tags: list[str]) -> str:
    tag_set = set(tags)
    if tag_set & SESSION_MAP["long"]:
        return "long"
    if tag_set & SESSION_MAP["short"]:
        return "short"
    return "medium"


def infer_quiz_popularity(owners_str: str, ccu: int) -> int:
    """Schätzt Popularität 0–10 aus Besitzeranzahl und CCU."""
    try:
        low = int(owners_str.split("..")[0].strip().replace(",", ""))
    except (ValueError, IndexError):
        low = 0

    if low >= 50_000_000 or ccu > 500_000:
        return 10
    if low >= 20_000_000 or ccu > 100_000:
        return 9
    if low >= 10_000_000 or ccu > 50_000:
        return 8
    if low >= 5_000_000  or ccu > 20_000:
        return 7
    if low >= 2_000_000  or ccu > 10_000:
        return 6
    if low >= 1_000_000  or ccu > 5_000:
        return 5
    if low >= 500_000    or ccu > 2_000:
        return 4
    if low >= 200_000    or ccu > 500:
        return 3
    if low >= 50_000     or ccu > 100:
        return 2
    return 1


def infer_platforms(detail: dict) -> list[str]:
    platforms = []
    plat = detail.get("platforms", {})
    if plat.get("windows") or plat.get("mac") or plat.get("linux"):
        platforms.append("pc")
    # SteamSpy gibt keine Konsolen-Plattformen zurück → Steam-API-Hinweis
    # Wir versuchen es aus dem Namen zu erahnen (nicht zuverlässig)
    tags = detail.get("tags", {})
    tag_names = list(tags.values()) if isinstance(tags, dict) else tags
    tag_set = set(str(t).lower() for t in tag_names)
    if "steam deck verified" in tag_set or "steam deck playable" in tag_set:
        platforms.append("steamdeck")
    return platforms or ["pc"]


def build_description(name: str, genres: list[str], tags: list[str]) -> str:
    tag_str = ", ".join(tags[:5]) if tags else "various gameplay styles"
    genre_str = "/".join(g.title() for g in genres[:2]) if genres else "Game"
    return f"{genre_str} game featuring {tag_str}."


def calculate_review_score(positive: int, negative: int) -> int:
    total = positive + negative
    if total < 100:
        return 0
    return round((positive / total) * 100)


# ── API-Helfer ─────────────────────────────────────────────────────────────────

def fetch_json(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("type") == "error":
                return None
            return data
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [WARN] Fetch fehlgeschlagen ({url}): {e}")
    return None


def fetch_candidate_appids(sources: list[str]) -> list[int]:
    """Holt AppIDs aus mehreren SteamSpy-Listen (dedupliziert, Reihenfolge erhalten)."""
    seen = set()
    appids = []
    for source in sources:
        print(f"  Fetching SteamSpy {source}…")
        data = fetch_json(LIST_URL.format(source=source))
        if not data:
            print(f"  [WARN] Keine Daten für {source}")
            continue
        for appid_str in data:
            appid = int(appid_str)
            if appid not in seen:
                seen.add(appid)
                appids.append(appid)
        time.sleep(1)
    return appids


def fetch_detail(appid: int) -> dict | None:
    return fetch_json(DETAIL_URL.format(appid=appid))


def fetch_steam_applist() -> list[int]:
    """Paginiert durch SteamSpy 'all' Endpoint – liefert alle bekannten AppIDs."""
    appids = []
    page = 0
    while True:
        print(f"  Seite {page}...", end=" ", flush=True)
        data = fetch_json(STEAMSPY_ALL_URL.format(page=page))
        if not data or len(data) == 0:
            print("Ende.")
            break
        appids.extend(int(k) for k in data.keys())
        print(f"{len(data)} Spiele ({len(appids)} total)")
        page += 1
        time.sleep(1)
    return appids


def load_seen_ids() -> set[int]:
    if SEEN_IDS_FILE.exists():
        with open(SEEN_IDS_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen: set[int]) -> None:
    with open(SEEN_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)


# ── Haupt-Logik ────────────────────────────────────────────────────────────────

# ── Repair & Validation ────────────────────────────────────────────────────────

SOFTWARE_GENRES = {
    'Utilities','Animation & Modeling','Design & Illustration',
    'Video Production','Photo Editing','Audio Production',
    'Game Development','Web Publishing','Education','Software Training'
}

def is_numeric_tags(game: dict) -> bool:
    """Prüfe ob steam_tags numerisch sind (Daten-Fehler)."""
    tags = game.get('steam_tags', [])
    if not tags:
        return True
    return str(tags[0]).isdigit()


def is_software_tool(game: dict) -> bool:
    """Prüfe ob Spiel ein Nicht-Spiel (Tool/Utilities) ist."""
    genres = set(game.get('steam_genres', []))
    return bool(genres) and genres.issubset(SOFTWARE_GENRES)


def infer_secondary_fields(steam_genres: list) -> tuple[str, str, str] | None:
    """Leite difficulty, story, session_length aus steam_genres ab."""
    sg = set(steam_genres)
    if 'Sports' in sg or 'Racing' in sg:
        return 'hard', 'irrelevant', 'short'
    if 'Massively Multiplayer' in sg:
        return 'hard', 'irrelevant', 'long'
    if 'Casual' in sg:
        return 'chill', 'nice', 'short'
    if 'Strategy' in sg or 'Simulation' in sg:
        return 'medium', 'nice', 'long'
    if 'RPG' in sg:
        return 'medium', 'nice', 'long'
    return None


def repair_database(db: dict) -> dict:
    """Repariere secondary fields + flagge software tools."""
    games = db['games']
    stats = {'secondary_changed': 0, 'software_flagged': 0, 'skipped_text_tags': 0}
    field_dist = {'quiz_difficulty': {}, 'quiz_story': {}, 'quiz_session_length': {}}

    for g in games:
        if is_software_tool(g):
            if not g.get('is_software_tool'):
                g['is_software_tool'] = True
                stats['software_flagged'] += 1
            continue

        if not is_numeric_tags(g):
            stats['skipped_text_tags'] += 1
        else:
            result = infer_secondary_fields(g.get('steam_genres', []))
            if result:
                diff, story, sess = result
                if g.get('quiz_difficulty') != diff:
                    g['quiz_difficulty'] = diff
                if g.get('quiz_story') != story:
                    g['quiz_story'] = story
                if g.get('quiz_session_length') != sess:
                    g['quiz_session_length'] = sess
                stats['secondary_changed'] += 1

        for f in ['quiz_difficulty', 'quiz_story', 'quiz_session_length']:
            v = g.get(f, '?')
            field_dist[f][v] = field_dist[f].get(v, 0) + 1

    print(f"\nStats: {stats}")
    for f, dist in sorted(field_dist.items()):
        print(f"  {f}: {dict(sorted(dist.items()))}")

    return db


# ── Validierung ────────────────────────────────────────────────────────────────

def is_skippable(detail: dict) -> tuple[bool, str]:
    """Gibt (True, Grund) zurück wenn das Spiel übersprungen werden soll."""
    name = detail.get("name", "")

    # Kein Name → kaputte API-Antwort
    if not name:
        return True, "kein Name"

    # AppID auf Blocklist
    if detail.get("appid") in BLOCKLIST_APPIDS:
        return True, "auf Blocklist"

    # DLC/Soundtrack/Tool erkennen
    tags_raw = detail.get("tags", {})
    tag_names = list(tags_raw.values()) if isinstance(tags_raw, dict) else tags_raw
    tag_lower = {str(t).lower() for t in tag_names}
    if any(kw in tag_lower for kw in SKIP_TAG_KEYWORDS):
        return True, f"Tag deutet auf DLC/Soundtrack hin"

    # Typische Nicht-Spiel-Namen
    name_lower = name.lower()
    if any(x in name_lower for x in ("soundtrack", "dlc", "demo", "playtest", "artbook", "ost ", " ost")):
        return True, "Name deutet auf Nicht-Spiel hin"

    # Zu wenige Reviews → kein verlässlicher Score
    positive = detail.get("positive", 0)
    negative = detail.get("negative", 0)
    if positive + negative < 100:
        return True, f"zu wenige Reviews ({positive + negative})"

    # Spiel scheint shut down zu sein
    if positive == 0 and negative == 0:
        return True, "null Reviews – wahrscheinlich abgeschaltet"

    return False, ""


def map_detail_to_game(detail: dict) -> dict:
    appid    = detail.get("appid") or detail.get("steam_appid")
    name     = detail.get("name", "Unknown")
    dev      = detail.get("developer", "")
    pub      = detail.get("publisher", "")
    positive = detail.get("positive", 0)
    negative = detail.get("negative", 0)
    ccu      = detail.get("ccu", 0)
    owners   = detail.get("owners", "0 .. 0")

    # Preis: SteamSpy liefert Cent (oder 0 wenn free)
    price_raw = detail.get("price", 0) or detail.get("initialprice", 0)
    try:
        price_eur = round(int(price_raw) / 100, 2)
    except (ValueError, TypeError):
        price_eur = 0.0
    is_free = price_eur == 0

    # Tags: SteamSpy liefert {tag_name: vote_count, ...} — Keys sind die Namen
    tags_raw = detail.get("tags", {})
    if isinstance(tags_raw, dict):
        steam_tags = list(tags_raw.keys())  # Keys = tag names (values = vote counts)
    else:
        steam_tags = [str(t) for t in list(tags_raw)]

    # Genres aus SteamSpy
    genres_raw = detail.get("genre", "") or ""
    steam_genres = [g.strip() for g in genres_raw.split(",") if g.strip()]

    review_score = calculate_review_score(positive, negative)
    quiz_popularity = infer_quiz_popularity(owners, ccu)

    return {
        "appid":            int(appid),
        "name":             name,
        "developer":        dev,
        "publisher":        pub,
        "price_eur":        price_eur,
        "is_free":          is_free,
        "owners":           owners,
        "ccu":              ccu,
        "positive":         positive,
        "negative":         negative,
        "review_score":     review_score,
        "steam_url":        f"https://store.steampowered.com/app/{appid}",
        "steam_genres":     steam_genres,
        "steam_tags":       steam_tags,
        "description":      build_description(name, infer_quiz_genres(steam_tags), steam_tags),
        "quiz_genres":      infer_quiz_genres(steam_tags),
        "quiz_players":     infer_quiz_players(steam_tags),
        "quiz_online":      infer_quiz_online(steam_tags),
        "quiz_difficulty":  infer_quiz_difficulty(steam_tags),
        "quiz_story":       infer_quiz_story(steam_tags),
        "quiz_session_length": infer_quiz_session(steam_tags),
        "quiz_popularity":  quiz_popularity,
        "platforms":        infer_platforms(detail),
    }


def run(dry_run: bool, limit: int | None, min_score: int, all_steam: bool = False):
    print(f"\n{'[DRY RUN] ' if dry_run else ''}fetch_games.py – WGTP Daten-Updater")
    print(f"Datei: {DATA_FILE}")
    print(f"Min. Review-Score: {min_score} | Limit: {limit or 'kein'} | Modus: {'Steam AppList' if all_steam else 'SteamSpy Top-100'}\n")

    # ── Bestehende Daten laden ─────────────────────────────────────────────────
    if not DATA_FILE.exists():
        sys.exit(f"Fehler: {DATA_FILE} nicht gefunden.")

    with open(DATA_FILE, encoding="utf-8-sig") as f:
        db = json.load(f)

    existing_ids: set[int] = {g["appid"] for g in db["games"]}
    print(f"Bestehende Spiele: {len(existing_ids)}")

    seen_ids: set[int] = load_seen_ids() if all_steam else set()
    if all_steam:
        print(f"Bereits verarbeitet: {len(seen_ids)} AppIDs")

    # ── Kandidaten holen ───────────────────────────────────────────────────────
    print("\nSchritt 1: Kandidaten-AppIDs holen...")
    if all_steam:
        all_ids = fetch_steam_applist()
        candidates = [aid for aid in all_ids
                      if aid not in existing_ids and aid not in seen_ids and aid not in BLOCKLIST_APPIDS]
        print(f"  Steam AppList: {len(all_ids)} total | Noch nicht verarbeitet: {len(candidates)}")
    else:
        raw_ids = fetch_candidate_appids(STEAMSPY_SOURCES)
        candidates = [aid for aid in raw_ids if aid not in existing_ids and aid not in BLOCKLIST_APPIDS]
        print(f"  Gesamt-Kandidaten: {len(raw_ids)} | Neue (nicht in DB): {len(candidates)}")

    # ── Details abrufen und filtern ────────────────────────────────────────────
    print("\nSchritt 2: Details abrufen und bewerten...")
    added = []
    skipped_log = []
    processed_count = 0

    for i, appid in enumerate(candidates):
        # Im --all-steam Modus zaehlt limit die verarbeiteten AppIDs (nicht nur hinzugefuegte)
        if all_steam:
            if limit and processed_count >= limit:
                print(f"\nLimit ({limit} verarbeitet) erreicht – stoppe.")
                break
        else:
            if limit and len(added) >= limit:
                print(f"\nLimit ({limit}) erreicht – stoppe.")
                break

        processed_count += 1
        print(f"  [{i+1}/{len(candidates)}] AppID {appid}...", end=" ", flush=True)

        if all_steam and not dry_run:
            seen_ids.add(appid)

        detail = fetch_detail(appid)

        if not detail:
            print("API-Fehler, übersprungen.")
            skipped_log.append((appid, "API-Fehler"))
            time.sleep(1)
            continue

        detail["appid"] = appid  # sicherstellen dass appid vorhanden ist

        skip, reason = is_skippable(detail)
        if skip:
            print(f"übersprungen ({reason})")
            skipped_log.append((appid, reason))
            time.sleep(1)
            continue

        game = map_detail_to_game(detail)

        # Review-Score-Filter
        if game["review_score"] < min_score:
            reason = f"Score {game['review_score']} < {min_score}"
            print(f"übersprungen ({reason})")
            skipped_log.append((appid, reason))
            time.sleep(1)
            continue

        print(f"OK -> \"{game['name']}\" (Score: {game['review_score']}, Pop: {game['quiz_popularity']})")

        if not dry_run:
            db["games"].append(game)
            existing_ids.add(appid)

        added.append(game)
        time.sleep(1)  # SteamSpy Rate-Limit

    # ── Zusammenfassung ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Neu hinzugefügt: {len(added)} Spiele")
    if skipped_log:
        print(f"Übersprungen:    {len(skipped_log)} Spiele")

    if added:
        print("\nNeu:")
        for g in added:
            flag = " [HIDDEN GEM]" if g["quiz_popularity"] <= 6 and g["review_score"] >= 88 else ""
            print(f"  - {g['name']} ({g['review_score']}%){flag}")

    # Fortschritt speichern (auch wenn keine neuen Spiele hinzugefügt wurden)
    if all_steam and not dry_run:
        save_seen_ids(seen_ids)
        print(f"Fortschritt: {len(seen_ids)} AppIDs gesamt verarbeitet -> seen_appids.json")

    if dry_run:
        print("\n[DRY RUN] Keine Änderungen geschrieben.")
        return

    if not added:
        print("Keine neuen Spiele – Datei unverändert.")
        return

    # Metadata aktualisieren
    db["metadata"]["last_updated"] = str(date.today())
    db["metadata"]["total_games"]  = len(db["games"])

    # Backup schreiben
    backup_path = DATA_FILE.with_suffix(f".backup_{date.today()}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"\nBackup: {backup_path}")

    # Originaldatei überschreiben
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"Gespeichert: {DATA_FILE} ({len(db['games'])} Spiele total)")

    # ── Schritt 3: Repariere sekundäre Felder + Flagge Software-Tools ──────
    print(f"\nSchritt 3: Repariere sekundäre Felder...")
    db = repair_database(db)

    # Metadata aktualisieren
    db["metadata"]["last_updated"] = str(date.today())
    db["metadata"]["total_games"]  = len(db["games"])

    # Reparierte Datei speichern
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"Repariert & Gespeichert: {DATA_FILE}")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WGTP – games_data.json Updater via SteamSpy")
    parser.add_argument("--dry-run",   action="store_true", help="Nur anzeigen, nichts schreiben")
    parser.add_argument("--limit",     type=int, default=None, help="Max. neue Spiele (Standard: alle)")
    parser.add_argument("--min-score",  type=int, default=60,        help="Min. Review-Score 0–100 (Standard: 60)")
    parser.add_argument("--all-steam", action="store_true",           help="Alle Steam-Spiele via Steam AppList (statt SteamSpy Top-100)")
    args = parser.parse_args()

    run(dry_run=args.dry_run, limit=args.limit, min_score=args.min_score, all_steam=args.all_steam)
