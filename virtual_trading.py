"""Virtual trading account and Yahoo Finance market-data service."""

import json
import base64
import math
import os
import tempfile
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import yfinance as yf

from nse_live import IST, get_live_quote, get_market_status, is_market_open
import stock_search

STARTING_CASH = 15000.0
MONTHLY_SIP = 2000.0
DEFAULT_STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC",
    "BHARTIARTL", "LT", "TATAMOTORS", "WIPRO", "AXISBANK", "KOTAKBANK",
    "SUNPHARMA", "BAJFINANCE", "TITAN", "ASIANPAINT", "MARUTI",
]

_POPULAR_STOCKS = tuple(DEFAULT_STOCKS)
_QUOTE_CACHE_SECONDS = 60
_CHART_CACHE_SECONDS = 300
_COMPANY_NAMES = {
    "RELIANCE": "Reliance Industries Ltd",
    "TCS": "Tata Consultancy Services Ltd",
    "INFY": "Infosys Ltd",
    "HDFCBANK": "HDFC Bank Ltd",
    "ICICIBANK": "ICICI Bank Ltd",
    "SBIN": "State Bank of India",
    "ITC": "ITC Ltd",
    "BEL": "Bharat Electronics Ltd",
    "BHARTIARTL": "Bharti Airtel Ltd",
    "LT": "Larsen & Toubro Ltd",
    "TATAMOTORS": "Tata Motors Ltd",
    "WIPRO": "Wipro Ltd",
    "AXISBANK": "Axis Bank Ltd",
    "KOTAKBANK": "Kotak Mahindra Bank Ltd",
    "SUNPHARMA": "Sun Pharmaceutical Industries Ltd",
    "BAJFINANCE": "Bajaj Finance Ltd",
    "TITAN": "Titan Company Ltd",
    "ASIANPAINT": "Asian Paints Ltd",
    "MARUTI": "Maruti Suzuki India Ltd",
}


