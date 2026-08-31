"""
QUEST Knowledge Library & Games/Education Section
=================================================
Matches pixel-perfect modern web app design with dedicated sidebar,
top search bar with profile controls, curated learning cards,
interactive reading modals, video player placeholders, and XP progression.
"""

import streamlit as st
import textwrap
import edu_db

# ──────────────────────────────────────────────────────────────────────────────
# Curated Knowledge Library Articles & Modules Data
# ──────────────────────────────────────────────────────────────────────────────

ARTICLES_DATA = [
    {
        "id": "glossary_trading_terms",
        "category": "BASICS",
        "cat_color": "#3b82f6",
        "cat_bg": "rgba(59, 130, 246, 0.12)",
        "title": "Glossary of Trading Terms",
        "summary": "Understand key trading terms and jargon used in the financial markets.",
        "read_time": "8 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #0b132b 0%, #1c2541 100%)",
        "svg_icon": "book_glow",
        "content": """
### 📖 Master the Essential Market Language

When navigating the Indian equities markets (NSE & BSE), knowing standard financial terminology is your first unfair advantage. Here are the core concepts every investor must know:

#### 1. Fundamental Metrics
- **P/E Ratio (Price to Earnings):** Measures a company's current share price relative to its per-share earnings. A high P/E could mean the stock is overvalued or investors anticipate rapid growth.
- **EPS (Earnings Per Share):** The portion of a company's profit allocated to each outstanding share of common stock.
- **Dividend Yield:** Financial ratio that shows how much a company pays out in dividends each year relative to its stock price.

#### 2. Market Dynamics
- **Market Capitalization:** Total dollar or rupee market value of a company's outstanding shares (Large-Cap > ₹20,000 Cr, Mid-Cap ₹5,000 - ₹20,000 Cr, Small-Cap < ₹5,000 Cr).
- **Liquidity:** The ease with which an asset can be rapidly bought or sold in the market without causing a drastic price impact.
- **Bull vs. Bear Market:** A Bull market represents sustained upward price momentum (+20% from lows), while a Bear market denotes persistent downward contraction (-20% from highs).
        """
    },
    {
        "id": "power_of_compounding",
        "category": "INVESTING",
        "cat_color": "#10b981",
        "cat_bg": "rgba(16, 185, 129, 0.12)",
        "title": "The Power of Compounding",
        "summary": "Learn how compounding can help your wealth grow exponentially.",
        "read_time": "6 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #062c1e 0%, #0d5c3a 100%)",
        "svg_icon": "plant_growth",
        "content": """
### 🌱 Compounding: The Eighth Wonder of the World

Compound interest is interest calculated on the initial principal, which also includes all of the accumulated interest from previous periods.

#### The Mathematical Formula
$$A = P \\left(1 + \\frac{r}{n}\\right)^{nt}$$

Where:
- **$A$** = the future value of the investment
- **$P$** = the principal investment amount
- **$r$** = annual interest rate (decimal)
- **$n$** = number of times interest is compounded per year
- **$t$** = time period in years

#### The Rule of 72
To estimate how many years it will take to double your investment:
$$\\text{Years to Double} \\approx \\frac{72}{\\text{Annual Return (\\%)}}$$
*Example:* At an average NIFTY 50 CAGR of 12%, your portfolio doubles roughly every **6 years**!
        """
    },
    {
        "id": "capital_gains_tax_guide",
        "category": "TAXES",
        "cat_color": "#f59e0b",
        "cat_bg": "rgba(245, 158, 11, 0.12)",
        "title": "A Guide to Capital Gains Tax",
        "summary": "Everything you need to know about capital gains tax in India.",
        "read_time": "7 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #2b1704 0%, #59350b 100%)",
        "svg_icon": "tax_calc",
        "content": """
### 📋 Indian Capital Gains Taxation Framework

Capital gains tax applies when you sell capital assets (equity shares, mutual funds, real estate, gold) at a profit.

#### 1. Listed Equity & Equity Mutual Funds
- **Short-Term Capital Gains (STCG):** Holding period $\\le 12$ months. Taxed at **20%** (Section 111A, Budget 2024 update).
- **Long-Term Capital Gains (LTCG):** Holding period $> 12$ months. Taxed at **12.5%** on gains exceeding **₹1.25 Lakh per financial year** (Section 112A).

#### 2. Key Tax Optimization Strategies
- **Tax-Loss Harvesting:** Realizing losses on underperforming stocks to offset taxable capital gains before the financial year ends on March 31.
- **₹1.25 Lakh Exemption Utilization:** Booking LTCG profits annually up to ₹1.25L tax-free and reinvesting.
        """
    },
    {
        "id": "support_resistance_levels",
        "category": "TRADING",
        "cat_color": "#8b5cf6",
        "cat_bg": "rgba(139, 92, 246, 0.12)",
        "title": "Support and Resistance Levels",
        "summary": "Identify key support and resistance levels to make better trading decisions.",
        "read_time": "5 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #1b0a2a 0%, #3b1d5a 100%)",
        "svg_icon": "candlestick_chart",
        "content": """
### 📈 Technical Analysis: Support & Resistance

Support and Resistance are price levels on a chart where price movement tends to pause or reverse due to concentration of demand or supply.

#### 1. Support Level (Floor)
- Price zone where buying pressure overcomes selling pressure, preventing the stock from falling further.
- **Psychological Drivers:** Value buyers step in, short sellers cover their positions.

#### 2. Resistance Level (Ceiling)
- Price zone where selling pressure overcomes buying pressure, capping further price gains.
- **Psychological Drivers:** Profit takers sell, trapped buyers from previous peaks exit at break-even.

#### 3. The Polarity Principle
When a strong resistance level is broken decisively with heavy volume, it flips to become a **new support level** on subsequent pullbacks.
        """
    },
    {
        "id": "build_emergency_fund",
        "category": "PERSONAL FINANCE",
        "cat_color": "#ec4899",
        "cat_bg": "rgba(236, 72, 153, 0.12)",
        "title": "Build an Emergency Fund",
        "summary": "Why an emergency fund is crucial and how to build one step by step.",
        "read_time": "6 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #2b0616 0%, #591638 100%)",
        "svg_icon": "phone_savings",
        "content": """
### 🛡️ Financial Shield: Emergency Fund Blueprint

An emergency fund is a stash of liquid money set aside to cover unforeseen financial surprises (job loss, medical emergency, critical repairs).

#### How Much Do You Need?
- **Salaried with stable job:** 3 to 6 months of mandatory living expenses (rent, EMI, food, utilities, insurance).
- **Self-employed / Freelancer:** 6 to 12 months of living expenses due to variable cash flows.

#### Where to Park Your Emergency Fund?
1. **High-Yield Savings Accounts:** Instant ATM access & liquidity.
2. **Liquid Mutual Funds:** T+1 redemption with indexation benefits & slightly higher yields than traditional savings.
3. **Sweep-in Fixed Deposits:** Instant liquidation without breakage penalties.
        """
    },
    {
        "id": "diversification_strategies",
        "category": "ADVANCED STRATEGIES",
        "cat_color": "#06b6d4",
        "cat_bg": "rgba(6, 182, 212, 0.12)",
        "title": "Diversification Strategies",
        "summary": "Reduce risk and maximize returns with smart diversification.",
        "read_time": "9 min read",
        "xp_reward": 50,
        "bg_gradient": "linear-gradient(135deg, #04242b 0%, #0d4a58 100%)",
        "svg_icon": "compass_map",
        "content": """
### 🧭 Modern Portfolio Theory & Asset Allocation

Diversification is the practice of spreading investments across various financial instruments, industries, and asset classes to minimize total risk.

#### The Free Lunch in Finance
As Nobel laureate Harry Markowitz demonstrated, combining non-correlated assets allows an investor to **reduce portfolio volatility without sacrificing expected returns**.

#### Multi-Dimensional Diversification Framework
1. **Asset Class Diversification:** Equities (Growth), Sovereign Debt/Bonds (Stability), Gold/REITs (Inflation Hedge).
2. **Sectoral Balance:** Avoid over-weighting in a single industry (e.g., keeping IT, Banking, FMCG, Pharma, Energy well-balanced).
3. **Geographic Diversification:** Allocating 10-15% into international equities (e.g., US S&P 500 / Nasdaq 100) to mitigate domestic sovereign risk.
        """
    }
]


