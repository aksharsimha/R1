"""
QUEST Firebase Sync Layer
==========================
Bridges local JSON files ↔ Firestore.

On login:  hydrate()  → pulls data from Firestore → writes to local files
On save:   sync_*()   → called after local writes → pushes to Firestore

This dual-write approach ensures:
  - All existing code that reads local files still works (zero changes to risk_analyzer)
  - Data persists in Firestore across deploys
  - Local dev experience is unchanged
"""

import json
import os
import sys
from dataclasses import asdict


def hydrate(username: str, user_data_dir: str):
    """
    Pull all user data from Firestore → write to local JSON files.
    Called once after login. If Firestore has data, it overwrites local.
    If Firestore is empty, keeps whatever local data exists (or creates defaults).
    """
    from firebase_db import get_holdings, get_transactions_fb, get_predictions_fb, get_ewma_state, get_news_archive

    os.makedirs(user_data_dir, exist_ok=True)

    # ── Holdings ──────────────────────────────────────────────────────────
    holdings_path = os.path.join(user_data_dir, "holdings.json")
    fb_holdings = get_holdings(username)
    if fb_holdings:
        _write_json(holdings_path, {"holdings": fb_holdings})
        print(f"[Sync] Hydrated holdings ({len(fb_holdings)} assets)", file=sys.stderr)
    elif not os.path.exists(holdings_path):
        _write_json(holdings_path, {"holdings": []})

    # ── Transactions ──────────────────────────────────────────────────────
    tx_path = os.path.join(user_data_dir, "transactions_log.json")
    fb_tx = get_transactions_fb(username)
    if fb_tx:
        _write_json(tx_path, fb_tx)
        print(f"[Sync] Hydrated transactions ({len(fb_tx)} entries)", file=sys.stderr)

    # ── Predictions ───────────────────────────────────────────────────────
    pred_path = os.path.join(user_data_dir, "predictions_log.json")
    fb_preds = get_predictions_fb(username)
    if fb_preds:
        _write_json(pred_path, fb_preds)
        print(f"[Sync] Hydrated predictions ({len(fb_preds)} entries)", file=sys.stderr)

    # ── V2 Forecasts ──────────────────────────────────────────────────────
    from firebase_db import get_v2_forecasts_fb
    v2_path = os.path.join(user_data_dir, "v2_forecast_log.json")
    fb_v2 = get_v2_forecasts_fb(username)
    if fb_v2:
        _write_json(v2_path, fb_v2)
        print(f"[Sync] Hydrated v2 forecasts ({len(fb_v2)} entries)", file=sys.stderr)

    # ── EWMA State ────────────────────────────────────────────────────────
    ewma_path = os.path.join(user_data_dir, "adaptive_state.json")
    fb_ewma = get_ewma_state(username)
    if fb_ewma.get("days_trained", 0) > 0:
        _write_json(ewma_path, fb_ewma)
        print(f"[Sync] Hydrated EWMA state ({fb_ewma['days_trained']} days)", file=sys.stderr)

    # ── News Archive ──────────────────────────────────────────────────────
    news_path = os.path.join(user_data_dir, "news_archive.json")
    fb_news = get_news_archive(username)
    if fb_news:
        _write_json(news_path, fb_news)
        print(f"[Sync] Hydrated news archive", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Sync functions — called after local saves to push to Firestore
# ──────────────────────────────────────────────────────────────────────────────

def sync_holdings(username: str, holdings_file: str):
    """Push local holdings.json to Firestore."""
    try:
        data = _read_json(holdings_file)
        if data and "holdings" in data:
            from firebase_db import save_holdings_fb
            save_holdings_fb(username, data["holdings"])
    except Exception as e:
        print(f"[Sync] Holdings sync failed: {e}", file=sys.stderr)


def sync_transactions(username: str, tx_file: str):
    """Push local transactions_log.json to Firestore."""
    try:
        data = _read_json(tx_file)
        if data is not None:
            from firebase_db import save_transactions_fb
            save_transactions_fb(username, data)
    except Exception as e:
        print(f"[Sync] Transactions sync failed: {e}", file=sys.stderr)


def sync_predictions(username: str, pred_file: str):
    """Push local predictions_log.json to Firestore."""
    try:
        data = _read_json(pred_file)
        if data is not None:
            from firebase_db import save_predictions_fb
            save_predictions_fb(username, data)
    except Exception as e:
        print(f"[Sync] Predictions sync failed: {e}", file=sys.stderr)


def sync_v2_forecasts(username: str, pred_file: str):
    """Push local v2_forecast_log.json to Firestore."""
    try:
        data = _read_json(pred_file)
        if data is not None:
            from firebase_db import save_v2_forecasts_fb
            save_v2_forecasts_fb(username, data)
    except Exception as e:
        print(f"[Sync] V2 Forecast sync failed: {e}", file=sys.stderr)


def sync_ewma_state(username: str, state_file: str):
    """Push local adaptive_state.json to Firestore."""
    try:
        data = _read_json(state_file)
        if data:
            from firebase_db import save_ewma_state
            save_ewma_state(username, data)
    except Exception as e:
        print(f"[Sync] EWMA sync failed: {e}", file=sys.stderr)


def sync_news_archive(username: str, news_file: str):
    """Push local news_archive.json to Firestore."""
    try:
        data = _read_json(news_file)
        if data:
            from firebase_db import save_news_archive
            save_news_archive(username, data)
    except Exception as e:
        print(f"[Sync] News sync failed: {e}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _write_json(path: str, data):
    """Atomic JSON write."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path: str):
    """Read JSON file, return None on failure."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
