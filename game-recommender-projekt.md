# What Game to Play – AI Game Recommender
## Projektplan & Implementierungs-Roadmap

---

## 📋 Projekt-Übersicht

### Vision
Eine Website, auf der Nutzer ein Quiz beantworten und basierend auf ihren Antworten eine KI-generierte Liste mit personalisierten Spielempfehlungen erhalten – inklusive bekannter Top-Games und Hidden Gems.

### Zielgruppe
Menschen, die gelangweilt sind und neue Games suchen, aber nicht wissen welche.

### Kernprobleme gelöst
- ❌ „Es gibt zu viele Games, ich weiß nicht was ich spielen soll"
- ❌ „Ich kenne nur die großen Titel, vermisse aber coole Indie Games"
- ❌ Empfehlungs-Algorithmen sind zu einfach (nur Genre-Matching)

### Unique Selling Point
AI identifiziert **Hidden Gems** und erklärt **WHY** jedes Spiel passt – nicht nur algorithmic Matching.

---

## 💰 Monetarisierungs-Strategie

| Einnahmequelle | Potential | Priorität |
|---|---|---|
| **Affiliate Links** (Steam/Epic) | €400-800/Mo | HIGH |
| **Freemium Pro Plan** (€2.99-4.99/Mo, no ads) | €150-500/Mo | HIGH |
| **Indie Game Developer Sponsorships** | €500-2.000/Mo | MEDIUM |
| **Newsletter Sponsorships** (mit 5k+ Subscribers) | €200-500/Mo | MEDIUM |
| **Ad Networks** (Google AdSense) | €200-400/Mo | LOW |

**Realistic Target nach 12 Monaten: €1.250-2.800/Mo**

---

## 🏗️ Technische Architektur

### Tech Stack
```
Frontend: React/Vue + Tailwind CSS (Quiz UI)
Backend: Node.js/Python (Next.js oder FastAPI)
Database: SQLite/PostgreSQL (Game Data)
Vector DB: Supabase Vector oder Pinecone (Embeddings)
LLM: Claude API (Recommendations)
Hosting: Vercel/Railway (Frontend) + Render/Railway (Backend)
```

### Data Flow
```
1. User füllt Quiz aus
2. Quiz-Antworten → User Profil JSON
3. User Profil → Vector Embedding (via OpenAI/Claude API)
4. Vector Search → Top 50 ähnliche Games finden
5. Top 50 + User Profil → Claude API Prompt
6. Claude → 10-15 personalisierte Recommendations mit Explanations
7. Display + Affiliate Links + Feedback Collection
```

---

## 📊 Daten-Quellen

### Phase 1: Game Database

**Option (EMPFOHLEN): Kaggle Dataset + SteamSpy Hybrid**
- Kaggle Dataset (Januar 2025): 150k+ Steam Games mit Metadata
- SteamSpy API: Tags, Player Statistics, bessere Bewertungen
- Kombination: Beide sources mergen → vollständige Game DB

**Implementation:**
```python
# 1. Kaggle Dataset runterladen
kaggle datasets download -d fronkongames/steam-games-dataset

# 2. SteamSpy API für erweiterte Daten
# Loop durch alle AppIDs, fetch von https://steamspy.com/api.php
# Rate Limit: ~1 request/sec (großzügig)

# 3. Merge in SQLite
# CREATE TABLE games (
#   appid INTEGER PRIMARY KEY,
#   name TEXT,
#   description TEXT,
#   price REAL,
#   release_date TEXT,
#   genres TEXT (JSON),
#   tags TEXT (JSON),
#   rating FLOAT,
#   player_count TEXT,
#   embedding BLOB (1536 dims)
# )
```

**Struktur eines Game-Objekts:**
```json
{
  "appid": 570,
  "name": "Dota 2",
  "description": "Defend the ancient...",
  "price": 0,
  "release_date": "2013-07-09",
  "genres": ["Action", "Strategy"],
  "tags": ["MOBA", "Competitive", "Multiplayer", "Team-based"],
  "rating": 8.5,
  "player_count_estimate": "500k-1M",
  "platforms": ["Windows", "Mac", "Linux"],
  "embedding": [0.234, 0.512, ..., 0.891]
}
```

