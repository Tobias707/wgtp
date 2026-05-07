from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from models import QuizRequest, RecommendResponse, GameResult, FeedbackRequest
import json
import numpy as np
from datetime import datetime
import os
from sentence_transformers import SentenceTransformer
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

games_data = None
games_list = None
embedding_model = None
games_by_name = {}

@app.on_event("startup")
def load_games():
    global games_data, games_list, embedding_model, games_by_name
    try:
        print("Loading sentence-transformer model...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Model loaded")

        data_path = os.path.join(os.path.dirname(__file__), "..", "games_data.json")
        with open(data_path, "r", encoding="utf-8") as f:
            games_data = json.load(f)
        games_list = games_data["games"]
        games_by_name = {g["name"].lower(): g for g in games_list}
        print(f"Loaded {len(games_list)} games with embeddings")
    except Exception as e:
        print(f"Error loading data: {e}")
        raise


@app.get("/health")
def health():
    return {"status": "ok", "games_loaded": len(games_list) if games_list else 0}


GENRE_TAG_MAP = {
    'puzzle':     {'puzzle', 'logic', 'physics puzzle', 'point & click', 'hidden object', 'match 3', 'word game', 'escape room', 'sokoban', 'nonogram', 'tile-matching'},
    'rpg':        {'rpg', 'action rpg', 'crpg', 'dungeon crawler', 'jrpg', 'turn-based rpg', 'loot'},
    'strategy':   {'strategy', '4x', 'grand strategy', 'city builder', 'rts', 'tower defense', 'turn-based strategy', 'wargame', 'card game', 'card battler', 'deckbuilding', 'deckbuilder'},
    'simulation': {'simulation', 'farming sim', 'life sim', 'flight', 'tycoon', 'management', 'economy', 'cooking'},
    'roguelike':  {'rogue-like', 'rogue-lite', 'action roguelike', 'roguelite', 'roguelike'},
    'platformer': {'platformer', '2d platformer', 'metroidvania', 'runner', 'auto-runner', 'precision platformer'},
    'horror':     {'horror', 'survival horror', 'psychological horror'},
    'sports':     {'sports', 'racing', 'football', 'soccer', 'baseball', 'basketball', 'skating', 'golf'},
    'sandbox':    {'sandbox', 'open world survival craft', 'building', 'crafting', 'survival', 'base building'},
    'shooter':    {'fps', 'first-person shooter', 'third-person shooter', 'hero shooter', "shoot 'em up", 'bullet hell', 'twin stick shooter'},
    'adventure':  {'adventure', 'action-adventure', 'exploration', 'narrative', 'visual novel', 'walking simulator', 'interactive fiction'},
    'action':     {'action', "beat 'em up", 'fighting', 'brawler', 'hack and slash', 'martial arts'},
}

GENRE_PROFILE_TEXT = {
    'puzzle':     'puzzle adventure atmospheric mystery exploration cooperative escape room environmental puzzle first-person narrative puzzle immersive',
    'rpg':        'role-playing RPG character progression leveling stats dungeon loot',
    'strategy':   'strategy planning resource management city building turn-based real-time',
    'simulation': 'simulation management tycoon farming life economy',
    'roguelike':  'roguelike rogue-lite procedural permadeath run-based',
    'platformer': 'platformer jumping 2D metroidvania precision movement',
    'horror':     'horror scary atmospheric survival horror psychological thriller',
    'sports':     'sports racing football soccer competitive athletics',
    'sandbox':    'sandbox open world survival crafting building exploration',
    'shooter':    'first-person shooter FPS third-person shooter gun combat shooting',
    'adventure':  'adventure exploration narrative story-driven visual novel',
    'action':     'action fighting hack and slash brawler melee combat',
}

DIFFICULTY_PROFILE_TEXT = {
    'easy':   'casual easy relaxing accessible beginner-friendly low stakes cozy chill',
    'chill':  'casual easy relaxing accessible beginner-friendly low stakes cozy chill',
    'medium': 'moderate balanced normal difficulty approachable',
    'hard':   'challenging hard difficult punishing demanding precise unforgiving souls-like',
}

SESSION_LENGTH_PROFILE_TEXT = {
    'short':  'quick sessions bite-sized short play time casual pick up and play',
    'medium': 'medium sessions one to two hours moderate playtime',
    'long':   'long sessions immersive deep extended playtime epic adventure hours',
}

STORY_IMPORTANCE_PROFILE_TEXT = {
    'core':       'story-driven narrative rich deep lore character development cinematic plot-driven',
    'nice':       'light story some narrative context optional lore',
    'irrelevant': 'gameplay-focused no story minimal narrative pure mechanics action arcade',
}

PLAYERS_PROFILE_TEXT = {
    'solo':  'singleplayer solo single player no multiplayer offline alone',
    '2':     'co-op two players local co-op online co-op duo cooperative two-player couch co-op',
    '3-4':   'multiplayer 3 4 players co-op team cooperative online friends party',
    '5+':    'large multiplayer many players online multiplayer team-based group squad',
    'any':   'multiplayer singleplayer co-op flexible',
}

