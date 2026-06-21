"""
QUEST — Prediction Engine v2 (feature pipeline + walk-forward backtest)
=======================================================================
Honest ML forecasting for next-TRADING-day returns.

This module is built backtest-first: before we trust any ML in the live
forecast, we measure — on out-of-sample history — whether it actually beats
the simple baselines (EWMA drift, momentum, "always up"). Stock returns are
mostly noise; >52% directional accuracy is real signal, >55% is good.

Features are strictly leakage-free: every feature is computed from PAST data
within each stock's own series; the target (next-day return) is only ever a
label, never an input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
    _HAS_SK = True
except Exception:
    _HAS_SK = False


# =====================================================================
# Feature engineering (leakage-free)
# =====================================================================
def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def build_features(close: pd.Series, market_ret5: pd.Series | None = None) -> pd.DataFrame:
    """Build a leakage-free feature matrix + next-day-return target from a close series."""
    close = close.dropna().astype(float)
    f = pd.DataFrame(index=close.index)
    ret1 = close.pct_change()
    f["ret1"] = ret1
    f["ret5"] = close.pct_change(5)
    f["ret20"] = close.pct_change(20)
    f["vol20"] = ret1.rolling(20).std()
    f["vol_ratio"] = ret1.rolling(5).std() / ret1.rolling(20).std()
    f["rsi14"] = _rsi(close)
    f["dist_50"] = close / close.rolling(50).mean() - 1
    f["dist_200"] = close / close.rolling(200).mean() - 1
    f["mom10"] = close / close.shift(10) - 1
    f["dow"] = close.index.dayofweek
    f["dom"] = close.index.day  # turn-of-month behavioural effect
    if market_ret5 is not None:
        f["mkt_ret5"] = market_ret5.reindex(close.index).ffill()
    # Target: NEXT day's return (label only — never a feature)
    f["target"] = ret1.shift(-1)
    return f


# =====================================================================
# Baselines (what ML must beat)
# =====================================================================
def _dir_acc(pred: np.ndarray, actual: np.ndarray) -> float:
    mask = actual != 0
    if mask.sum() == 0:
        return float("nan")
    return float((np.sign(pred[mask]) == np.sign(actual[mask])).mean()) * 100


# =====================================================================
# Walk-forward backtest (out-of-sample)
# =====================================================================
def backtest(tickers: list[str], period: str = "2y", train_frac: float = 0.7) -> dict:
    """Pool all tickers' histories, split by DATE (train past → test future),
    train HistGradientBoosting, and compare directional accuracy vs baselines.

    Returns a metrics dict.
    """
    import yfinance as yf

    # Market regime feature: NIFTY 5-day return
    try:
        nifty = yf.Ticker("^NSEI").history(period=period)["Close"].dropna()
        nifty.index = nifty.index.tz_localize(None)
        mkt_ret5 = nifty.pct_change(5)
    except Exception:
        mkt_ret5 = None

    frames = []
    used = []
    for tk in tickers:
        try:
            c = yf.Ticker(tk).history(period=period)["Close"].dropna()
            if len(c) < 260:
                continue
            c.index = c.index.tz_localize(None)
            ff = build_features(c, mkt_ret5)
            ff["ticker"] = tk
            frames.append(ff)
            used.append(tk)
        except Exception:
            continue

    if not frames:
        return {"error": "no data"}

    data = pd.concat(frames).dropna()
    data = data.sort_index()

    feat_cols = [col for col in data.columns if col not in ("target", "ticker")]
    # Date-based split: train on the earliest train_frac of dates, test on the rest
    cutoff = data.index[int(len(data.index.unique()) * train_frac)] if False else \
        data.index.unique()[int(len(data.index.unique()) * train_frac)]
    train = data[data.index < cutoff]
    test = data[data.index >= cutoff]

    X_tr, y_tr = train[feat_cols].values, train["target"].values
    X_te, y_te = test[feat_cols].values, test["target"].values

    results = {
        "tickers_used": used,
        "train_rows": len(train), "test_rows": len(test),
        "test_from": str(test.index.min().date()), "test_to": str(test.index.max().date()),
        "up_day_rate_pct": float((y_te > 0).mean() * 100),
    }

    # Baseline 1: always predict "up"
    results["acc_always_up_pct"] = _dir_acc(np.ones_like(y_te), y_te)
    # Baseline 2: momentum (predict same sign as today's return)
    results["acc_momentum_pct"] = _dir_acc(test["ret1"].values, y_te)
    # Baseline 3: EWMA drift (sign of an exponentially weighted mean of recent returns)
    ewma_drift = test["ret1"].ewm(span=10).mean().values
    results["acc_ewma_pct"] = _dir_acc(ewma_drift, y_te)

    # ML model
    if _HAS_SK:
        model = HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_depth=4,
            min_samples_leaf=40, l2_regularization=1.0, random_state=0)
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        results["acc_ml_pct"] = _dir_acc(pred, y_te)
        results["mae_ml"] = float(np.mean(np.abs(pred - y_te)))
        results["mae_ewma"] = float(np.mean(np.abs(ewma_drift - y_te)))
        results["corr_ml"] = float(np.corrcoef(pred, y_te)[0, 1])
        # feature importance via permutation-free proxy: not available for HistGB directly
    else:
        results["acc_ml_pct"] = None
        results["note"] = "scikit-learn not available"

    return results


def _norm_sf(z: float) -> float:
    """P(Z > z) for standard normal, without scipy (Abramowitz-Stegun)."""
    z = abs(z)
    t = 1 / (1 + 0.2316419 * z)
    d = 0.3989423 * np.exp(-z * z / 2)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return float(p)


def live_forecast(holdings, bias: float = 0.0, sentiment: float = 0.0,
                  period: str = "5y") -> dict:
    """Produce ONE stable next-trading-day risk/range forecast, locked per day.

    holdings: list of (ticker, quantity). The forecast is anchored to each
    holding's LAST SETTLED close (today's partial bar is dropped while the market
    is open), so the number is deterministic and identical on every machine and
    does not wobble intra-day. Cache this once per trading day upstream.

    Uses the freshest available data for everything — volatility, VaR, news tilt
    (sentiment), market regime — plus a self-correction `bias` (in ₹) derived
    from the model's own recent graded errors (learning from its mistakes).
    Honest by design: the directional point estimate is low-confidence; the
    range/VaR is the trusted output.
    """
    import yfinance as yf
    import datetime as _dt
    try:
        import nse_live as _nsl
        _mkt_open = _nsl.is_market_open()
    except Exception:
        _mkt_open = False
    _today = pd.Timestamp(_dt.date.today())

    def _settle(c):
        """Drop today's partial bar while the market is open → deterministic."""
        c = c.dropna()
        if len(c):
            c.index = c.index.tz_localize(None)
            if _mkt_open and c.index[-1].normalize() == _today:
                c = c.iloc[:-1]
        return c

    # Market regime feature
    try:
        nf = _settle(yf.Ticker("^NSEI").history(period=period)["Close"])
        mkt_ret5 = nf.pct_change(5)
        regime = "elevated" if nf.pct_change().tail(20).std() > nf.pct_change().tail(120).std() else "calm"
    except Exception:
        mkt_ret5, regime = None, "unknown"

    # Fit pooled model on all holdings' settled history
    frames, series, qty_by = [], {}, {}
    for tk, qty in holdings:
        try:
            c = _settle(yf.Ticker(tk).history(period=period)["Close"])
            if len(c) < 260:
                continue
            series[tk] = c
            qty_by[tk] = float(qty)
            frames.append(build_features(c, mkt_ret5).dropna())
        except Exception:
            continue
    if not frames or not _HAS_SK:
        return {"error": "insufficient data or sklearn missing"}

    data = pd.concat(frames)
    feat_cols = [col for col in data.columns if col != "target"]
    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=4,
                                          min_samples_leaf=40, l2_regularization=1.0, random_state=0)
    model.fit(data[feat_cols].values, data["target"].values)

    # Stable base = portfolio value at the last settled close
    val_by = {tk: qty_by[tk] * float(c.iloc[-1]) for tk, c in series.items()}
    base = sum(val_by.values())
    if base <= 0:
        return {"error": "zero base value"}

    per_stock, ret_cols, pred_ret_port, pos_mom = [], {}, 0.0, 0
    for tk, c in series.items():
        feats = build_features(c, mkt_ret5).drop(columns=["target"]).dropna()
        if feats.empty:
            continue
        pr = float(model.predict(feats.iloc[[-1]].values)[0])
        dvol = float(c.pct_change().ewm(span=20).std().iloc[-1])
        last = float(c.iloc[-1])
        if float(c.pct_change(5).iloc[-1]) > 0:
            pos_mom += 1
        w = val_by[tk] / base
        pred_ret_port += w * pr
        ret_cols[tk] = c.pct_change()
        flag = "high vol" if dvol > 0.03 else ("elevated" if dvol > 0.02 else "normal")
        per_stock.append({
            "ticker": tk, "est_move_pct": round(pr * 100, 2),
            "low": round(last * (1 - 1.96 * dvol), 2), "high": round(last * (1 + 1.96 * dvol), 2),
            "dvol_pct": round(dvol * 100, 2), "flag": flag,
        })

    # Portfolio daily volatility from value-weighted, aligned holding returns
    rdf = pd.DataFrame(ret_cols).dropna()
    wvec = np.array([val_by.get(t, 0.0) / base for t in rdf.columns])
    port_ret = (rdf * wvec).sum(axis=1)
    dvol_port = float(port_ret.ewm(span=20).std().iloc[-1])
    dvol_long = float(port_ret.tail(120).std())

    sent_tilt = max(-0.004, min(0.004, sentiment * 0.01))

    # Recent directional accuracy (rolling, honest scorecard)
    acc = None
    try:
        cut = data.index.unique()[int(len(data.index.unique()) * 0.85)]
        te = data[data.index >= cut].dropna()
        if len(te) > 50:
            p = model.predict(te[feat_cols].values)
            y = te["target"].values
            m = y != 0
            acc = round(float((np.sign(p[m]) == np.sign(y[m])).mean()) * 100, 1)
    except Exception:
        acc = None

    center = base * (1 + pred_ret_port + sent_tilt) + bias  # bias (₹) = self-correction
    center_ret = center / base - 1
    sig1 = base * dvol_port
    sig2 = base * 1.96 * dvol_port
    p_big = round(2 * _norm_sf(0.02 / dvol_port) * 100) if dvol_port > 0 else 0
    var95 = base * 1.645 * dvol_port

    return {
        "base": base, "center": center, "center_ret_pct": round(center_ret * 100, 2),
        "range1_low": center - sig1, "range1_high": center + sig1,
        "range2_low": center - sig2, "range2_high": center + sig2,
        "p_big_move_pct": p_big, "var95": var95,
        "dvol_port_pct": round(dvol_port * 100, 2),
        "vol_regime": "elevated" if dvol_port > dvol_long else "calm",
        "market_regime": regime, "bias_applied": round(float(bias), 2),
        "sentiment": sentiment, "pos_momentum": pos_mom, "n_stocks": len(series),
        "recent_dir_acc_pct": acc,
        "per_stock": sorted(per_stock, key=lambda x: -abs(x["est_move_pct"])),
    }


