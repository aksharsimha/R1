import json
import os
import sys
from datetime import datetime
from risk_analyzer import Asset, load_holdings, save_holdings
from adaptive_engine import update_after_actual, adaptive_forecast

# Always resolve files relative to this module so CWD doesn't matter
_HERE = os.path.dirname(os.path.abspath(__file__))

HOLDINGS_FILE     = os.path.join(_HERE, "holdings.json")
TRANSACTIONS_FILE = os.path.join(_HERE, "transactions_log.json")

def set_data_dir(user_dir: str) -> None:
    """Redirect all ledger storage to a user-specific directory."""
    global HOLDINGS_FILE, TRANSACTIONS_FILE, PREDICTIONS_FILE
    HOLDINGS_FILE     = os.path.join(user_dir, "holdings.json")
    TRANSACTIONS_FILE = os.path.join(user_dir, "transactions_log.json")
    PREDICTIONS_FILE  = os.path.join(user_dir, "predictions_log.json")


def _safe_write_json(filepath: str, data) -> bool:
    """
    Atomic JSON write: serialise to a .tmp file first, then os.replace() it
    over the target.  If the process crashes mid-write the original file is
    untouched.  Returns True on success, False on failure (error logged).
    """
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)  # ensure_ascii=True (default) keeps output ASCII-safe
        os.replace(tmp, filepath)   # atomic on Windows + POSIX
        return True
    except Exception as _write_err:
        print(f"[LEDGER] Write failed for {filepath}: {_write_err}", file=sys.stderr)
        # Clean up orphaned .tmp if it exists
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

def get_transactions():
    if not os.path.exists(TRANSACTIONS_FILE):
        return []
    with open(TRANSACTIONS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def log_transaction(action: str, asset_name: str, amount: float, details: str):
    txs = get_transactions()
    txs.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "asset": asset_name,
        "amount": amount,
        "details": details
    })
    with open(TRANSACTIONS_FILE, "w") as f:
        json.dump(txs, f, indent=2)

def get_total_value(holdings):
    return sum(h.amount for h in holdings)

def update_asset_holdings(asset_name: str, new_invested: float, new_quantity: float):
    holdings = load_holdings(HOLDINGS_FILE) if os.path.exists(HOLDINGS_FILE) else []
    found = False
    old_amt = 0.0
    for h in holdings:
        if h.name == asset_name:
            old_amt = h.amount
            h.amount = new_invested
            h.quantity = new_quantity
            found = True
            break

    if found:
        save_holdings(holdings, HOLDINGS_FILE)
        log_transaction("UPDATE_HOLDINGS", asset_name, new_invested, f"Invested: Rs.{new_invested:,.2f}, Qty: {new_quantity}")
        return True
    return False

def update_asset_percentage(asset_name: str, target_percentage: float):
    """
    Sets the asset amount so that its weight becomes target_percentage (0 to 1).
    amount = (target_percentage * Total_Other) / (1 - target_percentage)
    """
    if target_percentage >= 1.0 or target_percentage < 0.0:
        raise ValueError("Percentage must be between 0.0 and 0.99")

    holdings = load_holdings(HOLDINGS_FILE) if os.path.exists(HOLDINGS_FILE) else []

    # Find asset
    asset = None
    total_other = 0.0
    for h in holdings:
        if h.name == asset_name:
            asset = h
        else:
            total_other += h.amount

    if not asset:
        return False

    old_amount = asset.amount
    if total_other == 0.0:
        new_amount = 0.0 # Can't calculate percentage if everything else is 0, unless target is 1.0
    else:
        new_amount = (target_percentage * total_other) / (1.0 - target_percentage)

    asset.amount = new_amount
    save_holdings(holdings, HOLDINGS_FILE)
    log_transaction("UPDATE_PERCENTAGE", asset_name, new_amount, f"Changed from Rs.{old_amount:,.2f} to Rs.{new_amount:,.2f} (Target: {target_percentage*100:.1f}%)")
    return True

def add_asset(name: str, asset_type: str, identifier: str, amount: float, quantity: float = 0.0):
    holdings = load_holdings(HOLDINGS_FILE) if os.path.exists(HOLDINGS_FILE) else []
    for h in holdings:
        if h.name == name:
            return False # Already exists

    new_asset = Asset(name=name, asset_type=asset_type, identifier=identifier, amount=amount, quantity=quantity)
    holdings.append(new_asset)
    save_holdings(holdings, HOLDINGS_FILE)
    log_transaction("ADD_ASSET", name, amount, f"Added new asset (Type: {asset_type}, ID: {identifier}, Qty: {quantity})")
    return True

def remove_asset(asset_name: str):
    holdings = load_holdings(HOLDINGS_FILE) if os.path.exists(HOLDINGS_FILE) else []
    old_len = len(holdings)
    holdings = [h for h in holdings if h.name != asset_name]

    if len(holdings) < old_len:
        save_holdings(holdings, HOLDINGS_FILE)
        log_transaction("REMOVE_ASSET", asset_name, 0.0, "Asset removed from portfolio")
        return True
    return False

