"""
add_manual_games.py — Add non-Steam games (Riot, Ubisoft, Epic) to games_data.json.

Usage:
    py add_manual_games.py            # add all entries (skips existing appids)
    py add_manual_games.py --dry-run  # preview without writing
"""

import argparse
import json
import sys
import io
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_FILE = Path(__file__).parent / "games_data.json"

# fmt: off
MANUAL_GAMES = [

    # ── Riot Games ────────────────────────────────────────────────────────────────

    {
        "appid": 9900001,
        "name": "League of Legends",
        "developer": "Riot Games",
        "publisher": "Riot Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 76,
        "quiz_popularity": 10,
        "platforms": ["pc", "mobile"],
        "steam_tags": [
            "MOBA", "Strategy", "Multiplayer", "Free to Play", "Competitive",
            "Team-Based", "PvP", "Fantasy", "Action", "Top-Down",
        ],
        "description": (
            "The world's most-played PC game. Two teams of 5 champions battle to destroy "
            "the enemy Nexus. Enormous champion roster, deep meta, very high skill ceiling. "
            "Free to play with cosmetic purchases."
        ),
        "steam_url": "https://www.leagueoflegends.com",
    },
    {
        "appid": 9900002,
        "name": "Valorant",
        "developer": "Riot Games",
        "publisher": "Riot Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 82,
        "quiz_popularity": 9,
        "platforms": ["pc"],
        "steam_tags": [
            "FPS", "Hero Shooter", "Tactical", "Competitive", "Multiplayer",
            "Free to Play", "PvP", "Team-Based", "First-Person", "Shooter",
        ],
        "description": (
            "Free-to-play 5v5 tactical shooter from Riot Games. Unique agent abilities meet "
            "precise gunplay. High skill ceiling, deep ranked mode, strong esports scene."
        ),
        "steam_url": "https://playvalorant.com",
    },
    {
        "appid": 9900003,
        "name": "Teamfight Tactics",
        "developer": "Riot Games",
        "publisher": "Riot Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 79,
        "quiz_popularity": 7,
        "platforms": ["pc", "mobile"],
        "steam_tags": [
            "Auto Battler", "Strategy", "Turn-Based Strategy", "Multiplayer",
            "Free to Play", "PvP", "Tactical", "Fantasy", "Casual",
        ],
        "description": (
            "Riot's auto battler set in the League of Legends universe. Draft and position "
            "champions each round. Eight players compete until one remains. Regular seasonal "
            "content keeps the meta fresh."
        ),
        "steam_url": "https://teamfighttactics.leagueoflegends.com",
    },
    {
        "appid": 9900004,
        "name": "Legends of Runeterra",
        "developer": "Riot Games",
        "publisher": "Riot Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 83,
        "quiz_popularity": 6,
        "platforms": ["pc", "mobile"],
        "steam_tags": [
            "Card Game", "Strategy", "Roguelike Deckbuilder", "Multiplayer",
            "Free to Play", "PvP", "Fantasy", "Singleplayer",
        ],
        "description": (
            "Strategic card game set in the League of Legends universe. Build decks from "
            "multiple regions, each with distinct mechanics. Generous free-to-play model, "
            "deep single-player Path of Champions mode."
        ),
        "steam_url": "https://playruneterra.com",
    },

    # ── Ubisoft ───────────────────────────────────────────────────────────────────

    {
        "appid": 9900101,
        "name": "Rainbow Six Siege",
        "developer": "Ubisoft Montreal",
        "publisher": "Ubisoft",
        "price_eur": 9.99,
        "is_free": False,
        "review_score": 84,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "FPS", "Tactical", "Multiplayer", "Competitive", "Team-Based",
            "PvP", "Action", "First-Person", "Shooter", "Strategy", "Military",
        ],
        "description": (
            "Tactical 5v5 operator shooter. Destructible environments and unique gadgets per "
            "operator reward creative approaches. Very high skill ceiling. Strong ranked and "
            "esports scene. Years of post-launch content."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/rainbow-six/siege",
    },
    {
        "appid": 9900102,
        "name": "Assassin's Creed Valhalla",
        "developer": "Ubisoft Montreal",
        "publisher": "Ubisoft",
        "price_eur": 59.99,
        "is_free": False,
        "review_score": 80,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "Action RPG", "Open World", "Action-Adventure", "Singleplayer",
            "Story Rich", "Historical", "Vikings", "Exploration", "Stealth", "RPG",
        ],
        "description": (
            "Massive open-world action RPG set in Viking-age England. Lead Norse raids, "
            "build a settlement, and forge alliances across a richly detailed map. "
            "100+ hours of content with deep RPG progression."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/assassins-creed/valhalla",
    },
    {
        "appid": 9900103,
        "name": "Far Cry 6",
        "developer": "Ubisoft Toronto",
        "publisher": "Ubisoft",
        "price_eur": 59.99,
        "is_free": False,
        "review_score": 75,
        "quiz_popularity": 7,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "FPS", "Open World", "Action-Adventure", "Singleplayer", "Shooter",
            "First-Person", "Story Rich", "Exploration", "Co-op", "Military",
        ],
        "description": (
            "Open-world FPS set on a fictional Caribbean island under a dictator's rule. "
            "Play a guerrilla fighter with improvised weapons and gadgets. "
            "Big chaotic sandbox with optional co-op."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/far-cry/far-cry-6",
    },
    {
        "appid": 9900104,
        "name": "The Division 2",
        "developer": "Massive Entertainment",
        "publisher": "Ubisoft",
        "price_eur": 9.99,
        "is_free": False,
        "review_score": 80,
        "quiz_popularity": 7,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "Looter Shooter", "Third-Person Shooter", "Action RPG", "Co-op",
            "Online Co-Op", "Multiplayer", "Open World", "Shooter", "PvE", "PvP",
        ],
        "description": (
            "Looter shooter set in a post-pandemic Washington D.C. Solo or 4-player co-op "
            "missions, rich gear progression, and challenging endgame raids. "
            "Polished gunplay with a dense open world."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/the-division/the-division-2",
    },
    {
        "appid": 9900105,
        "name": "Anno 1800",
        "developer": "Ubisoft Blue Byte",
        "publisher": "Ubisoft",
        "price_eur": 39.99,
        "is_free": False,
        "review_score": 87,
        "quiz_popularity": 6,
        "platforms": ["pc"],
        "steam_tags": [
            "City Builder", "Strategy", "Management", "Economy", "Building",
            "Historical", "Singleplayer", "Multiplayer", "Exploration", "Simulation",
        ],
        "description": (
            "Deep city-builder and economic strategy set in the 19th century industrial era. "
            "Manage complex supply chains, colonize new world islands, engage in diplomacy "
            "and naval combat. Excellent long-term depth."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/anno/anno-1800",
    },
    {
        "appid": 9900106,
        "name": "For Honor",
        "developer": "Ubisoft Montreal",
        "publisher": "Ubisoft",
        "price_eur": 14.99,
        "is_free": False,
        "review_score": 77,
        "quiz_popularity": 6,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "Fighting", "Melee", "Action", "Multiplayer", "Competitive",
            "Team-Based", "PvP", "Historical", "Third-Person", "Medieval",
        ],
        "description": (
            "Unique melee combat game pitting knights, vikings, samurai, and wu lin against "
            "each other. Deep directional combat system with high skill ceiling. "
            "Mix of multiplayer modes and a story campaign."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/for-honor",
    },
    {
        "appid": 9900107,
        "name": "Watch Dogs: Legion",
        "developer": "Ubisoft Toronto",
        "publisher": "Ubisoft",
        "price_eur": 29.99,
        "is_free": False,
        "review_score": 75,
        "quiz_popularity": 6,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "Open World", "Action-Adventure", "Stealth", "Hacking", "Singleplayer",
            "Story Rich", "Cyberpunk", "Sci-fi", "Third-Person", "Multiplayer",
        ],
        "description": (
            "Open-world action game set in a near-future London under authoritarian surveillance. "
            "Recruit any NPC in the city to your resistance. Hacking, stealth, and combat "
            "in a dense, reactive city."
        ),
        "steam_url": "https://www.ubisoft.com/en-us/game/watch-dogs/legion",
    },

    # ── Microsoft / Xbox ─────────────────────────────────────────────────────────

    {
        "appid": 9900301,
        "name": "Minecraft",
        "developer": "Mojang Studios",
        "publisher": "Microsoft",
        "price_eur": 29.99,
        "is_free": False,
        "review_score": 92,
        "quiz_popularity": 10,
        "platforms": ["pc", "playstation", "xbox", "switch", "mobile"],
        "steam_tags": [
            "Sandbox", "Building", "Survival", "Open World", "Crafting",
            "Multiplayer", "Singleplayer", "Family Friendly", "Exploration",
            "Creative", "Procedural Generation", "Cute",
        ],
        "description": (
            "The best-selling game of all time. Mine resources, craft tools, and build anything "
            "imaginable in a procedurally generated world. Survival or pure creative mode. "
            "Infinite replayability, massive modding community."
        ),
        "steam_url": "https://www.minecraft.net",
    },
    {
        "appid": 9900302,
        "name": "Sea of Thieves",
        "developer": "Rare",
        "publisher": "Xbox Game Studios",
        "price_eur": 39.99,
        "is_free": False,
        "review_score": 82,
        "quiz_popularity": 7,
        "platforms": ["pc", "xbox"],
        "steam_tags": [
            "Open World", "Multiplayer", "Co-op", "Online Co-Op", "Adventure",
            "Sailing", "Pirates", "Exploration", "Action-Adventure", "PvP", "PvE",
        ],
        "description": (
            "Shared-world pirate adventure. Crew a ship with friends, hunt treasure, battle "
            "skeleton forts, and clash with rival pirates. Gorgeous water and a freeform "
            "sandbox that rewards creative play."
        ),
        "steam_url": "https://www.seaofthieves.com",
    },
    {
        "appid": 9900303,
        "name": "Age of Empires IV",
        "developer": "Relic Entertainment",
        "publisher": "Xbox Game Studios",
        "price_eur": 39.99,
        "is_free": False,
        "review_score": 82,
        "quiz_popularity": 6,
        "platforms": ["pc", "xbox"],
        "steam_tags": [
            "RTS", "Strategy", "Historical", "Multiplayer", "Singleplayer",
            "Real-Time with Pause", "Management", "Base-Building", "Military", "Medieval",
        ],
        "description": (
            "Fourth mainline entry in the legendary real-time strategy series. Eight distinct "
            "civilizations with unique mechanics across four historical campaigns. Deep multiplayer "
            "with strong ranked scene."
        ),
        "steam_url": "https://www.ageofempires.com/games/age-of-empires-iv",
    },

    # ── Blizzard / Activision (Battle.net) ───────────────────────────────────────

    {
        "appid": 9900401,
        "name": "World of Warcraft",
        "developer": "Blizzard Entertainment",
        "publisher": "Blizzard Entertainment",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 82,
        "quiz_popularity": 9,
        "platforms": ["pc"],
        "steam_tags": [
            "MMORPG", "RPG", "Massively Multiplayer", "Fantasy", "Online Co-Op",
            "PvP", "PvE", "Adventure", "Open World", "Multiplayer",
        ],
        "description": (
            "The defining MMORPG. Twenty years of content across a vast fantasy world. "
            "Raid with guilds, conquer PvP battlegrounds, or explore at your own pace. "
            "Free to level 20, subscription for full access."
        ),
        "steam_url": "https://worldofwarcraft.blizzard.com",
    },
    {
        "appid": 9900402,
        "name": "Overwatch 2",
        "developer": "Blizzard Entertainment",
        "publisher": "Blizzard Entertainment",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 76,
        "quiz_popularity": 9,
        "platforms": ["pc", "playstation", "xbox", "switch"],
        "steam_tags": [
            "Hero Shooter", "FPS", "Multiplayer", "Free to Play", "Team-Based",
            "Competitive", "PvP", "Action", "First-Person", "Colorful", "E-sports",
        ],
        "description": (
            "Free-to-play 5v5 hero shooter sequel from Blizzard. Diverse roster of heroes "
            "with unique abilities across multiple game modes. Fast-paced team fights with "
            "deep role synergies. Strong esports presence."
        ),
        "steam_url": "https://overwatch.blizzard.com",
    },
    {
        "appid": 9900403,
        "name": "Hearthstone",
        "developer": "Blizzard Entertainment",
        "publisher": "Blizzard Entertainment",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 78,
        "quiz_popularity": 8,
        "platforms": ["pc", "mobile"],
        "steam_tags": [
            "Card Game", "Strategy", "Multiplayer", "Free to Play", "PvP",
            "Fantasy", "Singleplayer", "Roguelike Deckbuilder", "Turn-Based Strategy",
        ],
        "description": (
            "Blizzard's hugely popular digital card game set in the Warcraft universe. "
            "Build decks from hundreds of cards and duel opponents. Multiple modes including "
            "Arena drafts, Battlegrounds auto-battler, and solo adventures."
        ),
        "steam_url": "https://hearthstone.blizzard.com",
    },
    {
        "appid": 9900404,
        "name": "StarCraft II",
        "developer": "Blizzard Entertainment",
        "publisher": "Blizzard Entertainment",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 88,
        "quiz_popularity": 7,
        "platforms": ["pc"],
        "steam_tags": [
            "RTS", "Strategy", "Competitive", "Sci-fi", "Multiplayer",
            "Singleplayer", "E-sports", "Base-Building", "Military", "Real-Time with Pause",
        ],
        "description": (
            "The pinnacle of real-time strategy. Command Terran, Zerg, or Protoss across "
            "three full single-player campaigns. Free multiplayer with one of the deepest "
            "competitive skill ceilings in gaming."
        ),
        "steam_url": "https://starcraft2.blizzard.com",
    },
    {
        "appid": 9900405,
        "name": "Call of Duty: Warzone",
        "developer": "Infinity Ward / Raven Software",
        "publisher": "Activision",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 76,
        "quiz_popularity": 9,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "Battle Royale", "FPS", "Multiplayer", "Free to Play", "Shooter",
            "First-Person", "PvP", "Tactical", "Military", "Realistic", "Action",
        ],
        "description": (
            "Free-to-play battle royale set in the Call of Duty universe. Up to 150 players "
            "fight across large maps with realistic gunplay. Regular seasonal updates with "
            "new weapons, operators, and limited-time modes."
        ),
        "steam_url": "https://www.callofduty.com/warzone",
    },

    # ── PlayStation Studios (on PC via their own launcher / EGS) ─────────────────

    {
        "appid": 9900501,
        "name": "Marvel's Spider-Man Remastered",
        "developer": "Insomniac Games",
        "publisher": "Sony Interactive Entertainment",
        "price_eur": 59.99,
        "is_free": False,
        "review_score": 93,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation"],
        "steam_tags": [
            "Action-Adventure", "Superhero", "Open World", "Singleplayer", "Story Rich",
            "Third-Person", "Action", "Combat", "Exploration", "Atmospheric",
        ],
        "description": (
            "Definitive Spider-Man game. Swing across a stunning open-world Manhattan, "
            "battle iconic villains, and experience a cinematic story. Fluid web-swinging "
            "and acrobatic combat feel genuinely superheroic."
        ),
        "steam_url": "https://www.playstation.com/en-us/games/marvels-spider-man-remastered",
    },
    {
        "appid": 9900502,
        "name": "The Last of Us Part I",
        "developer": "Naughty Dog",
        "publisher": "Sony Interactive Entertainment",
        "price_eur": 59.99,
        "is_free": False,
        "review_score": 87,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation"],
        "steam_tags": [
            "Action-Adventure", "Survival", "Singleplayer", "Story Rich", "Post-apocalyptic",
            "Third-Person", "Atmospheric", "Emotional", "Horror", "Stealth",
        ],
        "description": (
            "Landmark narrative action game following Joel and Ellie across a post-pandemic "
            "United States. Masterful storytelling, tense stealth-survival gameplay, and one "
            "of gaming's most emotionally powerful stories."
        ),
        "steam_url": "https://www.playstation.com/en-us/games/the-last-of-us-part-i",
    },
    {
        "appid": 9900503,
        "name": "Ghost of Tsushima",
        "developer": "Sucker Punch Productions",
        "publisher": "Sony Interactive Entertainment",
        "price_eur": 59.99,
        "is_free": False,
        "review_score": 91,
        "quiz_popularity": 7,
        "platforms": ["pc", "playstation"],
        "steam_tags": [
            "Action-Adventure", "Open World", "Singleplayer", "Story Rich", "Historical",
            "Stealth", "Samurai", "Atmospheric", "Third-Person", "Exploration",
        ],
        "description": (
            "Beautiful open-world samurai game set in feudal Japan during the Mongol invasion. "
            "Fluid katana combat, deep stealth options, and a stunning world to explore. "
            "Excellent PC port with full Legends co-op mode included."
        ),
        "steam_url": "https://www.playstation.com/en-us/games/ghost-of-tsushima",
    },

    # ── EA App ────────────────────────────────────────────────────────────────────

    {
        "appid": 9900601,
        "name": "EA Sports FC 25",
        "developer": "EA Vancouver",
        "publisher": "Electronic Arts",
        "price_eur": 69.99,
        "is_free": False,
        "review_score": 75,
        "quiz_popularity": 9,
        "platforms": ["pc", "playstation", "xbox", "switch"],
        "steam_tags": [
            "Sports", "Football (Soccer)", "Multiplayer", "Singleplayer",
            "Competitive", "Simulation", "E-sports", "Online Co-Op", "PvP",
        ],
        "description": (
            "EA's flagship football simulation. Realistic player likenesses, licensed clubs, "
            "and polished match engine. Ultimate Team card-collecting mode dominates player time. "
            "Best-selling sports franchise globally."
        ),
        "steam_url": "https://www.ea.com/games/ea-sports-fc/ea-sports-fc-25",
    },
    {
        "appid": 9900602,
        "name": "Battlefield 2042",
        "developer": "DICE",
        "publisher": "Electronic Arts",
        "price_eur": 9.99,
        "is_free": False,
        "review_score": 76,
        "quiz_popularity": 7,
        "platforms": ["pc", "playstation", "xbox"],
        "steam_tags": [
            "FPS", "Multiplayer", "Action", "Military", "Shooter", "First-Person",
            "Team-Based", "PvP", "Large Scale", "Destruction",
        ],
        "description": (
            "Large-scale multiplayer FPS set in a near-future battlefield. 128-player matches "
            "on massive maps with vehicles, gadgets, and destructible environments. Recovered "
            "significantly post-launch — now a solid Battlefield experience."
        ),
        "steam_url": "https://www.ea.com/games/battlefield/battlefield-2042",
    },

    # ── Other major non-Steam ─────────────────────────────────────────────────────

    {
        "appid": 9900701,
        "name": "Roblox",
        "developer": "Roblox Corporation",
        "publisher": "Roblox Corporation",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 78,
        "quiz_popularity": 10,
        "platforms": ["pc", "xbox", "mobile"],
        "steam_tags": [
            "Sandbox", "Free to Play", "Multiplayer", "Family Friendly", "Casual",
            "Building", "Creative", "Colorful", "Open World", "Cute",
        ],
        "description": (
            "Massive platform of user-created games spanning every genre. Huge social element — "
            "play obbys, tycoons, shooters, or roleplay worlds created by the community. "
            "Extremely popular with younger audiences."
        ),
        "steam_url": "https://www.roblox.com",
    },
    {
        "appid": 9900702,
        "name": "Final Fantasy XIV Online",
        "developer": "Square Enix",
        "publisher": "Square Enix",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 90,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation"],
        "steam_tags": [
            "MMORPG", "RPG", "Massively Multiplayer", "Fantasy", "Story Rich",
            "Online Co-Op", "PvE", "Anime", "Open World", "Multiplayer",
        ],
        "description": (
            "The best MMORPG currently running. Free trial through two full expansions. "
            "Rich storytelling across a 14-expansion arc, excellent job system, "
            "outstanding raid design, and a welcoming community."
        ),
        "steam_url": "https://www.finalfantasyxiv.com",
    },

    # ── Epic Games ────────────────────────────────────────────────────────────────

    {
        "appid": 9900201,
        "name": "Fortnite",
        "developer": "Epic Games",
        "publisher": "Epic Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 76,
        "quiz_popularity": 10,
        "platforms": ["pc", "playstation", "xbox", "switch", "mobile"],
        "steam_tags": [
            "Battle Royale", "Building", "Multiplayer", "Free to Play", "Third-Person Shooter",
            "Shooter", "PvP", "Action", "Colorful", "Survival", "Co-op",
        ],
        "description": (
            "Massively popular free-to-play battle royale. 100 players drop onto a shrinking "
            "island combining shooting with unique building mechanics. Constant crossover events "
            "and seasonal content. Available on all platforms."
        ),
        "steam_url": "https://www.fortnite.com",
    },
    {
        "appid": 9900202,
        "name": "Rocket League",
        "developer": "Psyonix",
        "publisher": "Epic Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 91,
        "quiz_popularity": 8,
        "platforms": ["pc", "playstation", "xbox", "switch"],
        "steam_tags": [
            "Sports", "Racing", "Multiplayer", "Competitive", "Free to Play",
            "PvP", "Team-Based", "Driving", "Arcade", "E-sports",
        ],
        "description": (
            "Rocket-powered cars play soccer in an arena. Deceptively simple to learn, "
            "with an enormous skill ceiling — aerial mechanics take hundreds of hours to master. "
            "One of the best competitive games ever made."
        ),
        "steam_url": "https://www.rocketleague.com",
    },
    {
        "appid": 9900203,
        "name": "Fall Guys",
        "developer": "Mediatonic",
        "publisher": "Epic Games",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 79,
        "quiz_popularity": 7,
        "platforms": ["pc", "playstation", "xbox", "switch"],
        "steam_tags": [
            "Battle Royale", "Party Game", "Multiplayer", "Platformer", "Casual",
            "Free to Play", "Colorful", "Funny", "Cute", "Family Friendly",
        ],
        "description": (
            "Chaotic party battle royale where jellybean characters race and stumble through "
            "obstacle courses. Up to 60 players eliminated round by round. Bright, silly, "
            "and accessible fun for all ages."
        ),
        "steam_url": "https://www.fallguys.com",
    },
    {
        "appid": 9900204,
        "name": "Genshin Impact",
        "developer": "HoYoverse",
        "publisher": "HoYoverse",
        "price_eur": 0.0,
        "is_free": True,
        "review_score": 84,
        "quiz_popularity": 9,
        "platforms": ["pc", "playstation", "mobile"],
        "steam_tags": [
            "Action RPG", "Open World", "Free to Play", "Anime", "Singleplayer",
            "Co-op", "Online Co-Op", "Fantasy", "RPG", "Exploration", "Story Rich",
        ],
        "description": (
            "Stunning open-world action RPG with gacha mechanics. Explore the vast world of "
            "Teyvat across diverse regions, solve puzzles, and build a team of elemental characters. "
            "Massive free content updates every six weeks."
        ),
        "steam_url": "https://genshin.hoyoverse.com",
    },
]
# fmt: on