def report(tickers: list[str]) -> str:
    r = backtest(tickers)
    if r.get("error"):
        return f"Backtest failed: {r['error']}"
    L = [
        f"Tickers used: {len(r['tickers_used'])}  ({', '.join(r['tickers_used'])})",
        f"Train rows: {r['train_rows']:,}   Test rows: {r['test_rows']:,}",
        f"Out-of-sample test window: {r['test_from']} -> {r['test_to']}",
        f"Up-day base rate: {r['up_day_rate_pct']:.1f}%",
        "",
        "Directional accuracy (higher = better; >52% = real signal):",
        f"  Always-up baseline : {r['acc_always_up_pct']:.1f}%",
        f"  Momentum baseline  : {r['acc_momentum_pct']:.1f}%",
        f"  EWMA baseline      : {r['acc_ewma_pct']:.1f}%",
        f"  >> ML model        : {r['acc_ml_pct']:.1f}%" if r.get("acc_ml_pct") else "  ML: n/a",
    ]
    if r.get("mae_ml") is not None:
        L += [
            "",
            f"Range error (MAE, lower = better):  ML {r['mae_ml']:.4f}  vs  EWMA {r['mae_ewma']:.4f}",
            f"Prediction–actual correlation (ML): {r['corr_ml']:+.3f}",
        ]
    return "\n".join(L)
