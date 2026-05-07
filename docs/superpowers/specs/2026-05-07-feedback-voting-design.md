# Design: Game Feedback Voting System

**Date:** 2026-05-07  
**Status:** Approved

## Overview

Add thumbs up/down buttons to each game recommendation card. Votes are stored in Supabase and influence future recommendation scores for users with similar genre profiles (Option C: aggregated score per game + genre bucket).

---

## 1. Frontend UI

**Location:** Right side of `card-top` in each game card (`wgtp.html`)

**Buttons:** Two small icon buttons (👍 👎) as a third column in the card-top flex row

**Visual states:**
- **Thumbs up clicked:** Button highlighted green, card gets subtle green left-border accent
- **Thumbs down clicked:** Button highlighted red, card dims to ~40% opacity
- **Switching vote:** Clicking the opposite button switches state; both votes are sent to backend (they cancel out in aggregation)
- **No undo:** Can only switch direction, not remove

**API call:** `POST /api/feedback` on every vote change — fire-and-forget, no UI feedback needed

**Payload:**
```json
{ "appid": 413150, "genres": ["rpg", "adventure"], "vote": "up" }
```

---

## 2. Backend — New Endpoint

**`POST /api/feedback`** added to `backend/main.py`

**Request model** (new in `models.py`):
```python
class FeedbackRequest(BaseModel):
    appid: int
    genres: List[str]
    vote: str  # "up" or "down"
```

**Logic:**
1. Sort genres alphabetically, join with comma → genre_bucket (e.g. `"adventure,rpg"`)
2. Map vote to integer: `"up"` → `+1`, `"down"` → `-1`
3. Write row to Supabase via REST API using `httpx` sync — dispatched via FastAPI `BackgroundTasks` so the response returns immediately
4. Return `{"ok": true}`

**Environment variables** (set on Railway):
- `SUPABASE_URL` — e.g. `https://xyz.supabase.co`
- `SUPABASE_KEY` — anon/public key

No Supabase SDK — plain HTTP POST to Supabase REST API.

---

## 3. Supabase Schema

**Table: `game_feedback`**

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | auto-generated primary key |
| `appid` | integer | Steam app ID |
| `genre_bucket` | text | sorted genres joined by comma, e.g. `"adventure,rpg"` |
| `vote` | integer | `+1` or `-1` |
| `created_at` | timestamptz | auto-set by Supabase |

**Index:** on `(appid, genre_bucket)` for fast lookup during scoring.

---

## 4. Algorithm Integration

**Where:** In `/api/recommend`, after computing all scores but before final sort.

**Steps:**
1. Collect all appids of scored candidate games
2. Compute current user's genre_bucket (same logic: sorted, comma-joined)
3. Single Supabase GET query: fetch all rows where `appid IN (...)` AND `genre_bucket = <user_bucket>`
4. Aggregate per appid: `net_votes = COUNT(vote=1) - COUNT(vote=-1)`
5. Apply capped adjustment: `score += clamp(net_votes × 2, -12, +12)`

**Cap rationale:** ±12 points out of 100 — noticeable but never overrides semantic matching. Maxes out at 6 net votes in either direction.

---

## 5. Constraints & Limits

- Feedback only affects users with the **exact same genre_bucket** — no cross-genre contamination
- Max score impact: **±12 points** regardless of vote count
- No user identity stored — only appid, genre_bucket, vote, timestamp
- Votes accumulate indefinitely in Supabase (free tier: 500MB, plenty for years of votes)
- If Supabase is unreachable: feedback write fails silently, recommend endpoint falls back to zero adjustment (try/except around both calls)

---

## Files Changed

| File | Change |
|------|--------|
| `wgtp.html` | Add thumb buttons to `cardHtml()`, vote state tracking, POST to /api/feedback |
| `backend/models.py` | Add `FeedbackRequest` model |
| `backend/main.py` | Add `POST /api/feedback` endpoint; add Supabase vote lookup + score adjustment in `/api/recommend` |
| `backend/requirements.txt` | Add `httpx` |