ONLINE_PREFERENCE_PROFILE_TEXT = {
    'online':   'online multiplayer internet required play with others connected',
    'offline':  'offline singleplayer no internet local no online required',
    'any':      'online or offline flexible singleplayer multiplayer',
}

ADULT_TAGS = {"sexual content", "nsfw", "adult only content", "hentai", "nudity"}

CORE_GENRES = {'shooter', 'horror', 'roguelike', 'puzzle', 'simulation'}
BLEND_GENRES = {'action', 'adventure', 'rpg', 'platformer', 'strategy', 'sandbox', 'sports'}

GOOD_SIMULATION_TAGS = {'farming sim', 'life sim', 'tycoon', 'management', 'economy', 'cooking', 'flight'}


def get_genre_tag_set(genres: list) -> set:
    tags = set()
    for g in genres:
        if g in GENRE_TAG_MAP:
            tags.update(GENRE_TAG_MAP[g])
    return tags


def get_core_genres_from_list(genres: list) -> set:
    return set(g for g in genres if g in CORE_GENRES)


def get_blend_genres_from_list(genres: list) -> set:
    return set(g for g in genres if g in BLEND_GENRES)


def budget_to_float(budget_str: str) -> float:
    if budget_str == "free":
        return 0.0
    elif budget_str == "<5":
        return 5.0
    elif budget_str == "<10":
        return 10.0
    elif budget_str == "<30":
        return 30.0
    else:
        return 999999.0


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)


def _write_feedback(appid: int, genre_bucket: str, vote: int):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{SUPABASE_URL}/rest/v1/game_feedback",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"appid": appid, "genre_bucket": genre_bucket, "vote": vote},
            )
    except Exception as e:
        print(f"[feedback] Supabase write failed: {e}")


def fetch_votes(appids: list, genre_bucket: str) -> dict:
    """Returns {appid: net_votes} for the given appids and genre_bucket."""
    if not SUPABASE_URL or not SUPABASE_KEY or not appids or not genre_bucket:
        return {}
    try:
        appid_list = ",".join(str(a) for a in appids)
        url = (
            f"{SUPABASE_URL}/rest/v1/game_feedback"
            f"?appid=in.({appid_list})"
            f"&genre_bucket=eq.{genre_bucket}"
            f"&select=appid,vote"
        )
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url, headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            })
        if resp.status_code != 200:
            return {}
        net_votes: dict = {}
        for row in resp.json():
            aid = row["appid"]
            net_votes[aid] = net_votes.get(aid, 0) + row["vote"]
        return net_votes
    except Exception as e:
        print(f"[feedback] Supabase read failed: {e}")
        return {}


@app.post("/api/feedback")
def feedback(req: FeedbackRequest, background_tasks: BackgroundTasks):
    if not req.genres:
        return {"ok": True}
    genre_bucket = ",".join(sorted(req.genres))
    vote_int = 1 if req.vote == "up" else -1
    background_tasks.add_task(_write_feedback, req.appid, genre_bucket, vote_int)
    return {"ok": True}


