from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import QuizRequest, RecommendResponse, GameResult
import json
import numpy as np
from datetime import datetime
import os
from sentence_transformers import SentenceTransformer

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
games_by_name = {}  # lowercase name -> game dict for loved/disliked lookups

@app.on_event("startup")
def load_games():
    global games_data, games_list, embedding_model, games_by_name
    try:
        # Load embedding model (same one used for preprocessing)
        print("Loading sentence-transformer model...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Model loaded")

        # Load games data
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
    'puzzle':     'puzzle logic brain teaser point and click hidden object',
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


def get_genre_tag_set(genres: list) -> set:
    tags = set()
    for g in genres:
        if g in GENRE_TAG_MAP:
            tags.update(GENRE_TAG_MAP[g])
    return tags


def budget_to_float(budget_str: str) -> float:
    """Convert budget string to float EUR"""
    if budget_str == "free":
        return 0.0
    elif budget_str == "<5":
        return 5.0
    elif budget_str == "<10":
        return 10.0
    elif budget_str == "<30":
        return 30.0
    else:
        return 999999.0  # "any" or other = unlimited


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors"""
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)


def build_user_profile_text(quiz: QuizRequest) -> str:
    genres_str = ", ".join(quiz.genres) if quiz.genres else "any genre"
    genre_expansions = " ".join(GENRE_PROFILE_TEXT[g] for g in quiz.genres if g in GENRE_PROFILE_TEXT)
    loved_str = ", ".join(quiz.loved_games) if quiz.loved_games else "none"
    disliked_str = ", ".join(quiz.disliked_games) if quiz.disliked_games else "none"

    # Inject actual tags from loved games so embedding anchors toward their vocabulary
    loved_tag_words = []
    for game_name in quiz.loved_games:
        match = games_by_name.get(game_name.lower())
        if match:
            loved_tag_words.extend(match.get("steam_tags", [])[:10])
    loved_tag_anchor = ""
    if loved_tag_words:
        unique_tags = list(dict.fromkeys(loved_tag_words))  # dedupe, preserve order
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
        f"Popularity preference: {quiz.popularity}/10. "
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
        # Build user profile text
        user_text = build_user_profile_text(quiz)

        # Embed user profile using sentence-transformer
        user_embedding = embedding_model.encode(user_text, convert_to_numpy=True)

        # Blend in loved game embeddings — pulls user vector toward known preferences
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
        user_genre_tags = get_genre_tag_set(quiz.genres)

        scored_games = []

        for game in games_list:
            # Hard filter: budget
            if game.get("price_eur", 0) > budget_max:
                continue

            # Hard filter: minimum review quality
            if game.get("review_score", 0) < 75:
                continue

            # Hard filter: adult content
            game_tags_lower_set = {t.lower() for t in game.get("steam_tags", [])}
            if game_tags_lower_set.intersection(ADULT_TAGS):
                continue

            # Get embedding similarity
            if "embedding" not in game:
                continue

            game_embedding = game["embedding"]
            similarity = cosine_similarity(user_embedding, game_embedding)

            # Start with embedding similarity score
            score = similarity * 100

            # Apply soft filters
            # Genre mismatch: heavy penalty when user picked genres but game has none matching
            if user_genre_tags:
                if not game_tags_lower_set.intersection(user_genre_tags):
                    score -= 80

            # Disliked games penalty
            if game["name"].lower() in disliked_set:
                score -= 100

            # Platform mismatch penalty
            game_platforms = set(game.get("platforms", []))
            user_platforms = set(quiz.platforms)
            if user_platforms and game_platforms:
                if not game_platforms.intersection(user_platforms):
                    score -= 70

            # Players mismatch penalty (use quiz_players)
            if quiz.players != "any":
                game_players = game.get("quiz_players", [])
                if quiz.players not in game_players:
                    score -= 35

            # Check for hidden gem
            is_hidden_gem = (
                game.get("quiz_popularity", 10) <= 6 and
                game.get("review_score", 0) >= 88
            )

            scored_games.append({
                "game": game,
                "score": score,
                "similarity": similarity,
                "is_hidden_gem": is_hidden_gem
            })

        # Sort by score (descending)
        scored_games.sort(key=lambda x: x["score"], reverse=True)

        # Get top 10-12, prioritizing hidden gems
        top_games = []
        hidden_gems_included = 0

        for item in scored_games:
            if len(top_games) >= 12:
                break

            # Include hidden gems earlier if we don't have 2-3 yet
            if item["is_hidden_gem"]:
                if hidden_gems_included < 3:
                    top_games.append(item)
                    hidden_gems_included += 1
            else:
                top_games.append(item)

        # Fill remaining slots if needed
        if len(top_games) < 10:
            for item in scored_games:
                if len(top_games) >= 10:
                    break
                if item not in top_games:
                    top_games.append(item)

        # Build response
        results = []
        for item in top_games[:10]:  # Return exactly top 10
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
                is_hidden_gem=item["is_hidden_gem"]
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
