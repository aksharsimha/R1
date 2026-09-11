"""Premium, functional paper-trading terminal for QUEST."""

import base64
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import edu_db
import virtual_trading as engine


def _money(value):
    return f"₹{float(value):,.2f}"


def _signed_money(value):
    value = float(value)
    return f"{'+' if value >= 0 else '-'}₹{abs(value):,.2f}"


def _render_css():
    st.markdown("""
    <style>
    .vt-wrap { max-width: 1480px; margin: 0 auto; }
    .vt-hero { padding: 22px 0 18px; }
    .vt-eyebrow { color: var(--q-pos); font-size: .72rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
    .vt-hero h1 { margin: 5px 0 3px; color: var(--q-text); font-size: 2.2rem; letter-spacing: -.04em; }
    .vt-hero p { margin: 0; color: var(--q-text-3); font-size: 1rem; }
    .vt-card { background: var(--q-surface); border: 1px solid var(--q-border); border-radius: 10px; padding: 20px; box-shadow: 0 14px 32px rgba(0, 0, 0, .2), inset 0 1px 0 rgba(255,255,255,.04); }
    .vt-wallet { border-color: var(--q-pos); background: var(--q-surface-2); }
    .vt-label { color: var(--q-text-2); font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
    .vt-big { color: var(--q-text); font-size: 2.2rem; font-weight: 800; margin: 7px 0; }
    .vt-muted { color: var(--q-text-3); font-size: .84rem; }
    .vt-kpi { min-height: 105px; }
    .vt-kpi-value { color: var(--q-text); font-size: 1.28rem; font-weight: 750; margin-top: 9px; }
    .vt-section { color: var(--q-text); font-size: 1.2rem; font-weight: 750; margin: 25px 0 11px; }
    .vt-stock { background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: 10px; padding: 13px; min-height: 90px; box-shadow: inset 0 1px 0 rgba(255,255,255,.035); }
    .vt-stock strong { color: var(--q-text); display: block; font-size: 1rem; }
    .vt-stock span { color: var(--q-text-2); font-size: .8rem; }
    .vt-logo { width: 32px; height: 32px; border-radius: 50%; object-fit: contain; background: #ffffff; vertical-align: middle; margin-right: 8px; padding: 2px; box-shadow: 0 2px 4px rgba(0,0,0,0.25); }
    .vt-logo-fallback { display: none; width: 32px; height: 32px; align-items: center; justify-content: center; border-radius: 50%; margin-right: 8px; color: #fff; background: linear-gradient(135deg, #6366f1, var(--q-pos)); font-size: .75rem; font-weight: 800; vertical-align: middle; }
    .vt-sentiment { margin-top: 18px; padding: 15px 4px 2px; border-top: 1px solid var(--q-border); }
    .vt-sentiment strong { display: block; font-size: 1.18rem; margin: 5px 0 10px; }
    .vt-sentiment-track { position: relative; display: flex; gap: 4px; align-items: center; height: 34px; border-radius: 5px; background: linear-gradient(90deg, #ef4444 0%, #fb7185 30%, #fbbf24 50%, #34d399 70%, #16a34a 100%); }
    .vt-sentiment-track i { display: block; flex: 1; height: 27px; border-radius: 5px; background: transparent; }
    .vt-sentiment-track b { position: absolute; bottom: -6px; width: 0; height: 0; transform: translateX(-50%); border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 12px solid var(--q-text); filter: drop-shadow(0 0 4px rgba(255,255,255,.35)); }
    .vt-sentiment-legend { display: flex; justify-content: space-between; color: var(--q-text-3); font-size: .72rem; margin-top: 8px; }
    .vt-event { display: grid; grid-template-columns: 78px 26px 1fr auto; align-items: center; gap: 8px; padding: 7px 10px; margin-bottom: 5px; background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: 11px; }
    .vt-event-date { color: var(--q-text-3); font-size: .68rem; }
    .vt-event-icon { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 8px; background: var(--q-accent-weak); font-size: .8rem; }
    .vt-event-copy strong { display: block; color: var(--q-text); font-size: .78rem; }
    .vt-event-copy span { color: var(--q-text-3); font-size: .67rem; }
    .vt-event-copy a { color: var(--q-text); text-decoration: none; }
    .vt-event-detail { color: var(--q-text-2); font-size: .77rem; text-align: right; }
    .vt-positive { color: var(--q-pos) !important; }
    .vt-negative { color: var(--q-neg) !important; }
    .vt-divider { border-top: 1px solid var(--q-border); margin: 16px 0; }
    div[data-testid="stForm"] { border: 0; padding: 0; }
    .vt-card, .vt-stock, div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stDataFrame"] { border-radius: 18px !important; overflow: hidden; }
    .stButton > button, .stTextInput input, .stSelectbox [data-baseweb="select"], .stNumberInput input { border-radius: 8px !important; }
    @media (max-width: 800px) { .vt-hero h1 { font-size: 1.8rem; } .vt-big { font-size: 1.75rem; } }
    </style>
    """, unsafe_allow_html=True)