---

## 🎯 Quiz & User Profiling

### Quiz Design (8-10 Fragen)

```
Q1: "Welche Genres magst du?" (Multi-select)
    → Tags: Indie, Action, Puzzle, RPG, Strategy, etc.

Q2: "Solo oder Multiplayer?"
    → Preference: Solo / Multiplayer / Doesn't Matter

Q3: "Competitive oder Chill/Relaxed?"
    → Slider: 0 (Chill) --- 10 (Competitive)

Q4: "Wie viel Zeit pro Woche?"
    → Options: <2h, 2-5h, 5-10h, 10+ h

Q5: "Welche Games hast du GELIEBT?" (Free Text)
    → Input: "Stardew Valley, Celeste, Hades"
    → Diese Games für Context nutzen

Q6: "Was langweilt dich?"
    → Tags: Grinding, Microtransactions, Competitive, etc.

Q7: "Single-Player Story oder Open World?"
    → Radio: Story-driven / Open World / Doesn't Matter

Q8: "Grafik-Style Preference?"
    → Options: Pixel Art, 3D AAA, Stylized, Realistic

Q9: (Optional) "Budget?"
    → Slider: Free to Play --- 60€+

Q10: (Optional) "Spoiler Tolerance?"
    → Radio: Spoil me, casual story, story is key
```

### User Profile Output

```json
{
  "session_id": "uuid",
  "timestamp": "2025-04-28T10:30:00Z",
  "quiz_answers": {
    "genres": ["Indie", "Puzzle", "Adventure"],
    "playstyle": "Solo",
    "competitive_level": 2,
    "hours_per_week": "2-5h",
    "loved_games": ["Stardew Valley", "Celeste"],
    "avoid_tags": ["Grinding", "Multiplayer-mandatory"],
    "story_preference": "Story-driven",
    "graphics": "Pixel Art",
    "budget": 30,
    "story_spoilers": "casual"
  },
  "user_embedding": [0.145, 0.892, ..., 0.421],
  "user_profile_text": "Chill Indie Puzzle Lover. Loves story-driven experiences and pixel art games. Plays 2-5 hours per week solo. Avoids grindy/competitive games."
}
```

---

## 🧠 AI Recommendation Engine

### Step 1: Vector Similarity Search

```python
# Generiere User-Embedding aus Quiz Answers
user_embedding = generate_embedding(user_profile_text)

# Finde Top 50-100 Games mit ähnlichsten Embeddings
similar_games = vector_db.search(user_embedding, top_k=100)

# Filter: Entferne Games mit Tags die User haßt
filtered_games = [g for g in similar_games 
                  if not any(tag in user_avoid_tags for tag in g.tags)]

# Top 50 behalten
top_50_candidates = filtered_games[:50]
```

### Step 2: Claude Ranking & Explanation

```python
# Baue Prompt für Claude
prompt = f"""
USER PROFILE:
{json.dumps(user_profile, indent=2)}

CANDIDATE GAMES (Top 50 matches):
{format_games_for_prompt(top_50_candidates)}

TASK:
1. Select the 10-12 BEST matches for this user
2. Include 2-3 HIDDEN GEMS (lesser-known games the algorithm might miss)
3. For EACH game, explain WHY it matches their preferences
4. Rank by relevance (best match first)
5. Format as JSON with: game_name, steam_url, why_it_matches, is_hidden_gem

IMPORTANT: Be specific about WHY each game matches. Don't generic recommendations.
Example: "You loved Stardew Valley's relaxing pace → Spiritfarer has similar zen gameplay"
"""

response = claude.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)

recommendations = parse_json_from_response(response.content)
```

### Step 3: Enhance with Steam Data

```python
# Für jedes empfohlenes Game:
# 1. Hole Steam Affiliate Link (SteamDB format)
# 2. Hole aktuellen Preis, Reviews, User Count
# 3. Hole Screenshots/Header Image URL

enhanced_recommendations = []
for game in recommendations:
    steam_data = fetch_steam_data(game.appid)
    game.steam_url = generate_affiliate_link(game.appid)
    game.current_price = steam_data.price
    game.positive_reviews = steam_data.positive_count
    game.header_image = steam_data.header_image
    enhanced_recommendations.append(game)
```

