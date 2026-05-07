# Feedback Voting System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add thumbs up/down buttons to each game card; votes are stored in Supabase and apply a capped score adjustment (±12 pts) to future recommendations for users with the same genre profile.

**Architecture:** Frontend sends `POST /api/feedback` on every vote (fire-and-forget). Backend writes to Supabase via plain HTTP. On each `/api/recommend` call, backend fetches net votes for candidate games matching the user's genre bucket and adjusts scores before ranking.

**Tech Stack:** FastAPI + httpx (backend), Supabase REST API (storage), vanilla JS (frontend)

---

## File Map

| File | Change |
|------|--------|
| `backend/requirements.txt` | Add `httpx` |
| `backend/models.py` | Add `FeedbackRequest` model |
| `backend/main.py` | Add Supabase helpers, `POST /api/feedback`, vote adjustment in `/api/recommend` |
| `wgtp.html` | CSS for vote buttons, modify `cardHtml()`, add `voteState`, `sendFeedback()`, `attachVoteListeners()` |

---

## Task 0: Supabase Setup (Manual — do this first)

**No code to write. Complete before running any other task.**

- [ ] **Step 1: Create Supabase project**

Go to https://supabase.com → New project → note the **Project URL** and **anon public key** (Settings → API).

- [ ] **Step 2: Create the table**

In Supabase → SQL Editor → New Query, run:

```sql
CREATE TABLE game_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  appid integer NOT NULL,
  genre_bucket text NOT NULL,
  vote integer NOT NULL CHECK (vote IN (-1, 1)),
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_game_feedback_appid_bucket ON game_feedback (appid, genre_bucket);

ALTER TABLE game_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert" ON game_feedback
  FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "anon_select" ON game_feedback
  FOR SELECT TO anon USING (true);
```

- [ ] **Step 3: Add env vars to Railway**

Railway dashboard → your service → Variables → add:
- `SUPABASE_URL` = `https://<your-project-ref>.supabase.co`
- `SUPABASE_KEY` = your anon/public key

---

## Task 1: Add httpx Dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add httpx**

Open `backend/requirements.txt`. Append this line:

```
httpx
```

- [ ] **Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add httpx for Supabase REST calls"
```

---

## Task 2: Add FeedbackRequest Model

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Add model**

Open `backend/models.py`. The full file after change:

```python
from pydantic import BaseModel
from typing import List
from datetime import datetime


class QuizRequest(BaseModel):
    platforms: List[str]
    players: str
    online_preference: str
    budget: str
    genres: List[str]
    loved_games: List[str]
    disliked_games: List[str]
    session_length: str
    difficulty: str
    story_importance: str
    popularity: int


class FeedbackRequest(BaseModel):
    appid: int
    genres: List[str]
    vote: str  # "up" or "down"


class GameResult(BaseModel):
    appid: int
    name: str
    steam_url: str
    description: str
    price_eur: float
    review_score: int
    is_free: bool
    match_score: float
    is_hidden_gem: bool


class RecommendResponse(BaseModel):
    timestamp: datetime
    results: List[GameResult]
```

- [ ] **Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add FeedbackRequest model"
```

---

## Task 3: Supabase Helpers + /api/feedback Endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add imports and Supabase config at the top of main.py**

After the existing imports block (after `from sentence_transformers import SentenceTransformer`), add:

```python
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
```

- [ ] **Step 2: Add `_write_feedback` helper**

Add this function anywhere before the route definitions (e.g., after the `cosine_similarity` function):

```python
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
    except Exception:
        pass
```

- [ ] **Step 3: Add `POST /api/feedback` endpoint**

Add this route after the `/health` route:

```python
from fastapi import BackgroundTasks

@app.post("/api/feedback")
def feedback(req: FeedbackRequest, background_tasks: BackgroundTasks):
    genre_bucket = ",".join(sorted(req.genres))
    vote_int = 1 if req.vote == "up" else -1
    background_tasks.add_task(_write_feedback, req.appid, genre_bucket, vote_int)
    return {"ok": True}
```

Note: `from fastapi import BackgroundTasks` — add `BackgroundTasks` to the existing FastAPI import at the top of the file. The current import is `from fastapi import FastAPI, HTTPException` — change it to:

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
```

Also update the models import to include `FeedbackRequest`:

```python
from models import QuizRequest, RecommendResponse, GameResult, FeedbackRequest
```

- [ ] **Step 4: Test the endpoint locally**

Start the backend:
```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal, send a test vote:
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"appid": 413150, "genres": ["rpg", "adventure"], "vote": "up"}'
```

Expected response: `{"ok":true}`

If `SUPABASE_URL`/`SUPABASE_KEY` are not set locally, the write fails silently — that's correct. The endpoint still returns `{"ok":true}`.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add /api/feedback endpoint with Supabase write"
```