def _metric_card(label, value, sub="", tone=""):
    st.markdown(f"<div class='vt-card vt-kpi'><div class='vt-label'>{label}</div><div class='vt-kpi-value {tone}'>{value}</div><div class='vt-muted'>{sub}</div></div>", unsafe_allow_html=True)


def _logo_markup(symbol, quote=None):
    symbol = str(symbol or "?").upper().replace(".NS", "").replace(".BO", "").strip()
    initials = symbol[:2]
    logo_url = (quote or {}).get("logo_url", "")
    if not logo_url:
        try:
            logo_url = engine._get_logo_url(symbol)
        except Exception:
            logo_url = ""
    fallback = f"<span class='vt-logo-fallback'>{initials}</span>"
    image = f"<img class='vt-logo' src='{logo_url}' alt='' onerror=\"this.style.display='none';this.nextElementSibling.style.display='inline-flex'\">" if logo_url else ""
    if not image:
        fallback = f"<span class='vt-logo-fallback' style='display:inline-flex'>{initials}</span>"
    return f"{image}{fallback}"


def _selected_symbol(account):
    default = next(iter(account.get("holdings", {})), "RELIANCE")
    selected = st.session_state.get("gm_symbol", default)
    st.session_state.gm_symbol = selected
    return selected


def _sync_shared_balance(account):
    progress = edu_db.load_progress()
    account["cash"] = float(progress.get("virtual_balance", 15000.0))
    return account


def _save_shared_balance(account, previous_cash):
    progress = edu_db.load_progress()
    progress["virtual_balance"] = float(progress.get("virtual_balance", 15000.0)) + float(account["cash"]) - float(previous_cash)
    edu_db.save_progress(progress)


def _render_holdings(account, prefetched=None):
    st.markdown("<div class='vt-section'>💼 Your holdings</div>", unsafe_allow_html=True)
    holdings = account.get("holdings", {})
    if not holdings:
        st.markdown("<div class='vt-card'><h3>🌱 Your portfolio is ready</h3><p class='vt-muted'>You have ₹15,000 of virtual capital. Search for a stock below and start your first paper trade.</p></div>", unsafe_allow_html=True)
        return
    cols = st.columns(min(4, max(1, len(holdings))))
    for index, (symbol, holding) in enumerate(holdings.items()):
        quote = (prefetched or {}).get(symbol) or engine.get_quote(symbol)
        if not quote:
            continue
        quantity = float(holding.get("quantity", 0))
        invested = quantity * float(holding.get("average_cost", 0))
        pnl = quantity * (quote["price"] - float(holding.get("average_cost", 0)))
        tone = "vt-positive" if pnl >= 0 else "vt-negative"
        with cols[index % len(cols)]:
            st.markdown(f"<div class='vt-stock'><strong>{_logo_markup(symbol, quote)}{symbol}</strong><span>{quantity:g} shares · {_money(quote['price'])}</span><br><span class='{tone}'>{_signed_money(pnl)} · {pnl / invested * 100 if invested else 0:+.2f}%</span></div>", unsafe_allow_html=True)
            if st.button("View", key=f"vt_view_{symbol}", use_container_width=True):
                st.session_state.gm_symbol = symbol
                st.session_state.vt_order_side = "BUY"
                st.rerun()


