"""
Adaptive Prediction Engine — Exponential Weighted Moving Average (EWMA) Learning Model
========================================================================================
This module replaces the static μₚ (historical average daily return) with a dynamically
updating expected return that learns from every prediction error.

Components:
  1. Error Tracking         — stores each day's prediction error permanently
  2. EWMA μₚ Update         — α × actual_return + (1-α) × μₚ_old
  3. Bias Correction         — rolling 5-day mean error added to next forecast
  4. EWMA σₚ Update          — adaptive volatility for confidence ranges & VaR
  5. Dynamic α               — adapts learning rate based on error direction patterns
  6. Cold-start handling     — graceful bootstrap for first 1-3 days
"""

import json
import os
import math
from datetime import datetime

# Always write adaptive_state.json next to this file, regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTIVE_STATE_FILE = os.path.join(_HERE, "adaptive_state.json")

def set_data_dir(user_dir: str) -> None:
    """Redirect adaptive state storage to a user-specific directory."""
    global ADAPTIVE_STATE_FILE
    ADAPTIVE_STATE_FILE = os.path.join(user_dir, "adaptive_state.json")

# ──────────────────────────────────────────────────────────────────────────────
# State persistence helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """
    Load the persistent adaptive learning state from disk.

    IMPORTANT: If the file EXISTS but cannot be parsed (e.g. truncated during a
    concurrent write), we raise an exception rather than silently returning a
    blank default state.  Callers must catch this and abort — we must never
    overwrite a good state file with seed values just because of a transient
    read error.
    """
    if not os.path.exists(ADAPTIVE_STATE_FILE):
        # Genuinely first run — no history yet.
        return _default_state()
    with open(ADAPTIVE_STATE_FILE, "r") as f:
        raw = f.read()
    if not raw.strip():
        # File exists but is empty — treat as first run (safe: nothing to lose).
        return _default_state()
    try:
        return json.loads(raw)
    except Exception as exc:
        # File exists AND has content but failed to parse.  Do NOT fall back to
        # a blank default — that would erase all learning history on the next
        # _save_state call.  Raise so the caller aborts instead.
        raise RuntimeError(
            f"[AdaptiveEngine] Failed to parse {ADAPTIVE_STATE_FILE}: {exc}. "
            "The file may be partially written. Aborting to protect learning history."
        ) from exc


def _save_state(state: dict) -> None:
    """
    Atomically persist the adaptive learning state to disk.

    Writes to a .tmp file first, then os.replace() over the real file.
    This guarantees the target file is never left in a partially-written /
    truncated state if the process is interrupted mid-write (e.g. during a
    Streamlit auto-refresh cycle).
    """
    tmp = ADAPTIVE_STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, ADAPTIVE_STATE_FILE)


def _default_state() -> dict:
    """Return a blank adaptive state with no prior history."""
    return {
        "mu_ewma": None,           # EWMA expected daily return (₹), None = use historical
        "sigma_ewma": None,        # EWMA daily standard deviation (₹), None = use historical
        "learning_log": [],        # List of dicts: one entry per graded day
        "days_trained": 0,         # How many real graded days the model has seen
    }


def get_state() -> dict:
    return _load_state()


# ──────────────────────────────────────────────────────────────────────────────
# Alpha (learning rate) — staged by days trained, prevents overcorrection early
# ──────────────────────────────────────────────────────────────────────────────

def _compute_alpha(days_trained: int) -> float:
    """
    Staged learning rate — slower early, faster once the model is calibrated.

    Days  1–3  (cold-start)  : α = 0.10  — barely move from the seed
    Days  4–7  (warming up)  : α = 0.20  — moderate adaptation
    Days  8+  (calibrated)  : α = 0.30  — full EWMA speed
    """
    if days_trained < 4:
        return 0.10
    elif days_trained < 8:
        return 0.20
    else:
        return 0.30


# ──────────────────────────────────────────────────────────────────────────────
# Bias Correction — rolling 5-day mean of errors
# ──────────────────────────────────────────────────────────────────────────────

def _compute_bias(learning_log: list) -> float:
    """Return the average prediction error over the last 5 graded days."""
    if not learning_log:
        return 0.0
    window = learning_log[-5:]
    return sum(e["error"] for e in window) / len(window)


# ──────────────────────────────────────────────────────────────────────────────
# Core EWMA update — called once per graded day
# ──────────────────────────────────────────────────────────────────────────────

def update_after_actual(
    date_str: str,
    actual_close: float,
    prev_close: float,
    predicted_val: float,
    historical_mu: float,
    historical_sigma: float,
) -> dict:
    """
    Called by evaluate_past_predictions() after a day's actual close is locked in.

    Parameters
    ----------
    date_str          : 'YYYY-MM-DD' — the graded date
    actual_close      : portfolio value at actual market close
    prev_close        : portfolio value at the previous graded day's close
    predicted_val     : what the model had predicted for this date
    historical_mu     : static historical mean daily return (₹) — used as cold-start seed
    historical_sigma  : static historical daily std-dev (₹)      — used as cold-start seed

    Returns
    -------
    Updated state dict (already saved to disk), or the unchanged state if this
    date has already been trained on (idempotent — safe to call on every restart).
    """
    state = _load_state()
    log = state["learning_log"]

    # ── Idempotency guard ─────────────────────────────────────────────────────
    # If we have already trained on this date, do NOT re-apply the EWMA update.
    # This prevents every app restart from creating a duplicate learning step
    # for already-graded predictions (evaluate_past_predictions runs on every load).
    if any(entry["date"] == date_str for entry in log):
        return state  # Already trained — nothing to do, state on disk is correct.
    # Alpha staged by how many days the model has already been trained
    alpha = _compute_alpha(state["days_trained"])

    # Actual daily return in ₹
    actual_return = actual_close - prev_close

    # Error for this day
    error = actual_close - predicted_val

    # ── EWMA μ update ──────────────────────────────────────────────────────────
    mu_old = state["mu_ewma"] if state["mu_ewma"] is not None else historical_mu
    mu_new_raw = alpha * actual_return + (1 - alpha) * mu_old

    # Sanity cap: μ_new cannot exceed 3× |mu_old| in one update.
    # Uses historical_mu as floor for the cap so it is never near-zero on cold-start.
    cap = max(abs(mu_old) * 3.0, abs(historical_mu) * 3.0)
    mu_new = max(-cap, min(cap, mu_new_raw))
    cap_applied = mu_new != mu_new_raw

    # ── EWMA σ update ──────────────────────────────────────────────────────────
    sigma_old = state["sigma_ewma"] if state["sigma_ewma"] is not None else historical_sigma
    variance_new = alpha * (actual_return - mu_new) ** 2 + (1 - alpha) * sigma_old ** 2
    sigma_new = math.sqrt(max(variance_new, 0.0))

    # ── Append to learning log ─────────────────────────────────────────────────
    # Append the entry first so the current day's error is included in the
    # bias calculation.  bias_5d = mean of last-5 errors INCLUDING this day.
    log.append({
        "date": date_str,
        "actual_return": round(actual_return, 4),
        "mu_old": round(mu_old, 4),
        "mu_new_raw": round(mu_new_raw, 4),
        "mu_new": round(mu_new, 4),
        "cap_applied": cap_applied,
        "sigma_old": round(sigma_old, 4),
        "sigma_new": round(sigma_new, 4),
        "error": round(error, 4),
        "alpha_used": round(alpha, 2),
        "bias_5d": round(_compute_bias(log), 4),  # bias AFTER appending — includes this day
    })

    state["mu_ewma"] = mu_new
    state["sigma_ewma"] = sigma_new
    state["days_trained"] = len(log)

    _save_state(state)
    return state



# ──────────────────────────────────────────────────────────────────────────────
# Adaptive forecast — called when generating tomorrow's prediction
# ──────────────────────────────────────────────────────────────────────────────

def adaptive_forecast(
    last_confirmed_close: float,
    historical_mu: float,
    historical_sigma: float,
) -> dict:
    """
    Compute the adaptive 1-day forecast.

    Returns a dict with:
      predicted_val   : point estimate (₹)
      mu_used         : effective μₚ used in this forecast (₹)
      sigma_used      : effective σₚ used (₹)
      bias            : 5-day bias correction applied (₹)
      alpha           : learning rate used
      days_trained    : number of graded days the model has seen
      calibrating     : True if still in cold-start (<3 graded days)
      confidence      : 'high' | 'medium' | 'low'
    """
    state = _load_state()
    log = state["learning_log"]
    days = state["days_trained"]
    alpha = _compute_alpha(days)

    # ── Cold-start blending ────────────────────────────────────────────────────
    if days == 0:
        # Day 1: pure historical
        mu_used = historical_mu
        sigma_used = historical_sigma
    elif days == 1:
        # Day 2: 30% EWMA, 70% historical
        ewma_mu = state["mu_ewma"] if state["mu_ewma"] is not None else historical_mu
        mu_used = 0.3 * ewma_mu + 0.7 * historical_mu
        ewma_sig = state["sigma_ewma"] if state["sigma_ewma"] is not None else historical_sigma
        sigma_used = 0.3 * ewma_sig + 0.7 * historical_sigma
    elif days == 2:
        # Day 3: 70% EWMA, 30% historical
        ewma_mu = state["mu_ewma"] if state["mu_ewma"] is not None else historical_mu
        mu_used = 0.7 * ewma_mu + 0.3 * historical_mu
        ewma_sig = state["sigma_ewma"] if state["sigma_ewma"] is not None else historical_sigma
        sigma_used = 0.7 * ewma_sig + 0.3 * historical_sigma
    else:
        # Day 4+: full EWMA
        mu_used = state["mu_ewma"] if state["mu_ewma"] is not None else historical_mu
        sigma_used = state["sigma_ewma"] if state["sigma_ewma"] is not None else historical_sigma

    # ── Bias correction ────────────────────────────────────────────────────────
    bias = _compute_bias(log)

    # ── Point estimate ─────────────────────────────────────────────────────────
    predicted_val = last_confirmed_close + mu_used + bias

    # ── Confidence indicator ───────────────────────────────────────────────────
    confidence = _compute_confidence(log)

    return {
        "predicted_val": predicted_val,
        "mu_used": mu_used,
        "sigma_used": sigma_used,
        "bias": bias,
        "alpha": alpha,
        "days_trained": days,
        "calibrating": days < 3,
        "confidence": confidence,
    }


def _compute_confidence(log: list) -> str:
    """
    High   (green)  — last 3 absolute errors all under ₹300
    Medium (amber)  — last 3 absolute errors all under ₹600
    Low    (red)    — any error above ₹600
    """
    if len(log) < 3:
        return "calibrating"

    recent_errors = [abs(e["error"]) for e in log[-3:]]
    if all(e < 300 for e in recent_errors):
        return "high"
    elif all(e < 600 for e in recent_errors):
        return "medium"
    else:
        return "low"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for display
# ──────────────────────────────────────────────────────────────────────────────

def get_learning_log() -> list:
    """Return the full learning log for display."""
    state = _load_state()
    return state.get("learning_log", [])


def get_days_trained() -> int:
    state = _load_state()
    return state.get("days_trained", 0)
