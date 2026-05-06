"""
News Sentiment Engine — v2
============================
Changes vs v1:
  - get_asset_sentiment now accepts stock_name + sector_keywords as optional args
    (auto-inferred from ticker if not passed, so app.py calls without those args still work)
  - Default limit raised from 4 → 8
  - Connection Score (0–100) added per article
  - All articles permanently archived to news_archive.json (dedup by URL)
  - get_all_portfolio_sentiment() fetches news for EVERY stock in holdings.json
"""

import re
import json
import os
from datetime import datetime

import yfinance as yf

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Always write next to this file, regardless of the process CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
NEWS_ARCHIVE_FILE = os.path.join(_HERE, "news_archive.json")

POSITIVE_WORDS = {
    "surge", "surges", "gain", "gains", "profit", "profits", "growth", "jump", "jumps",
    "record", "bull", "bullish", "upgrade", "upgrades", "outperform", "beat", "beats",
    "higher", "positive", "strong", "dividend", "breakout", "soar", "soars", "rally", "rallies"
}

NEGATIVE_WORDS = {
    "drop", "drops", "fall", "falls", "loss", "losses", "decline", "declines", "plunge",
    "plunges", "crash", "bear", "bearish", "downgrade", "downgrades", "underperform",
    "miss", "misses", "lower", "negative", "weak", "selloff", "scandal", "lacklustre", "slump"
}

# Indian market context terms — used for +10 connection score bonus
INDIAN_MARKET_TERMS = {"nse", "bse", "nifty", "sensex", "dalal street", "sebi", "bombay stock", "national stock"}

# ETF fallback: if the ETF ticker returns 0 articles, search Yahoo Finance
# using these alternative tickers that have better news coverage.
# Key   = identifier as stored in holdings.json (lowercase comparison)
# Value = fallback ticker OR search term that yfinance accepts
ETF_FALLBACK_MAP = {
    "silverbees.ns": "SILVX",          # Silver price proxy
    "mon100.ns":     "QQQ",            # Nasdaq 100 ETF (US-listed, good news volume)
    "nxst.ns":       "NXST",           # Nexus Select Trust fallback
}

# Built-in sector keyword map keyed by ticker fragment (lowercase, no exchange suffix).
# Used for auto-inference when caller doesn't supply sector_keywords.
TICKER_SECTOR_MAP = {
    "tatasteel":  ["steel", "metal", "iron"],
    "recltd":     ["power", "electricity", "energy", "lending"],
    "rec":        ["power", "electricity", "energy", "lending"],
    "irctc":      ["railway", "rail", "tourism", "catering", "travel"],
    "jiofin":     ["finance", "financial", "jio", "banking", "nbfc"],
    "zomato":     ["food", "delivery", "restaurant", "quick commerce"],
    "eternal":    ["food", "delivery", "restaurant", "quick commerce"],
    "coalindia":  ["coal", "mining", "energy", "fossil"],
    "bel":        ["defence", "defense", "electronics", "bharat"],
    "silvbees":   ["silver", "metal", "commodity", "precious"],
    "goldbees":   ["gold", "commodity", "precious"],
    "niftybees":  ["index", "nifty", "etf", "fund"],
    "mofsl":      ["nasdaq", "fund", "etf", "index", "us market"],
    "motilal":    ["nasdaq", "fund", "etf", "index", "us market"],
    "nexus":      ["reit", "trust", "real estate", "mall", "retail"],
    "nxst":       ["reit", "trust", "real estate"],
}

# ──────────────────────────────────────────────────────────────────────────────
# Text helpers (unchanged from v1)
# ──────────────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[^\w\s]', '', text.lower())


def calculate_text_sentiment(text: str) -> float:
    """Returns a sentiment score between -1.0 and +1.0 via keyword matching."""
    words = clean_text(text).split()
    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
    total = pos_count + neg_count
    if total == 0:
        return 0.0
    return (pos_count - neg_count) / total


# ──────────────────────────────────────────────────────────────────────────────
# Connection Score
# ──────────────────────────────────────────────────────────────────────────────

def _infer_sector_keywords(ticker_symbol: str) -> list:
    """
    Auto-infer sector keywords from the ticker symbol using the built-in map.
    Falls back to an empty list if no match is found.
    """
    base = ticker_symbol.lower().replace(".ns", "").replace(".bo", "").replace(".bse", "")
    for key, keywords in TICKER_SECTOR_MAP.items():
        if key in base:
            return keywords
    return []