---

## Task 4: Vote Adjustment in /api/recommend

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add `fetch_votes` helper**

Add this function right after `_write_feedback`:

```python
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
    except Exception:
        return {}
```

- [ ] **Step 2: Apply vote adjustment in `/api/recommend`**

In the `recommend` function, find the line `# Sort by score (descending)` (currently around line 348). Insert the following block **immediately before** that line:

```python
        # Apply community feedback adjustment (capped at ±12 pts)
        if scored_games and quiz.genres:
            user_genre_bucket = ",".join(sorted(quiz.genres))
            candidate_appids = [item["game"]["appid"] for item in scored_games]
            net_votes_map = fetch_votes(candidate_appids, user_genre_bucket)
            for item in scored_games:
                net = net_votes_map.get(item["game"]["appid"], 0)
                item["score"] += max(-12, min(12, net * 2))
```

- [ ] **Step 3: Test locally**

With Supabase env vars set, manually insert a test vote via the Supabase table editor (or via `curl` to `/api/feedback`), then call `/api/recommend` with matching genres and verify the affected game's position shifts.

If Supabase is not available locally: confirm the endpoint still returns results normally (no crash), just without vote adjustment.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: apply community vote adjustment in /api/recommend"
```

---

## Task 5: Frontend — CSS for Vote Buttons

**Files:**
- Modify: `wgtp.html`

- [ ] **Step 1: Add CSS**

In `wgtp.html`, find the line:

```css
  .gems-section { margin-top: 40px; }
```

Insert the following block **immediately before** that line:

```css
  .vote-btns { display: flex; gap: 4px; flex-shrink: 0; align-self: flex-start; padding-top: 3px; }
  .vote-btn { background: none; border: 1px solid var(--border); border-radius: 4px; color: var(--text-dim); cursor: pointer; font-size: 14px; line-height: 1; padding: 5px 9px; transition: all 0.15s ease; }
  .vote-btn:hover { border-color: var(--border-strong); color: var(--text); }
  .vote-btn.up.active { border-color: rgba(194,255,61,0.4); color: var(--accent); background: var(--accent-dim); }
  .vote-btn.down.active { border-color: rgba(255,87,87,0.4); color: var(--danger); background: rgba(255,87,87,0.08); }
  .game-card.voted-down { opacity: 0.4; transition: opacity 0.2s ease; }
  .game-card.voted-up { border-left: 2px solid rgba(194,255,61,0.45); }
```

- [ ] **Step 2: Commit**

```bash
git add wgtp.html
git commit -m "style: add vote button CSS"
```

---

## Task 6: Frontend — Vote Buttons Logic

**Files:**
- Modify: `wgtp.html`

- [ ] **Step 1: Replace `cardHtml` function**

Find the existing `cardHtml` function (lines ~693–714):

```javascript
    function cardHtml(item, rank) {
      const g = item.game;
      return `<div class="game-card">
        <div class="card-top">
          <div class="card-rank">${String(rank).padStart(2, '0')}</div>
          <div class="card-main">
            <div class="card-name">${g.name}</div>
            <div class="card-badges">
              ${priceBadge(g)}
              <span class="badge ${scoreCls(g.review_score)}">${g.review_score}% ★</span>
            </div>
          </div>
        </div>
        <p class="card-desc">${g.description}</p>
        <a class="steam-link" href="${g.steam_url}?utm_source=wgtp" target="_blank" rel="noopener">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 10L10 2M10 2H4M10 2v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Auf Steam ansehen
        </a>
      </div>`;
    }
```

Replace with:

```javascript
    function cardHtml(item, rank) {
      const g = item.game;
      return `<div class="game-card" data-appid="${g.appid}">
        <div class="card-top">
          <div class="card-rank">${String(rank).padStart(2, '0')}</div>
          <div class="card-main">
            <div class="card-name">${g.name}</div>
            <div class="card-badges">
              ${priceBadge(g)}
              <span class="badge ${scoreCls(g.review_score)}">${g.review_score}% ★</span>
            </div>
          </div>
          <div class="vote-btns">
            <button class="vote-btn up" data-appid="${g.appid}" title="Passt zu mir">👍</button>
            <button class="vote-btn down" data-appid="${g.appid}" title="Passt nicht">👎</button>
          </div>
        </div>
        <p class="card-desc">${g.description}</p>
        <a class="steam-link" href="${g.steam_url}?utm_source=wgtp" target="_blank" rel="noopener">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 10L10 2M10 2H4M10 2v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Auf Steam ansehen
        </a>
      </div>`;
    }