def run(dry_run: bool):
    print(f"{'[DRY RUN] ' if dry_run else ''}add_manual_games.py")
    print(f"File: {DATA_FILE}\n")

    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    existing_ids = {g["appid"] for g in db["games"]}
    print(f"Existing games: {len(existing_ids)}")

    to_add = []
    skipped = []
    for g in MANUAL_GAMES:
        if g["appid"] in existing_ids:
            skipped.append(g["name"])
        else:
            to_add.append(g)

    if skipped:
        print(f"Already in DB (skipped): {skipped}")

    print(f"\nTo add: {len(to_add)}")
    for g in to_add:
        gem = " [HIDDEN GEM]" if g["quiz_popularity"] <= 6 and g["review_score"] >= 88 else ""
        print(f"  [{g['appid']}] {g['name']} (score:{g['review_score']} pop:{g['quiz_popularity']}){gem}")

    if dry_run or not to_add:
        if dry_run:
            print("\n[DRY RUN] No changes written.")
        return

    db["games"].extend(to_add)
    db["metadata"]["last_updated"] = str(date.today())
    db["metadata"]["total_games"] = len(db["games"])

    backup = DATA_FILE.with_suffix(f".backup_manual_{date.today()}.json")
    import shutil
    shutil.copy2(DATA_FILE, backup)
    print(f"\nBackup: {backup}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"Saved: {DATA_FILE} ({len(db['games'])} games total)")
    print("\nNext step: py embed_games.py  (generates rich_description + embeddings for new entries)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