def calculate_connection_score(
    title: str,
    summary: str,
    stock_name: str,
    ticker_symbol: str,
    sector_keywords: list = None,
) -> int:
    """
    Measures how directly relevant an article is to the specific holding.

    Scoring:
      +50  title contains stock name or ticker
      +25  title contains a sector keyword
      +15  summary contains stock name or ticker
      +10  article mentions Indian market terms (NSE/BSE/Nifty/Sensex)
      Max: 100
    """
    score = 0
    title_lower = (title or "").lower()
    summary_lower = (summary or "").lower()

    # Clean ticker to bare symbol (e.g. "TATASTEEL.NS" → "tatasteel")
    ticker_clean = ticker_symbol.lower().replace(".ns", "").replace(".bo", "").replace(".bse", "")
    name_tokens = stock_name.lower().split()  # match any word in stock name

    # +50 — title contains stock name or ticker
    if ticker_clean in title_lower or any(tok in title_lower for tok in name_tokens if len(tok) > 3):
        score += 50

    # +25 — title contains a sector keyword
    kws = sector_keywords if sector_keywords else _infer_sector_keywords(ticker_symbol)
    for kw in kws:
        if kw.lower() in title_lower:
            score += 25
            break  # only award once

    # +15 — summary contains stock name or ticker
    if ticker_clean in summary_lower or any(tok in summary_lower for tok in name_tokens if len(tok) > 3):
        score += 15

    # +10 — mentions Indian market context
    combined = title_lower + " " + summary_lower
    if any(term in combined for term in INDIAN_MARKET_TERMS):
        score += 10

    return min(score, 100)


def _connection_badge(score: int) -> str:
    if score >= 75:
        return "🔴 High"
    elif score >= 40:
        return "🟡 Medium"
    else:
        return "⚪ Low"


# ──────────────────────────────────────────────────────────────────────────────
# News Archive (persistent disk storage)
# ──────────────────────────────────────────────────────────────────────────────

def _load_archive() -> dict:
    """Load news_archive.json from disk. Returns {} on missing/corrupt file."""
    if not os.path.exists(NEWS_ARCHIVE_FILE):
        return {}
    with open(NEWS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def _save_archive(archive: dict) -> None:
    """
    Atomically persist the news archive to disk.
    Writes to a .tmp file first, then os.replace() so the real file is never
    left truncated if the process is interrupted mid-write.
    """
    tmp = NEWS_ARCHIVE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)
    os.replace(tmp, NEWS_ARCHIVE_FILE)


def get_archived_articles() -> dict:
    """Public helper — returns the full archive dict {ticker: [articles]}."""
    return _load_archive()


def _append_to_archive(ticker_symbol: str, article_record: dict) -> None:
    """
    Append article_record to the archive under ticker_symbol.
    Deduplication key:
      - URL when non-blank (primary key)
      - title + date[:10] when URL is blank (fallback — prevents Coal India
        'Basic Materials Roundup' type articles from duplicating every fetch)
    """
    archive = _load_archive()
    if ticker_symbol not in archive:
        archive[ticker_symbol] = []

    url = article_record.get("url", "").strip()

    if url:
        # Primary dedup: URL
        existing_urls = {a.get("url", "").strip() for a in archive[ticker_symbol]}
        if url in existing_urls:
            return  # Already stored — skip
    else:
        # Fallback dedup: title + date (first 10 chars)
        def _title_date_key(a):
            return (a.get("title", "").strip(), str(a.get("date", ""))[:10])

        this_key = (article_record.get("title", "").strip(),
                    str(article_record.get("date", ""))[:10])
        existing_keys = {_title_date_key(a) for a in archive[ticker_symbol]}
        if this_key in existing_keys:
            return  # Same headline + same date — skip

    archive[ticker_symbol].append(article_record)
    _save_archive(archive)


# ──────────────────────────────────────────────────────────────────────────────
# Core sentiment fetch — called per ticker
# ──────────────────────────────────────────────────────────────────────────────

