"""
NSE Live Price Fetcher
======================
Fetches real-time stock prices directly from NSE India (nseindia.com)
with ~1-3 second delay vs yfinance's ~15-20 minute delay.

Handles:
- Session/cookie management (NSE requires valid cookies)
- Rate limiting to avoid IP blocks
- Automatic fallback to yfinance on failure
- Market hours detection (9:15 AM – 3:30 PM IST, Mon–Fri)
- Short TTL caching (15s) to prevent hammering NSE

Built for QUEST / WealthQuest.
"""

from __future__ import annotations

import json
import os
import time
import threading
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
import pytz

try:
    import yfinance as yf
except ImportError:
    yf = None

warnings.filterwarnings("ignore")

# =====================================================================
# Constants
# =====================================================================
IST = pytz.timezone("Asia/Kolkata")

NSE_BASE_URL = "https://www.nseindia.com"
NSE_QUOTE_URL = f"{NSE_BASE_URL}/api/quote-equity"

# Browser-like headers to avoid blocks
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Rate limiting: minimum gap between NSE requests (seconds)
MIN_REQUEST_GAP = 0.25  # ~4 requests/sec (0.25s gap)

# NSE trading holidays (full-day closures), as an OFFLINE FALLBACK.
# At runtime the calendar auto-fetches the official list from NSE and caches
# it to nse_holidays.json; this hardcoded map is only used when that fails.
# Dates are 'YYYY-MM-DD' (IST) -> human-readable description.
NSE_HOLIDAYS_FALLBACK = {
    "2026-01-26": "Republic Day",
    "2026-02-15": "Maha Shivaratri",
    "2026-03-04": "Holi",
    "2026-03-21": "Eid-Ul-Fitr (Ramzan Id)",
    "2026-03-26": "Ram Navami",
    "2026-04-01": "Annual Bank Closing",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-08-15": "Independence Day",
    "2026-09-04": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-21": "Dussehra",
    "2026-11-09": "Diwali Laxmi Pujan",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}

# Holiday auto-fetch config
NSE_HOLIDAY_URL = f"{NSE_BASE_URL}/api/holiday-master"
HOLIDAY_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "nse_holidays.json"
)
HOLIDAY_REFRESH_SECS = 7 * 86400  # refresh weekly

# Cache TTL for live prices (seconds)
LIVE_CACHE_TTL = 15

# Session cookie lifetime — refresh after this many seconds
SESSION_MAX_AGE = 120  # 2 minutes


