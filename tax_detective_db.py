import json
import os
import threading
import time
import uuid
import firebase_sync
from edu_db import add_virtual_balance

_data_dir = None
_username = None
_lock = threading.Lock()
TAX_DETECTIVE_FILE = "tax_detective_state.json"

CASES = [
    {
        "id": "CASE 01 · CAPITAL GAINS",
        "title": "The ₹18,000 profit",
        "avatar": "AR",
        "scenario": "Arjun bought listed shares for ₹80,000 and sold them for ₹98,000 after holding them for 8 months. His friend says, “You made ₹18,000, so just add ₹18,000 to your normal income and you're done.” Arjun wants to know what actually needs to be investigated before filing his return.",
        "snapshot": [["Buy value", "₹80,000"], ["Sale value", "₹98,000"], ["Holding period", "8 months"], ["Profit", "₹18,000"]],
        "takeaway": "A profit from selling an investment is not automatically the same thing as salary or other ordinary income. The tax treatment depends on the asset and the applicable holding-period rules. The detective skill is identifying the correct income category before calculating tax.",
        "choices": [
            {"t": "Treat the ₹18,000 as normal salary income", "d": "It is money Arjun earned, so simply add it to his salary.", "why": "The fact that Arjun earned money does not determine its tax category. A gain from selling an investment can fall under capital-gains rules rather than salary. First classify the income; then calculate the tax.", "c": False},
            {"t": "Classify it as a capital gain and check the applicable rules", "d": "Identify the asset, holding period and relevant capital-gains treatment before calculating the tax.", "why": "This is the right investigation. Arjun made a gain from selling an investment, so he needs to determine the applicable capital-gains category and rate based on the asset and holding period.", "c": True},
            {"t": "Ignore it because ₹18,000 is a small profit", "d": "Small investment profits do not need to be reported if the amount is not significant.", "why": "A small amount is not automatically exempt from reporting or taxation. Whether tax is payable and how it is reported depends on the applicable rules, not simply on the size of the profit.", "c": False}
        ]
    },
    {
        "id": "CASE 02 · TRADING INCOME",
        "title": "The intraday trader",
        "avatar": "VK",
        "scenario": "Vikram buys and sells the same listed shares several times during the day. At the end of the month, he is up ₹35,000. He says, “I made money from shares, so this must be capital gains just like a normal investment.” But his activity looks very different from buying shares and holding them.",
        "snapshot": [["Trading style", "Intraday"], ["Net result", "+₹35,000"], ["Shares held overnight", "No"], ["Question", "How is it classified?"]],
        "takeaway": "Tax treatment can depend on the nature of the transaction, not just whether money was made. Frequent same-day equity trades can have different treatment from delivery-based investments, so the activity needs to be classified correctly.",
        "choices": [
            {"t": "Automatically classify it as long-term capital gains", "d": "The profit came from shares, so it should be treated like a long-term investment gain.", "why": "That does not fit the facts. Vikram did not hold the shares as a long-term investment; he repeatedly bought and sold them within the same day. The nature of the activity needs to be examined first.", "c": False},
            {"t": "Check the rules for intraday/speculative business activity", "d": "Recognise that same-day trades can have different tax treatment from delivery-based investments.", "why": "This is the key clue. Intraday equity trading is treated differently from simply buying shares for investment and taking delivery. Vikram should check the applicable rules rather than automatically calling the ₹35,000 a capital gain.", "c": True},
            {"t": "Ignore the profit because no shares were held at the end of the day", "d": "If the shares were sold before market close, there is no taxable income to report.", "why": "Not holding the shares overnight does not make the profit disappear. Vikram still completed transactions and needs to determine the correct tax treatment of the resulting trading income.", "c": False}
        ]
    },
    {
        "id": "CASE 03 · DIVIDEND INCOME",
        "title": "The dividend trap",
        "avatar": "RN",
        "scenario": "Rohan owns shares and receives ₹12,000 in dividends during the year. He never sold a single share, so he assumes there is nothing to report: “No sale means no tax.” Before accepting that answer, he opens his tax notes.",
        "snapshot": [["Shares sold", "None"], ["Dividend received", "₹12,000"], ["Investment still held", "Yes"], ["Question", "Is it taxable income?"]],
        "takeaway": "Taxable investment income is not limited to profits from selling an asset. Dividend income has its own tax treatment, so investors need to distinguish income received from holding an asset from gains made by selling it.",
        "choices": [
            {"t": "Report nothing because no shares were sold", "d": "Only selling an investment can create taxable income.", "why": "Selling is only one possible source of investment-related income. Rohan received a dividend because he held the shares, so he needs to consider the tax treatment of dividend income separately from capital gains.", "c": False},
            {"t": "Treat the ₹12,000 as a capital gain", "d": "It came from shares, so classify it the same way as a profit from selling shares.", "why": "The fact that money came from a share does not make every payment a capital gain. A dividend is income received from holding the investment, while a capital gain arises from transferring or selling the asset.", "c": False},
            {"t": "Check the specific tax treatment for dividend income", "d": "Recognise dividends as a separate type of investment income and verify how they should be reported.", "why": "This is the correct investigation. Rohan does not need to sell the shares for the dividend to matter for tax purposes. The dividend has its own treatment and should be reported according to the applicable rules.", "c": True}
        ]
    },
    {
        "id": "CASE 04 · HOLDING PERIOD",
        "title": "The 11-month sale",
        "avatar": "PS",
        "scenario": "Priya buys listed shares and sells them after 11 months for a profit of ₹32,000. She says, “It's a profit, so the tax should be the same no matter how long I held it.” Her friend says the holding period could change the tax treatment.",
        "snapshot": [["Asset", "Listed shares"], ["Holding period", "11 months"], ["Profit", "₹32,000"], ["Question", "Does time matter?"]],
        "takeaway": "For assets where holding period affects the tax category, the time an investment is held can change how the gain is treated. A Tax Detective should check the relevant holding-period rule before calculating tax on a stock profit.",
        "choices": [
            {"t": "Ignore the holding period because all stock profits are taxed identically", "d": "The only thing that matters is the ₹32,000 profit.", "why": "The profit amount matters, but it is not the only clue. Holding period can determine whether a gain falls into a short-term or long-term category, which can affect the applicable tax treatment.", "c": False},
            {"t": "Check the applicable holding-period threshold before calculating the tax", "d": "Use the asset type and time held to identify the correct capital-gains category first.", "why": "This is the key detective step. An 11-month holding period needs to be compared with the rule applicable to that asset. Once the category is established, the appropriate tax treatment can be applied.", "c": True},
            {"t": "Wait until the profit becomes larger before checking the holding period", "d": "Holding-period rules only become important for large profits.", "why": "The size of the profit does not remove the need to classify the transaction correctly. The holding period is a separate fact that can determine the category of the gain.", "c": False}
        ]
    }
]

