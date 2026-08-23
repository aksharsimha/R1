# ⚡ QUEST — Quantitative Unified Equity Surveillance Tracker

A personal **investing + planning** web app for the Indian markets (NSE/BSE).
Track your portfolio, measure its risk, compare stocks like a trader, read the
news that moves your holdings, plan your week, and talk to **MICHAEL**, an
AI assistant that can see all of it.

Built with Streamlit · Firebase · yfinance · Groq (Llama 3.3) · Plotly.

---

## ✨ What it does

### 📝 Latest Updates (August 23, 2026)
*By Aksharsimha*
- **Stock Validation & Limits:** Fixed zero-rupee purchase bugs and implemented robust historical ALL-TIME range validation for average buy prices (adjusted for stock splits).
- **Time/Timezone Sync:** Fixed `datetime.now()` to strictly use IST (`Asia/Kolkata`) across the dashboard and chat timestamps.
- **Routing & State Preservation:** Synced sidebar navigation with `st.query_params` to fix the Back/Forward browser buttons and resolved the refresh logout issue.
- **Mobile Rendering:** Injected responsive CSS media queries for phone-friendly login and dashboard flex stacking.
- **Table Column Hiding Bug:** Bypassed Streamlit's native cache bugs by downgrading Insights to `st.table` and dynamically binding the data editor's key to the user's multiselect columns.
- **Stock Search Dropdown:** Replaced manual ticker typing with a dynamic auto-complete `selectbox` powered by Yahoo Finance API (automatically hiding corrupted `.BO` data in favor of `.NS`).

*By Arnav*
- **Dashboard Sidebar:** Added the profile block, account switcher, functional Settings and Chat notification buttons, vertical hamburger collapse control, and restored the full dashboard navigation.
- **Settings:** Added a dedicated Settings sidebar with Dashboard, Profile, Theme, Password & Security, and Sign out sections. Profile supports avatar, display name, and summary editing; Theme supports light and dark modes.
- **Account Security:** Added Firebase-backed password changes, email changes with verification delivery, phone number updates, avatar persistence, and username migration with password checks and cooldown protection.
- **Multi-Account Switching:** Added signed multi-account remember-me cookies with legacy migration, forged-entry rejection, account forgetting support, password-free switching between remembered accounts, and a `+ Add account` login flow.
- **Remembered Account Persistence:** Active-account refreshes now upsert one signed cookie entry without wiping the other remembered accounts, so switching still works after reopening the browser.
- **Sidebar Layout:** Removed Streamlit column gutters and fixed sidebar containers to fluid sizing so the profile card, account selector, icon row, and navigation cards stay flush when the sidebar is resized.

QUEST is organised into a sidebar of sections:

| Section | What's inside |
|---|---|
| **Overview** | Live portfolio value (animated count-up), P&L, NIFTY 50 & SENSEX cards, risk score, invested/assets stats, a market-holiday calendar (with your Planner events), and your holdings as clean cards with inline **add / edit / remove** stock (auto-ticker lookup from a company name). |
| **Planner** | An editable **calendar** (add/remove events) + a **to-do list**. Events also show on the Overview calendar. |
| **Analytics** | Performance & visual analytics (allocation donut, correlation matrix) and the **Math Engine** (QR decomposition, eigenvalues, factor attribution). |
| **Projections** | Adaptive next-day forecast (EWMA) with confidence range and VaR. |
| **Insights** | AI-style buy/sell/hold recommendations and rebalancing suggestions. |
| **News** | Per-holding news + sentiment scoring. |
| **Activity** | Transaction ledger. |
| **Chat** | Person-to-person & group messaging. |
| **MICHAEL** | AI portfolio assistant — see below. |
| **Settings** | Profile, theme, password/security, and sign-out controls. |

### Risk analyzer (in the Overview → "View Risk Breakdown")
A composite **0–100 risk score** from weighted components (volatility, drawdown,
Sharpe, beta, VaR, RSI, distance from 200-DMA, concentration/HHI, correlation,
momentum, news sentiment), shown as a gauge + driver cards, with plain-English
"how to lower your score" actions.

### Compare & Analyze (a trader's toolkit, inside the Risk view)
- **Portfolio vs Market** — your 1-year return vs NIFTY 50 / SENSEX.
- **Compare stocks** — type 2+ company names → live web ticker lookup → normalized
  growth chart with **period** (1D–5Y + custom) and **chart type** (line / area /
  bar / candlestick with Bollinger Bands + moving averages), plus a table of
  Return %, Volatility, RSI, 50/200 cross, MACD, 52-week position, and a heuristic
  buy signal. Fundamentals (P/E, market cap, dividend yield, beta) too.