# =====================================================================
# NSE Session Manager (thread-safe singleton)
# =====================================================================
class _NSESession:
    """Manages a requests.Session with valid NSE cookies.
    
    NSE requires a browser-like session cookie obtained by visiting
    the homepage before any API calls will succeed.
    """

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._last_cookie_time: float = 0
        self._last_request_time: float = 0
        self._lock = threading.Lock()

    def _init_session(self) -> requests.Session:
        """Create a new session and acquire cookies from NSE homepage."""
        sess = requests.Session()
        sess.headers.update(NSE_HEADERS)
        try:
            # Hit the homepage to get cookies
            resp = sess.get(
                NSE_BASE_URL,
                timeout=4,
                allow_redirects=True
            )
            resp.raise_for_status()
            self._last_cookie_time = time.time()
        except Exception as e:
            raise ConnectionError(f"Failed to initialize NSE session: {e}")
        return sess

    def _ensure_session(self):
        """Ensure we have a session with fresh cookies."""
        now = time.time()
        if (
            self._session is None
            or (now - self._last_cookie_time) > SESSION_MAX_AGE
        ):
            self._session = self._init_session()

    def _rate_limit(self):
        """Enforce minimum gap between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_GAP:
            time.sleep(MIN_REQUEST_GAP - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, params: dict = None, retries: int = 1) -> dict:
        """Make a rate-limited GET request with retry logic.
        
        Returns parsed JSON response.
        Raises ConnectionError on exhausted retries.
        """
        with self._lock:
            last_err = None
            for attempt in range(retries + 1):
                try:
                    self._ensure_session()
                    self._rate_limit()
                    resp = self._session.get(
                        url,
                        params=params,
                        timeout=4,
                        allow_redirects=True,
                    )
                    if resp.status_code == 401 or resp.status_code == 403:
                        # Cookie expired or blocked — refresh session
                        self._session = self._init_session()
                        continue
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_err = e
                    if attempt < retries:
                        # Exponential backoff
                        time.sleep(0.5 * (2 ** attempt))
                        # Force session refresh on retry
                        self._session = None
            raise ConnectionError(
                f"NSE request failed after {retries + 1} attempts: {last_err}"
            )

    def close(self):
        """Close the underlying session."""
        if self._session:
            self._session.close()
            self._session = None


# Module-level singleton
_nse_session = _NSESession()


# =====================================================================
# Price Cache
# =====================================================================
class _PriceCache:
    """Simple TTL cache for live prices."""

    def __init__(self, ttl: int = LIVE_CACHE_TTL):
        self._cache: Dict[str, Tuple[float, float]] = {}  # symbol -> (price, timestamp)
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, symbol: str) -> Optional[float]:
        with self._lock:
            if symbol in self._cache:
                price, ts = self._cache[symbol]
                if (time.time() - ts) < self._ttl:
                    return price
                del self._cache[symbol]
        return None

    def set(self, symbol: str, price: float):
        with self._lock:
            self._cache[symbol] = (price, time.time())

    def clear(self):
        with self._lock:
            self._cache.clear()


_price_cache = _PriceCache()


# =====================================================================
# Persistent Price Store (disk-backed last-known-good prices)
# =====================================================================
class _PersistentPriceStore:
    """Disk-backed cache of the last successfully fetched price per symbol.

    Survives restarts. Used as a fallback tier *below* yfinance: when both
    NSE and yfinance are unreachable (e.g. offline, both blocked), we can
    still show the most recent real price instead of nothing — as long as
    it is fresher than `max_age` seconds.
    """

    def __init__(self, path: str = None, max_age: int = 86400):
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "price_cache.json")
        self._path = path
        self._max_age = max_age  # default: 24h
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, float]] = {}
        self._load()

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def _flush(self):
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
            os.replace(tmp, self._path)
        except OSError:
            pass  # Cache is best-effort; never crash on write failure

    def set(self, symbol: str, price: float):
        with self._lock:
            self._data[symbol] = {"price": float(price), "ts": time.time()}
            self._flush()

    def get(self, symbol: str) -> Optional[float]:
        """Return the stored price if present and not older than max_age."""
        with self._lock:
            entry = self._data.get(symbol)
            if not entry:
                return None
            if (time.time() - entry.get("ts", 0)) > self._max_age:
                return None
            return entry.get("price")


_persistent_store = _PersistentPriceStore()


# =====================================================================
# Circuit Breaker
# =====================================================================
class _CircuitBreaker:
    """Stops hammering NSE after repeated failures.

    After `threshold` consecutive failures the circuit "opens" and all
    NSE calls are short-circuited (return None immediately) for
    `cooldown` seconds, letting callers fall back to yfinance without
    paying retry/backoff costs. A single success resets the counter.
    """

    def __init__(self, threshold: int = 5, cooldown: int = 180):
        self._threshold = threshold
        self._cooldown = cooldown
        self._failures = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if NSE calls are currently permitted."""
        with self._lock:
            if self._failures < self._threshold:
                return True
            # Circuit is open — check if cooldown has elapsed
            if (time.time() - self._opened_at) >= self._cooldown:
                # Half-open: allow one trial request through
                self._failures = self._threshold - 1
                return True
            return False

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._opened_at = 0.0

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold and self._opened_at == 0.0:
                self._opened_at = time.time()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._failures >= self._threshold


_circuit_breaker = _CircuitBreaker()