def set_data_dir(data_dir: str, username: str = None):
    global _data_dir, _username
    _data_dir = data_dir
    _username = username

def _get_filepath() -> str:
    if not _data_dir:
        raise ValueError("tax_detective_db data directory not set. Call set_data_dir first.")
    return os.path.join(_data_dir, TAX_DETECTIVE_FILE)

DEFAULT_STATE = {
    "attempts": {},
    "current_attempt_id": None,
    "has_locked_reward": False
}

def _load_state() -> dict:
    filepath = _get_filepath()
    with _lock:
        if not os.path.exists(filepath):
            return DEFAULT_STATE.copy()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in DEFAULT_STATE.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            return DEFAULT_STATE.copy()

def _save_state(data: dict) -> None:
    filepath = _get_filepath()
    with _lock:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    if _username:
        try:
            firebase_sync.trigger_sync(_username, filepath)
        except Exception as e:
            print(f"Warning: Failed to sync tax detective state to Firebase: {e}")

def get_public_cases():
    """Return cases without the 'c' (correct) and 'why' flags to prevent cheating."""
    public_cases = []
    for case in CASES:
        pub_case = case.copy()
        pub_choices = []
        for choice in case["choices"]:
            pub_choices.append({
                "t": choice["t"],
                "d": choice["d"]
            })
        pub_case["choices"] = pub_choices
        public_cases.append(pub_case)
    return public_cases

