"""
embed_games.py — Tasks 1.2 + 1.3: Generate rich_description + embeddings for all games.

Usage:
    py embed_games.py               # full run: rich_description + embeddings
    py embed_games.py --skip-embed  # only generate rich_description (no ML model needed)
    py embed_games.py --dry-run     # print first 3 rich_descriptions, don't save
    py embed_games.py --force       # overwrite existing rich_description + embedding fields
"""

import io
import sys
import json
import argparse
import shutil
from pathlib import Path
from datetime import date

# Windows UTF-8 fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_FILE = Path(__file__).parent / "games_data.json"
BACKUP_FILE = Path(__file__).parent / f"games_data.backup_embed_{date.today()}.json"
EMBED_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Rich description helpers
# ---------------------------------------------------------------------------

def is_numeric_tag(tag) -> bool:
    """Return True if tag is a number (vote count bug) rather than a real tag name."""
    return str(tag).strip().isdigit()


def build_rich_description(game: dict) -> str:
    """
    Build a text description suitable for sentence-transformer embedding.

    Format: {name}. Tags: {text_tags}. {description[:500]}
    Uses only accurate SteamSpy fields — quiz_genres/difficulty/story/session excluded
    (those fields are corrupted; semantic matching handles genre/difficulty nuance instead).
    """
    name = game.get("name", "Unknown")

    raw_tags = game.get("steam_tags") or []
    text_tags = [str(t) for t in raw_tags if not is_numeric_tag(t)]
    tags_str = ", ".join(text_tags) if text_tags else "unknown"

    desc = (game.get("description") or "")[:500]

    return f"{name}. Tags: {tags_str}. {desc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate rich_description + embeddings for all games.")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Only generate rich_description, skip embedding computation.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print first 3 rich_descriptions and exit without saving.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing rich_description and embedding fields.")
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print(f"Loading {DATA_FILE} …")
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "games" not in data:
        raise ValueError(
            f"Unexpected structure in {DATA_FILE}: expected a dict with a 'games' key, "
            f"got {type(data).__name__}. "
            "Make sure you are loading the current games_data.json ({{metadata:{{...}}, games:[...]}} format)."
        )

    games = data["games"]
    print(f"Loaded {len(games)} games.")

    # ------------------------------------------------------------------
    # Step 1: Generate rich_description
    # ------------------------------------------------------------------
    generated_desc = 0
    skipped_desc = 0

    for i, game in enumerate(games):
        if i > 0 and i % 100 == 0:
            print(f"  Descriptions: {i}/{len(games)} …")

        if "rich_description" in game and not args.force:
            skipped_desc += 1
            continue

        game["rich_description"] = build_rich_description(game)
        generated_desc += 1

    print(f"Rich descriptions: {generated_desc} generated, {skipped_desc} skipped (already existed).")

    # ------------------------------------------------------------------
    # Dry-run: print samples and exit
    # ------------------------------------------------------------------
    if args.dry_run:
        print("\n=== DRY RUN — first 3 rich_descriptions ===\n")
        for game in games[:3]:
            print(f"[{game.get('appid')}] {game.get('name')}")
            print(f"  {game['rich_description']}")
            print()
        print("Dry-run complete. No changes saved.")
        return

    # ------------------------------------------------------------------
    # Step 2: Compute embeddings (unless --skip-embed)
    # ------------------------------------------------------------------
    generated_embed = 0
    skipped_embed = 0

    if args.skip_embed:
        print("--skip-embed flag set: skipping embedding computation.")
    else:
        # Lazy import with helpful error message
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print(
                "\nERROR: sentence-transformers is not installed.\n"
                "Install it with:\n"
                "    pip install sentence-transformers\n"
                "Then re-run this script."
            )
            sys.exit(1)

        # Collect game objects (dicts) that need embeddings — no index storage
        games_needing_embed = [
            game for game in games
            if "embedding" not in game or args.force
        ]
        skipped_embed = len(games) - len(games_needing_embed)

        if games_needing_embed:
            print(f"\nComputing embeddings for {len(games_needing_embed)} games "
                  f"(skipping {skipped_embed} that already have embeddings) …")
            print(f"Loading model '{EMBED_MODEL}' (first run downloads ~100 MB) …")

            model = SentenceTransformer(EMBED_MODEL)

            descriptions = [game["rich_description"] for game in games_needing_embed]

            print("Computing embeddings… (this takes 10–30 seconds)")
            embeddings_list = model.encode(
                descriptions,
                batch_size=64,
                show_progress_bar=True,
                convert_to_numpy=True,
            )

            # Write embeddings back directly into the game objects
            for game, embedding in zip(games_needing_embed, embeddings_list):
                game["embedding"] = embedding.tolist()
                generated_embed += 1

            # Verify shape for ALL embeddings, not just the first
            assert all(len(e) == 384 for e in embeddings_list), (
                f"Expected 384-dim embeddings for all {len(embeddings_list)} games, "
                f"but found at least one with wrong dimension: "
                f"{[len(e) for e in embeddings_list if len(e) != 384][:5]}"
            )
            print(f"Embedding shape verified: 384-dim for all {len(embeddings_list)} embeddings ✓")
        else:
            print("All games already have embeddings. Use --force to recompute.")
            skipped_embed = len(games)

    # ------------------------------------------------------------------
    # Step 3: Save — backup first
    # ------------------------------------------------------------------
    if BACKUP_FILE.exists():
        print(f"Backup already exists at {BACKUP_FILE}, skipping backup.")
    else:
        print(f"Creating backup: {BACKUP_FILE} …")
        shutil.copy2(DATA_FILE, BACKUP_FILE)

    print(f"Saving updated {DATA_FILE} …")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n=== Summary ===")
    total_with_desc = sum(1 for g in games if "rich_description" in g)
    total_with_embed = sum(1 for g in games if "embedding" in g)
    print(f"Games with rich_description : {total_with_desc}/{len(games)}")
    if not args.skip_embed:
        print(f"Games with embedding        : {total_with_embed}/{len(games)}")
        if total_with_embed > 0:
            # Shape check
            sample = games[next(i for i, g in enumerate(games) if "embedding" in g)]["embedding"]
            print(f"Embedding dimension         : {len(sample)} (expected 384)")
    print(f"rich_description generated  : {generated_desc}")
    if not args.skip_embed:
        print(f"Embeddings generated        : {generated_embed}")
        print(f"Embeddings skipped          : {skipped_embed}")
    print("Done.")


if __name__ == "__main__":
    main()