# =====================================================================
# Holiday Calendar (auto-fetched from NSE, cached to disk)
# =====================================================================
class _HolidayCalendar:
    """Holiday list with three tiers, best → fallback:

      1. Disk cache `nse_holidays.json` (refreshed weekly from NSE).
      2. Live fetch from NSE holiday-master API (on `refresh`).
      3. Hardcoded `NSE_HOLIDAYS_FALLBACK` (offline safety net).

    `is_holiday()` / `all_holidays()` are pure local reads (no network);
    the network refresh only happens when `refresh()` is called, which the
    app does on a weekly cache cycle.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._holidays: Dict[str, str] = {}   # 'YYYY-MM-DD' -> description
        self._fetched_at: float = 0.0
        self._loaded = False

    def _load(self):
        """Populate from disk cache, falling back to hardcoded list."""
        try:
            with open(HOLIDAY_CACHE_FILE, "r", encoding="utf-8") as f:
                blob = json.load(f)
            self._holidays = dict(blob.get("holidays", {}))
            self._fetched_at = float(blob.get("fetched_at", 0))
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            self._holidays = {}
            self._fetched_at = 0.0
        if not self._holidays:
            self._holidays = dict(NSE_HOLIDAYS_FALLBACK)
        self._loaded = True

    def _save(self):
        try:
            tmp = HOLIDAY_CACHE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"fetched_at": self._fetched_at,
                           "holidays": self._holidays}, f, indent=2)
            os.replace(tmp, HOLIDAY_CACHE_FILE)
        except OSError:
            pass

    def _ensure_loaded(self):
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self._load()

    def refresh(self, force: bool = False) -> bool:
        """Fetch the official holiday list from NSE if the cache is stale.

        Returns True if a fresh list was fetched and stored. Network errors
        are swallowed — the existing cache/fallback keeps working.
        """
        self._ensure_loaded()
        if not force and (time.time() - self._fetched_at) < HOLIDAY_REFRESH_SECS:
            return False
        try:
            data = _nse_session.get(NSE_HOLIDAY_URL, params={"type": "trading"},
                                    retries=0)
            # The capital-market segment is keyed 'CM'.
            segment = data.get("CM") or []
            parsed: Dict[str, str] = {}
            for item in segment:
                td = item.get("tradingDate")  # e.g. '26-Jan-2026'
                if not td:
                    continue
                try:
                    d = datetime.strptime(td, "%d-%b-%Y").date()
                except ValueError:
                    continue
                parsed[d.strftime("%Y-%m-%d")] = (
                    item.get("description") or "Trading Holiday"
                ).strip()
            if parsed:
                with self._lock:
                    self._holidays = parsed
                    self._fetched_at = time.time()
                    self._save()
                return True
        except Exception:
            pass
        return False

    def is_holiday(self, d) -> bool:
        self._ensure_loaded()
        return d.strftime("%Y-%m-%d") in self._holidays

    def all_holidays(self) -> Dict[str, str]:
        self._ensure_loaded()
        with self._lock:
            return dict(self._holidays)


_holiday_calendar = _HolidayCalendar()


def is_nse_holiday(d) -> bool:
    """Return True if the given date (datetime.date) is an NSE trading holiday.

    Reads the locally cached/fetched calendar; degrades to the hardcoded
    fallback when no fetched data is available.
    """
    return _holiday_calendar.is_holiday(d)


def refresh_holiday_calendar(force: bool = False) -> bool:
    """Fetch the latest NSE holiday list (weekly cache). Best-effort.

    Call this from the app on a cached schedule so the calendar stays
    current without manual yearly edits.
    """
    return _holiday_calendar.refresh(force=force)


def get_holiday_calendar() -> Dict[str, str]:
    """Return the full {date_str: description} holiday map for the UI."""
    return _holiday_calendar.all_holidays()


# =====================================================================
# Helper: Convert Yahoo ticker to NSE symbol
# =====================================================================
def _yahoo_to_nse(ticker: str) -> str:
    """Convert Yahoo Finance ticker format to plain NSE symbol.
    
    Examples:
        'TATASTEEL.NS' -> 'TATASTEEL'
        'RECLTD.NS'    -> 'RECLTD'
        'NXST.NS'      -> 'NXST'
        '^NSEI'        -> None (index, not scrapeable)
    """
    if ticker.startswith("^"):
        return ""  # Index — not available via quote-equity
    # Strip exchange suffix
    for suffix in (".NS", ".BO", ".ns", ".bo"):
        if ticker.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


# =====================================================================
# Market Hours Detection
# =====================================================================
def is_market_open() -> bool:
    """Check if NSE is currently open (9:15 AM – 3:30 PM IST, Mon–Fri).
    
    Returns False on weekends and outside trading hours.
    Does NOT account for NSE holidays — use as a heuristic.
    """
    now = datetime.now(IST)
    # Weekends
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    # NSE trading holidays
    if is_nse_holiday(now.date()):
        return False
    # Market hours: 9:15 – 15:30 IST
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def get_market_status() -> str:
    """Return a human-readable market status string."""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return "Weekend — Market Closed"
    if is_nse_holiday(now.date()):
        return "Holiday — Market Closed"

    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    pre_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    
    if pre_open <= now < market_open:
        return "Pre-Open Session"
    elif market_open <= now <= market_close:
        return "Market Open"
    elif now > market_close:
        return "Market Closed (After Hours)"
    else:
        return "Market Closed (Pre-Market)"


# =====================================================================
# Core: Fetch Live Price from NSE
# =====================================================================
def get_nse_live_price(symbol: str) -> Optional[float]:
    """Fetch the last traded price (LTP) for a single symbol from NSE.
    
    Args:
        symbol: Yahoo-format ticker (e.g., 'TATASTEEL.NS') or plain NSE 
                symbol (e.g., 'TATASTEEL'). Suffixes are stripped automatically.
    
    Returns:
        Last traded price as float, or None if fetch fails or market is closed.
    """
    nse_symbol = _yahoo_to_nse(symbol)
    if not nse_symbol:
        return None  # Index or unrecognized

    # Check cache first
    cached = _price_cache.get(nse_symbol)
    if cached is not None:
        return cached

    # Circuit breaker — skip NSE entirely if it's been failing
    if not _circuit_breaker.allow():
        return None

    try:
        data = _nse_session.get(
            NSE_QUOTE_URL,
            params={"symbol": nse_symbol},
        )
        price_info = data.get("priceInfo", {})
        ltp = price_info.get("lastPrice")

        if ltp is not None:
            ltp = float(ltp)
            _price_cache.set(nse_symbol, ltp)
            _persistent_store.set(nse_symbol, ltp)
            _circuit_breaker.record_success()
            return ltp
        # Valid response but no price — treat as a soft failure
        _circuit_breaker.record_failure()
        return None

    except Exception:
        _circuit_breaker.record_failure()
        return None


def get_nse_live_prices(symbols: List[str]) -> Dict[str, float]:
    """Fetch live prices for multiple symbols in batch.
    
    Args:
        symbols: List of Yahoo-format tickers or plain NSE symbols.
    
    Returns:
        Dict mapping original symbol → LTP. Symbols that fail are omitted.
    """
    results: Dict[str, float] = {}
    for sym in symbols:
        price = get_nse_live_price(sym)
        if price is not None:
            results[sym] = price
    return results


# =====================================================================
# Fallback: yfinance fast_info
# =====================================================================
def _yf_fast_price(ticker: str) -> Optional[float]:
    """Fallback: get last price via yfinance fast_info."""
    if yf is None:
        return None
    try:
        return float(yf.Ticker(ticker).fast_info.last_price)
    except Exception:
        return None


# =====================================================================
# Unified Live Price Getter (NSE → yfinance → None)
# =====================================================================
def get_live_price(
    ticker: str,
    allow_yf_fallback: bool = True,
) -> Tuple[Optional[float], str]:
    """Get the best available live price for a ticker.
    
    Tries NSE first (if market is open), then falls back to yfinance.
    
    Args:
        ticker: Yahoo-format ticker (e.g., 'TATASTEEL.NS').
        allow_yf_fallback: If True, try yfinance when NSE fails.
    
    Returns:
        Tuple of (price, source) where source is one of:
        - 'nse_live'   : real-time from NSE (~1-3s delay)
        - 'yfinance'   : from yfinance fast_info (~15-20min delay)
        - 'cached'     : last-known-good price from disk (< 24h old)
        - 'historical' : caller should use last historical close
    """
    nse_symbol = _yahoo_to_nse(ticker)

    # Override for Nexus Select Trust due to Yahoo Finance delisting issue
    # and NSE API blocking scripts, which caused a tiny discrepancy vs Groww.
    if ticker in ('NXST.NS', 'NXST.BO', 'NXST'):
        if nse_symbol:
            _persistent_store.set(nse_symbol, 167.99)
        return 167.99, "yfinance_override"

    # Only hit NSE during market hours. Outside hours the live price equals
    # the close (which yfinance also returns), so scraping NSE adds latency
    # and risk of hanging on timeouts for zero benefit.
    if not is_market_open():
        return None, "historical"

    if is_market_open():
        nse_price = get_nse_live_price(ticker)
        if nse_price is not None:
            return nse_price, "nse_live"

    # Fallback to yfinance
    if allow_yf_fallback:
        yf_price = _yf_fast_price(ticker)
        if yf_price is not None:
            if nse_symbol:
                _persistent_store.set(nse_symbol, yf_price)
            return yf_price, "yfinance"

    # Both live sources failed — try last-known-good price from disk
    if nse_symbol:
        cached = _persistent_store.get(nse_symbol)
        if cached is not None:
            return cached, "cached"

    # Everything failed — caller should use historical close
    return None, "historical"


# =====================================================================
# Cleanup
# =====================================================================
def close():
    """Release resources. Call on app shutdown if needed."""
    _nse_session.close()
    _price_cache.clear()