def build_user_profile_text(quiz: QuizRequest) -> str:
    genres_str = ", ".join(quiz.genres) if quiz.genres else "any genre"
    genre_expansions = " ".join(GENRE_PROFILE_TEXT[g] for g in quiz.genres if g in GENRE_PROFILE_TEXT)
    loved_str = ", ".join(quiz.loved_games) if quiz.loved_games else "none"
    disliked_str = ", ".join(quiz.disliked_games) if quiz.disliked_games else "none"

    loved_tag_words = []
    for game_name in quiz.loved_games:
        match = games_by_name.get(game_name.lower())
        if match:
            loved_tag_words.extend(match.get("steam_tags", [])[:10])
    loved_tag_anchor = ""
    if loved_tag_words:
        unique_tags = list(dict.fromkeys(loved_tag_words))
        loved_tag_anchor = f"Similar to games tagged: {', '.join(unique_tags)}. "

    difficulty_expansion = DIFFICULTY_PROFILE_TEXT.get(quiz.difficulty, quiz.difficulty)
    session_expansion = SESSION_LENGTH_PROFILE_TEXT.get(quiz.session_length, quiz.session_length)
    story_expansion = STORY_IMPORTANCE_PROFILE_TEXT.get(quiz.story_importance, quiz.story_importance)
    players_expansion = PLAYERS_PROFILE_TEXT.get(quiz.players, quiz.players)
    online_expansion = ONLINE_PREFERENCE_PROFILE_TEXT.get(quiz.online_preference, quiz.online_preference)

    text = (
        f"Looking for: {genres_str}. "
        f"{genre_expansions}. "
        f"{players_expansion}. "
        f"{online_expansion}. "
        f"{difficulty_expansion}. "
        f"{story_expansion}. "
        f"{session_expansion}. "
        f"Budget: {quiz.budget}. "
        f"Loved games: {loved_str}. "
        f"{loved_tag_anchor}"
        f"Disliked: {disliked_str}. "
        f"Platforms: {', '.join(quiz.platforms)}. "
    )
    return text


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(quiz: QuizRequest):
    if not games_list or not embedding_model:
        raise HTTPException(status_code=503, detail="Games data not loaded")

    try:
        user_text = build_user_profile_text(quiz)
        user_embedding = embedding_model.encode(user_text, convert_to_numpy=True)

        loved_vecs = []
        for game_name in quiz.loved_games:
            match = games_by_name.get(game_name.lower())
            if match and "embedding" in match:
                loved_vecs.append(np.array(match["embedding"]))
        if loved_vecs:
            loved_avg = np.mean(loved_vecs, axis=0)
            user_embedding = 0.65 * user_embedding + 0.35 * loved_avg
            norm = np.linalg.norm(user_embedding)
            if norm > 0:
                user_embedding = user_embedding / norm

        budget_max = budget_to_float(quiz.budget)
        disliked_set = set(g.lower() for g in quiz.disliked_games)
        loved_set = set(g.lower() for g in quiz.loved_games)
        user_core_genres = get_core_genres_from_list(quiz.genres)
        user_blend_genres = get_blend_genres_from_list(quiz.genres)

        debug_file = os.path.join(os.path.dirname(__file__), "..", "debug.log")
        with open(debug_file, "a", encoding="utf-8") as f:
            f.write(f"\nRequest: genres={quiz.genres}, core={user_core_genres}, blend={user_blend_genres}\n")

        scored_games = []

        for game in games_list:
            if game.get("price_eur", 0) > budget_max:
                continue
            if game.get("review_score", 0) < 75:
                continue

            game_tags_lower_set = {t.lower() for t in game.get("steam_tags", [])}
            if game_tags_lower_set.intersection(ADULT_TAGS):
                continue
            if game["name"].lower() in loved_set:
                continue

            if quiz.players != "any":
                game_players = game.get("quiz_players", [])
                if quiz.players not in game_players:
                    continue

            if 'horror' in user_core_genres:
                horror_tags = {'horror', 'survival horror', 'psychological horror'}
                if not game_tags_lower_set.intersection(horror_tags):
                    continue

            if 'shooter' in user_core_genres:
                shooter_tags = {'fps', 'first-person shooter', 'third-person shooter', 'hero shooter', "shoot 'em up", 'bullet hell', 'twin stick shooter'}
                if not game_tags_lower_set.intersection(shooter_tags):
                    continue

            if 'roguelike' in user_core_genres:
                roguelike_tags = {'rogue-like', 'rogue-lite', 'action roguelike', 'roguelite', 'roguelike'}
                if not game_tags_lower_set.intersection(roguelike_tags):
                    continue

            if 'puzzle' in user_core_genres:
                puzzle_tags = {'puzzle', 'logic', 'physics puzzle', 'point & click', 'hidden object', 'match 3', 'word game', 'escape room', 'sokoban', 'nonogram', 'tile-matching'}
                if not game_tags_lower_set.intersection(puzzle_tags):
                    continue

            if 'simulation' in user_core_genres:
                good_simulation_tags = {'farming sim', 'life sim', 'tycoon', 'management', 'economy', 'cooking'}
                if not game_tags_lower_set.intersection(good_simulation_tags):
                    continue

            if "embedding" not in game:
                continue

            game_embedding = game["embedding"]
            similarity = cosine_similarity(user_embedding, game_embedding)
            score = similarity * 100

            if user_blend_genres:
                blend_genre_tags = set()
                for g in user_blend_genres:
                    if g in GENRE_TAG_MAP:
                        blend_genre_tags.update(GENRE_TAG_MAP[g])
                if blend_genre_tags and not game_tags_lower_set.intersection(blend_genre_tags):
                    score -= 80

            if game["name"].lower() in disliked_set:
                score -= 100

            game_platforms = set(game.get("platforms", []))
            user_platforms = set(quiz.platforms)
            if user_platforms and game_platforms:
                if not game_platforms.intersection(user_platforms):
                    score -= 70

            scored_games.append({
                "game": game,
                "score": score,
                "similarity": similarity,
            })

        # Apply community feedback adjustment (capped at ±12 pts)
        if scored_games and quiz.genres:
            user_genre_bucket = ",".join(sorted(quiz.genres))
            candidate_appids = [item["game"]["appid"] for item in scored_games]
            net_votes_map = fetch_votes(candidate_appids, user_genre_bucket)
            for item in scored_games:
                net = net_votes_map.get(item["game"]["appid"], 0)
                item["score"] += max(-12, min(12, net * 2))

        scored_games.sort(key=lambda x: x["score"], reverse=True)

        results = []
        for item in scored_games[:10]:
            game = item["game"]
            results.append(GameResult(
                appid=game["appid"],
                name=game["name"],
                steam_url=game["steam_url"],
                description=game.get("description", ""),
                price_eur=game.get("price_eur", 0),
                review_score=game.get("review_score", 0),
                is_free=game.get("is_free", False),
                match_score=round(item["similarity"] * 100, 1),
            ))

        return RecommendResponse(
            timestamp=datetime.utcnow(),
            results=results
        )

    except Exception as e:
        print(f"Error in /api/recommend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