def get_case(case_index: int):
    if 0 <= case_index < len(CASES):
        return CASES[case_index]
    return None

def start_attempt() -> dict:
    state = _load_state()
    
    # If there's an ongoing attempt, return it instead of creating a new one
    curr_id = state.get("current_attempt_id")
    if curr_id and curr_id in state["attempts"]:
        att = state["attempts"][curr_id]
        if att["status"] == "in_progress":
            return att

    new_id = str(uuid.uuid4())
    attempt = {
        "id": new_id,
        "started_at": time.time(),
        "completed_at": None,
        "correct_count": 0,
        "total_cases": len(CASES),
        "reward_amount": 0,
        "status": "in_progress",
        "is_locked_for_reward": state.get("has_locked_reward", False),
        "answers": {}
    }
    
    state["attempts"][new_id] = attempt
    state["current_attempt_id"] = new_id
    _save_state(state)
    return attempt

def get_current_attempt() -> dict:
    state = _load_state()
    curr_id = state.get("current_attempt_id")
    if curr_id and curr_id in state["attempts"]:
        return state["attempts"][curr_id]
    return start_attempt()

def answer_case(case_index: int, option_index: int) -> dict:
    state = _load_state()
    curr_id = state.get("current_attempt_id")
    if not curr_id or curr_id not in state["attempts"]:
        raise ValueError("No active attempt found")
        
    attempt = state["attempts"][curr_id]
    if attempt["status"] != "in_progress":
        raise ValueError("Attempt is already completed")
        
    case = get_case(case_index)
    if not case:
        raise ValueError("Invalid case index")
        
    case_id = case["id"]
    if case_id in attempt["answers"]:
        raise ValueError("Case already answered")
        
    if not (0 <= option_index < len(case["choices"])):
        raise ValueError("Invalid option index")

    chosen_option = case["choices"][option_index]
    is_correct = chosen_option.get("c", False)
    
    # Identify correct index
    correct_index = next((i for i, c in enumerate(case["choices"]) if c.get("c")), -1)
    
    attempt["answers"][case_id] = {
        "chosen_option_index": option_index,
        "is_correct": is_correct,
        "answered_at": time.time()
    }
    
    if is_correct:
        attempt["correct_count"] += 1
        
    _save_state(state)
    
    return {
        "is_correct": is_correct,
        "correct_index": correct_index,
        "explanation": chosen_option.get("why", ""),
        "all_explanations": [c.get("why", "") for c in case["choices"]],
        "takeaway": case["takeaway"]
    }

def finish_attempt() -> dict:
    state = _load_state()
    curr_id = state.get("current_attempt_id")
    if not curr_id or curr_id not in state["attempts"]:
        raise ValueError("No active attempt found")
        
    attempt = state["attempts"][curr_id]
    if attempt["status"] == "completed":
        return attempt
        
    if len(attempt["answers"]) < len(CASES):
        raise ValueError("Cannot finish attempt before answering all cases")
        
    attempt["completed_at"] = time.time()
    attempt["status"] = "completed"
    
    # Calculate reward
    if attempt["is_locked_for_reward"]:
        attempt["reward_amount"] = 0
    else:
        if attempt["correct_count"] >= 3:
            attempt["reward_amount"] = attempt["correct_count"] * 5000
            # Lock future rewards
            state["has_locked_reward"] = True
            attempt["is_locked_for_reward"] = True
            # Add to wallet
            add_virtual_balance(float(attempt["reward_amount"]))
        else:
            attempt["reward_amount"] = 0
            
    # Clear current attempt ID so next visit starts a fresh one
    state["current_attempt_id"] = None
    
    _save_state(state)
    return attempt

def has_completed_run() -> bool:
    """Returns True if this user has ever completed a real (first) run."""
    state = _load_state()
    # has_locked_reward is set to True the moment a user finishes their one real run
    # (even if they scored < 3 and got ₹0 reward, has_locked_reward becomes True on finish).
    # However it is only set True when reward >= 3 correct. For users who finished with < 3,
    # we check if any attempt has status == "completed".
    if state.get("has_locked_reward", False):
        return True
    for att in state.get("attempts", {}).values():
        if att.get("status") == "completed":
            return True
    return False
