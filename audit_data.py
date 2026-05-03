"""
audit_data.py – One-time audit script for games_data.json quiz_* field integrity.

Scans every game for:
  - Invalid values in quiz_* enum fields
  - Empty quiz_genres lists
  - Numeric steam_tags (indicates a past bug storing vote counts instead of names)
  - Distribution anomalies (any single quiz_genre appearing in >80% of games)
  - Informational mismatch count: quiz_genres vs. what steam_tags would derive

Usage:
  py audit_data.py           # audit only, no writes
  py audit_data.py --fix     # fix corrupted entries and save games_data.json
"""

import argparse
import json
import sys
import io
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Paths ──────────────────────────────────────────────────────────────────────

DATA_FILE = Path(__file__).parent / "games_data.json"

# ── Valid value sets ───────────────────────────────────────────────────────────

VALID_QUIZ_GENRES = {
    "action", "rpg", "strategy", "puzzle", "adventure", "shooter",
    "simulation", "horror", "roguelike", "platformer", "sports", "sandbox",
}

VALID_QUIZ_PLAYERS = {"solo", "2", "3-4", "5+"}

VALID_QUIZ_ONLINE = {"offline", "online", "both"}

VALID_QUIZ_DIFFICULTY = {"chill", "medium", "hard"}

VALID_QUIZ_STORY = {"core", "nice", "irrelevant"}

VALID_QUIZ_SESSION_LENGTH = {"short", "medium", "long"}

# ── Genre tag mapping (mirrors fetch_games.py) ─────────────────────────────────

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
    "platformer":  {"Platformer","2D Platformer","Metroidvania","Runner"},
    "sports":      {"Sports","Racing","Football (Soccer)","Baseball","Basketball"},
    "sandbox":     {"Sandbox","Open World Survival Craft","Building","Crafting","Survival","Base Building"},
}

DISTRIBUTION_FLAG_THRESHOLD = 0.80  # flag if single genre appears in >80% of games


# ── Inference helpers (for --fix mode) ────────────────────────────────────────

def infer_quiz_genres(tags: list) -> list:
    tag_set = set(tags)
    genres = [g for g, keywords in GENRE_TAG_MAP.items() if tag_set & keywords]
    return genres or ["action"]


# ── Per-game checks ────────────────────────────────────────────────────────────

def has_numeric_tags(game: dict) -> bool:
    """Return True if steam_tags look like vote counts (numbers) instead of names."""
    tags = game.get("steam_tags", [])
    if not tags:
        return False
    # Check first few tags — if any are numeric strings or actual ints, flag it
    sample = tags[:5]
    return any(str(t).strip().lstrip("-").isdigit() for t in sample)


def check_game(game: dict) -> list:
    """
    Return a list of (field, issue_code, detail) tuples for each problem found.
    Empty list means no issues.
    """
    issues = []
    appid = game.get("appid", "?")
    name  = game.get("name", "?")

    # ── steam_tags numeric ──────────────────────────────────────────────────
    if has_numeric_tags(game):
        issues.append(("steam_tags", "NUMERIC_TAGS", game.get("steam_tags", [])[:5]))

    # ── quiz_genres ─────────────────────────────────────────────────────────
    genres = game.get("quiz_genres")
    if genres is None:
        issues.append(("quiz_genres", "MISSING", None))
    elif not isinstance(genres, list):
        issues.append(("quiz_genres", "NOT_A_LIST", genres))
    elif len(genres) == 0:
        issues.append(("quiz_genres", "EMPTY", None))
    else:
        invalid = [v for v in genres if v not in VALID_QUIZ_GENRES]
        if invalid:
            issues.append(("quiz_genres", "INVALID_VALUES", invalid))

    # ── quiz_players ────────────────────────────────────────────────────────
    players = game.get("quiz_players")
    if players is None:
        issues.append(("quiz_players", "MISSING", None))
    elif not isinstance(players, list):
        issues.append(("quiz_players", "NOT_A_LIST", players))
    else:
        invalid = [v for v in players if v not in VALID_QUIZ_PLAYERS]
        if invalid:
            issues.append(("quiz_players", "INVALID_VALUES", invalid))

    # ── quiz_online ─────────────────────────────────────────────────────────
    online = game.get("quiz_online")
    if online is None:
        issues.append(("quiz_online", "MISSING", None))
    elif online not in VALID_QUIZ_ONLINE:
        issues.append(("quiz_online", "INVALID_VALUE", online))

    # ── quiz_difficulty ─────────────────────────────────────────────────────
    difficulty = game.get("quiz_difficulty")
    if difficulty is None:
        issues.append(("quiz_difficulty", "MISSING", None))
    elif difficulty not in VALID_QUIZ_DIFFICULTY:
        issues.append(("quiz_difficulty", "INVALID_VALUE", difficulty))

    # ── quiz_story ──────────────────────────────────────────────────────────
    story = game.get("quiz_story")
    if story is None:
        issues.append(("quiz_story", "MISSING", None))
    elif story not in VALID_QUIZ_STORY:
        issues.append(("quiz_story", "INVALID_VALUE", story))

    # ── quiz_session_length ─────────────────────────────────────────────────
    session = game.get("quiz_session_length")
    if session is None:
        issues.append(("quiz_session_length", "MISSING", None))
    elif session not in VALID_QUIZ_SESSION_LENGTH:
        issues.append(("quiz_session_length", "INVALID_VALUE", session))

    # ── quiz_popularity ─────────────────────────────────────────────────────
    pop = game.get("quiz_popularity")
    if pop is None:
        issues.append(("quiz_popularity", "MISSING", None))
    elif not isinstance(pop, int) or isinstance(pop, bool) or not (0 <= pop <= 10):
        issues.append(("quiz_popularity", "INVALID_VALUE", pop))

    return issues