# --- Prediction Tracking ---
PREDICTIONS_FILE = os.path.join(_HERE, "predictions_log.json")

def get_predictions():
    if not os.path.exists(PREDICTIONS_FILE):
        return []
    with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save_daily_prediction(
    target_date: str,
    expected_val: float,
    expected_change: float,
    drivers: dict,
    base_close: float = None,   # the portfolio close value used as V0 for this prediction
):
    preds = get_predictions()

    for p in preds:
        if p["target_date"] == target_date:
            # Only update if it hasn't been evaluated yet
            if p.get("real_val") is None:
                p["expected_val"] = expected_val
                p["expected_change"] = expected_change
                p["drivers"] = drivers
                if base_close is not None:
                    p["base_close"] = base_close
            break
    else:
        preds.append({
            "target_date": target_date,
            "expected_val": expected_val,
            "expected_change": expected_change,
            "drivers": drivers,
            "real_val": None,
            "variance_reason": None,
            "base_close": base_close,   # V0 that generated this prediction
        })
    _safe_write_json(PREDICTIONS_FILE, preds)


def confirm_manual_close(target_date: str, actual_close: float) -> bool:
    """
    Write a user-confirmed actual close price into predictions_log.json.

    Sets real_val, manually_confirmed=True, and auto-generates variance_reason.
    Only acts on entries where real_val is still None.
    Returns True if the entry was found and updated, False otherwise.
    """
    preds = get_predictions()
    updated = False

    for p in preds:
        if p["target_date"] == target_date and p.get("real_val") is None:
            diff = actual_close - p["expected_val"]
            if abs(diff) < (actual_close * 0.001):
                reason = "Spot on! The portfolio behaved exactly as the volatility model predicted."
            elif diff > 0:
                top_driver = max(p["drivers"].items(), key=lambda x: x[1])[0] if p.get("drivers") else "the market"
                reason = (f"Outperformed by Rs.{diff:,.2f}. {top_driver} and overall market "
                          f"strength exceeded our expected 1-day drift.")
            else:
                top_driver = min(p["drivers"].items(), key=lambda x: x[1])[0] if p.get("drivers") else "the market"
                reason = (f"Underperformed by Rs.{abs(diff):,.2f}. Unexpected negative pressure, "
                          f"likely dragged by {top_driver}.")

            p["real_val"]           = actual_close
            p["manually_confirmed"] = True
            p["variance_reason"]    = reason
            updated = True
            break

    if updated:
        _safe_write_json(PREDICTIONS_FILE, preds)
    return updated


# =============================================================================
# EWMA CATCH-UP  —  single source of truth for all EWMA learning
# =============================================================================

def ewma_catchup(historical_mu: float = 0.0, historical_sigma: float = 0.0) -> int:
    """
    Unconditional EWMA catch-up.  Must be called on every app load.

    Simple rule (no exceptions):
      Read predictions_log.json.
      Read adaptive_state.json learning_log.
      Build a set of dates already trained on.
      For every graded entry (real_val is not None) whose date is NOT in that set:
        -> call update_after_actual immediately, in chronological order.

    Properties:
      - Completely decoupled from grading logic
      - Idempotent: update_after_actual skips dates already in learning_log
      - Chronologically ordered: EWMA compounds correctly
      - No dependency on current_val, market data, or session state

    Returns: number of new entries processed this call.
    """
    if historical_mu == 0.0:
        # Seeds not available yet (called before market data loaded) — skip silently
        return 0

    preds = get_predictions()
    if not preds:
        return 0

    # Build set of dates already in the learning log — O(1) lookup per entry
    try:
        from adaptive_engine import _load_state as _ae_load_state
        existing_dates = {e["date"] for e in _ae_load_state().get("learning_log", [])}
    except RuntimeError as _state_err:
        # File is corrupt — do NOT touch it
        print(f"[EWMA catchup] Cannot read adaptive_state (corrupt?): {_state_err}", file=sys.stderr)
        return 0
    except Exception as _err:
        print(f"[EWMA catchup] Cannot read adaptive_state: {_err}", file=sys.stderr)
        return 0

    # Collect all graded entries missing from learning log, sort oldest-first
    missing = sorted(
        [
            p for p in preds
            if p.get("real_val") is not None
            and p["target_date"] not in existing_dates
        ],
        key=lambda p: p["target_date"],
    )

    if not missing:
        return 0

    processed = 0
    for p in missing:
        date_str   = p["target_date"]
        real_val   = p["real_val"]
        prev_close = p.get("base_close")
        if prev_close is None:
            # Fallback reconstruction from stored prediction components
            prev_close = p["expected_val"] - p.get("expected_change", 0.0)

        try:
            update_after_actual(
                date_str=date_str,
                actual_close=real_val,
                prev_close=prev_close,
                predicted_val=p["expected_val"],
                historical_mu=historical_mu,
                historical_sigma=historical_sigma,
            )
            processed += 1
            print(
                f"[EWMA catchup] Trained on {date_str}: "
                f"actual=Rs.{real_val:,.2f}, predicted=Rs.{p['expected_val']:,.2f}",
                file=sys.stderr,
            )
        except RuntimeError as _state_err:
            # adaptive_state.json unreadable mid-loop — abort to protect history
            print(f"[EWMA catchup] ABORT at {date_str}: {_state_err}", file=sys.stderr)
            break
        except Exception as _err:
            print(f"[EWMA catchup] Failed {date_str}: {_err}", file=sys.stderr)

    if processed:
        print(f"[EWMA catchup] Done — processed {processed} new graded day(s).", file=sys.stderr)

    return processed


