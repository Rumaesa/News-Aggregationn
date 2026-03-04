# PulseWire — News Aggregator + Sentiment Analysis

A full-stack app: FastAPI backend fetching live news from NewsAPI, with VADER sentiment analysis, served to an interactive HTML dashboard.

---

## 📁 Project Structure

```
pulsewire/
├── backend/
│   ├── main.py            # FastAPI app — all routes + sentiment logic
│   ├── requirements.txt   # Python dependencies
│   └── .env.example       # Copy to .env and add your API key
└── frontend/
    └── index.html         # Dashboard — open in browser or serve statically
```

---

## 🚀 Quick Start

### 1. Get a free NewsAPI key
Sign up at https://newsapi.org/register — it's free for development (100 req/day).

### 2. Set up the backend

```bash
cd backend

# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and replace YOUR_NEWSAPI_KEY_HERE with your actual key
```

### 3. Run the backend

```bash
uvicorn main:app --reload --port 8000
```

The API is now live at http://localhost:8000

Test it: http://localhost:8000/news?source=all

### 4. Open the frontend

Just open `frontend/index.html` in your browser.

- Set **Backend URL** to `http://localhost:8000`
- The dashboard fetches live news and analyzes sentiment automatically
- Auto-refreshes every 5 minutes

---

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /news?source=all&page_size=20` | Top headlines with sentiment |
| `GET /news/search?q=AI&page_size=20` | Search all news |
| `GET /sentiment/trend` | 12h hourly sentiment breakdown |
| `GET /` | Health check |

**Source options:** `all`, `reuters`, `bbc`, `bloomberg`, `techcrunch`

---

## 🧠 How Sentiment Works

Uses **VADER** (Valence Aware Dictionary and sEntiment Reasoner):
- Analyzes article title + description combined
- Returns a **compound score** from −1.0 (very negative) to +1.0 (very positive)
- Thresholds: `≥ 0.05` = Positive, `≤ -0.05` = Negative, else Neutral

To use **Claude API** for more nuanced sentiment instead, swap the `analyze()` function in `main.py` with a call to `anthropic.messages.create()`.

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NEWS_API_KEY` | — | Required. Set in `.env` |
| `source` query param | `all` | Filter by news source |
| `page_size` | 20 | Number of articles (max 50 on free tier) |

---

## 🔧 Upgrading Ideas

- **Swap VADER for Claude API** — richer, context-aware sentiment
- **Add a database** (SQLite/PostgreSQL) to store articles and trend history
- **Schedule background fetches** with APScheduler or Celery
- **Deploy** backend to Railway/Render, frontend to Vercel/Netlify
- **Add email alerts** when negative sentiment exceeds a threshold
