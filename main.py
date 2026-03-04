"""
PulseWire — FastAPI Backend
Fetches news from NewsAPI + analyzes sentiment using VADER
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Tuple
import httpx
import os
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="PulseWire API", version="1.0.0")

# Allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # In production: restrict to your frontend domain
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Config ────────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "YOUR_NEWSAPI_KEY_HERE")
NEWS_API_BASE = "https://newsapi.org/v2"

SOURCES = {
    "bbc":         "bbc-news",
    "reuters":     "reuters",
    "bloomberg":   "bloomberg",
    "techcrunch":  "techcrunch",
    "all":         "bbc-news,reuters,bloomberg,techcrunch",
}

analyzer = SentimentIntensityAnalyzer()


# ── Models ────────────────────────────────────────────────────────────────────
class Article(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    sentiment: str          # "positive" | "negative" | "neutral"
    sentiment_score: float  # compound score −1 to +1
    confidence: float       # abs(score), 0 to 1


class SentimentStats(BaseModel):
    total: int
    positive: int
    negative: int
    neutral: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    avg_score: float


class NewsResponse(BaseModel):
    articles: List[Article]
    stats: SentimentStats
    fetched_at: str


class TrendPoint(BaseModel):
    hour: str
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    article_count: int


# ── Sentiment helper ──────────────────────────────────────────────────────────
def analyze(text: str) -> Tuple[str, float]:
    """Return (label, compound_score) for given text."""
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return label, round(compound, 4)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", summary="Health check")
def root():
    return {"status": "ok", "service": "PulseWire API"}


@app.get("/news", response_model=NewsResponse, summary="Fetch + analyze news")
async def get_news(  # type: ignore
    source: str = Query("all", description="Source key: all | bbc | reuters | bloomberg | techcrunch"),
    q: Optional[str] = Query(None, description="Optional keyword filter"),
    page_size: int = Query(20, ge=1, le=50),
):
    source_ids = SOURCES.get(source.lower(), SOURCES["all"])

    params = {
        "apiKey": NEWS_API_KEY,
        "sources": source_ids,
        "pageSize": page_size,
        "language": "en",
        "sortBy": "publishedAt",
    }
    if q:
        params["q"] = q

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{NEWS_API_BASE}/top-headlines", params=params)

    if resp.status_code == 401:
        raise HTTPException(401, "Invalid NewsAPI key. Set NEWS_API_KEY env var.")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"NewsAPI error: {resp.text}")

    raw = resp.json().get("articles", [])

    articles: List[Article] = []
    for i, item in enumerate(raw):
        title = item.get("title") or ""
        desc  = item.get("description") or ""
        text  = f"{title}. {desc}"

        label, score = analyze(text)

        pub = item.get("publishedAt", "")
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            pub_fmt = dt.strftime("%b %d, %H:%M UTC")
        except Exception:
            pub_fmt = pub

        articles.append(Article(
            id=f"art_{i}",
            title=title,
            summary=desc or "No description available.",
            source=item.get("source", {}).get("name", "Unknown"),
            url=item.get("url", "#"),
            published_at=pub_fmt,
            sentiment=label,
            sentiment_score=score,
            confidence=round(abs(score), 4),
        ))

    # Stats
    total = len(articles)
    pos = sum(1 for a in articles if a.sentiment == "positive")
    neg = sum(1 for a in articles if a.sentiment == "negative")
    neu = total - pos - neg
    avg = round(sum(a.sentiment_score for a in articles) / max(total, 1), 4)

    stats = SentimentStats(
        total=total,
        positive=pos, negative=neg, neutral=neu,
        positive_pct=round(pos / max(total, 1) * 100, 1),
        negative_pct=round(neg / max(total, 1) * 100, 1),
        neutral_pct =round(neu / max(total, 1) * 100, 1),
        avg_score=avg,
    )

    return NewsResponse(
        articles=articles,
        stats=stats,
        fetched_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


@app.get("/news/search", response_model=NewsResponse, summary="Search everything endpoint")
async def search_news(
    q: str = Query(..., description="Search query"),
    page_size: int = Query(20, ge=1, le=50),
):
    params = {
        "apiKey": NEWS_API_KEY,
        "q": q,
        "pageSize": page_size,
        "language": "en",
        "sortBy": "publishedAt",
        "from": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{NEWS_API_BASE}/everything", params=params)

    if resp.status_code == 401:
        raise HTTPException(401, "Invalid NewsAPI key.")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"NewsAPI error: {resp.text}")

    raw = resp.json().get("articles", [])
    articles = []
    for i, item in enumerate(raw):
        title = item.get("title") or ""
        desc  = item.get("description") or ""
        label, score = analyze(f"{title}. {desc}")
        pub = item.get("publishedAt","")
        try:
            pub_fmt = datetime.fromisoformat(pub.replace("Z","+00:00")).strftime("%b %d, %H:%M UTC")
        except Exception:
            pub_fmt = pub

        articles.append(Article(
            id=f"srch_{i}",
            title=title, summary=desc or "No description.",
            source=item.get("source",{}).get("name","Unknown"),
            url=item.get("url","#"),
            published_at=pub_fmt,
            sentiment=label, sentiment_score=score, confidence=round(abs(score),4),
        ))

    total=len(articles); pos=sum(1 for a in articles if a.sentiment=="positive")
    neg=sum(1 for a in articles if a.sentiment=="negative"); neu=total-pos-neg
    avg=round(sum(a.sentiment_score for a in articles)/max(total,1),4)

    return NewsResponse(
        articles=articles,
        stats=SentimentStats(total=total,positive=pos,negative=neg,neutral=neu,
            positive_pct=round(pos/max(total,1)*100,1),
            negative_pct=round(neg/max(total,1)*100,1),
            neutral_pct=round(neu/max(total,1)*100,1),avg_score=avg),
        fetched_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


@app.get("/sentiment/trend", response_model=List[TrendPoint], summary="Hourly sentiment trend (last 12h)")
async def sentiment_trend():
    """
    Fetches articles per hour for the last 12 hours and returns sentiment breakdown.
    Note: NewsAPI free tier limits historical granularity; this uses a sliding window.
    """
    params = {
        "apiKey": NEWS_API_KEY,
        "sources": SOURCES["all"],
        "pageSize": 100,
        "language": "en",
        "sortBy": "publishedAt",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{NEWS_API_BASE}/top-headlines", params=params)

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, "NewsAPI error fetching trend data")

    raw = resp.json().get("articles", [])

    # Bucket by hour
    buckets: Dict[str, list] = {}
    now = datetime.utcnow()
    for h in range(12):
        hour_key = (now - timedelta(hours=11-h)).strftime("%H:00")
        buckets[hour_key] = []

    for item in raw:
        pub = item.get("publishedAt","")
        try:
            dt = datetime.fromisoformat(pub.replace("Z","+00:00")).replace(tzinfo=None)
            hk = dt.strftime("%H:00")
            if hk in buckets:
                title = item.get("title","")
                desc = item.get("description","")
                label, score = analyze(f"{title}. {desc}")
                buckets[hk].append(label)
        except Exception:
            pass

    trend = []
    for hour_key, labels in buckets.items():
        n = len(labels) or 1
        pos = labels.count("positive")
        neg = labels.count("negative")
        neu = labels.count("neutral")
        trend.append(TrendPoint(
            hour=hour_key,
            positive_pct=round(pos/n*100,1),
            negative_pct=round(neg/n*100,1),
            neutral_pct=round(neu/n*100,1),
            article_count=len(labels),
        ))

    return trend
