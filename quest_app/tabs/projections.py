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
    st.subheader("Future Portfolio Projections")

    # ── v2 risk/range forecast (the honest box) ──────────────────────────────
    if not df.empty and summary['total_value'] > 0:
        import prediction_engine as _pe
        import datetime as _vdt
        import nse_live as _vnse
        _vpal = ui_theme.palette()

        _nd = _vdt.date.today() + _vdt.timedelta(days=1)
        for _ in range(10):
            if _nd.weekday() < 5 and not _vnse.is_nse_holiday(_nd):
                break
            _nd += _vdt.timedelta(days=1)

        # Holdings as (ticker, quantity) — forecast anchors to the settled close
        from risk_analyzer import GOLD_PROXY as _GOLD, AssetType as _AT
        _holdings = []
        for _a in current_assets:
            _tk = _GOLD if _a.asset_type == _AT.DIGITAL_GOLD else _a.identifier
            if _tk and _a.asset_type != _AT.MUTUAL_FUND:
                _holdings.append((_tk, float(_a.quantity)))

        # ── Self-correction: grade matured forecasts, derive a bias (₹) from recent errors ──
        import json as _tj2, os as _to2
        _tlog_file = _to2.path.join(st.session_state.get("_quest_data_dir", "."), "v2_forecast_log.json")
        try:
            with open(_tlog_file, encoding="utf-8") as _tf:
                _tlog = _tj2.load(_tf)
        except Exception:
            _tlog = []
        _today_str = _vdt.date.today().strftime("%Y-%m-%d")
        _target_str = _nd.strftime("%Y-%m-%d")
        _cur_val = round(float(summary['total_value']), 2)
        for _e in _tlog:
            if _e.get("actual") is None and _e.get("target_date") == _today_str:
                _e["actual"] = _cur_val
                _e["error"] = round(_cur_val - _e["predicted"], 2)
                if _e.get("base") is not None:
                    _e["hit"] = ((_cur_val - _e["base"]) >= 0) == ((_e["predicted"] - _e["base"]) >= 0)
        _graded = [e for e in _tlog if e.get("actual") is not None and e.get("error") is not None]
        # bias = mean recent error (actual − predicted), clamped to ±0.5% of value
        _bias = 0.0
        if _graded:
            _recent_err = [e["error"] for e in sorted(_graded, key=lambda x: x["target_date"])[-10:]]
            _bias = sum(_recent_err) / len(_recent_err)
            _cap = 0.005 * _cur_val
            _bias = max(-_cap, min(_cap, _bias))

        # Forecast LOCKED per trading day (keyed by date) → one stable number everywhere
        @st.cache_data(ttl=86400, show_spinner="Training the forecast model on 5 years of data…")
        def _v2_forecast(holdings, day, bias, sent):
            return _pe.live_forecast(list(holdings), bias=bias, sentiment=sent)

        _fc = _v2_forecast(tuple(_holdings), _today_str,
                           round(float(_bias), 2),
                           round(float(portfolio_sentiment_score), 3))

        if _fc and not _fc.get("error"):
            _up = _fc['center_ret_pct'] >= 0
            _arrow = '▲' if _up else '▼'
            _tone = 'pos' if _up else 'neg'
            _acc = _fc['recent_dir_acc_pct'] if _fc['recent_dir_acc_pct'] is not None else '—'
            _sent_lbl = ('positive' if _fc['sentiment'] > 0.15
                         else 'negative' if _fc['sentiment'] < -0.15 else 'neutral')
            st.markdown(f"""
            <div class="q-card q-enter" style="margin-bottom:14px;">
              <div style="font-size:.8rem;color:var(--q-text-3);margin-bottom:10px;">Tomorrow's outlook · next trading day: <b style="color:var(--q-text);">{_nd.strftime('%a %d %b')}</b></div>
              <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">
                <span class="q-mono" style="font-size:1.9rem;font-weight:500;color:var(--q-text);letter-spacing:-.5px;">₹{_fc['center']:,.2f}</span>
                <span class="q-mono" style="color:var(--q-{_tone});font-weight:500;font-size:1rem;">{_arrow} {abs(_fc['center_ret_pct']):.2f}%</span>
                <span class="q-pill" style="background:var(--q-warn-weak);color:var(--q-warn);">LOW confidence · {_acc}% directional</span>
              </div>
              <div style="margin-top:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;">
                <div class="q-metric"><div class="lbl">Likely range · 68% (1σ)</div><div class="val">₹{_fc['range1_low']:,.2f} – ₹{_fc['range1_high']:,.2f}</div></div>
                <div class="q-metric"><div class="lbl">Wider range · 95% (2σ)</div><div class="val">₹{_fc['range2_low']:,.2f} – ₹{_fc['range2_high']:,.2f}</div></div>
              </div>
              <div style="margin-top:12px;font-size:.88rem;color:var(--q-text-2);line-height:1.9;">
                <div>📊 <b style="color:var(--q-text);">{_fc['p_big_move_pct']}%</b> chance of a move bigger than ±2%</div>
                <div>🛡️ <b>95% VaR:</b> you're unlikely to lose more than <b style="color:var(--q-text);">₹{_fc['var95']:,.2f}</b> tomorrow</div>
              </div>
              <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--q-border);">
                <div style="font-size:.76rem;color:var(--q-text-3);margin-bottom:7px;">What's driving it</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">Volatility · {_fc['vol_regime']} ({_fc['dvol_port_pct']}%/day)</span>
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">News · {_sent_lbl}</span>
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">Momentum · {_fc['pos_momentum']}/{_fc['n_stocks']} trending up</span>
                </div>
              </div>
              <div style="margin-top:12px;font-size:.72rem;color:var(--q-text-3);line-height:1.6;">
                ⓘ Model scorecard: {_acc}% directional — barely above chance. <b style="color:var(--q-text-2);">Trust the range, not the arrow.</b> Range error beats the old EWMA model. Re-trained on fresh data each day.
              </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("📋 Per-stock outlook"):
                _vrows = [{
                    "Stock": s['ticker'].replace('.NS', '').replace('.BO', ''),
                    "Est. move": f"{s['est_move_pct']:+.2f}%",
                    "Tomorrow range": f"₹{s['low']:.1f} – ₹{s['high']:.1f}",
                    "Daily vol": f"{s['dvol_pct']:.1f}%",
                    "Risk": ("🔴 " if s['flag'] == 'high vol' else "🟠 " if s['flag'] == 'elevated' else "🟢 ") + s['flag'],
                } for s in _fc['per_stock']]
                st.dataframe(pd.DataFrame(_vrows), use_container_width=True, hide_index=True)

            st.markdown("---")
            # ── Prediction tracker (v2): log each forecast, grade it next trading day ──
            import json as _tj2, os as _to2, datetime as _td2
            _tlog_file = _to2.path.join(st.session_state.get("_quest_data_dir", "."), "v2_forecast_log.json")
            try:
                with open(_tlog_file, encoding="utf-8") as _tf:
                    _tlog = _tj2.load(_tf)
            except Exception:
                _tlog = []
            _today_str = _td2.date.today().strftime("%Y-%m-%d")
            _target_str = _nd.strftime("%Y-%m-%d")
            _cur_val = round(float(summary['total_value']), 2)

            _changed = False
            for _e in _tlog:
                if _e.get("actual") is None and _e.get("target_date") == _today_str:
                    _e["actual"] = _cur_val
                    _e["error"] = round(_cur_val - _e["predicted"], 2)
                    if _e.get("base") is not None:
                        _e["hit"] = ((_cur_val - _e["base"]) >= 0) == ((_e["predicted"] - _e["base"]) >= 0)
                    _changed = True
            if not any(_e.get("target_date") == _target_str for _e in _tlog):
                _tlog.append({"made_on": _today_str, "target_date": _target_str,
                              "base": _cur_val, "predicted": round(float(_fc['center']), 2),
                              "actual": None, "error": None, "hit": None})
                _changed = True
            if _changed:
                try:
                    with open(_tlog_file, "w", encoding="utf-8") as _tf:
                        _tj2.dump(_tlog[-90:], _tf, indent=2)
                except Exception:
                    pass

            st.markdown("##### Prediction tracker")
            st.caption("Each forecast graded against what actually happened. Builds forward from today — honest, no backfilled guesses.")
            _graded = [e for e in _tlog if e.get("actual") is not None]
            if _graded:
                _hits = sum(1 for e in _graded if e.get("hit"))
                _dacc = _hits / len(_graded) * 100
                _mae = sum(abs(e["error"]) for e in _graded) / len(_graded)
                st.markdown(f"**Track record:** {len(_graded)} graded day(s) · directional accuracy **{_dacc:.0f}%** · avg error **₹{_mae:,.2f}**")
                _trows = [{"Target date": e["target_date"],
                           "Predicted": f"₹{e['predicted']:,.2f}",
                           "Actual": f"₹{e['actual']:,.2f}",
                           "Error": f"{e['error']:+,.2f}",
                           "Direction": ("hit ✅" if e.get("hit") else "miss ❌" if e.get("hit") is not None else "-")}
                          for e in sorted(_graded, key=lambda x: x["target_date"], reverse=True)[:15]]
                st.dataframe(pd.DataFrame(_trows), use_container_width=True, hide_index=True)
            else:
                _pending = [e for e in _tlog if e.get("actual") is None]
                if _pending:
                    _p = _pending[-1]
                    st.info(f"First forecast logged: ₹{_p['predicted']:,.2f} for {_p['target_date']}. "
                            f"It gets graded when you open QUEST on that trading day — the track record grows from here.")