---

## 📈 Implementation Roadmap (4 Wochen)

### WOCHE 1: Foundation
**Ziel:** Data + UI gerüst

- [ ] Kaggle Dataset runterladen + lokal in SQLite importieren
- [ ] SteamSpy API Integration schreiben (fetch alle 150k Games)
- [ ] React Frontend scaffolding (Next.js oder Vite)
- [ ] Quiz Component bauen (8-10 Fragen, Form State Management)
- [ ] Basic Styling (Tailwind)

**Deliverable:** Nutzer können Quiz beantworten, Antworten werden in JSON gespeichert

---

### WOCHE 2: Vector DB + Embeddings
**Ziel:** Similarity Search funktioniert

- [ ] OpenAI/Claude Embeddings API Integration
  - Text von jedem Game (name + description + tags) → Embedding (1536 dims)
  - User-Quiz Answers → User Embedding
- [ ] Supabase Vector DB Setup (oder Pinecone Alternative)
- [ ] Similarity Search Function schreiben
- [ ] Test: User antwortet Quiz → Top 50 Games finden

**Deliverable:** Backend kann Quiz-Answers in Embeddings konvertieren und ähnliche Games finden

---

### WOCHE 3: Claude Integration + Display
**Ziel:** Full End-to-End funktioniert

- [ ] Claude API Integration
  - Prompt schreiben (User Profile + Top 50 Games → Recommendations)
  - Error Handling + Retry Logic
  - Response Parsing (JSON)
- [ ] Recommendations Display UI
  - Game Cards mit: Titel, Why It Matches, Price, Steam Link
  - Hidden Gem Badge
  - Rating/Reviews anzeigen
- [ ] Steam Affiliate Links integrieren
- [ ] Feedback System (Thumbs up/down)

**Deliverable:** Vollständiger Flow: Quiz → AI Recommendations → Display mit Links

---

### WOCHE 4: Polish + Deploy
**Ziel:** Production-ready

- [ ] Performance Optimierung
  - Caching von Embeddings
  - Query Optimization
  - API Response Times < 5 seconds
- [ ] Error Handling + Edge Cases
- [ ] Mobile Responsiveness testen
- [ ] Analytics Setup
  - Tracking: Quiz starts, Recommendations clicked, Affiliate conversions
  - Heatmap: Welche Games werden geklickt
- [ ] SEO Optimization
  - Meta Tags, Open Graph
  - Structured Data (JSON-LD)
  - robots.txt + sitemap.xml
- [ ] Deploy auf Vercel (Frontend) + Render/Railway (Backend)
- [ ] Google AdSense Integration

**Deliverable:** Live Website mit Traffic

---

## 🔄 Feedback Loop & Continuous Improvement

### Woche 5+: Daten sammeln & Lernen

```python
# Speichere für jede Empfehlung:
# - Welche Games wurden empfohlen
# - Welche der User geklickt hat
# - Welche der User mit Thumbs-up rated

feedback_entry = {
    "session_id": "uuid",
    "user_profile": {...},
    "recommended_games": ["Game1", "Game2", ...],
    "clicked_games": ["Game2", "Game5"],
    "liked_games": ["Game2"],
    "disliked_games": ["Game1"],
    "timestamp": "...",
    "feedback_rating": 4.5  # 1-5 Sterne für gesamte Session
}

# Nach ~1000 Sessions: Analysiere Patterns
# - Welche User-Typen sind am zufriedensten?
# - Welche Games werden am oft empfohlen vs. geklickt?
# - Wo kann Claude besser sein?

# Optional: Fine-tune Local LLM mit echten Feedback-Daten
# (Später Phase, wenn genug Daten vorhanden)
```

---

## 🎨 UI/UX Meilensteine

### Page 1: Quiz
```
"What Game Should You Play?"
[Multiple Choice / Sliders / Text Input]
"Get Started" Button
```

### Page 2: Loading Screen
```
"Finding your perfect games..."
Spinner + Progress Message
"Analyzing your taste..." → "Searching database..." → "Getting recommendations..."
```