### MICHAEL — the AI assistant
- Runs on **Groq (Llama 3.3 70B)** — free, fast, no per-user key (one shared key
  in app secrets; users can optionally bring their own).
- **Sees** your portfolio, risk, predictions, news sentiment, and your Planner
  (events + to-dos).
- **Live tools** — calls `get_quote` (any stock's real-time price + indicators)
  and `get_index` (NIFTY/SENSEX/Bank Nifty) on demand, so it answers with real
  current data and can suggest + validate stock ideas.
- **Persistent memory** — the conversation is saved per user and reloaded across
  sessions. A daily-briefing starter ties your money to your schedule.
- Personality: a sharp, dry-witted Mumbai trading-desk veteran.

### Other foundations
- **Real-time-ish pricing** — NSE scraping during market hours with yfinance /
  cached / historical fallbacks; market-status aware (skips closed market & holidays).
- **Auto-updating NSE holiday calendar** (fetched + cached, with a hardcoded fallback).
- **Firebase auth** (email login, signup, password reset) + Firestore sync, so each
  user has their own isolated, cloud-backed portfolio.
- **Theme system** — calm light & refined dark, switchable in the sidebar.
- **"Try a live demo"** login button (sample portfolio, no signup).

---

## 🗂 Project structure

| File | Role |
|---|---|
| `app.py` | The Streamlit app — all sections/UI. |
| `ui_theme.py` | Design system: tokens, light/dark themes, components, CSS. |
| `risk_analyzer.py` | Risk metrics, scoring, price resolution, portfolio analysis. |
| `nse_live.py` | Live NSE prices, holiday calendar, circuit breaker, persistent cache. |
| `adaptive_engine.py` | EWMA self-learning forecast engine. |
| `portfolio_ledger.py` | Holdings + transactions + predictions persistence. |
| `news_sentiment.py` | News fetch (Yahoo) + sentiment scoring. |
| `firebase_db.py` / `firebase_sync.py` | Auth + Firestore sync. |
| `login_page.py` | Login / signup UI. |
| `quest_app/main.py` | Authenticated dashboard routing and sidebar. |
| `quest_app/settings.py` | Account Settings page and settings navigation. |
| `chat_system.py` | User-to-user / group chat. |
| `pdf_generator.py` | PDF report export. |
| `tests/test_nse_live.py` | Unit tests for the price/holiday/cache layer. |

---

## 🚀 Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Secrets go in `.streamlit/`:
- `firebase_key.json` — Firebase service account
- `firebase_web_api_key.txt` — Firebase Web API key
- `.streamlit/secrets.toml` → `GROQ_API_KEY = "gsk_..."` (free, from console.groq.com) to power MICHAEL for everyone

## ☁️ Deploy (Streamlit Community Cloud)

Push to GitHub → share.streamlit.io → pick the repo, branch `master`, `app.py`.
Add the same secrets in the app's **Secrets** panel (TOML):

```toml
firebase_web_api_key = "AIza..."
GROQ_API_KEY = "gsk_..."

[firebase]
type = "service_account"
project_id = "..."
# ...rest of the service-account fields
```

---

## ⚠️ Caveats (honest)
- Market data is from **yfinance / NSE scraping** — accurate end-of-day, ~15-min
  delayed intraday, and Yahoo can occasionally have a bad tick. Cross-check
  anything money-critical with your broker.
- The prediction engine is a **single-factor EWMA** — a real statistical model, but
  not ML and not a crystal ball. Treat forecasts and MICHAEL's "signals" as research,
  **not financial advice**.
- News is currently **Yahoo-only** (single source).
- On Streamlit Community Cloud the filesystem is ephemeral; user data is kept safe in
  **Firestore** and re-hydrated on load.

## 🛣 Roadmap
- Prediction engine **v2** — math + behavioural-economics + ML (LightGBM) + daily
  news + self-feedback, blended by recent accuracy; skip non-trading days.
- **Multi-source news** (beyond Yahoo).
- **Login page** mobile polish.
- Split `app.py` into modules.
- True **mobile** experience.

---

*Built by Aksharsimha (Last Updated: August 23, 2026). Research & education tool — not investment advice.*