```

- [ ] **Step 2: Add `voteState`, `sendFeedback`, `attachVoteListeners`**

Find the line immediately before `const topHtml = top.map(...)`:

```javascript
    const topHtml = top.map((item, i) => cardHtml(item, i + 1)).join('');
```

Insert the following three blocks **immediately before** that line:

```javascript
    const voteState = {};

    function sendFeedback(appid, vote) {
      const feedbackUrl = 'https://wgtp-production.up.railway.app/api/feedback';
      const genres = ans.genres || [];
      fetch(feedbackUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ appid, genres, vote }),
      }).catch(() => {});
    }

    function attachVoteListeners() {
      document.querySelectorAll('.vote-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const appid = parseInt(btn.dataset.appid);
          const direction = btn.classList.contains('up') ? 'up' : 'down';
          if (voteState[appid] === direction) return;
          voteState[appid] = direction;
          const card = document.querySelector(`.game-card[data-appid="${appid}"]`);
          const upBtn = document.querySelector(`.vote-btn.up[data-appid="${appid}"]`);
          const downBtn = document.querySelector(`.vote-btn.down[data-appid="${appid}"]`);
          card.classList.remove('voted-up', 'voted-down');
          upBtn.classList.remove('active');
          downBtn.classList.remove('active');
          if (direction === 'up') {
            card.classList.add('voted-up');
            upBtn.classList.add('active');
          } else {
            card.classList.add('voted-down');
            downBtn.classList.add('active');
          }
          sendFeedback(appid, direction);
        });
      });
    }
```

- [ ] **Step 3: Call `attachVoteListeners()` after DOM injection**

Find:

```javascript
    document.getElementById('restart').addEventListener('click', () => {
      state.current = 0; state.answers = {}; render();
    });
```

Add `attachVoteListeners();` on the line **immediately before** that:

```javascript
    attachVoteListeners();
    document.getElementById('restart').addEventListener('click', () => {
      state.current = 0; state.answers = {}; render();
    });
```

- [ ] **Step 4: Open wgtp.html in a browser and test manually**

1. Open `wgtp.html` directly in browser (or via local server)
2. Complete the quiz
3. Verify thumbs buttons appear on every card (right side of card header)
4. Click 👍 on a card → card gets green left border, 👍 button turns green
5. Click 👎 on a different card → card dims to ~40% opacity, 👎 button turns red
6. Click 👍 on a card that already has 👎 → state switches, dimming removed, green border applied
7. Open browser DevTools → Network tab → verify `POST /api/feedback` is sent on each vote

- [ ] **Step 5: Commit**

```bash
git add wgtp.html
git commit -m "feat: add thumbs up/down voting to game cards"
```

---

## Task 7: Deploy + End-to-End Test

- [ ] **Step 1: Push to Railway**

Railway auto-deploys on push to main. Push:

```bash
git push
```

Wait for Railway to finish deploying (check Railway dashboard).

- [ ] **Step 2: Verify /api/feedback on production**

```bash
curl -X POST https://wgtp-production.up.railway.app/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"appid": 413150, "genres": ["rpg", "adventure"], "vote": "down"}'
```

Expected: `{"ok":true}`

- [ ] **Step 3: Verify vote written to Supabase**

Supabase dashboard → Table Editor → `game_feedback` → should contain one row with `appid=413150, genre_bucket="adventure,rpg", vote=-1`.

- [ ] **Step 4: Verify vote influences recommendations**

In Supabase SQL Editor, manually insert 5 downvotes for a specific game + genre_bucket:

```sql
INSERT INTO game_feedback (appid, genre_bucket, vote) VALUES
  (413150, 'adventure,rpg', -1),
  (413150, 'adventure,rpg', -1),
  (413150, 'adventure,rpg', -1),
  (413150, 'adventure,rpg', -1),
  (413150, 'adventure,rpg', -1);
```

Then call `/api/recommend` with `genres: ["rpg", "adventure"]` and verify Stardew Valley (appid 413150) ranks lower than without these votes (score should be -10 pts).

```bash
curl -X POST https://wgtp-production.up.railway.app/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "platforms": ["pc"], "players": "solo", "online_preference": "offline",
    "budget": "any", "genres": ["rpg", "adventure"],
    "loved_games": [], "disliked_games": [],
    "session_length": "long", "difficulty": "medium",
    "story_importance": "core", "popularity": 5
  }'
```

Note Stardew Valley's position. Then delete those test votes:

```sql
DELETE FROM game_feedback WHERE appid = 413150 AND genre_bucket = 'adventure,rpg';
```

Call again and confirm Stardew Valley returns to its original rank.

- [ ] **Step 5: Commit (if any final fixes made)**

```bash
git add -A
git commit -m "fix: <describe any fixes>"
```
