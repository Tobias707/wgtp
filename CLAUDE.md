# CLAUDE.md – What Game to Play (WGTP)

## Project Overview

Game recommendation website. Users answer 10-question quiz about gaming preferences → receive 10-12 personalized game recommendations ranked by match score.

**Tech:** Semantic matching via embeddings (no LLM calls, self-contained).

---

## Status (2026-05-03)

### ✅ Done
- [x] Data prep: 1942 games with rich_description + 384-dim embeddings
- [x] Backend API: FastAPI /api/recommend endpoint (models.py, main.py, requirements.txt)
- [x] Frontend: wgtp.html integrated with API client

### ⏳ Remaining
- [x] Test backend locally (health + /api/recommend verified 2026-05-03)
- [ ] Deploy backend to production (Render/Railway)
- [ ] Update wgtp.html API URL to production
- [ ] End-to-end testing with 5+ different user profiles

---

## File Structure (Current)

```
d:\ProjektWGTP\
├── CLAUDE.md                    ← this file
├── wgtp.html                    ← main app: quiz + results
├── games_data.json              ← 1942 games + embeddings
├── fetch_games.py               ← fetch new games from SteamSpy
├── audit_data.py                ← data quality check script
├── embed_games.py               ← pre-compute embeddings
├── bootstrap_appids.py          ← initial appid seeding (legacy)
└── backend/
    ├── main.py                  ← FastAPI /api/recommend
    ├── models.py                ← request/response schemas
    └── requirements.txt         ← dependencies
```

---

## How It Works

### Data Layer

Each game in `games_data.json` has:

```json
{
  "appid": 413150,
  "name": "Stardew Valley",
  "steam_tags": ["Farming Sim", "Pixel Graphics", "Relaxing", "RPG", ...],
  "description": "You've inherited your grandfather's old farm plot...",
  "quiz_players": ["solo", "2"],
  "quiz_popularity": 9,
  "price_eur": 14.99,
  "review_score": 98,
  "platforms": ["pc", "playstation", "xbox", "switch", "mobile", "steamdeck"],
  "rich_description": "Stardew Valley. Tags: Farming Sim, Pixel Graphics, ... Description: You've inherited...",
  "embedding": [0.234, -0.102, 0.456, ...] // 384 floats
}
```

**Key:** `rich_description` + `embedding` are what drives matching. Other quiz_* fields stay in DB but are NOT used for matching (they were corrupted; semantic matching handles that nuance).

### Recommendation Algorithm

**Request:** POST /api/recommend with quiz answers
```json
{
  "platforms": ["pc"],
  "players": "solo",
  "online_preference": "offline",
  "budget": "<30",
  "genres": ["rpg", "adventure"],
  "loved_games": ["Stardew Valley"],
  "disliked_games": ["Fortnite"],
  "session_length": "long",
  "difficulty": "medium",
  "story_importance": "core",
  "popularity": 5
}
```

**Process:**
1. Build user profile text from quiz answers
2. Embed text using sentence-transformer (same model used for games)
3. Compute cosine similarity: user_vector vs all 1942 game_embeddings (~100-200ms)
4. Apply soft filters (post-ranking):
   - Budget: hard filter (exclude if price > budget)
   - Disliked games: -100 penalty
   - Platform mismatch: -70 penalty
   - Players mismatch: -35 penalty
5. Mark hidden gems (quiz_popularity ≤ 6 AND review_score ≥ 88)
6. Return top 10 games

**Response:**
```json
{
  "timestamp": "2026-05-03T...",
  "results": [
    {
      "appid": 413150,
      "name": "Stardew Valley",
      "steam_url": "https://store.steampowered.com/app/413150",
      "description": "...",
      "price_eur": 14.99,
      "review_score": 98,
      "is_free": false,
      "match_score": 87.5,
      "is_hidden_gem": false
    },
    ...
  ]
}
```

---

## Deployment Checklist

### Step 1: Test Backend Locally

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then in browser:
- http://localhost:8000/health → should return `{"status": "ok", "games_loaded": 1942}`
- Open wgtp.html, fill quiz, submit → should see results from localhost:8000/api/recommend

### Step 2: Deploy Backend to Production

Options:
- **Render.com** (easy): Push repo, set environment
- **Railway** (easy): Similar to Render
- **Fly.io** (efficient): Fast, good for Python

Steps:
1. Create account on chosen platform
2. Connect GitHub repo (or upload code)
3. Set build command: `pip install -r backend/requirements.txt`
4. Set start command: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
5. Note the deployed URL (e.g., `https://wgtp-api.render.com`)

### Step 3: Update Frontend API URL

In `wgtp.html`, line ~672, change:
```javascript
const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/recommend';
```

To production URL:
```javascript
const apiUrl = 'https://wgtp-api.render.com/api/recommend';
```

### Step 4: Test End-to-End

Deploy wgtp.html to Vercel (or static host).

Test with 5+ different quiz profiles:
- [ ] User wants RPG + long sessions → returns RPGs
- [ ] User selects rare genre (roguelike) + specific budget → returns best roguelikes + near-matches
- [ ] User dislikes all mainstream → hidden gems rank higher
- [ ] User loves Stardew Valley + wants cozy → returns similar cozy games
- [ ] User selects impossible combo → still returns 10 games (no crash)

---

## Data Quality Notes

**What's good:**
- steam_tags: accurate (from SteamSpy)
- steam_description: accurate
- price_eur, review_score, platforms: clean

**What we ignore (corrupted):**
- quiz_genres, quiz_difficulty, quiz_story, quiz_session_length: auto-inferred, often wrong
- Solution: semantic matching on rich_description handles all that nuance automatically

**If data quality issues arise:**
- Run: `python audit_data.py` → reports suspicious patterns
- Run: `python fetch_games.py` → refreshes data from SteamSpy
- Run: `python embed_games.py` → recomputes embeddings after data changes

---

## Key Decisions

- **No LLM calls** — self-contained, no API dependencies
- **Embeddings pre-computed** — no runtime overhead
- **Semantic matching** — robust to data quality issues
- **Quiz_players soft filter only** — simplest/cleanest categorical filter
- **10 results per request** — reasonable size
- **Hidden gems discovery** — surface good low-popularity games

---

## Contact

Email: tobias.l.ulmer@gmail.com

*Last updated: 2026-05-03 — implementation complete, ready for deployment testing*
