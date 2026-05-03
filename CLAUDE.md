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
- [x] Test backend locally (health + /api/recommend verified 2026-05-03)
- [x] Deploy backend to Railway: https://wgtp-production.up.railway.app
- [x] Update wgtp.html API URL to production
- [x] Algorithm tuning round 1 (2026-05-03) — see Algorithm Changelog below

### ⏳ Remaining
- [ ] Continue algorithm tuning based on real recommendation feedback
- [ ] Test remaining edge-case profiles (impossible combo, popularity extremes)

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
1. Build user profile text from quiz answers (with semantic keyword expansion)
2. Inject loved game steam_tags into profile text as tag anchor
3. Embed text using sentence-transformer (same model used for games)
4. Blend embedding: 65% profile vector + 35% average of loved game vectors (re-normalized)
5. Hard filters (skip game entirely):
   - Budget: exclude if price > budget
   - Quality: exclude if review_score < 75
   - Adult content: exclude if tagged Sexual Content / NSFW / Adult Only / Hentai / Nudity
6. Compute cosine similarity: user_vector vs remaining game_embeddings
7. Apply soft penalties (post-similarity):
   - Genre mismatch: -80 (if user selected genres but game has none matching)
   - Disliked games: -100
   - Platform mismatch: -70
   - Players mismatch: -35
8. Mark hidden gems (quiz_popularity ≤ 6 AND review_score ≥ 88)
9. Return top 10 games (prioritize up to 3 hidden gems)

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
- **No tag-based difficulty penalty** — Steam difficulty tags too sparse for reliable coverage; use semantic expansion instead

---

## Algorithm Changelog

### Round 1 — 2026-05-03

**Problems found via 4 test profiles:**

| Profile | Issue | Root Cause |
|---|---|---|
| RPG+adventure, Stardew loved, easy | Stardew Valley ranked #9 | Proper noun "Stardew Valley" has no semantic weight; embedding blind to loved games |
| RPG+adventure, easy | Only Up #3 (Parkour/Difficult, 73% review) | Broad tags ("Adventure","Rogue-like") escaped genre penalty; generic embedding near many vectors |
| RPG+adventure, easy | Changed #7 (Sexual Content/Horror) | Had "Adventure"+"RPG" tags so passed genre filter; no content filter existed |
| Roguelike, Hades loved | Only Up #6 again | Same root cause: "Rogue-like" tag + low review score not filtered |

**Fixes applied (commits `283a24f` → `02ec279`):**

1. **Loved game tag injection** (`283a24f`) — Inject loved game's actual steam_tags into profile text so embedding anchors to their vocabulary. "Loved: Stardew Valley" → "Similar to games tagged: Farming Sim, Relaxing, RPG, ..."

2. **Loved game embedding blend** (`283a24f`) — 65% profile vector + 35% average of loved game vectors. Stardew Valley jumped from #9 → #1.

3. **Difficulty semantic expansion** (`6d434c5`) — "easy" → "casual easy relaxing accessible beginner-friendly low stakes cozy chill" before embedding. Raw enum value had near-zero semantic weight.

4. **Session length + story expansion** (`1b27dee`) — Same treatment: "long" → "long sessions immersive deep extended playtime epic adventure hours"; "core" → "story-driven narrative rich deep lore character development cinematic plot-driven".

5. **Review score hard filter** (`07a010e`) — Skip games with review_score < 75. Removes floaters like Only Up (73%) that score high via generic embeddings.

6. **Adult content hard filter** (`07a010e`) — Skip games tagged Sexual Content / NSFW / Adult Only Content / Hentai / Nudity. Removes Changed and similar from all profiles.

**Results after fixes (profile: RPG+adventure, Stardew loved, easy, story=core, long):**
```
1. Stardew Valley       83.6  ✅
2. Hero's Adventure     63.5  ✅ (RPG/adventure)
3. Sun Haven            62.7  ✅ (Farming Sim + RPG)
4. My Time at Portia    62.0  ✅ (Farming Sim + RPG + cozy)
(Only Up and Changed no longer appear)
```

---

## Contact

Email: tobias.l.ulmer@gmail.com

*Last updated: 2026-05-03 — algorithm tuning round 1 complete, continuing feedback loop*