def _company_key(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


_KNOWN_INDIAN_SYMBOLS_BY_NAME = {
    _company_key(name): symbol for symbol, name in _COMPANY_NAMES.items()
}
_KNOWN_INDIAN_SYMBOLS_BY_NAME.update({
    _company_key("HDFC Bank Limited"): "HDFCBANK",
    _company_key("Infosys Limited"): "INFY",
    _company_key("Reliance Industries Limited"): "RELIANCE",
})
_COMPANY_DOMAINS = {
    "RELIANCE": "ril.com", "TCS": "tcs.com", "INFY": "infosys.com",
    "HDFCBANK": "hdfcbank.com", "ICICIBANK": "icicibank.com", "SBIN": "sbi.co.in",
    "ITC": "itcportal.com", "BEL": "bel-india.in", "BHARTIARTL": "airtel.in",
    "LT": "larsentoubro.com", "TATAMOTORS": "tatamotors.com", "WIPRO": "wipro.com",
    "AXISBANK": "axisbank.com", "KOTAKBANK": "kotak.com", "SUNPHARMA": "sunpharma.com",
    "BAJFINANCE": "bajajfinserv.in", "TITAN": "titancompany.in", "ASIANPAINT": "asianpaints.com",
    "MARUTI": "marutisuzuki.com", "IRCTC": "irctctourism.com",
    "FEDERALBNK": "federalbank.co.in", "HINDUNILVR": "hul.co.in", "TATASTEEL": "tatasteel.com",
    "NTPC": "ntpc.co.in", "POWERGRID": "powergrid.in", "ONGC": "ongcindia.com",
    "COALINDIA": "coalindia.in", "ADANIENT": "adanienterprises.com", "ADANIPORTS": "adaniports.com",
    "ZOMATO": "zomato.com", "ETERNAL": "zomato.com", "PAYTM": "paytm.com",
    "NYKAA": "nykaa.com", "DMART": "dmartindia.com", "NESTLEIND": "nestle.in",
    "BRITANNIA": "britannia.co.in", "CIPLA": "cipla.com", "DRREDDY": "drreddys.com",
    "APOLLOHOSP": "apollohospitals.com", "EICHERMOT": "eicher.in",
    "HEROMOTOCO": "heromotocorp.com", "BAJAJ-AUTO": "bajajauto.com", "M&M": "mahindra.com",
    "INDUSINDBK": "indusind.com", "BANKBARODA": "bankofbaroda.in", "PNB": "pnbindia.in",
    "CANBK": "canarabank.com", "UNIONBANK": "unionbankofindia.co.in",
    "IDFCFIRSTB": "idfcfirstbank.com", "BANDHANBNK": "bandhanbank.com",
    "YESBANK": "yesbank.in", "TECHM": "techmahindra.com", "HCLTECH": "hcltech.com",
    "LTIM": "ltimindtree.com", "PERSISTENT": "persistent.com", "COFORGE": "coforge.com",
    "MPHASIS": "mphasis.com", "TATACONSUM": "tataconsumer.com", "DABUR": "dabur.com",
    "MARICO": "marico.com", "GODREJCP": "godrejcp.com", "VBL": "varunbeverages.com",
    "DLF": "dlf.in", "LODHA": "lodhagroup.in", "GODREJPROP": "godrejproperties.com",
    "OBEROIRLTY": "oberoirealty.com", "HAL": "hal-india.co.in", "MAZDOCK": "mazagondock.in",
    "BHEL": "bhel.com", "GAIL": "gailonline.com", "IOC": "iocl.com",
    "BPCL": "bharatpetroleum.in", "HPCL": "hindustanpetroleum.com", "OIL": "oil-india.com",
    "IRFC": "irfc.co.in", "REC": "recindia.nic.in", "PFC": "pfcindia.com",
    "IREDA": "ireda.in", "RVNL": "rvnl.org", "IRCON": "ircon.org",
    "RAILTEL": "railtelindia.com", "CDSL": "cdslindia.com", "BSE": "bseindia.com",
    "MCX": "mcxindia.com", "HAVELLS": "havells.com", "POLYCAB": "polycab.com",
    "TRENT": "mytrent.com", "SUZLON": "suzlon.com", "INOXWIND": "inoxwind.com",
    "KPITTECH": "kpit.com", "TATAELXSI": "tataelxsi.com", "TATAPOWER": "tatapower.com",
    "ADANIPOWER": "adanipower.com", "JSWSTEEL": "jswsteel.in", "JSWENERGY": "jsw.in",
    "VEDL": "vedantalimited.com", "NMDC": "nmdc.co.in", "SAIL": "sail.co.in",
    "IDEA": "myvi.in", "INDUSTOWER": "industowers.com", "NXST": "nexusselecttrust.com",
}
_COMPANY_LOGO_URLS = {
    "WIPRO": "https://upload.wikimedia.org/wikipedia/commons/a/a0/Wipro_Primary_Logo_Color_RGB.svg",
    "BEL": "https://upload.wikimedia.org/wikipedia/commons/e/e8/Bel_logo.jpg",
    "ETERNAL": "https://upload.wikimedia.org/wikipedia/commons/f/fd/Zomato-logo.png",
    "INFY": "https://upload.wikimedia.org/wikipedia/commons/9/95/Infosys_logo.svg",
}


def _clean_symbol(value: str) -> str:
    return str(value or "").strip().upper().replace(" ", "")


@lru_cache(maxsize=512)
def _get_logo_url(ticker: str) -> str:
    """Resolve a current company brand logo from verified domains or metadata."""
    base_symbol = ticker.rsplit(".", 1)[0].upper().replace(" ", "")
    fixed_logo_url = _COMPANY_LOGO_URLS.get(base_symbol)
    if fixed_logo_url:
        return fixed_logo_url

    domain = _COMPANY_DOMAINS.get(base_symbol, "")
    if not domain:
        try:
            info = yf.Ticker(ticker).get_info()
            website = str(info.get("website") or "").strip()
            if website:
                parsed = urlparse(website if "://" in website else f"https://{website}")
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
        except Exception:
            pass

    if domain:
        return f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{domain}&size=128"

    return _monogram_logo(base_symbol, "#4f46e5", "#ffffff")


def _download_image_data(image_url: str) -> str:
    try:
        request = Request(image_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urlopen(request, timeout=3) as response:
            content_type = response.headers.get("Content-Type", "image/png").split(";", 1)[0]
            if content_type.startswith("image/"):
                image_data = response.read(256 * 1024)
                if len(image_data) > 40:
                    return f"data:{content_type};base64,{base64.b64encode(image_data).decode('ascii')}"
    except Exception:
        pass
    return ""


def _monogram_logo(label: str, background: str, foreground: str) -> str:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        f'<circle cx="64" cy="64" r="64" fill="{background}"/>'
        f'<text x="64" y="72" text-anchor="middle" font-family="Arial,sans-serif" '
        f'font-size="34" font-weight="700" fill="{foreground}">{label}</text></svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _default_account() -> dict:
    now = datetime.now(IST)
    next_sip = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    return {
        "cash": STARTING_CASH,
        "holdings": {},
        "transactions": [],
        "watchlist": [],
        "sim_state": {
            "last_sip_date": None,
            "next_sip_date": next_sip.strftime("%Y-%m-%d"),
        },
        "metrics": {
            "total_sip_contributions": 0.0,
            "months_completed": 0,
            "total_realized_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        },
    }


def _account_path(username: str, base_dir: Optional[str] = None) -> str:
    root = base_dir or os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(root, "users", username)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "virtual_trading.json")


def _process_auto_sip(account: dict) -> None:
    sim_state = account.get("sim_state", {})
    next_sip_date_str = sim_state.get("next_sip_date")
    if not next_sip_date_str:
        return
        
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    
    new_sip_added = 0.0
    while next_sip_date_str <= today_str:
        amount = float(MONTHLY_SIP)
        account["cash"] = float(account.get("cash", 0.0)) + amount
        new_sip_added += amount
        
        metrics = account.setdefault("metrics", {})
        metrics["total_sip_contributions"] = float(metrics.get("total_sip_contributions", 0.0)) + amount
        metrics["months_completed"] = int(metrics.get("months_completed", 0)) + 1
        
        sim_state["last_sip_date"] = next_sip_date_str
        
        account.setdefault("transactions", []).append({
            "timestamp": f"{next_sip_date_str}T09:15:00",
            "type": "SIP",
            "symbol": "Virtual SIP",
            "quantity": 0,
            "price": amount,
            "value": amount
        })
        
        sip_date = datetime.strptime(next_sip_date_str, "%Y-%m-%d")
        next_month = (sip_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        next_sip_date_str = next_month.strftime("%Y-%m-%d")
        sim_state["next_sip_date"] = next_sip_date_str
        
    if new_sip_added > 0:
        account["_new_sip_added"] = float(account.get("_new_sip_added", 0.0)) + new_sip_added

def load_account(username: str, base_dir: Optional[str] = None) -> dict:
    path = _account_path(username, base_dir)
    if not os.path.exists(path):
        default = _default_account()
        _process_auto_sip(default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as account_file:
            data = json.load(account_file)
    except (OSError, json.JSONDecodeError):
        default = _default_account()
        _process_auto_sip(default)
        return default
    default = _default_account()
    default.update({key: value for key, value in data.items() if key in default})
    default["sim_state"] = {**_default_account()["sim_state"], **data.get("sim_state", {})}
    default["metrics"] = {**_default_account()["metrics"], **data.get("metrics", {})}
    default["holdings"] = data.get("holdings", {}) or {}
    default["transactions"] = data.get("transactions", []) or []
    default["watchlist"] = data.get("watchlist", []) or []
    
    _process_auto_sip(default)
    return default


def save_account(account: dict, username: str, base_dir: Optional[str] = None) -> dict:
    path = _account_path(username, base_dir)
    fd, temp_path = tempfile.mkstemp(prefix="virtual_trading_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as account_file:
            json.dump(account, account_file, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return account


def ensure_account(username: str, base_dir: Optional[str] = None) -> dict:
    account = load_account(username, base_dir)
    return save_account(account, username, base_dir)


def _ticker(symbol: str) -> str:
    clean = _clean_symbol(symbol)
    clean = clean.replace(".BO", ".NS")
    
    # Check if this is a known US stock to avoid appending .NS
    import stock_search
    # _load_stocks is cached in memory
    for item in stock_search._load_stocks():
        if item.get("symbol") == clean:
            if item.get("region") == "US":
                return clean
            break
            
    return clean if clean.endswith(".NS") else f"{clean}.NS"


def _normalize_quote(ticker: str, quote: dict, source: str) -> Optional[dict]:
    price = quote.get("price")
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return None
    previous_close = quote.get("previous_close") or price
    previous_close = float(previous_close) if math.isfinite(float(previous_close)) and float(previous_close) > 0 else float(price)
    change = float(price) - previous_close
    exchange = ticker.rsplit(".", 1)[-1]
    return {
        "symbol": ticker.rsplit(".", 1)[0],
        "ticker": ticker,
        "company": str(quote.get("company") or _COMPANY_NAMES.get(ticker.rsplit(".", 1)[0]) or stock_search.get_company_name(ticker.rsplit(".", 1)[0])),
        "exchange": "NSE" if exchange == "NS" else "BSE" if exchange == "BO" else exchange,
        "currency": "INR",
        "price": float(price),
        "previous_close": previous_close,
        "change": change,
        "change_pct": change / previous_close * 100 if previous_close else 0.0,
        "source": source,
        "updated_at": datetime.now(IST).isoformat(),
        "logo_url": _get_logo_url(ticker),
    }


@lru_cache(maxsize=1)
def get_usd_inr() -> float:
    try:
        quote = yf.Ticker("USDINR=X")
        # Get the latest regular market price
        return float(quote.fast_info.last_price)
    except:
        return 83.50  # Fallback exchange rate

@lru_cache(maxsize=512)
def _get_quote_cached(ticker: str, cache_bucket: int) -> Optional[dict]:
    price, previous_close, source = get_live_quote(ticker)
    if price is None:
        return None
        
    quote = _normalize_quote(ticker, {"price": price, "previous_close": previous_close}, source)
    
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        # This is a US stock, convert USD to INR
        rate = get_usd_inr()
        quote["price"] *= rate
        if quote.get("previous_close"):
            quote["previous_close"] *= rate
        quote["change"] *= rate
        quote["currency"] = "INR"
        quote["_original_usd_price"] = price
        quote["_exchange_rate"] = rate
        
    return quote


def get_quote(symbol: str, company: str = "") -> Optional[dict]:
    ticker = _ticker(symbol)
    quote = _get_quote_cached(ticker, int(time.time() // _QUOTE_CACHE_SECONDS))
    if quote and company:
        quote["company"] = company
    return quote


@lru_cache(maxsize=128)
def _get_events_cached(ticker: str, cache_bucket: int) -> tuple:
    events = []
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends.tail(8)
        for event_date, amount in dividends.items():
            try:
                events.append({
                    "date": event_date.strftime("%d %b %Y"),
                    "title": "Dividend",
                    "subtitle": "Ex date",
                    "detail": f"₹{float(amount):,.2f} per share",
                    "type": "dividend",
                })
            except (TypeError, ValueError, AttributeError):
                continue
    except Exception:
        pass

    try:
        earnings = stock.earnings_dates
        if earnings is not None and not earnings.empty:
            for event_date in earnings.index[:6]:
                try:
                    events.append({
                        "date": event_date.strftime("%d %b %Y"),
                        "title": "Earnings result",
                        "subtitle": "Yahoo Finance earnings date",
                        "detail": "Company event",
                        "type": "earnings",
                    })
                except (TypeError, ValueError, AttributeError):
                    continue
    except Exception:
        pass

    try:
        quarterly = stock.quarterly_income_stmt
        periods = list(quarterly.columns)[:4] if quarterly is not None and not quarterly.empty else []
        for period in periods:
            events.append({"date": period.strftime("%d %b %Y"), "title": "Quarterly result", "subtitle": "Yahoo Finance financial period", "detail": "Quarterly results", "type": "quarterly"})
    except Exception:
        pass

    try:
        annual = stock.income_stmt
        periods = list(annual.columns)[:3] if annual is not None and not annual.empty else []
        for period in periods:
            events.append({"date": period.strftime("%d %b %Y"), "title": "Annual result", "subtitle": "Yahoo Finance financial period", "detail": "Annual results", "type": "annual"})
    except Exception:
        pass

    try:
        for item in (stock.news or [])[:5]:
            content = item.get("content", item)
            title = content.get("title") or item.get("title")
            if not title:
                continue
            link = content.get("canonicalUrl", {}).get("url", "") or item.get("link", "")
            published = content.get("pubDate") or item.get("providerPublishTime")
            if isinstance(published, (int, float)):
                published = datetime.fromtimestamp(published, IST).strftime("%d %b %Y")
            elif published:
                published = str(published)[:10]
            events.append({
                "date": published or "Recent",
                "title": str(title),
                "subtitle": content.get("provider", {}).get("displayName", "Yahoo Finance News") if isinstance(content, dict) else "Yahoo Finance News",
                "detail": "Read Yahoo Finance news",
                "type": "news",
                "url": link,
            })
    except Exception:
        pass

    priority = {"quarterly": 0, "annual": 1, "earnings": 2, "dividend": 3, "news": 4}
    events.sort(key=lambda item: (priority.get(item.get("type"), 9), item.get("date", "")), reverse=False)
    return tuple(events[:18])


def get_events(symbol: str) -> list[dict]:
    return list(_get_events_cached(_ticker(symbol), int(time.time() // 900)))


def search_stocks(query: str, limit: int = 50) -> list[dict]:
    query = str(query or "").strip()
    if not query:
        return []
    import stock_search
    matches = stock_search.search_stocks(query, limit=limit)
    results = []
    for item in matches:
        sym = item["symbol"]
        ticker = item["ticker"]
        company = item["company"]
        exchange = item.get("exchange", "NSE")
        results.append({
            "symbol": sym,
            "ticker": ticker,
            "company": str(company),
            "exchange": exchange,
            "price": 0.0,
            "previous_close": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "source": "stock_search",
            "logo_url": _get_logo_url(ticker),
        })
    return results


def get_market_stocks() -> list[dict]:
    """Fetch quotes for all popular stocks in parallel."""
    def _fetch(symbol):
        return symbol, get_quote(symbol)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(_POPULAR_STOCKS), 12)) as executor:
        futures = {executor.submit(_fetch, sym): sym for sym in _POPULAR_STOCKS}
        for future in as_completed(futures):
            try:
                symbol, quote = future.result()
                if quote:
                    results[symbol] = quote
            except Exception:
                pass
    return [results[sym] for sym in _POPULAR_STOCKS if sym in results]


def prefetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Pre-warm the lru_cache for a list of symbols in parallel.
    Returns a dict mapping symbol -> quote for immediate use in UI rendering.
    """
    if not symbols:
        return {}

    def _fetch(symbol):
        return symbol, get_quote(symbol)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as executor:
        futures = {executor.submit(_fetch, sym): sym for sym in symbols}
        for future in as_completed(futures):
            try:
                symbol, quote = future.result()
                if quote:
                    results[symbol] = quote
            except Exception:
                pass
    return results


def get_chart(symbol: str, range_label: str = "1M") -> list[dict]:
    ranges = {
        "1D": [("5d", "15m"), ("5d", "30m")],
        "1W": [("1mo", "1h"), ("1mo", "1d")],
        "1M": [("3mo", "1d")],
        "3M": [("6mo", "1d")],
        "6M": [("1y", "1d")],
        "1Y": [("2y", "1d")],
        "5Y": [("5y", "1wk"), ("5y", "1mo")],
    }
    ticker = _ticker(symbol)
    for period, interval in ranges.get(range_label, ranges["1M"]):
        try:
            history = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if history.empty or "Close" not in history:
                continue
            points = []
            seen_times = set()
            for index, value in history["Close"].dropna().items():
                try:
                    numeric_value = float(value)
                    timestamp = index.isoformat()
                except (TypeError, ValueError, AttributeError):
                    continue
                if not math.isfinite(numeric_value) or numeric_value <= 0 or timestamp in seen_times:
                    continue
                seen_times.add(timestamp)
                points.append({"time": timestamp, "price": numeric_value})
            points.sort(key=lambda point: point["time"])
            if points:
                return points
        except Exception:
            continue
    return []


@lru_cache(maxsize=256)
def _get_chart_cached(ticker: str, range_label: str, cache_bucket: int) -> tuple:
    return tuple(get_chart(ticker, range_label))


def get_cached_chart(symbol: str, range_label: str = "1M") -> list[dict]:
    return list(_get_chart_cached(_ticker(symbol), range_label, int(time.time() // _CHART_CACHE_SECONDS)))


def market_data_health(symbols: list[str]) -> list[dict]:
    """Return a compact audit report for quote and chart availability."""
    report = []
    for symbol in symbols:
        quote = get_quote(symbol)
        report.append({
            "symbol": symbol,
            "quote": bool(quote),
            "charts": {label: bool(get_cached_chart(symbol, label)) for label in ("1D", "1W", "1M", "1Y")},
        })
    return report


def portfolio_metrics(account: dict) -> dict:
    invested = 0.0
    current_value = 0.0
    today_pnl = 0.0
    for symbol, holding in account.get("holdings", {}).items():
        quote = get_quote(symbol)
        if not quote:
            continue
        quantity = float(holding.get("quantity", 0.0))
        average = float(holding.get("average_cost", 0.0))
        invested += quantity * average
        current_value += quantity * quote["price"]
        today_pnl += quantity * quote["change"]
    cash = float(account.get("cash", STARTING_CASH))
    total_sip = float(account.get("metrics", {}).get("total_sip_contributions", 0.0))
    contributed = STARTING_CASH + total_sip
    total_pnl = current_value - invested + float(account.get("metrics", {}).get("total_realized_pnl", 0.0))
    portfolio_value = cash + current_value
    return {
        "portfolio_value": portfolio_value,
        "cash": cash,
        "invested": invested,
        "current_value": current_value,
        "total_pnl": total_pnl,
        "total_return_pct": total_pnl / contributed * 100 if contributed else 0.0,
        "today_pnl": today_pnl,
        "today_pnl_pct": today_pnl / current_value * 100 if current_value else 0.0,
        "total_sip": total_sip,
        "holdings_count": len(account.get("holdings", {})),
    }


def buy(account: dict, symbol: str, quantity: float, price: float) -> None:
    symbol = symbol.upper()
    quantity = float(quantity)
    price = float(price)
    if quantity <= 0 or price <= 0:
        raise ValueError("Enter a valid quantity.")
    value = quantity * price
    if value > float(account.get("cash", 0.0)):
        raise ValueError("Not enough virtual cash for this order.")
    holding = account.setdefault("holdings", {}).get(symbol, {"quantity": 0.0, "average_cost": 0.0})
    old_qty = float(holding.get("quantity", 0.0))
    old_invested = old_qty * float(holding.get("average_cost", 0.0))
    new_qty = old_qty + quantity
    account["cash"] = float(account.get("cash", 0.0)) - value
    account["holdings"][symbol] = {"quantity": new_qty, "average_cost": (old_invested + value) / new_qty, "total_invested": old_invested + value}
    account.setdefault("transactions", []).append({"timestamp": datetime.now(IST).isoformat(), "type": "BUY", "symbol": symbol, "quantity": quantity, "price": price, "value": value})
    account.setdefault("metrics", {})["total_trades"] = int(account["metrics"].get("total_trades", 0)) + 1


def sell(account: dict, symbol: str, quantity: float, price: float) -> None:
    symbol = symbol.upper()
    quantity = float(quantity)
    holding = account.get("holdings", {}).get(symbol)
    if not holding or quantity <= 0 or quantity > float(holding.get("quantity", 0.0)):
        raise ValueError("You do not own enough shares to sell.")
    average = float(holding.get("average_cost", 0.0))
    value = quantity * float(price)
    realized = quantity * (float(price) - average)
    remaining = float(holding["quantity"]) - quantity
    account["cash"] = float(account.get("cash", 0.0)) + value
    if remaining <= 0:
        account["holdings"].pop(symbol)
    else:
        holding["quantity"] = remaining
        holding["total_invested"] = remaining * average
    metrics = account.setdefault("metrics", {})
    metrics["total_trades"] = int(metrics.get("total_trades", 0)) + 1
    metrics["total_realized_pnl"] = float(metrics.get("total_realized_pnl", 0.0)) + realized
    key = "winning_trades" if realized >= 0 else "losing_trades"
    metrics[key] = int(metrics.get(key, 0)) + 1
    account.setdefault("transactions", []).append({"timestamp": datetime.now(IST).isoformat(), "type": "SELL", "symbol": symbol, "quantity": quantity, "price": float(price), "value": value, "realized_pnl": realized})


def market_state() -> dict:
    now = datetime.now(IST)
    return {"open": is_market_open(), "status": get_market_status(), "time": now.strftime("%d %b %Y · %H:%M IST")}