def get_asset_sentiment(
    ticker_symbol: str,
    stock_name: str = "",
    sector_keywords: list = None,
    limit: int = 8,
) -> dict:
    """
    Fetch and grade up to `limit` news articles for `ticker_symbol`.

    Parameters
    ----------
    ticker_symbol    : Yahoo Finance ticker (e.g. "TATASTEEL.NS")
    stock_name       : Human-readable name — used in connection score matching.
                       Auto-inferred from ticker if empty.
    sector_keywords  : Optional list of sector words for connection scoring.
                       Auto-inferred from TICKER_SECTOR_MAP if None.
    limit            : Max articles to process. Default 8.

    Returns
    -------
    dict with keys:
      score         : float — average sentiment score (-1.0 to +1.0)
      status        : str  — "Bullish" | "Bearish" | "Neutral"
      articles      : list of article dicts
      error         : str (only present on failure)
    """
    # Infer stock_name from ticker if not provided
    if not stock_name:
        stock_name = ticker_symbol.replace(".NS", "").replace(".BO", "")

    # Auto-infer sector keywords if not provided
    if sector_keywords is None:
        sector_keywords = _infer_sector_keywords(ticker_symbol)

    try:
        ticker = yf.Ticker(ticker_symbol)
        # yfinance can return None instead of [] on some tickers — guard against it
        news_items = ticker.news or []

        # ── ETF fallback: if 0 articles returned, try the fallback ticker ─────
        if not news_items:
            fallback_ticker = ETF_FALLBACK_MAP.get(ticker_symbol.lower())
            if fallback_ticker:
                try:
                    fallback_items = yf.Ticker(fallback_ticker).news or []
                    if fallback_items:
                        news_items = fallback_items
                except Exception:
                    pass  # fallback failed too — continue with empty list

        if not news_items:
            return {"score": 0.0, "status": "Neutral", "articles": []}

        articles = []
        total_score = 0.0
        today_str = datetime.now().strftime("%Y-%m-%d")

        for item in news_items[:limit]:
            if not item or not isinstance(item, dict):
                continue
            # Handle both old and new yfinance news dict formats.
            # Use 'or item' so that if "content" key exists but is None,
            # we fall back to the item dict itself instead of crashing.
            content = item.get("content") or item
            if not isinstance(content, dict):
                continue

            title   = content.get("title", "") or ""
            summary = content.get("summary", "") or ""
            link    = (
                (content.get("clickThroughUrl") or {}).get("url", "")
                or content.get("link", "")
                or ""
            )
            pub_date = (
                content.get("pubDate", "")
                or content.get("providerPublishTime", "")
                or ""
            )
            provider = (
                (content.get("provider") or {}).get("displayName", "Unknown")
                or content.get("publisher", "Unknown")
                or "Unknown"
            )

            # ── Sentiment grading (unchanged from v1) ─────────────────────────
            title_score   = calculate_text_sentiment(title)
            summary_score = calculate_text_sentiment(summary)
            article_score = (title_score * 2.0 + summary_score) / 3.0

            if article_score > 0.2:
                sentiment_label = "🟢 Positive"
            elif article_score < -0.2:
                sentiment_label = "🔴 Negative"
            else:
                sentiment_label = "⚪ Neutral"

            # ── Connection Score (new) ─────────────────────────────────────────
            conn_score = calculate_connection_score(
                title, summary, stock_name, ticker_symbol, sector_keywords
            )
            conn_badge = _connection_badge(conn_score)

            article_dict = {
                "title":            title,
                "summary":          summary,
                "link":             link,
                "provider":         provider,
                "date":             pub_date,
                "score":            article_score,
                "sentiment_label":  sentiment_label,
                "connection_score": conn_score,
                "connection_badge": conn_badge,
            }
            articles.append(article_dict)
            total_score += article_score

            # ── Persist to archive ─────────────────────────────────────────────
            archive_record = {
                "date":             today_str,
                "title":            title,
                "summary":          summary,
                "url":              link,
                "sentiment_score":  round(article_score, 4),
                "sentiment_label":  sentiment_label,
                "connection_score": conn_score,
            }
            try:
                _append_to_archive(ticker_symbol, archive_record)
            except Exception:
                pass  # Archive failure must never crash live sentiment display

        avg_score = total_score / len(articles) if articles else 0.0

        if avg_score > 0.15:
            overall = "Bullish"
        elif avg_score < -0.15:
            overall = "Bearish"
        else:
            overall = "Neutral"

        return {
            "score":    avg_score,
            "status":   overall,
            "articles": articles,
        }

    except Exception as e:
        return {"score": 0.0, "status": "Error", "articles": [], "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Batch function — ALL stocks in portfolio
# ──────────────────────────────────────────────────────────────────────────────

def get_all_portfolio_sentiment(holdings_file: str = "holdings.json") -> dict:
    """
    Reads every holding from holdings_file and fetches sentiment for each one.

    This is the "cover all stocks" function — it is not limited to top 5 or any
    fixed count. If the user adds or removes a stock, the next call automatically
    covers the updated list.

    Returns
    -------
    dict keyed by ticker symbol:
    {
      "TATASTEEL.NS": { score, status, articles },
      "IRCTC.NS":     { ... },
      ...
    }

    All articles are saved to news_archive.json as a side effect.
    """
    try:
        from risk_analyzer import load_holdings
        holdings = load_holdings(holdings_file)
    except Exception:
        return {}

    results = {}
    for holding in holdings:
        identifier = getattr(holding, "identifier", None)
        name = getattr(holding, "name", "")
        if not identifier:
            continue
        results[identifier] = get_asset_sentiment(
            ticker_symbol=identifier,
            stock_name=name,
            limit=8,
        )
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Archive reader — for history display
# ──────────────────────────────────────────────────────────────────────────────

def get_archived_articles(ticker_symbol: str = None) -> dict:
    """
    Return archived articles from disk.

    If ticker_symbol is provided → returns list of articles for that ticker.
    If ticker_symbol is None     → returns the full archive dict.
    """
    archive = _load_archive()
    if ticker_symbol is not None:
        return archive.get(ticker_symbol, [])
    return archive