### Page 3: Results
```
"Based on your profile, here are 12 games for you:"

[Game Card 1]
- Title + Header Image
- "Why it matches:" [Explanation from Claude]
- Price + Reviews
- [Steam Link - Affiliate] [Wishlist] [Thumbs Up/Down]
- [Hidden Gem Badge] (if applicable)

[Game Card 2]
...

[Newsletter Signup CTA at bottom]
```

---

## 📊 Success Metrics (First 6 Months)

| Metrik | Target | Realistic |
|---|---|---|
| Monthly Visitors | 10k-50k | 10-20k |
| Quiz Completions | 20-40% of visitors | 25% |
| Click-Through to Steam | 15-25% of results shown | 20% |
| Freemium Conversion | 2-4% | 2% |
| Affiliate Revenue | €400-800/Mo | €400/Mo |
| Pro Subscriptions | 50-100 users | 50 users |
| Newsletter Signups | 500-1k | 500 |

---

## 🚀 Launch Checklist

**Before Going Live:**
- [ ] Sitemap + robots.txt
- [ ] Google Search Console
- [ ] Google Analytics 4
- [ ] Error Monitoring (Sentry)
- [ ] Performance Monitoring (Vercel Analytics)
- [ ] SSL Certificate
- [ ] Rate Limiting (API)
- [ ] Database Backup Strategy
- [ ] Mobile Tested (iOS + Android)
- [ ] All Links Tested (especially Affiliate)

**After Going Live:**
- [ ] Submit Sitemap to Google
- [ ] Create Google Ads Campaign (optional)
- [ ] Share on Reddit (r/gaming, r/IndieGaming, r/gamingsuggestions)
- [ ] Share on ProductHunt
- [ ] Outreach to Gaming Blogs
- [ ] Create Twitter/X Account + post results
- [ ] Newsletter Email #1 (welcome + how it works)

---

## 💸 Cost Breakdown (First Month)

| Item | Cost |
|---|---|
| Claude API (1000 recommendations × €0.01) | €10 |
| OpenAI Embeddings (150k games × $0.00002) | €3 |
| Supabase Vector DB (free tier) | €0 |
| Hosting (Vercel free + Render) | €0 |
| Domain (.com/de) | €12 |
| **TOTAL** | ~**€25/month** |

**After 6 Months (if 10k/Mo users):**
- Claude API Costs: €50-100/Mo
- Server Costs: €0-50/Mo (Render paid if needed)
- **Total Operational Cost: €50-150/Mo**
- **Revenue Target: €1.250-2.800/Mo**
- **Profit: €1.100-2.750/Mo** 🎉

---

## 🎯 Next Steps

1. **Repo Setup:** `git init` + GitHub
2. **Data Pipeline:** Script zum Downloaden + Mergen Kaggle + SteamSpy
3. **Frontend Scaffolding:** `npm create vite@latest` (React)
4. **Backend Setup:** Node.js + Express oder Python + FastAPI
5. **Start Week 1:** Implement Checklist abhaken

---

## 📝 Wichtige Notes

- **Rechtliches:** Steam Daten sind öffentlich, scraping ist legal. Aber respektiere Rate Limits.
- **SEO:** Fokus auf Long-tail Keywords wie "what indie game should i play", "best puzzle games 2025", "hidden gem games"
- **Differentiation:** Andere Tools geben nur Rankings. Du erklärst WHY + Hidden Gems = unique value
- **Skalierung:** Mit lokale LLM (Ollama + Mistral) kannst du Claude später ersetzen wenn Costs zu hoch werden
- **Feedback ist Gold:** Jede Session gibt dir Daten. Nach 1000 Sessions kannst du smarter werden

---

## 🎮 Go Build It!

Du hast alles was du brauchst:
- Clear Problem: People bored, don't know what games to play
- Clear Solution: AI finds personalized + hidden gem recommendations
- Clear Monetization: Affiliate + Freemium + Sponsorships
- Clear Tech: Claude API + Vector DB + React

**Estimated Timeline: 4 Wochen MVP → Launch**
**Potential Revenue: €1-3k/Mo nach 6 Monaten**

Viel Erfolg! 🚀
