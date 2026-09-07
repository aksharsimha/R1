"""
Ultra-fast, fuzzy-matching Indian stock & ETF search engine for QUEST.
Matches company names, tickers, brand aliases, and handles spelling mistakes seamlessly.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

# Preloaded popular / large-cap weighting for prioritizing top companies
POPULAR_LARGE_CAPS: Dict[str, int] = {
    "RELIANCE": 200, "TCS": 200, "HDFCBANK": 200, "ICICIBANK": 200, "INFY": 200,
    "BHARTIARTL": 190, "SBIN": 190, "ITC": 190, "LICI": 190, "HINDUNILVR": 190,
    "LT": 180, "BAJFINANCE": 180, "TATAMOTORS": 185, "MARUTI": 180, "SUNPHARMA": 180,
    "KOTAKBANK": 170, "AXISBANK": 170, "TITAN": 170, "ADANIENT": 170, "ADANIPORTS": 170,
    "NTPC": 160, "TATASTEEL": 175, "POWERGRID": 160, "ONGC": 160, "COALINDIA": 160,
    "M&M": 160, "BAJAJFINSV": 160, "ULTRACEMCO": 160, "ASIANPAINT": 160, "WIPRO": 165,
    "HCLTECH": 150, "ZOMATO": 160, "ETERNAL": 150, "JIOFIN": 160, "TRENT": 165,
    "NESTLEIND": 150, "IOC": 140, "BEL": 150, "HAL": 150, "DLF": 140, "GRASIM": 140,
    "TATAPOWER": 160, "JSWSTEEL": 140, "TECHM": 140, "LTIM": 140, "DIVISLAB": 140,
    "CIPLA": 140, "DRREDDY": 140, "EICHERMOT": 140, "HEROMOTOCO": 140, "APOLLOHOSP": 140,
    "IRCTC": 150, "IRFC": 140, "RVNL": 140, "SUZLON": 140, "VEDL": 140, "BHEL": 140,
    "BPCL": 140, "GAIL": 140, "PFC": 140, "REC": 140, "IREDA": 140, "PAYTM": 140,
    "NYKAA": 140, "DMART": 140, "PIDILITIND": 150, "HAVELLS": 140, "POLYCAB": 140,
    "VOLTAS": 140, "TATACOMM": 140, "TATACHEM": 140, "TATAELXSI": 145, "TATATECH": 145,
    "TATACONSUM": 150, "NIFTYBEES": 160, "GOLDBEES": 160, "SILVERBEES": 160,
    "BANKBEES": 160, "MON100": 160, "NXST": 130, "EMBASSY": 130, "BIRET": 130
}

# Curated dictionary of common brand names, former names, and phonetic aliases
ALIASES: Dict[str, List[str]] = {
    "RELIANCE": ["Reliance", "Reliance Industries", "RIL", "Mukesh Ambani", "Reliance Ind"],
    "ZOMATO": ["Zomato", "Eternal", "Zomato Ltd", "Blinkit", "Zomto"],
    "ETERNAL": ["Zomato", "Eternal", "Zomato Ltd", "Blinkit", "Zomto"],
    "PAYTM": ["Paytm", "One97 Communications", "One 97", "Paytm Payments"],
    "NYKAA": ["Nykaa", "FSN E-Commerce Ventures", "Nyka"],
    "DMART": ["Dmart", "Avenue Supermarts", "Radhakishan Damani"],
    "JIOFIN": ["Jio Financial Services", "Jio Finance", "Jio", "Reliance Jio"],
    "BHARTIARTL": ["Airtel", "Bharti Airtel", "Bharti", "Airtel India"],
    "SBIN": ["SBI", "State Bank of India", "State Bank"],
    "HDFCBANK": ["HDFC", "HDFC Bank", "Housing Development Finance", "HDFC Bank Ltd"],
    "ICICIBANK": ["ICICI", "ICICI Bank", "ICICI Bank Ltd"],
    "KOTAKBANK": ["Kotak", "Kotak Mahindra Bank", "Uday Kotak"],
    "AXISBANK": ["Axis Bank", "Axis", "Axis Bank Ltd"],
    "TATAMOTORS": ["Tata Motors", "Tata Motor", "Tata EV", "Jaguar Land Rover", "JLR", "Tata Motors Ltd"],
    "TCS": ["Tata Consultancy Services", "TCS", "Tata Consultancy"],
    "TATASTEEL": ["Tata Steel", "Tata Steel Ltd"],
    "TATAPOWER": ["Tata Power", "Tata Solar", "Tata Power Ltd"],
    "TATACONSUM": ["Tata Consumer Products", "Tata Tea", "Tata Salt", "Tata Consumer"],
    "TATACHEM": ["Tata Chemicals", "Tata Chem"],
    "TATAELXSI": ["Tata Elxsi"],
    "TATATECH": ["Tata Technologies", "Tata Tech"],
    "TATACOMM": ["Tata Communications", "Tata Comm", "VSNL"],
    "TRENT": ["Trent", "Westside", "Zudio", "Tata Trent", "Trent Ltd"],
    "LT": ["Larsen & Toubro", "L&T", "Larsen and Toubro", "Larsen", "L&T Ltd"],
    "INFY": ["Infosys", "Infy", "Narayana Murthy", "Infosys Ltd"],
    "WIPRO": ["Wipro", "Azim Premji", "Wipro Ltd"],
    "ITC": ["ITC", "ITC Limited", "Indian Tobacco Company", "Aashirvaad", "Sunfeast", "Bingo"],
    "MARUTI": ["Maruti Suzuki", "Maruti", "Suzuki", "Maruti Suzuki India"],
    "BAJFINANCE": ["Bajaj Finance", "Bajaj Fin"],
    "BAJAJFINSV": ["Bajaj Finserv"],
    "BAJAJ-AUTO": ["Bajaj Auto", "Pulsar"],
    "M&M": ["Mahindra & Mahindra", "Mahindra", "M&M", "Mahindra Auto", "Scorpio", "Thar"],
    "SUNPHARMA": ["Sun Pharma", "Sun Pharmaceutical", "Dilip Shanghvi"],
    "CIPLA": ["Cipla"],
    "DRREDDY": ["Dr Reddy", "Dr. Reddy's Laboratories", "Dr Reddys"],
    "APOLLOHOSP": ["Apollo Hospitals", "Apollo Hospital", "Apollo Pharmacy"],
    "TITAN": ["Titan", "Titan Company", "Tanishq", "Fastrack", "Eyeplus"],
    "ASIANPAINT": ["Asian Paints", "Asian Paint"],
    "BERGEPAINT": ["Berger Paints", "Berger Paint"],
    "PIDILITIND": ["Pidilite", "Fevicol", "Dr Fixit", "M-Seal", "Fevi Kwik"],
    "NESTLEIND": ["Nestle", "Nestle India", "Maggi", "Nescafe", "KitKat"],
    "BRITANNIA": ["Britannia", "Good Day", "Bourbon"],
    "HINDUNILVR": ["HUL", "Hindustan Unilever", "Surf Excel", "Dove", "Lifebuoy", "Rin"],
    "DABUR": ["Dabur", "Chyawanprash", "Real Juice", "Dabur India"],
    "MARICO": ["Marico", "Parachute", "Saffola"],
    "GODREJCP": ["Godrej Consumer", "Godrej", "Goodknight", "Cinthol"],
    "VBL": ["Varun Beverages", "Pepsi India", "VBL", "Pepsi", "Mountain Dew"],
    "HAL": ["HAL", "Hindustan Aeronautics", "Tejas"],
    "BEL": ["BEL", "Bharat Electronics"],
    "BHEL": ["BHEL", "Bharat Heavy Electricals"],
    "IRCTC": ["IRCTC", "Indian Railway Catering and Tourism", "Rail Neer"],
    "RVNL": ["RVNL", "Rail Vikas Nigam"],
    "IRFC": ["IRFC", "Indian Railway Finance Corporation"],
    "IREDA": ["IREDA", "Indian Renewable Energy Development Agency"],
    "SUZLON": ["Suzlon", "Suzlon Energy", "Wind Energy"],
    "INOXWIND": ["Inox Wind"],
    "VEDL": ["Vedanta", "Anil Agarwal"],
    "ADANIENT": ["Adani Enterprises", "Adani", "Gautam Adani"],
    "ADANIPORTS": ["Adani Ports", "Mundra Port", "APSEZ"],
    "ADANIPOWER": ["Adani Power"],
    "ADANIGREEN": ["Adani Green Energy", "Adani Green"],
    "ATGL": ["Adani Total Gas", "Adani Gas"],
    "AWL": ["Adani Wilmar", "Fortune Oil"],
    "AMBUJACEM": ["Ambuja Cements", "Ambuja Cement"],
    "ACC": ["ACC Limited", "ACC Cement"],
    "ULTRACEMCO": ["UltraTech Cement", "UltraTech", "Aditya Birla Cement"],
    "NXST": ["Nexus Select Trust", "Nexus REIT", "NXST"],
    "EMBASSY": ["Embassy Office Parks REIT", "Embassy REIT"],
    "BIRET": ["Brookfield India Real Estate Trust", "Brookfield REIT"],
    "MINDSPACE": ["Mindspace Business Parks REIT", "Mindspace REIT"],
    "NIFTYBEES": ["Nippon India ETF Nifty 50 BeES", "NIFTY BEES", "NiftyBeES", "Nifty 50 ETF"],
    "GOLDBEES": ["Nippon India ETF Gold BeES", "Gold Bees", "Gold ETF"],
    "SILVERBEES": ["Nippon India ETF Silver BeES", "Silver Bees", "Silver ETF"],
    "BANKBEES": ["Nippon India ETF Nifty Bank BeES", "Bank Bees", "Bank Nifty ETF"],
    "MON100": ["Motilal Oswal Nasdaq 100 ETF", "MON100", "Nasdaq 100 ETF"],
    "JUNIORBEES": ["Nippon India ETF Nifty Next 50 Junior BeES", "Junior Bees"],
    "ITBEES": ["Nippon India ETF Nifty IT BeES", "IT Bees"],
    "AUTOBEES": ["Nippon India ETF Nifty Auto BeES", "Auto Bees"],
    "PHARMABEES": ["Nippon India ETF Nifty Pharma BeES", "Pharma Bees"],
    "IDEA": ["Vodafone Idea", "Vi", "Idea"],
    "INDUSTOWER": ["Indus Towers", "Bharti Infratel"],
}

# Supplementary stocks and ETFs not always present in standard equity CSV
EXTRA_STOCKS: List[Dict[str, str]] = [
    {"symbol": "TATAMOTORS", "company": "Tata Motors Limited", "ticker": "TATAMOTORS.NS", "exchange": "NSE"},
    {"symbol": "ZOMATO", "company": "Zomato Limited (Eternal)", "ticker": "ZOMATO.NS", "exchange": "NSE"},
    {"symbol": "NIFTYBEES", "company": "Nippon India ETF Nifty 50 BeES", "ticker": "NIFTYBEES.NS", "exchange": "NSE"},
    {"symbol": "GOLDBEES", "company": "Nippon India ETF Gold BeES", "ticker": "GOLDBEES.NS", "exchange": "NSE"},
    {"symbol": "SILVERBEES", "company": "Nippon India ETF Silver BeES", "ticker": "SILVERBEES.NS", "exchange": "NSE"},
    {"symbol": "BANKBEES", "company": "Nippon India ETF Nifty Bank BeES", "ticker": "BANKBEES.NS", "exchange": "NSE"},
    {"symbol": "MON100", "company": "Motilal Oswal Nasdaq 100 ETF", "ticker": "MON100.NS", "exchange": "NSE"},
    {"symbol": "JUNIORBEES", "company": "Nippon India ETF Nifty Next 50 Junior BeES", "ticker": "JUNIORBEES.NS", "exchange": "NSE"},
    {"symbol": "ITBEES", "company": "Nippon India ETF Nifty IT BeES", "ticker": "ITBEES.NS", "exchange": "NSE"},
    {"symbol": "AUTOBEES", "company": "Nippon India ETF Nifty Auto BeES", "ticker": "AUTOBEES.NS", "exchange": "NSE"},
    {"symbol": "PHARMABEES", "company": "Nippon India ETF Nifty Pharma BeES", "ticker": "PHARMABEES.NS", "exchange": "NSE"},
    {"symbol": "NXST", "company": "Nexus Select Trust REIT", "ticker": "NXST.NS", "exchange": "NSE"},
    {"symbol": "EMBASSY", "company": "Embassy Office Parks REIT", "ticker": "EMBASSY.NS", "exchange": "NSE"},
    {"symbol": "BIRET", "company": "Brookfield India Real Estate Trust", "ticker": "BIRET.NS", "exchange": "NSE"},
    {"symbol": "MINDSPACE", "company": "Mindspace Business Parks REIT", "ticker": "MINDSPACE.NS", "exchange": "NSE"},
]

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nse_equities.json")
_STOCKS_CACHE: Optional[List[Dict[str, str]]] = None


def _load_stocks() -> List[Dict[str, str]]:
    """Loads all NSE equities and ETFs into memory."""
    global _STOCKS_CACHE
    if _STOCKS_CACHE is not None:
        return _STOCKS_CACHE

    stock_map: Dict[str, Dict[str, str]] = {}
    if os.path.exists(_DB_PATH):
        try:
            with open(_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                sym = item.get("symbol", "").strip().upper()
                if sym:
                    stock_map[sym] = {
                        "symbol": sym,
                        "company": item.get("company", sym),
                        "ticker": f"{sym}.NS",
                        "exchange": "NSE"
                    }
        except Exception:
            pass

    for extra in EXTRA_STOCKS:
        sym = extra["symbol"].upper()
        stock_map[sym] = extra

    _STOCKS_CACHE = list(stock_map.values())
    return _STOCKS_CACHE


def _score_candidate(query: str, symbol: str, company: str) -> int:
    """
    Evaluates how closely a security matches a user query (0-1500 score).
    Handles spelling mistakes, acronyms, brand aliases, and multi-word searches.
    """
    q = query.lower().strip()
    s = symbol.lower()
    c = company.lower()

    if not q:
        return 0

    pop_boost = POPULAR_LARGE_CAPS.get(symbol, 0)
    q_clean = re.sub(r"[^a-z0-9]", "", q)
    s_clean = re.sub(r"[^a-z0-9]", "", s)
    c_clean = re.sub(r"[^a-z0-9]", "", c)

    max_score = 0

    # 1. Alias & Brand Names check
    alias_list = ALIASES.get(symbol, [])
    for al in alias_list:
        al_l = al.lower()
        al_clean = re.sub(r"[^a-z0-9]", "", al_l)
        if q == al_l or (len(q_clean) >= 2 and q_clean == al_clean):
            score = 1200
        elif al_l.startswith(q) or (len(q_clean) >= 2 and al_clean.startswith(q_clean)):
            score = 1100 - len(al_l)
        elif q in al_l or (len(q_clean) >= 3 and q_clean in al_clean):
            score = 950 - len(al_l)
        else:
            r_al = difflib.SequenceMatcher(None, q, al_l).ratio()
            r_clean = difflib.SequenceMatcher(None, q_clean, al_clean).ratio()
            best_r = max(r_al, r_clean)
            if best_r >= 0.70:
                score = int(best_r * 900)
            else:
                score = 0
        if score > max_score:
            max_score = score

    # 2. Exact Symbol check
    if q == s or (len(q_clean) >= 2 and q_clean == s_clean):
        score = 1000
    elif s.startswith(q) or (len(q_clean) >= 2 and s_clean.startswith(q_clean)):
        score = 900 - len(s)
    elif q in s or (len(q_clean) >= 2 and q_clean in s_clean):
        score = 800 - len(s)
    else:
        score = 0
    if score > max_score:
        max_score = score

    # 3. Company Words & Prefixes
    c_words = re.findall(r"[a-z0-9]+", c)
    for w in c_words:
        if w == q or (len(q_clean) >= 3 and w == q_clean):
            score = 850
        elif w.startswith(q) and len(q) >= 2:
            score = 800 - (len(w) - len(q))
        elif len(q) >= 3 and q in w:
            score = 750
        else:
            score = 0
        if score > max_score:
            max_score = score

    # 4. Multi-token Query Matching (e.g. 'tata moters', 'reliance ind', 'silver bees')
    q_tokens = re.findall(r"[a-z0-9]+", q)
    if len(q_tokens) > 1:
        matched_tokens = 0
        total_ratio = 0.0
        for tok in q_tokens:
            best_tok_match = 0.0
            for w in c_words:
                if w.startswith(tok):
                    best_tok_match = max(best_tok_match, 1.0)
                else:
                    r = difflib.SequenceMatcher(None, tok, w).ratio()
                    if r >= 0.70:
                        best_tok_match = max(best_tok_match, r)
            for al in alias_list:
                for al_w in re.findall(r"[a-z0-9]+", al.lower()):
                    if al_w.startswith(tok):
                        best_tok_match = max(best_tok_match, 1.0)
                    else:
                        r = difflib.SequenceMatcher(None, tok, al_w).ratio()
                        if r >= 0.70:
                            best_tok_match = max(best_tok_match, r)
            if best_tok_match >= 0.70:
                matched_tokens += 1
                total_ratio += best_tok_match
        if matched_tokens == len(q_tokens):
            score = 700 + int(total_ratio * 60)
            if score > max_score:
                max_score = score
        elif matched_tokens > 0:
            score = 350 + int(total_ratio * 40)
            if score > max_score:
                max_score = score

    # 5. Fuzzy Match against Symbol or Company (Typo correction: 'relaince', 'infocys', 'wiproo')
    ratio_s = difflib.SequenceMatcher(None, q, s).ratio()
    if ratio_s >= 0.70:
        score = int(ratio_s * 600)
        if score > max_score:
            max_score = score

    max_word_ratio = max((difflib.SequenceMatcher(None, q, w).ratio() for w in c_words if len(w) >= 3), default=0.0)
    if max_word_ratio >= 0.70:
        score = int(max_word_ratio * 650)
        if score > max_score:
            max_score = score

    if max_score > 0:
        return max_score + pop_boost
    return 0


def _query_yahoo_search(query: str) -> List[Dict[str, str]]:
    """Fetches live search results from Yahoo Finance API for unlisted / rare scrips."""
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(query.strip())
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.0) as r:
            data = json.loads(r.read().decode("utf-8"))
        quotes = data.get("quotes", [])
        results = []
        for q in quotes:
            sym = q.get("symbol", "")
            exch = str(q.get("exchange", "")).upper()
            q_type = str(q.get("quoteType", "")).upper()
            if q_type in ("EQUITY", "MUTUALFUND", "ETF") and (exch in ("NSI", "BSE") or sym.endswith((".NS", ".BO"))):
                clean_sym = sym.replace(".NS", "").replace(".BO", "")
                comp = q.get("longname") or q.get("shortname") or clean_sym
                results.append({
                    "symbol": clean_sym,
                    "company": str(comp),
                    "ticker": f"{clean_sym}.NS" if not sym.endswith(".BO") or exch == "NSI" else sym,
                    "exchange": "NSE" if (exch == "NSI" or not sym.endswith(".BO")) else "BSE"
                })
        return results
    except Exception:
        return []


@lru_cache(maxsize=512)
def search_stocks(query: str, limit: int = 30) -> List[Dict[str, str]]:
    """
    Searches across Indian equities, REITs, ETFs and mutual funds.
    Fuzzy-matches misspellings, brand aliases, and ticker codes.
    Returns sorted list of matches:
    [{'symbol': 'RELIANCE', 'company': 'Reliance Industries Limited', 'ticker': 'RELIANCE.NS', 'exchange': 'NSE'}, ...]
    """
    query = str(query or "").strip()
    if not query:
        return []

    stocks = _load_stocks()
    scored_items: List[Tuple[int, Dict[str, str]]] = []
    seen_symbols = set()

    for item in stocks:
        sym = item["symbol"]
        score = _score_candidate(query, sym, item["company"])
        if score >= 350:
            scored_items.append((score, item))
            seen_symbols.add(sym.upper())

    # If query returned few or no results, query Yahoo search as well
    if len(scored_items) < 5:
        yahoo_results = _query_yahoo_search(query)
        for y_item in yahoo_results:
            sym = y_item["symbol"].upper()
            if sym not in seen_symbols:
                score = _score_candidate(query, sym, y_item["company"])
                if score < 350:
                    score = 450  # Give live Yahoo matches decent score
                scored_items.append((score, y_item))
                seen_symbols.add(sym)

    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored_items[:limit]]


def lookup_ticker(query: str) -> Optional[str]:
    """Resolves a stock or company name to its primary ticker (e.g. 'RELIANCE.NS')."""
    results = search_stocks(query, limit=1)
    if results:
        return results[0]["ticker"]
    return None


def get_company_name(symbol: str) -> str:
    """Returns official or brand company name for a given ticker or symbol."""
    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    stocks = _load_stocks()
    for item in stocks:
        if item["symbol"].upper() == clean_sym:
            return item["company"]
    return clean_sym