def _render_buy_search():
    st.markdown("<div class='vt-section'>🌎 Discover US & Global Stocks</div>", unsafe_allow_html=True)
    query = st.text_input("Search company name or ticker", placeholder="Try Apple, Tesla, NVIDIA, Microsoft...", key="gm_stock_query").strip()
    if not query:
        st.caption("Search when you are ready to buy. Your portfolio is already above. 🌎")
        return
    matches = engine.search_stocks(query, region="US")
    if not matches:
        st.info("No international stock matched that company name yet.")
        return
    selected_label = st.selectbox(
        "Choose a US security",
        [f"{m['symbol']} - {m['company']}" for m in matches],
        key="gm_stock_select"
    )
    symbol = selected_label.split(" - ")[0]
    
    # We fetch the quote directly to show the USD equivalent too.
    quote = engine.get_quote(symbol)
    rate = quote.get("_exchange_rate", 83.5) if quote else 83.5
    st.info(f"💱 **Live Exchange Rate Applied:** 1 USD = ₹{rate:.2f}")

    if st.button("Trade this stock", type="primary", use_container_width=True, key="gm_trade_btn"):
        st.session_state.gm_symbol = symbol
        st.session_state.vt_order_side = "BUY"
        st.rerun()


def _render_chart(symbol, quote):
    st.markdown(f"<div class='vt-section'>📊 {symbol} · {quote.get('exchange', 'NSE')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='vt-card'><div class='vt-label'>Yahoo Finance last price</div><div class='vt-big'>{_money(quote['price'])}</div><div class='{'vt-positive' if quote['change_pct'] >= 0 else 'vt-negative'}'>{quote['change']:+.2f} · {quote['change_pct']:+.2f}%</div>", unsafe_allow_html=True)
    updated_at = quote.get("updated_at", "").replace("T", " ").split(".", 1)[0]
    st.caption(f"Last updated: {updated_at} IST · Source: {quote.get('source', 'Yahoo Finance')}")
    period = st.segmented_control("Chart range", ["1D", "1W", "1M", "3M", "6M", "1Y", "5Y"], default="1M", key="vt_chart_period")
    points = engine.get_cached_chart(symbol, period)
    if not points:
        st.warning("Market history is temporarily unavailable from Yahoo Finance.")
    else:
        fig = go.Figure(go.Scatter(x=[point["time"] for point in points], y=[point["price"] for point in points], mode="lines", line={"color": "#a78bfa", "width": 2.5}, fill="tozeroy", fillcolor="rgba(167,139,250,.08)", hovertemplate="%{x}<br>₹%{y:,.2f}<extra></extra>"))
        fig.update_layout(height=310, margin={"l": 0, "r": 0, "t": 12, "b": 0}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis={"showgrid": False, "nticks": 5}, yaxis={"showgrid": True, "gridcolor": "rgba(148,163,184,.1)", "tickprefix": "₹"}, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_sentiment(points)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_events(symbol):
    events = engine.get_events(symbol)
    st.markdown(f"<div class='vt-section'>🗓️ {symbol} events & news</div>", unsafe_allow_html=True)
    if not events:
        st.info("Yahoo Finance has no recent events or news for this stock.")
        return
    selected_events = []
    for event_type in ("dividend", "quarterly", "annual", "earnings", "news"):
        event = next((item for item in events if item.get("type") == event_type), None)
        if event:
            selected_events.append(event)
    for event in events:
        if event not in selected_events and len(selected_events) < 6:
            selected_events.append(event)
    for index, event in enumerate(selected_events[:6]):
        icon = "💸" if event["type"] == "dividend" else "📊" if event["type"] in {"earnings", "quarterly", "annual"} else "📰"
        link = event.get("url")
        title = f"<a href='{link}' target='_blank'>{event['title']}</a>" if link else event["title"]
        st.markdown(
            f"<div class='vt-event'><div class='vt-event-date'>{event['date']}</div><div class='vt-event-icon'>{icon}</div><div class='vt-event-copy'><strong>{title}</strong><span>{event['subtitle']}</span></div><div class='vt-event-detail'>{event['detail']}</div></div>",
            unsafe_allow_html=True,
        )


def _render_sentiment(points):
    recent = points[-20:]
    if len(recent) < 2:
        return
    first = recent[0]["price"]
    last = recent[-1]["price"]
    change_pct = ((last - first) / first * 100) if first else 0.0
    position = max(0.0, min(100.0, 50.0 + change_pct * 8.0))
    label = "Bullish" if position >= 62 else "Bearish" if position <= 38 else "Neutral"
    label_color = "var(--q-pos)" if label == "Bullish" else "var(--q-neg)" if label == "Bearish" else "var(--q-warn)"
    bars = "".join("<i></i>" for _ in range(25))
    st.markdown(
        f"<div class='vt-sentiment'><div class='vt-label'>📈 Technical mood · based on selected range</div><strong style='color:{label_color}'>{label}</strong><div class='vt-sentiment-track'>{bars}<b style='left:{position}%;'></b></div><div class='vt-sentiment-legend'><span>Bearish</span><span>Neutral</span><span>Bullish</span></div></div>",
        unsafe_allow_html=True,
    )


def _render_trade(account, username, base_dir, symbol, quote):
    st.markdown("<div class='vt-section'>⚡ Trade</div>", unsafe_allow_html=True)
    holding = account.get("holdings", {}).get(symbol, {})
    owned = float(holding.get("quantity", 0))
    with st.container(border=True):
        side = st.radio("Order type", ["BUY", "SELL"], horizontal=True, key="gm_order_side")
        quantity = st.number_input("Quantity", min_value=0.01, value=1.0, step=1.0, key="gm_order_quantity")
        price = float(quote["price"])
        value = quantity * price
        st.write(f"Price: **{_money(price)}**")
        st.write(f"{'Estimated order value' if side == 'BUY' else 'Estimated proceeds'}: **{_money(value)}**")
        st.write(f"{'Available cash' if side == 'BUY' else 'Owned shares'}: **{_money(account['cash']) if side == 'BUY' else f'{owned:g}'}**")
        if side == "SELL":
            average = float(holding.get("average_cost", 0))
            st.write(f"Estimated P&L: **{_signed_money(quantity * (price - average))}**")
        if st.button(f"{'🟢 BUY' if side == 'BUY' else '🔴 SELL'} {symbol}", type="primary", use_container_width=True):
            try:
                previous_cash = float(account["cash"])
                (engine.buy if side == "BUY" else engine.sell)(account, symbol, quantity, price)
                _save_shared_balance(account, previous_cash)
                engine.save_account(account, username, base_dir)
                # Award XP for trading activity
                total_trades = account.get("metrics", {}).get("total_trades", 0)
                if total_trades == 1:
                    edu_db.award_xp(100, "first_trade_bonus")
                edu_db.award_xp(15, "trade_executed")
                # Portfolio diversity milestone
                holdings_count = len(account.get("holdings", {}))
                if holdings_count == 5:
                    edu_db.award_xp(50, "portfolio_milestone")
                # Pass fresh account across the rerun boundary so the page
                # immediately reflects the trade without a stale disk read.
                st.session_state["gm_fresh_account"] = account
                st.session_state["gm_trade_msg"] = f"{'Bought' if side == 'BUY' else 'Sold'} {quantity:g} {symbol}! 🎉"
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _render_activity(account):
    st.markdown("<div class='vt-section'>🧾 Recent activity</div>", unsafe_allow_html=True)
    transactions = account.get("transactions", [])[-6:][::-1]
    if not transactions:
        st.info("Your completed trades will appear here.")
        return
    rows = []
    for item in transactions:
        if not isinstance(item, dict):
            continue
        order_type = str(item.get("type", "ACTIVITY")).upper()
        symbol = item.get("symbol", item.get("stock", "Virtual SIP"))
        quantity = item.get("quantity", 0)
        price = item.get("price", item.get("execution_price", 0))
        value = item.get("value", item.get("total_value", 0))
        icon = "🟢" if order_type == "BUY" else "🔴" if order_type == "SELL" else "💰"
        rows.append({
            "Type": f"{icon} {order_type}",
            "Stock": symbol,
            "Qty": quantity,
            "Price": _money(price),
            "Value": _money(value),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render(user_info, user_data_dir=None):
    username = user_info.get("username", "demo_guest")

    has_intl = False
    if username and username != "demo_guest":
        try:
            import firebase_db
            has_intl = firebase_db.has_entitlement(username, "intl_stocks")
        except Exception:
            has_intl = False
    else:
        try:
            has_intl = bool(edu_db.load_progress().get("entitlements", {}).get("intl_stocks"))
        except Exception:
            has_intl = False

    if not has_intl:
        st.markdown("""
        <div style="background:var(--q-surface-2, #18191c); border:1px solid var(--q-border, #262a31); border-radius:16px; padding:3rem 1.5rem; text-align:center; max-width:620px; margin:2.5rem auto 1.5rem;">
            <div style="font-size:3rem; margin-bottom:0.8rem;">🔒</div>
            <h2 style="color:var(--q-text, #f1f3f5); font-size:1.5rem; font-weight:700; margin-bottom:0.5rem;">Global Markets is Locked</h2>
            <p style="color:var(--q-text-2, #b7bcc4); font-size:0.92rem; line-height:1.5; margin-bottom:0;">
                Unlock direct paper-trading access to NASDAQ, NYSE, and international equities with real-time currency conversion using the <strong>US & Global Stocks Pass</strong>.
            </p>
        </div>
        """, unsafe_allow_html=True)
        col_pad1, col_btn, col_pad2 = st.columns([1, 1.2, 1])
        with col_btn:
            if st.button("🛒 Unlock in Shop", type="primary", use_container_width=True, key="unlock_intl_in_shop"):
                st.query_params["page"] = "Shop"
                st.rerun()
        return

    if user_data_dir:
        base_dir = __import__("os").path.dirname(__import__("os").path.dirname(user_data_dir))
    else:
        base_dir = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))

    # Use the freshly-mutated account from a just-completed trade so the page
    # reflects the change immediately without a stale disk/edu_db round-trip.
    if "gm_fresh_account" in st.session_state:
        account = st.session_state.pop("gm_fresh_account")
    else:
        account = _sync_shared_balance(engine.ensure_account(username, base_dir))
        engine.save_account(account, username, base_dir)

    # Pre-fetch all needed quotes in parallel to warm the lru_cache before any
    # serial rendering code runs (portfolio_metrics, _render_holdings, etc.)
    symbol = _selected_symbol(account)
    all_symbols = list(account.get("holdings", {}).keys())
    if symbol not in all_symbols:
        all_symbols.append(symbol)
    prefetched = engine.prefetch_quotes(all_symbols)

    metrics = engine.portfolio_metrics(account)
    quote = prefetched.get(symbol) or engine.get_quote(symbol)
    _render_css()

    # Show trade success toast from the previous interaction (set in _render_trade)
    if trade_msg := st.session_state.pop("gm_trade_msg", None):
        st.success(trade_msg)

    st.markdown("""<div class='vt-wrap'>
    <div class='vt-hero'>
        <div class='vt-eyebrow'>Wall Street Access</div>
        <h1>Global Markets Simulator</h1>
        <p>Trade US equities with real-time currency conversion.</p>
    </div>
    """, unsafe_allow_html=True)
    wallet_col, level_col = st.columns([2, 1])
    with wallet_col:
        st.markdown(f"<div class='vt-card vt-wallet'><div class='vt-label'>💰 Virtual balance</div><div class='vt-big'>{_money(metrics['cash'])}</div><div class='vt-muted'>Available to trade · {_money(metrics['cash'])}</div></div>", unsafe_allow_html=True)
    with level_col:
        level = min(10, 1 + int(metrics["holdings_count"] / 3))
        st.markdown(f"<div class='vt-card'><div class='vt-label'>🏆 Portfolio level</div><div class='vt-big'>Level {level}</div><div class='vt-muted'>{metrics['holdings_count']} stocks collected · {account['metrics'].get('total_trades', 0)} trades XP</div></div>", unsafe_allow_html=True)

    kpis = st.columns(6)
    values = [("Portfolio value", _money(metrics["portfolio_value"]), "Cash + holdings", ""), ("Available cash", _money(metrics["cash"]), "Spendable balance", ""), ("Invested", _money(metrics["invested"]), "Cost basis", ""), ("Total P&L", _signed_money(metrics["total_pnl"]), f"{metrics['total_return_pct']:+.2f}%", "vt-positive" if metrics["total_pnl"] >= 0 else "vt-negative"), ("Today's P&L", _signed_money(metrics["today_pnl"]), f"{metrics['today_pnl_pct']:+.2f}%", "vt-positive" if metrics["today_pnl"] >= 0 else "vt-negative"), ("Total SIP", _money(metrics["total_sip"]), "Virtual contributions", "")]
    for col, data in zip(kpis, values):
        with col:
            _metric_card(*data)

    _render_holdings(account, prefetched)
    _render_buy_search()
    state = engine.market_state()
    st.caption(f"{'🟢' if state['open'] else '🔴'} {state['status']} · NSE · {state['time']}")
    if quote:
        chart_col, trade_col = st.columns([1.7, 1])
        with chart_col:
            _render_chart(symbol, quote)
            _render_events(symbol)
        with trade_col:
            _render_trade(account, username, base_dir, symbol, quote)
    else:
        st.warning(f"Yahoo Finance cannot load {symbol} right now. Choose another ticker to continue.")

    _render_activity(account)
    sip_col, allocation_col = st.columns(2)
    with sip_col:
        st.markdown("<div class='vt-section'>📅 Monthly SIP</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='vt-card'><div class='vt-big'>{_money(engine.MONTHLY_SIP)}</div><div class='vt-muted'>Virtual contribution · Total contributed {_money(metrics['total_sip'])}</div></div>", unsafe_allow_html=True)
    with allocation_col:
        st.markdown("<div class='vt-section'>🧩 Allocation</div>", unsafe_allow_html=True)
        labels = list(account.get("holdings", {}).keys()) + (["Cash"] if metrics["cash"] else [])
        values = []
        for item in labels:
            if item == "Cash":
                values.append(metrics["cash"])
            else:
                holding = account["holdings"][item]
                item_quote = engine.get_quote(item)
                values.append(float(holding.get("quantity", 0)) * item_quote["price"] if item_quote else 0)
        if values:
            total_allocation = sum(values)
            legend_labels = [
                f"{label} · {value / total_allocation * 100:.1f}%" if total_allocation else label
                for label, value in zip(labels, values)
            ]
            fig = go.Figure(go.Pie(labels=legend_labels, values=values, hole=.62, textinfo="none", marker={"colors": ["#a78bfa", "#60a5fa", "#34d399", "#fbbf24", "#fb7185"]}))
            fig.update_layout(height=290, margin={"l": 0, "r": 0, "t": 0, "b": 20}, paper_bgcolor="rgba(0,0,0,0)", showlegend=True, legend={"font": {"color": "#cbd5e1"}})
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Buy your first stock to see allocation.")
    st.markdown("</div>", unsafe_allow_html=True)