def genres_match_tags(game: dict) -> bool:
    """
    Return True if the quiz_genres field contains at least one genre
    that can be derived from steam_tags. False = mismatch (informational only).
    """
    tags = game.get("steam_tags", [])
    # If tags are numeric we can't derive genres, skip mismatch check
    if has_numeric_tags(game):
        return True
    derived = set(infer_quiz_genres(tags))
    current = set(game.get("quiz_genres") or [])
    # Overlap means at least partial match — only flag if zero overlap
    return bool(current & derived)


# ── Fix helpers ────────────────────────────────────────────────────────────────

def fix_game(game: dict, issues: list) -> bool:
    """
    Apply fixes for all detected issues. Returns True if anything was changed.
    """
    changed = False
    tags = game.get("steam_tags", [])
    # If tags are numeric, we can't derive sensible genres from them
    tags_ok = not has_numeric_tags(game)

    for field, code, detail in issues:
        if field == "quiz_genres" and code in ("EMPTY", "INVALID_VALUES", "MISSING", "NOT_A_LIST"):
            new_genres = infer_quiz_genres(tags) if tags_ok else ["action"]
            if game.get("quiz_genres") != new_genres:
                game["quiz_genres"] = new_genres
                changed = True

        elif field == "quiz_players" and code in ("INVALID_VALUES", "MISSING", "NOT_A_LIST"):
            game["quiz_players"] = ["solo"]
            changed = True

        elif field == "quiz_online" and code in ("INVALID_VALUE", "MISSING"):
            game["quiz_online"] = "offline"
            changed = True

        elif field == "quiz_difficulty" and code in ("INVALID_VALUE", "MISSING"):
            game["quiz_difficulty"] = "medium"
            changed = True

        elif field == "quiz_story" and code in ("INVALID_VALUE", "MISSING"):
            game["quiz_story"] = "nice"
            changed = True

        elif field == "quiz_session_length" and code in ("INVALID_VALUE", "MISSING"):
            game["quiz_session_length"] = "medium"
            changed = True

        elif field == "quiz_popularity" and code in ("INVALID_VALUE", "MISSING"):
            game["quiz_popularity"] = 5
            changed = True

        # Note: NUMERIC_TAGS is not auto-fixable (needs re-fetch from SteamSpy)

    return changed


# ── Main audit logic ───────────────────────────────────────────────────────────