# ──────────────────────────────────────────────────────────────────────────────
# Thumbnail Renderers (Pure SVG Icons matching mockup aesthetic)
# ──────────────────────────────────────────────────────────────────────────────

def _render_card_svg(icon_type: str) -> str:
    if icon_type == "book_glow":
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="bookBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#091024"/>
                    <stop offset="100%" stop-color="#141e3c"/>
                </linearGradient>
                <radialGradient id="glow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
                    <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
                </radialGradient>
            </defs>
            <rect width="400" height="200" fill="url(#bookBg)"/>
            <circle cx="200" cy="110" r="90" fill="url(#glow)"/>
            <!-- Open Book -->
            <path d="M 120 140 Q 160 130 200 135 Q 240 130 280 140 L 280 95 Q 240 85 200 90 Q 160 85 120 95 Z" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
            <path d="M 200 90 L 200 135" stroke="#38bdf8" stroke-width="2"/>
            <!-- Floating Glowing Keywords -->
            <text x="145" y="65" fill="#38bdf8" font-size="11" font-weight="700" opacity="0.85" font-family="Inter,sans-serif">IPO</text>
            <text x="220" y="65" fill="#818cf8" font-size="11" font-weight="700" opacity="0.85" font-family="Inter,sans-serif">Bull Market</text>
            <text x="110" y="90" fill="#94a3b8" font-size="10" font-weight="600" opacity="0.75" font-family="Inter,sans-serif">P/E Ratio</text>
            <text x="260" y="90" fill="#34d399" font-size="10" font-weight="600" opacity="0.75" font-family="Inter,sans-serif">Liquidity</text>
            <text x="140" y="115" fill="#a78bfa" font-size="9" font-weight="600" opacity="0.8" font-family="Inter,sans-serif">Dividend</text>
            <text x="235" y="115" fill="#f472b6" font-size="9" font-weight="600" opacity="0.8" font-family="Inter,sans-serif">Volatility</text>
            <text x="175" y="155" fill="#67e8f9" font-size="10" font-weight="600" opacity="0.9" font-family="Inter,sans-serif">Asset Allocation</text>
        </svg>
        """
    elif icon_type == "plant_growth":
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="plantBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#052217"/>
                    <stop offset="100%" stop-color="#0d422f"/>
                </linearGradient>
            </defs>
            <rect width="400" height="200" fill="url(#plantBg)"/>
            <!-- Jar with coins -->
            <rect x="165" y="90" width="70" height="75" rx="8" fill="rgba(255,255,255,0.08)" stroke="#10b981" stroke-width="1.5"/>
            <!-- Coins stack -->
            <ellipse cx="200" cy="145" rx="25" ry="7" fill="#fbbf24"/>
            <ellipse cx="200" cy="135" rx="25" ry="7" fill="#f59e0b"/>
            <ellipse cx="200" cy="125" rx="25" ry="7" fill="#fbbf24"/>
            <ellipse cx="200" cy="115" rx="25" ry="7" fill="#fef08a"/>
            <!-- Sprouting Seedling -->
            <path d="M 200 90 Q 200 55 195 45" stroke="#34d399" stroke-width="3.5" fill="none" stroke-linecap="round"/>
            <path d="M 195 55 Q 175 40 180 30 Q 195 35 195 55 Z" fill="#10b981"/>
            <path d="M 198 50 Q 220 38 215 28 Q 200 32 198 50 Z" fill="#34d399"/>
            <!-- Upward compound curve -->
            <path d="M 80 150 Q 200 135 320 40" stroke="#10b981" stroke-width="2.5" stroke-dasharray="4,4" fill="none" opacity="0.6"/>
            <circle cx="320" cy="40" r="4" fill="#34d399"/>
        </svg>
        """
    elif icon_type == "tax_calc":
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="taxBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#1f1406"/>
                    <stop offset="100%" stop-color="#3d2407"/>
                </linearGradient>
            </defs>
            <rect width="400" height="200" fill="url(#taxBg)"/>
            <!-- Document Notepad -->
            <rect x="180" y="35" width="130" height="135" rx="6" fill="#f8fafc" stroke="#f59e0b" stroke-width="1.5"/>
            <!-- Notepad Rings -->
            <circle cx="195" cy="42" r="3" fill="#cbd5e1"/>
            <circle cx="215" cy="42" r="3" fill="#cbd5e1"/>
            <circle cx="235" cy="42" r="3" fill="#cbd5e1"/>
            <circle cx="255" cy="42" r="3" fill="#cbd5e1"/>
            <circle cx="275" cy="42" r="3" fill="#cbd5e1"/>
            <circle cx="295" cy="42" r="3" fill="#cbd5e1"/>
            <text x="210" y="105" fill="#0f172a" font-size="28" font-weight="900" font-family="Inter,sans-serif" letter-spacing="2">TAX</text>
            <!-- Calculator on Left -->
            <rect x="90" y="60" width="75" height="105" rx="8" fill="#1e293b" stroke="#f59e0b" stroke-width="1.5"/>
            <rect x="100" y="70" width="55" height="20" rx="3" fill="#0f172a"/>
            <text x="145" y="85" fill="#f59e0b" font-size="11" font-weight="700" text-anchor="end" font-family="monospace">12.5%</text>
            <!-- Buttons -->
            <circle cx="108" cy="105" r="4" fill="#475569"/>
            <circle cx="127" cy="105" r="4" fill="#475569"/>
            <circle cx="146" cy="105" r="4" fill="#475569"/>
            <circle cx="108" cy="122" r="4" fill="#475569"/>
            <circle cx="127" cy="122" r="4" fill="#475569"/>
            <circle cx="146" cy="122" r="4" fill="#475569"/>
            <circle cx="108" cy="139" r="4" fill="#475569"/>
            <circle cx="127" cy="139" r="4" fill="#475569"/>
            <circle cx="146" cy="139" r="4" fill="#f59e0b"/>
        </svg>
        """
    elif icon_type == "candlestick_chart":
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="chartBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#120822"/>
                    <stop offset="100%" stop-color="#261044"/>
                </linearGradient>
            </defs>
            <rect width="400" height="200" fill="url(#chartBg)"/>
            <!-- Grid lines -->
            <line x1="50" y1="50" x2="350" y2="50" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
            <line x1="50" y1="100" x2="350" y2="100" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
            <line x1="50" y1="150" x2="350" y2="150" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
            <!-- Resistance Line -->
            <line x1="60" y1="65" x2="340" y2="65" stroke="#f43f5e" stroke-width="1.5" stroke-dasharray="5,5"/>
            <text x="345" y="69" fill="#f43f5e" font-size="9" font-weight="700" font-family="Inter,sans-serif">Resistance</text>
            <!-- Support Line -->
            <line x1="60" y1="140" x2="340" y2="140" stroke="#06b6d4" stroke-width="1.5" stroke-dasharray="5,5"/>
            <text x="345" y="144" fill="#06b6d4" font-size="9" font-weight="700" font-family="Inter,sans-serif">Support</text>
            <!-- Candlesticks -->
            <!-- 1 Bull -->
            <line x1="90" y1="110" x2="90" y2="145" stroke="#10b981" stroke-width="1.5"/>
            <rect x="84" y="118" width="12" height="20" fill="#10b981" rx="1"/>
            <!-- 2 Bear -->
            <line x1="120" y1="105" x2="120" y2="135" stroke="#f43f5e" stroke-width="1.5"/>
            <rect x="114" y="110" width="12" height="18" fill="#f43f5e" rx="1"/>
            <!-- 3 Bull (Bounce from support) -->
            <line x1="150" y1="125" x2="150" y2="150" stroke="#10b981" stroke-width="1.5"/>
            <rect x="144" y="130" width="12" height="15" fill="#10b981" rx="1"/>
            <!-- 4 Big Bull -->
            <line x1="180" y1="85" x2="180" y2="135" stroke="#10b981" stroke-width="1.5"/>
            <rect x="174" y="90" width="12" height="38" fill="#10b981" rx="1"/>
            <!-- 5 Bull (Reaching resistance) -->
            <line x1="210" y1="60" x2="210" y2="105" stroke="#10b981" stroke-width="1.5"/>
            <rect x="204" y="65" width="12" height="30" fill="#10b981" rx="1"/>
            <!-- 6 Bear (Rejection from resistance) -->
            <line x1="240" y1="60" x2="240" y2="110" stroke="#f43f5e" stroke-width="1.5"/>
            <rect x="234" y="68" width="12" height="28" fill="#f43f5e" rx="1"/>
            <!-- 7 Bear -->
            <line x1="270" y1="88" x2="270" y2="125" stroke="#f43f5e" stroke-width="1.5"/>
            <rect x="264" y="92" width="12" height="24" fill="#f43f5e" rx="1"/>
        </svg>
        """
    elif icon_type == "phone_savings":
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="phoneBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#240715"/>
                    <stop offset="100%" stop-color="#4a0e2a"/>
                </linearGradient>
            </defs>
            <rect width="400" height="200" fill="url(#phoneBg)"/>
            <!-- Phone frame -->
            <rect x="145" y="25" width="110" height="160" rx="16" fill="#0f172a" stroke="#ec4899" stroke-width="2"/>
            <rect x="180" y="32" width="40" height="4" rx="2" fill="#334155"/>
            <!-- Donut Chart Inside Phone -->
            <circle cx="200" cy="90" r="30" fill="none" stroke="#334155" stroke-width="10"/>
            <circle cx="200" cy="90" r="30" fill="none" stroke="#ec4899" stroke-width="10" stroke-dasharray="90 190" stroke-linecap="round"/>
            <circle cx="200" cy="90" r="30" fill="none" stroke="#38bdf8" stroke-width="10" stroke-dasharray="50 190" stroke-dashoffset="-90" stroke-linecap="round"/>
            <circle cx="200" cy="90" r="30" fill="none" stroke="#10b981" stroke-width="10" stroke-dasharray="40 190" stroke-dashoffset="-140" stroke-linecap="round"/>
            <!-- Emergency Fund Shield -->
            <rect x="160" y="135" width="80" height="28" rx="6" fill="rgba(236,72,153,0.15)" stroke="#ec4899" stroke-width="1"/>
            <text x="200" y="152" fill="#f472b6" font-size="9" font-weight="700" text-anchor="middle" font-family="Inter,sans-serif">🛡️ 6 Mo Fund</text>
        </svg>
        """
    else:  # compass_map
        return """
        <svg viewBox="0 0 400 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:12px 12px 0 0;">
            <defs>
                <linearGradient id="compBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#031d24"/>
                    <stop offset="100%" stop-color="#0a3d4a"/>
                </linearGradient>
            </defs>
            <rect width="400" height="200" fill="url(#compBg)"/>
            <!-- Globe / Map circles -->
            <circle cx="200" cy="100" r="75" fill="none" stroke="rgba(6,182,212,0.2)" stroke-width="1"/>
            <ellipse cx="200" cy="100" rx="75" ry="30" fill="none" stroke="rgba(6,182,212,0.15)" stroke-width="1"/>
            <ellipse cx="200" cy="100" rx="35" ry="75" fill="none" stroke="rgba(6,182,212,0.15)" stroke-width="1"/>
            <!-- Compass Outer Ring -->
            <circle cx="200" cy="100" r="50" fill="rgba(15,23,42,0.85)" stroke="#06b6d4" stroke-width="2.5"/>
            <circle cx="200" cy="100" r="42" fill="none" stroke="#22d3ee" stroke-width="1" stroke-dasharray="3,3"/>
            <!-- Needle -->
            <polygon points="200,60 206,100 194,100" fill="#ef4444"/>
            <polygon points="200,140 206,100 194,100" fill="#94a3b8"/>
            <circle cx="200" cy="100" r="4" fill="#0f172a" stroke="#06b6d4" stroke-width="1.5"/>
            <!-- Direction markers -->
            <text x="200" y="55" fill="#06b6d4" font-size="8" font-weight="700" text-anchor="middle" font-family="Inter,sans-serif">N</text>
            <text x="200" y="152" fill="#94a3b8" font-size="8" font-weight="700" text-anchor="middle" font-family="Inter,sans-serif">S</text>
            <text x="248" y="103" fill="#94a3b8" font-size="8" font-weight="700" text-anchor="middle" font-family="Inter,sans-serif">E</text>
            <text x="152" y="103" fill="#94a3b8" font-size="8" font-weight="700" text-anchor="middle" font-family="Inter,sans-serif">W</text>
        </svg>
        """


# ──────────────────────────────────────────────────────────────────────────────
# Article Reader Dialog with Video Placeholder & XP Reward
# ──────────────────────────────────────────────────────────────────────────────

@st.dialog("📚 Knowledge Library Module")
def _show_article_dialog(article_dict):
    art_id = article_dict["id"]
    title = article_dict["title"]
    category = article_dict["category"]
    cat_color = article_dict["cat_color"]
    read_time = article_dict["read_time"]
    content = article_dict["content"]
    xp_award = article_dict.get("xp_reward", 50)
    
    prog = edu_db.load_progress()
    is_completed = art_id in prog.get("completed_articles", [])
    is_bookmarked = art_id in prog.get("bookmarks", [])

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-size:0.75rem;font-weight:700;background:{article_dict['cat_bg']};color:{cat_color};padding:3px 10px;border-radius:12px;">{category}</span>
        <span style="font-size:0.8rem;color:var(--q-text-3);">⏱ {read_time}</span>
    </div>
    <h2 style="margin:0 0 10px;color:var(--q-text);font-size:1.4rem;">{title}</h2>
    """, unsafe_allow_html=True)

    # Video Player Container Placeholder
    st.markdown(textwrap.dedent("""
    <div style="background:rgba(0,0,0,0.3);border:1.5px dashed rgba(112,126,171,0.25);border-radius:12px;padding:24px;text-align:center;margin:12px 0 16px;">
        <div style="width:48px;height:48px;border-radius:50%;background:rgba(99,102,241,0.2);color:#818cf8;display:inline-flex;align-items:center;justify-content:center;font-size:1.4rem;margin-bottom:6px;">▶</div>
        <div style="font-weight:600;font-size:0.95rem;color:var(--q-text);">Video Lecture Attached to this Module</div>
        <div style="font-size:0.78rem;color:var(--q-text-3);margin-top:2px;">You can provide video links anytime to attach direct video streams here.</div>
    </div>
    """), unsafe_allow_html=True)

    # Article Text
    st.markdown(content)

    st.markdown("<hr style='border:0;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

    # Interactive Action Buttons
    c_btn1, c_btn2 = st.columns([1.5, 1])
    with c_btn1:
        if is_completed:
            st.success(f"✅ Completed (+{xp_award} XP Claimed)")
        else:
            if st.button(f"Mark as Completed (+{xp_award} XP) 🎓", key=f"btn_comp_{art_id}", type="primary", use_container_width=True):
                new_xp = edu_db.complete_article(art_id, xp_award)
                st.toast(f"🎉 Awesome! You earned +{xp_award} XP. Total XP: {new_xp}", icon="⭐")
                st.rerun()

    with c_btn2:
        bm_label = "★ Bookmarked" if is_bookmarked else "☆ Bookmark"
        if st.button(bm_label, key=f"btn_bm_{art_id}", use_container_width=True):
            now_bm = edu_db.toggle_bookmark(art_id)
            if now_bm:
                st.toast("Saved to your bookmarks! 🔖")
            else:
                st.toast("Removed from bookmarks.")
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Main Knowledge Library Render Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def render(user_info):
    prog = edu_db.load_progress()
    user_xp = prog.get("total_xp", 0)
    user_lvl = prog.get("current_level", "Level 1")
    user_bookmarks = set(prog.get("bookmarks", []))

    # ══════════════════════════════════════════════════════════════════════════
    # Custom CSS: Minimalist Sidebar & Knowledge Library Theme
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <style>
        /* Knowledge Library Header Styling */
        .kl-title {
            font-size: 1.85rem;
            font-weight: 800;
            color: var(--q-text);
            margin: 0 0 4px 0;
            letter-spacing: -0.5px;
        }
        .kl-subtitle {
            font-size: 0.95rem;
            color: var(--q-text-3);
            margin: 0 0 20px 0;
        }

        /* Top Bar Styling */
        .kl-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .kl-search-box {
            display: flex;
            align-items: center;
            background: var(--q-surface-2);
            border: 1px solid var(--q-border);
            border-radius: 10px;
            padding: 8px 14px;
            flex-grow: 1;
            max-width: 600px;
        }
        .kl-search-shortcut {
            font-size: 0.72rem;
            background: rgba(255,255,255,0.06);
            color: var(--q-text-3);
            border-radius: 4px;
            padding: 2px 6px;
            font-family: monospace;
            margin-left: auto;
        }

        /* Article Card Styles */
        .kl-card {
            background: var(--q-surface);
            border: 1px solid var(--q-border);
            border-radius: 14px;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
            margin-bottom: 16px;
        }
        .kl-card:hover {
            transform: translateY(-3px);
            border-color: rgba(99,102,241,0.4);
            box-shadow: 0 10px 24px -10px rgba(0,0,0,0.5);
        }
        .kl-card-body {
            padding: 14px 16px 16px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }
        .kl-card-cat {
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }
        .kl-card-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--q-text);
            margin: 0 0 6px 0;
            line-height: 1.35;
        }
        .kl-card-desc {
            font-size: 0.82rem;
            color: var(--q-text-2);
            line-height: 1.45;
            margin: 0 0 14px 0;
            flex-grow: 1;
        }
        .kl-card-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.78rem;
            color: var(--q-text-3);
            border-top: 1px solid rgba(255,255,255,0.04);
            padding-top: 10px;
        }

        /* Sidebar Logo */
        .kl-sidebar-logo {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 4px 18px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            margin-bottom: 16px;
        }
        .kl-logo-circle {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            color: #fff;
            font-size: 1.1rem;
        }
    </style>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # User XP Stats Card in Sidebar (Matching Image 1)
    # ══════════════════════════════════════════════════════════════════════════
    st.sidebar.markdown(f"""
    <div style="background:var(--q-surface-2);border:1px solid var(--q-border);border-radius:10px;padding:12px;margin:12px 0;">
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--q-text-3);margin-bottom:4px;">
            <span>YOUR PROGRESS</span>
            <span style="color:#facc15;font-weight:700;">⭐ {user_xp} XP</span>
        </div>
        <div style="font-size:0.85rem;font-weight:600;color:var(--q-text);">Rank: {user_lvl}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("💼 Portfolio Dashboard", key="btn_back_portfolio", use_container_width=True):
        st.query_params["workspace"] = "professional"
        st.query_params["page"] = "Overview"
        st.rerun()

    if st.sidebar.button("🏠 Switch to Hub", key="btn_back_hub", use_container_width=True):
        st.query_params["page"] = "Hub"
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # Top Navigation Bar (Search + Notification + Profile matching Image 1)
    # ══════════════════════════════════════════════════════════════════════════
    top_col_search, top_col_profile = st.columns([3, 1])

    with top_col_search:
        search_query = st.text_input(
            "Search Knowledge Library",
            placeholder="🔍  Search for articles, topics, or keywords...  (⌘ K)",
            key="kl_search_input",
            label_visibility="collapsed"
        )

    with top_col_profile:
        _dname = user_info.get("display_name", "User")
        _av = user_info.get("avatar")
        _av_tag = f'<img src="{_av}" style="width:30px;height:30px;border-radius:50%;object-fit:cover;">' if _av else f'<div style="width:30px;height:30px;border-radius:50%;background:#3b82f6;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:0.85rem;">{_dname[:1].upper()}</div>'
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:flex-end;gap:12px;padding-top:4px;">
            <span style="font-size:1.15rem;color:var(--q-text-2);cursor:pointer;" title="Notifications">🔔</span>
            <div style="display:flex;align-items:center;gap:6px;">
                {_av_tag}
                <span style="font-size:0.85rem;font-weight:600;color:var(--q-text);">{_dname}</span>
                <span style="font-size:0.75rem;color:var(--q-text-3);">▼</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # View 1: Knowledge Library (Matching Image 1)
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # Knowledge Library Main View (Matching Image 1)
    # ══════════════════════════════════════════════════════════════════════════
    # Header + Sort Filter
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown("""
        <div class="kl-title">Knowledge Library</div>
        <div class="kl-subtitle">Learn. Grow. Make smarter financial decisions.</div>
        """, unsafe_allow_html=True)
    with h_col2:
        sort_filter = st.selectbox(
            "Filter",
            ["Latest", "All Categories", "BASICS", "INVESTING", "TAXES", "TRADING", "PERSONAL FINANCE", "ADVANCED STRATEGIES", "Bookmarked 🔖"],
            key="kl_sort_filter",
            label_visibility="collapsed"
        )

    # Filter Articles
    filtered_articles = ARTICLES_DATA
    if sort_filter == "Bookmarked 🔖":
        filtered_articles = [a for a in filtered_articles if a["id"] in user_bookmarks]
    elif sort_filter != "Latest" and sort_filter != "All Categories":
        filtered_articles = [a for a in filtered_articles if a["category"] == sort_filter]

    if search_query and search_query.strip():
        sq = search_query.strip().lower()
        filtered_articles = [
            a for a in filtered_articles
            if sq in a["title"].lower()
            or sq in a["summary"].lower()
            or sq in a["category"].lower()
            or sq in a["content"].lower()
        ]

    # ── 6 Card Grid (2 Rows x 3 Columns) ──────────────────────────────────
    if not filtered_articles:
        st.info("No learning modules found matching your search or filters.")
    else:
        # Chunk into rows of 3
        rows = [filtered_articles[i:i + 3] for i in range(0, len(filtered_articles), 3)]
        for r_idx, row in enumerate(rows):
            cols = st.columns(3, gap="medium")
            for c_idx, art in enumerate(row):
                with cols[c_idx]:
                    art_id = art["id"]
                    cat = art["category"]
                    cat_color = art["cat_color"]
                    cat_bg = art["cat_bg"]
                    title = art["title"]
                    summary = art["summary"]
                    read_time = art["read_time"]
                    svg_code = _render_card_svg(art["svg_icon"])
                    is_bm = art_id in user_bookmarks
                    bm_icon = "🔖" if is_bm else "☆"

                    # Render card visual & metadata
                    st.markdown(textwrap.dedent(f"""
                    <div class="kl-card">
                        <div style="height:150px;width:100%;overflow:hidden;background:#0b1120;">
                            {svg_code}
                        </div>
                        <div class="kl-card-body">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                <span class="kl-card-cat" style="color:{cat_color};background:{cat_bg};padding:3px 8px;border-radius:6px;">{cat}</span>
                                <span style="font-size:0.9rem;cursor:pointer;" title="Bookmark">{bm_icon}</span>
                            </div>
                            <div class="kl-card-title">{title}</div>
                            <div class="kl-card-desc">{summary}</div>
                            <div class="kl-card-footer">
                                <span>⏱ {read_time}</span>
                                <span style="color:var(--q-accent);font-weight:600;">+50 XP</span>
                            </div>
                        </div>
                    </div>
                    """), unsafe_allow_html=True)

                    # Clickable Read Button below card
                    if st.button(f"Read Module →", key=f"btn_open_{art_id}", use_container_width=True):
                        _show_article_dialog(art)

    # ── Bottom Pagination Bar (Matching Image 1) ──────────────────────────
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    pag_col1, pag_col2 = st.columns([1.5, 2])
    with pag_col1:
        st.markdown(f"<span style='color:var(--q-text-3);font-size:0.85rem;'>Showing <strong>1-{len(filtered_articles)}</strong> of <strong>128</strong> articles</span>", unsafe_allow_html=True)
    with pag_col2:
        st.markdown("""
        <div style="display:flex;justify-content:flex-end;align-items:center;gap:6px;font-size:0.82rem;">
            <span style="padding:4px 8px;border-radius:6px;border:1px solid var(--q-border);color:var(--q-text-3);cursor:pointer;">&lt;</span>
            <span style="padding:4px 10px;border-radius:6px;background:rgba(99,102,241,0.2);color:#818cf8;font-weight:700;">1</span>
            <span style="padding:4px 10px;border-radius:6px;border:1px solid var(--q-border);color:var(--q-text-2);cursor:pointer;">2</span>
            <span style="padding:4px 10px;border-radius:6px;border:1px solid var(--q-border);color:var(--q-text-2);cursor:pointer;">3</span>
            <span style="color:var(--q-text-3);padding:0 4px;">...</span>
            <span style="padding:4px 10px;border-radius:6px;border:1px solid var(--q-border);color:var(--q-text-2);cursor:pointer;">22</span>
            <span style="padding:4px 8px;border-radius:6px;border:1px solid var(--q-border);color:var(--q-text-3);cursor:pointer;">&gt;</span>
        </div>
        """, unsafe_allow_html=True)
