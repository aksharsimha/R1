# CHANGELOG — QUEST (Quantitative Unified Equity Surveillance Tracker)

All notable changes to the QUEST portfolio system are documented here.

---

## [2026-06-20] — UI Makeover: nav polish + holdings redesign

### Changed
- **Section routing now renders only the active section** (was: render-all
  then hide via `_Sink`). Fixes the "flash of all sections" on switch and makes
  each load much faster (one section's code runs, not all 8). 8 sections:
  Overview · Analytics · Projections · Insights · News · Activity · Chat · MICHAEL.
- **Smooth fade-in** (`q-page-in`) on section transitions.
- **Calendar shrunk** — fixed 36px day cells instead of `aspect-ratio:1`
  (it was filling the whole screen on desktop).
- **Holdings redesigned** — the 15-column spreadsheet is replaced with clean
  cards (name, type, qty, invested→current, P&L, risk pill, allocation bar).
  Inline **Add / Edit / Remove** (expanders) moved onto Overview, reusing the
  existing `add_asset`/`update_asset_holdings`/`remove_asset` functions.
- **Allocation donut cleaned up** — bigger hole, percentages inside slices,
  tiny-slice labels hidden (`uniformtext_mode='hide'`) to kill the overlap.

### Done in follow-up
- **News redesigned**: article cards, stock-card headers, and the summary bar
  recolored to theme tokens (bullish=accent/green, bearish=coral, neutral=muted);
  the emoji-heavy summary bar is now a clean flat stat row.
- **Removed the sidebar Portfolio Manager** (radio + 4 forms) — add/edit/remove
  now lives inline on Overview. Kept the `load_holdings` call that the rest of
  the dashboard depends on.

---

## [2026-06-20] — UI Makeover: 5-section navigation

### Changed
- **Replaced the 9 `st.tabs` with a 5-section sidebar nav**: Overview ·
  Analytics · Insights · Activity · MICHAEL. A sidebar radio drives a
  `_slot()` router that maps each old tab to a section. Inactive sections
  render into a cleared placeholder (`_Sink`) so all bodies still execute
  (side effects preserved, matching the old st.tabs behaviour) but only the
  active section is visible.
  - Overview = hero + calendar + holdings (old Portfolio Data tab)
  - Analytics = Performance + Math Engine + Projections
  - Insights = AI Recommendations + News & Sentiment
  - Activity = Transaction Ledger + Chat
  - MICHAEL = AI assistant (its own section)
- The Overview hero/calendar/risk-breakdown block is now gated to the
  Overview section.

### Still to do
- Sub-tabs within Analytics/Insights/Activity; Advanced toggle for the math;
  move Add/Remove stock inline onto Overview (still in sidebar for now).

---

## [2026-06-20] — UI Makeover: Theme-sweep (light mode everywhere)

### Changed
- **Plotly charts themed**: added `ui_theme.style_fig()` (transparent bg,
  theme font/grid/legend/hover colors, accent colorway) and applied it to all
  7 charts — fixes white chart text being invisible in light mode.
- **Swept remaining tabs to theme variables**: News, Chat, MICHAEL assistant,
  Recommendations, Projections. Removed gradient text headers, near-white inline
  text (`#e2e8f0`/`#fff`), and white-overlay card backgrounds — replaced with
  `var(--q-*)`. Light and dark now both render correctly across the app.

---

## [2026-06-20] — UI Makeover: Foundation + Overview (Phase 0–2)

### Added
- **`ui_theme.py`** — new design-system module: design tokens as CSS variables
  for two themes (calm light / refined dark), `init_theme()`, `current_theme()`,
  `theme_toggle()`, `css()`, and component helpers (`metric_card`, `pill`,
  `holding_row`, `value_hero`). Flat aesthetic, motion keyframes, respects
  `prefers-reduced-motion`.
- **Sidebar theme switch** — toggle between light and dark at runtime.

### Changed
- **Removed the old 358-line "Ultra Premium Dark Mode" CSS block** (aurora
  glow, neon) from `app.py`; replaced with `ui_theme.css()` injection.
- **Overview redesigned**: hero portfolio value + P&L with status/source pills,
  responsive stat grid (`auto-fit`), and entrance animations.
- **Holiday calendar reskinned** to follow the active theme palette (was
  hardcoded neon); flat card, no glow.

### Notes
- This is Phase 0–2 of a multi-phase makeover. Remaining: app shell/nav
  (9 tabs → 4 sections), Analytics (+Advanced math toggle), Insights, Activity.
  Other tabs still use the old inline styles until their phase lands.

---

## [2026-06-20] — Auto-Updating Holiday Calendar

### Added
- **Auto-fetched holiday calendar** (`nse_live.py`): `_HolidayCalendar` pulls
  the official NSE trading-holiday list from the holiday-master API, caches it
  to `nse_holidays.json`, and refreshes weekly. Three tiers: disk cache → live
  NSE fetch → hardcoded `NSE_HOLIDAYS_FALLBACK`. No more manual yearly edits.
  New public API: `refresh_holiday_calendar()`, `get_holiday_calendar()`.
- **Home-screen calendar widget** (`app.py`): Google-Calendar-style month grid
  under the hero cards. Month navigation (‹ ›), today ringed in green, weekends
  dimmed, holidays highlighted in red with hover tooltips (holiday name), a
  legend, and a "Next holiday" countdown. Holiday data refreshed weekly via a
  cached loader.

---

## [2026-06-20] — Tests, Persistent Cache & Decimal Display

### Added
- **Persistent price cache** (`nse_live.py`): `_PersistentPriceStore` saves the
  last-known-good price per symbol to `price_cache.json`. New `'cached'`
  fallback tier sits between yfinance and historical, so when both live
  sources are down we show the most recent real price (< 24h old) instead of
  nothing. New UI label "Last-known price (cached)".
- **Unit tests** (`tests/test_nse_live.py`): 19 tests covering the
  NSE→yfinance→cached→historical fallback chain, circuit breaker, persistent
  store (incl. expiry/reload), holiday detection, and symbol conversion.
  All mocked — no network. Run: `python -m unittest tests.test_nse_live -v`.

### Fixed
- **Decimal display**: hero cards (Current Value, Invested, P&L) and chat
  portfolio-share cards now show full paise (`:,.2f`) instead of rounding to
  the nearest rupee. ₹42,670 → ₹42,669.76.

---

## [2026-06-20] — NSE Reliability & Performance

### Added
- **NSE holiday awareness** (`nse_live.py`): `is_market_open()` and
  `get_market_status()` now treat NSE trading holidays as closed (previously
  every weekday counted as a trading day). Holidays live in the `NSE_HOLIDAYS`
  table — update it yearly.
- **Circuit breaker** (`nse_live.py`): after 5 consecutive NSE failures, live
  calls short-circuit for 180s and fall straight through to yfinance, skipping
  the retry/backoff cost on bad days. A single success resets it.

### Changed
- **Parallel batch fetch** (`risk_analyzer.py`): `batch_fetch_live_prices()`
  now fetches tickers concurrently via a thread pool instead of sequentially,
  cutting per-refresh latency from ~N×gap to roughly the slowest single call.
- Rate-limit comment in `nse_live.py` corrected to reflect the actual 0.25s gap.

### Housekeeping
- Moved one-off scripts (`fix_*`, `test_*`, `_append_michael.py`,
  `check_prices.py`) into `scratch/`. Added `*.zip` to `.gitignore`.

---

## [2026-06-20] — Real-Time NSE Data Integration

### Problem
The system relied exclusively on **yfinance** for market data, which delivers
Indian market prices with a **15–20 minute delay** from the actual exchange.
During market hours, the portfolio valuation and P&L figures were consistently
stale.

### Solution
Added **direct NSE India scraping** for real-time prices (~1–3 second delay)
during market hours, with automatic fallback to yfinance when NSE is
unavailable.

### New Files

| File | Purpose |
|------|---------|
| `nse_live.py` | NSE live price scraping module — session management, rate limiting, caching, and fallback logic |

### Modified Files

| File | What Changed |
|------|-------------|
| `risk_analyzer.py` | Added `get_current_price()` function for live price resolution (NSE → yfinance → historical). Updated `analyze_asset()` to use live prices for current valuation. Added `price_source` field to `StockReport`. Portfolio summary now includes market status and data source info. |
| `app.py` | Auto-refresh reduced from 60s → 30s. Hero section now shows a **live market status indicator** (green/red dot) and **dynamic data source label** (NSE real-time / yfinance delayed / historical). |
| `requirements.txt` | Added `pytz>=2024.1` for IST timezone handling. |

### Architecture

```
Price Resolution Order (during market hours):
  1. NSE India (nseindia.com/api/quote-equity)  →  ~1-3s delay    ✅
  2. yfinance fast_info.last_price               →  ~15-20min delay
  3. Last historical close                       →  end-of-day only

Historical metrics (volatility, beta, Sharpe, VaR, etc.):
  → Still use yfinance 2-year data (unchanged)

Mutual fund NAVs:
  → Still use api.mfapi.in (unchanged, updates once daily)
```

### UI Changes
- **Market Value card** now shows:
  - 🟢 green dot + "Market Open" during trading hours (9:15 AM – 3:30 PM IST)
  - 🔴 red dot + "Market Closed" outside trading hours
  - Data source: "Live via NSE (real-time)" / "Via yfinance (~15min delay)" / "Historical close"
- Auto-refresh interval reduced from 60s → 30s

### Technical Details — NSE Scraping

- **Session cookies**: NSE requires visiting the homepage first to obtain valid session cookies before API calls succeed.
- **Rate limiting**: Built-in throttle at ~3 requests/second to stay under NSE's radar.
- **Retry logic**: Exponential backoff on failures (up to 3 attempts).
- **Cache**: 15-second TTL cache to prevent redundant NSE hits on each Streamlit rerun.
- **Thread safety**: All session and cache operations are thread-safe via locks.

### Caveats

1. NSE scraping can occasionally be blocked by IP rate limits. The system
   falls back gracefully to yfinance when this happens.
2. NSE does not provide mutual fund NAVs — MF prices still update once daily.
3. Market hours detection does not account for NSE holidays (treats them as
   regular weekdays).
4. ETFs and equities both use the same NSE quote-equity endpoint.

---

## [Pre-2026-06-20] — Initial System

Original QUEST system with:
- yfinance for all equity/ETF data (~15-20min delayed)
- api.mfapi.in for mutual fund NAVs
- GOLDBEES.NS as digital gold proxy
- Streamlit dashboard with 60s auto-refresh
- Firebase authentication and sync
- News sentiment analysis via yfinance + NewsAPI
- Adaptive risk engine with EWMA
- Chat system and portfolio ledger
- PDF report generation
