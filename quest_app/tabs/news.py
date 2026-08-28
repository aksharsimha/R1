import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings
from news_sentiment import get_archived_articles
import nse_live as _nse


def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    total_invested = df['Invested (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary['total_value']
    except Exception:
        total_val = 0.0
    import datetime as _dt

    # ── Inject CSS ─────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .news-card {
        background: var(--q-surface);
        border: 1px solid var(--q-border);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.2rem;
    }
    .art-card {
        background: var(--q-surface-2);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        transition: background 0.2s;
    }
    .art-card:hover { background: var(--q-accent-weak); }
    .art-link {
        color: var(--q-text);
        text-decoration: none;
        font-weight: 500;
        font-size: 0.95rem;
        line-height: 1.4;
        transition: color 0.2s;
    }
    .art-link:hover {
        color: var(--q-accent);
    }
    .badge {
        display: inline-block;
        font-size: 0.72rem;
        font-family: 'JetBrains Mono', monospace;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 6px;
        background: var(--q-surface-2);
        color: var(--q-text-2);
    }
    .summary-bar {
        background: var(--q-accent-weak);
        border: 1px solid var(--q-border);
        border-radius: 12px;
        padding: 0.9rem 1.4rem;
        margin-bottom: 1.6rem;
        font-size: 0.9rem;
        color: var(--q-text-2);
        font-family: 'Inter', sans-serif;
    }
    .skeleton {
        background: var(--q-surface-2);
        border-radius: 10px;
        height: 100px;
        margin-bottom: 12px;
    }
    @keyframes shimmer {
        0%   { background-position: 100% 50%; }
        100% { background-position:   0% 50%; }
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Helpers ─────────────────────────────────────────────────────
    import pytz
    _IST = pytz.timezone("Asia/Kolkata")

    def _parse_pub_date(raw):
        if not raw:
            return None
        try:
            if isinstance(raw, (int, float)):
                return _dt.datetime.fromtimestamp(raw, tz=_dt.timezone.utc).astimezone(_IST)
            raw_str = str(raw).strip()
            if raw_str.endswith("Z"):
                return _dt.datetime.fromisoformat(raw_str.replace("Z", "+00:00")).astimezone(_IST)
            if "+" in raw_str or (len(raw_str) > 10 and "-" in raw_str[10:]):
                return _dt.datetime.fromisoformat(raw_str).astimezone(_IST)
            dt_naive = _dt.datetime.fromisoformat(raw_str[:19])
            return dt_naive.replace(tzinfo=_dt.timezone.utc).astimezone(_IST)
        except Exception:
            return None

    def _format_pub_date(pub_dt):
        if not pub_dt:
            return "", ""
        now_ist = _dt.datetime.now(_IST)
        diff = now_ist - pub_dt
        sec = diff.total_seconds()
        if sec < 0:
            rel = "Just now"
        elif sec < 60:
            rel = f"{int(sec)}s ago"
        elif sec < 3600:
            mins = int(sec // 60)
            rel = f"{mins}m ago"
        elif sec < 86400:
            hrs = int(sec // 3600)
            rel = f"{hrs}h ago"
        elif sec < 172800:
            rel = "Yesterday"
        else:
            days = int(sec // 86400)
            rel = f"{days}d ago"
        date_str = pub_dt.strftime("%d %b %Y, %I:%M %p IST")
        return date_str, rel

    def _render_article(art, idx):
        """Render a single article card as HTML."""
        _np = ui_theme.palette()
        sent_label = art.get('sentiment_label', '⚪ Neutral')
        art_color = (
            _np['pos'] if 'Positive' in sent_label
            else _np['neg'] if 'Negative' in sent_label
            else 'transparent'
        )
        border = f'border-left: 3px solid {art_color};' if art_color != 'transparent' else ''

        conn_score = art.get('connection_score', 0)
        conn_badge = art.get('connection_badge', '⚪ Low')
        if conn_score >= 75:
            conn_color = _np['neg']
        elif conn_score >= 40:
            conn_color = _np['warn']
        else:
            conn_color = _np['text_3']

        sent_color = _np['pos'] if 'Positive' in sent_label else _np['neg'] if 'Negative' in sent_label else _np['text_3']
        score_val = art.get('score', 0.0)

        pub_dt = _parse_pub_date(art.get('date'))
        date_str, rel_str = _format_pub_date(pub_dt)
        time_meta = f" &bull; {date_str} &bull; <span style='color:var(--q-accent);font-weight:500;'>{rel_str}</span>" if date_str else ""
        provider  = art.get('provider', 'Unknown')
        title     = art.get('title', '(no title)')
        summary   = art.get('summary', '')
        link      = art.get('link', '#')
        # Cap summary to 2 lines via CSS max-height
        summary_snippet = (summary[:220] + '…') if len(summary) > 220 else summary

        return f"""
        <div class="art-card" style="{border}">
            <a class="art-link" href="{link}" target="_blank">{title}</a>
            <p style="font-size:0.78rem; color:var(--q-text-3); margin:4px 0 8px;">
                {provider}{time_meta}
            </p>
            <span class="badge" style="color:{conn_color};">Relevance: {conn_badge} ({conn_score})</span>
            <span class="badge" style="color:{sent_color};">Sentiment: {score_val:+.2f}</span>
            <p style="font-size:0.82rem; color:var(--q-text-2); margin-top:8px; line-height:1.5;">{summary_snippet}</p>
        </div>
        """

    def _render_stock_card(asset_name, status, score, articles_html_list, article_count, stale_count):
        """Render the outer stock card header."""
        _sp = ui_theme.palette()
        s_icon  = '🟢' if status == 'Bullish' else '🔴' if status == 'Bearish' else '⚪'
        s_color = _sp['pos'] if status == 'Bullish' else _sp['neg'] if status == 'Bearish' else _sp['text_3']
        stale_note = f' &middot; {stale_count} stale hidden' if stale_count else ''
        return f"""
        <div class="news-card">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.6rem;">
                <h4 style="margin:0; color:var(--q-text); font-family:'Inter',sans-serif;">{asset_name}</h4>
                <span style="color:{s_color}; font-weight:700; font-size:0.9rem;">
                    {s_icon} {status} &nbsp;
                    <span style="font-family:'JetBrains Mono',monospace;">{score:+.2f}</span>
                </span>
            </div>
            <p style="margin:0 0 0.8rem; font-size:0.78rem; color:var(--q-text-3);">
                {article_count} recent article(s){stale_note}
            </p>
        """

    if not df.empty:
        _cutoff = _dt.datetime.now(_IST) - _dt.timedelta(days=30)

        # ── Summary bar ────────────────────────────────────────────
        # Use the cached sentiment computed at app startup
        _nsp = ui_theme.palette()
        _ps = portfolio_sentiment_score
        _ps_label = 'Bullish' if _ps > 0.15 else 'Bearish' if _ps < -0.15 else 'Neutral'
        _ps_color = _nsp['pos'] if _ps > 0.15 else _nsp['neg'] if _ps < -0.15 else _nsp['text_3']

        # Retrieve per-stock statuses from session cache if available
        _cached_statuses = st.session_state.get('_news_statuses', {})
        _n_bull = sum(1 for v in _cached_statuses.values() if v == 'Bullish')
        _n_bear = sum(1 for v in _cached_statuses.values() if v == 'Bearish')
        _n_neut = len(current_assets) - _n_bull - _n_bear

        # Sentinel adj from session_state (set when prediction was computed)
        _sent_adj_disp = st.session_state.get('_sent_adj_display', None)
        _adj_color = (_nsp['pos'] if _sent_adj_disp and _sent_adj_disp > 0
                      else _nsp['neg'] if _sent_adj_disp and _sent_adj_disp < 0
                      else _nsp['text_3'])
        _adj_part = (
            f" &nbsp;|&nbsp; Prediction adjustment: "
            f"<span style='color:{_adj_color};'>{f'{_sent_adj_disp:+.2f}' if _sent_adj_disp is not None else 'N/A'}</span>"
        )

        st.markdown(
            f"""<div class="summary-bar" style="display:flex;flex-wrap:wrap;align-items:center;gap:16px;">
                <span style='color:var(--q-text-2);font-weight:500;'>Today's sentiment</span>
                <span style='color:{_nsp['pos']};'>● {_n_bull} bullish</span>
                <span style='color:{_nsp['neg']};'>● {_n_bear} bearish</span>
                <span style='color:var(--q-text-3);'>● {_n_neut} neutral</span>
                <span style='color:var(--q-text-3);'>across {len(current_assets)} holdings</span>
                <span style='margin-left:auto;color:var(--q-text-3);'>Overall
                  <span style='color:{_ps_color}; font-weight:500; font-family:"JetBrains Mono",monospace;'>{_ps:+.2f} ({_ps_label})</span>
                  {_adj_part}
                </span>
            </div>""",
            unsafe_allow_html=True
        )

        # ── Per-stock cards ─────────────────────────────────────────────
        _new_statuses = {}

        for asset_obj in current_assets:
            asset_name = asset_obj.name
            identifier = asset_obj.identifier

            if not identifier:
                st.warning(f"No valid identifier for {asset_name} — skipping.")
                continue

            # Loading skeleton shown while spinner spins
            _ph = st.empty()
            _ph.markdown('<div class="skeleton"></div>', unsafe_allow_html=True)

            try:
                with st.spinner(''):
                    sentiment_data = get_asset_sentiment(
                        identifier, stock_name=asset_name, limit=8
                    )

                # Filter stale
                fresh = []
                stale_count = 0
                for art in sentiment_data.get('articles', []):
                    pub_dt = _parse_pub_date(art.get('date'))
                    if pub_dt is None or pub_dt >= _cutoff:
                        fresh.append(art)
                    else:
                        stale_count += 1

                # Sort by connection score descending
                fresh.sort(key=lambda a: a.get('connection_score', 0), reverse=True)

                status = sentiment_data.get('status', 'Neutral')
                score  = sentiment_data.get('score', 0.0)
                _new_statuses[identifier] = status

                _ph.empty()  # remove skeleton

                # Build article HTML
                top4_html   = ''.join(_render_article(a, i) for i, a in enumerate(fresh[:4]))
                extra_html  = ''.join(_render_article(a, i+4) for i, a in enumerate(fresh[4:]))

                # Stock card header
                st.markdown(
                    _render_stock_card(asset_name, status, score, [], len(fresh), stale_count),
                    unsafe_allow_html=True
                )

                if fresh:
                    st.markdown(top4_html, unsafe_allow_html=True)
                    if extra_html:
                        with st.expander(f"Show {len(fresh) - 4} more article(s)"):
                            st.markdown(extra_html, unsafe_allow_html=True)
                else:
                    err = sentiment_data.get('error', '')
                    if err:
                        st.caption(f"No news available — {err}")
                    elif stale_count:
                        st.caption(f"All {stale_count} available articles are older than 30 days.")
                    else:
                        st.caption(f"No recent news found for {asset_name} — sentiment defaulting to neutral.")

                # Close card div
                st.markdown('</div>', unsafe_allow_html=True)

            except Exception:
                _ph.empty()
                st.markdown(
                    f'<div class="news-card"><h4 style="color:var(--q-text);">{asset_name}</h4>'
                    f'<p style="color:var(--q-text-3);">News unavailable — No news available</p></div>',
                    unsafe_allow_html=True
                )

        # Save statuses for summary bar next render
        if _new_statuses:
            st.session_state['_news_statuses'] = _new_statuses

        # ── News Archive section ──────────────────────────────────────────
        st.markdown('---')
        with st.expander('🗂️ News Archive — Browse past articles by date'):
            st.caption('Articles are saved every time news is fetched. Select a date to review what was circulating on that day.')

            _archive = get_archived_articles()  # full dict {ticker: [articles]}

            # Collect all dates present in the archive
            _all_dates = set()
            for _ticker_arts in _archive.values():
                for _a in _ticker_arts:
                    _d = _a.get('date', '')
                    if _d:
                        _all_dates.add(_d[:10])

            if not _all_dates:
                st.info('No archived articles yet. Articles will appear here after the first news fetch.')
            else:
                _min_date = _dt.date.fromisoformat(min(_all_dates))
                _max_date = _dt.date.fromisoformat(max(_all_dates))
                _sel_date = st.date_input(
                    'Select date',
                    value=_max_date,
                    min_value=_min_date,
                    max_value=_max_date,
                    key='news_archive_date',
                )
                _sel_str = str(_sel_date)

                _found_any = False
                for asset_obj in current_assets:
                    _ticker = asset_obj.identifier
                    if not _ticker:
                        continue
                    _ticker_arts = _archive.get(_ticker, [])
                    _day_arts = [
                        a for a in _ticker_arts
                        if a.get('date', '')[:10] == _sel_str
                    ]
                    if not _day_arts:
                        continue
                    _found_any = True

                    # Sort by connection_score descending
                    _day_arts.sort(key=lambda a: a.get('connection_score', 0), reverse=True)

                    _arch_status = 'Neutral'
                    _arch_score  = sum(a.get('sentiment_score', 0) for a in _day_arts) / len(_day_arts)
                    if _arch_score > 0.15: _arch_status = 'Bullish'
                    elif _arch_score < -0.15: _arch_status = 'Bearish'

                    # Map archive record fields to art-card expected keys
                    def _arch_to_art(a):
                        return {
                            'title':            a.get('title', ''),
                            'summary':          a.get('summary', ''),
                            'link':             a.get('url', '#'),
                            'provider':         a.get('provider', 'Archived'),
                            'date':             a.get('date', ''),
                            'score':            a.get('sentiment_score', 0.0),
                            'sentiment_label':  a.get('sentiment_label', '⚪ Neutral'),
                            'connection_score': a.get('connection_score', 0),
                            'connection_badge': ('🔴 High' if a.get('connection_score', 0) >= 75
                                                 else '🟡 Medium' if a.get('connection_score', 0) >= 40
                                                 else '⚪ Low'),
                        }

                    st.markdown(
                        _render_stock_card(asset_obj.name, _arch_status, _arch_score, [], len(_day_arts), 0),
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        ''.join(_render_article(_arch_to_art(a), i) for i, a in enumerate(_day_arts)),
                        unsafe_allow_html=True
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

                if not _found_any:
                    st.info(f'No articles archived for {_sel_str}.')

    else:
        st.info('Add some assets to see live news sentiment.')

    # =============================================================================
    # MICHAEL — Portfolio Intelligence Assistant (last tab)
    # =============================================================================
    # 💬 CHAT TAB
    # =============================================================================