# =============================================================================
# GRADING  —  only writes real_val; EWMA is handled entirely by ewma_catchup()
# =============================================================================

def evaluate_past_predictions(
    current_val: float,
    has_mf: bool = False,
    historical_mu: float = 0.0,
    historical_sigma: float = 0.0,
):
    """
    Grade past predictions and trigger EWMA + cascade updates.

    Grading writes real_val into predictions_log.json.
    All EWMA learning is then delegated to ewma_catchup() which is the
    single source of truth — it handles both freshly graded entries and
    any previously missed entries in one consistent pass.

    historical_mu    : static historical mean daily return (Rs.) — used as EWMA seed
    historical_sigma : static historical daily std-dev (Rs.)     — used as EWMA seed
    """
    preds = get_predictions()
    changed = False
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    close_hour   = 21 if has_mf else 15
    close_minute = 0  if has_mf else 30

    for p in preds:
        target_date_str = p["target_date"]

        if p.get("real_val") is None:
            can_grade = False

            if today_str > target_date_str:
                can_grade = True
            elif today_str == target_date_str:
                if now.hour > close_hour or (now.hour == close_hour and now.minute >= close_minute):
                    can_grade = True

            if can_grade:
                p["real_val"] = current_val
                diff = current_val - p["expected_val"]

                if abs(diff) < (current_val * 0.001):
                    reason = "Spot on! The portfolio behaved exactly as the volatility model predicted."
                elif diff > 0:
                    top_driver = max(p["drivers"].items(), key=lambda x: x[1])[0] if p["drivers"] else "the market"
                    reason = f"Outperformed by Rs.{diff:,.2f}. {top_driver} and overall market strength exceeded our expected 1-day drift."
                else:
                    top_driver = min(p["drivers"].items(), key=lambda x: x[1])[0] if p["drivers"] else "the market"
                    reason = f"Underperformed by Rs.{abs(diff):,.2f}. The portfolio suffered unexpected negative pressure, likely dragged by {top_driver}."

                p["variance_reason"] = reason
                changed = True

    if changed:
        _safe_write_json(PREDICTIONS_FILE, preds)

    # ── EWMA: run catch-up for every graded entry not yet in learning_log ────
    # Handles both entries just graded above AND any previously missed entries.
    ewma_catchup(historical_mu=historical_mu, historical_sigma=historical_sigma)

    # ── Cascade: recalculate the next ungraded prediction with fresh bias ────
    if historical_mu != 0.0:
        try:
            from datetime import timedelta
            preds = get_predictions()  # re-read after ewma_catchup updated adaptive_state
            graded = sorted(
                [p for p in preds if p.get("real_val") is not None],
                key=lambda x: x["target_date"],
            )
            if graded:
                latest    = graded[-1]
                graded_dt = datetime.strptime(latest["target_date"], "%Y-%m-%d")
                current_v = latest["real_val"]

                next_entry = None
                for offset in range(1, 8):
                    candidate_str = (graded_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
                    for q in preds:
                        if q["target_date"] == candidate_str and q.get("real_val") is None:
                            next_entry = q
                            break
                    if next_entry is not None:
                        break

                if next_entry is not None:
                    fc = adaptive_forecast(
                        last_confirmed_close=current_v,
                        historical_mu=historical_mu,
                        historical_sigma=historical_sigma,
                    )
                    next_entry["expected_val"]    = fc["predicted_val"]
                    next_entry["expected_change"] = fc["predicted_val"] - current_v
                    next_entry["base_close"]      = current_v
                    _safe_write_json(PREDICTIONS_FILE, preds)
                    print(
                        f"[Cascade] Recalculated {next_entry['target_date']} -> "
                        f"Rs.{fc['predicted_val']:,.2f} "
                        f"(bias={fc['bias']:+.4f}, mu={fc['mu_used']:+.4f})",
                        file=sys.stderr,
                    )
        except Exception as _cascade_err:
            print(f"[Cascade] Warning: recalculation failed: {_cascade_err}", file=sys.stderr)