def run_audit(fix: bool) -> None:
    print(f"audit_data.py – WGTP Data Integrity Auditor")
    print(f"File: {DATA_FILE}")
    print(f"Mode: {'AUDIT + FIX' if fix else 'AUDIT ONLY'}\n")

    if not DATA_FILE.exists():
        sys.exit(f"ERROR: {DATA_FILE} not found.")

    with open(DATA_FILE, encoding="utf-8-sig") as f:
        db = json.load(f)

    games = db.get("games", [])
    total = len(games)
    print(f"Loaded {total} games.\n")

    # ── Counters ──────────────────────────────────────────────────────────
    count_invalid_genres      = 0
    count_empty_genres        = 0
    count_invalid_players     = 0
    count_invalid_online      = 0
    count_invalid_difficulty  = 0
    count_invalid_story       = 0
    count_invalid_session     = 0
    count_invalid_popularity  = 0
    count_numeric_tags        = 0
    count_mismatch            = 0
    count_fixed               = 0

    # Genre distribution counter
    genre_dist: dict[str, int] = {g: 0 for g in VALID_QUIZ_GENRES}

    # ── Per-game scan ─────────────────────────────────────────────────────
    for game in games:
        appid = game.get("appid", "?")
        name  = game.get("name", "?")

        issues = check_game(game)

        # Accumulate counters per issue type
        for field, code, detail in issues:
            if field == "steam_tags" and code == "NUMERIC_TAGS":
                count_numeric_tags += 1
                print(f'[{appid}] "{name}" — steam_tags={detail} NUMERIC_TAGS')

            elif field == "quiz_genres":
                if code == "EMPTY":
                    count_empty_genres += 1
                    print(f'[{appid}] "{name}" — quiz_genres=[] EMPTY')
                elif code in ("INVALID_VALUES", "NOT_A_LIST", "MISSING"):
                    count_invalid_genres += 1
                    print(f'[{appid}] "{name}" — quiz_genres={game.get("quiz_genres")} {code}: {detail}')

            elif field == "quiz_players":
                count_invalid_players += 1
                print(f'[{appid}] "{name}" — quiz_players={game.get("quiz_players")} {code}: {detail}')

            elif field == "quiz_online":
                count_invalid_online += 1
                print(f'[{appid}] "{name}" — quiz_online={game.get("quiz_online")!r} INVALID_VALUE')

            elif field == "quiz_difficulty":
                count_invalid_difficulty += 1
                print(f'[{appid}] "{name}" — quiz_difficulty={game.get("quiz_difficulty")!r} INVALID_VALUE')

            elif field == "quiz_story":
                count_invalid_story += 1
                print(f'[{appid}] "{name}" — quiz_story={game.get("quiz_story")!r} INVALID_VALUE')

            elif field == "quiz_session_length":
                count_invalid_session += 1
                print(f'[{appid}] "{name}" — quiz_session_length={game.get("quiz_session_length")!r} INVALID_VALUE')

            elif field == "quiz_popularity":
                count_invalid_popularity += 1
                print(f'[{appid}] "{name}" — quiz_popularity={game.get("quiz_popularity")!r} INVALID_VALUE')

        # Mismatch check (informational, no per-game print)
        genres_field = game.get("quiz_genres")
        if isinstance(genres_field, list) and len(genres_field) > 0:
            # Only check mismatch when genres field looks valid
            valid_genres_in_field = [v for v in genres_field if v in VALID_QUIZ_GENRES]
            if valid_genres_in_field and not genres_match_tags(game):
                count_mismatch += 1
                # Derive what we'd suggest for informational purposes
                derived = infer_quiz_genres(game.get("steam_tags", []))
                # Print mismatch line only if no other genre issues for this game
                genre_issue_codes = [code for f, code, _ in issues if f == "quiz_genres"]
                if not genre_issue_codes:
                    print(f'[{appid}] "{name}" — quiz_genres={genres_field} MISMATCH (steam_tags suggest: {derived})')

        # Genre distribution
        genres_val = game.get("quiz_genres")
        if isinstance(genres_val, list):
            for g in genres_val:
                if g in genre_dist:
                    genre_dist[g] += 1

        # Apply fixes if requested
        if fix and issues:
            if fix_game(game, issues):
                count_fixed += 1

    # ── Distribution check ────────────────────────────────────────────────
    suspicious_genres = []
    if total > 0:
        for genre, cnt in genre_dist.items():
            if cnt / total > DISTRIBUTION_FLAG_THRESHOLD:
                suspicious_genres.append((genre, cnt, cnt / total * 100))

    # ── Summary report ────────────────────────────────────────────────────
    print()
    print("===== AUDIT REPORT =====")
    print(f"Total games: {total}")
    print(f"Games with invalid quiz_genres values: {count_invalid_genres}")
    print(f"Games with empty quiz_genres: {count_empty_genres}")
    print(f"Games with invalid quiz_players: {count_invalid_players}")
    print(f"Games with invalid quiz_online: {count_invalid_online}")
    print(f"Games with invalid quiz_difficulty: {count_invalid_difficulty}")
    print(f"Games with invalid quiz_story: {count_invalid_story}")
    print(f"Games with invalid quiz_session_length: {count_invalid_session}")
    print(f"Games with invalid quiz_popularity: {count_invalid_popularity}")
    print(f"Games with numeric steam_tags: {count_numeric_tags}")
    print(f"Genre distribution (flagged if >{DISTRIBUTION_FLAG_THRESHOLD*100:.0f}% of games):")

    sorted_genres = sorted(genre_dist.items(), key=lambda x: -x[1])
    for genre, cnt in sorted_genres:
        pct = cnt / total * 100 if total else 0
        flag = " *** SUSPICIOUS ***" if cnt / total > DISTRIBUTION_FLAG_THRESHOLD and total > 0 else ""
        print(f"  {genre}: {cnt} ({pct:.1f}%){flag}")

    if suspicious_genres:
        print(f"\n  WARNING: {len(suspicious_genres)} genre(s) appear in >{DISTRIBUTION_FLAG_THRESHOLD*100:.0f}% of games:")
        for genre, cnt, pct in suspicious_genres:
            print(f"    {genre}: {cnt} ({pct:.1f}%) — possible mass-tagging bug")

    print(f"Games with quiz_genres mismatch vs steam_tags: {count_mismatch} (these are OK if genres overlap)")

    if fix:
        print(f"\nGames fixed and saved: {count_fixed}")

    print("===== END REPORT =====")

    # ── Save if fixing ────────────────────────────────────────────────────
    if fix and count_fixed > 0:
        # Update metadata
        db["metadata"]["last_updated"] = str(date.today())

        # Backup
        backup_path = DATA_FILE.with_suffix(f".backup_audit_{date.today()}.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nBackup written: {backup_path}")

        # Save fixed data
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"Saved fixed data: {DATA_FILE}")
    elif fix and count_fixed == 0:
        print("\nNo fixes needed — file unchanged.")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WGTP – Audit (and optionally fix) quiz_* fields in games_data.json"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix invalid/empty quiz_* fields and save games_data.json",
    )
    args = parser.parse_args()

    run_audit(fix=args.fix)
