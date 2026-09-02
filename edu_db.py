import json
import os
import threading
import firebase_sync

_data_dir = None
_username = None
_lock = threading.Lock()
EDU_PROGRESS_FILE = "edu_progress.json"

LEVEL_PROGRESSION = [
    {"level": 1, "id": "level_1", "name": "Level 1 — First ₹1,000", "min_xp": 0, "next_xp": 350, "stage": "Start Investing"},
    {"level": 2, "id": "level_2", "name": "Level 2 — Grow Your Money", "min_xp": 350, "next_xp": 750, "stage": "Start Investing"},
    {"level": 3, "id": "level_3", "name": "Level 3 — Reach Your Goal", "min_xp": 750, "next_xp": 1250, "stage": "Start Investing"},
    {"level": 4, "id": "level_4", "name": "Level 4 — What's Your Style?", "min_xp": 1250, "next_xp": 1850, "stage": "Build Your Portfolio"},
    {"level": 5, "id": "level_5", "name": "Level 5 — Build Your Portfolio", "min_xp": 1850, "next_xp": 2550, "stage": "Build Your Portfolio"},
    {"level": 6, "id": "level_6", "name": "Level 6 — What Happens If...?", "min_xp": 2550, "next_xp": 3350, "stage": "Build Your Portfolio"},
    {"level": 7, "id": "level_7", "name": "Level 7 — News Detective", "min_xp": 3350, "next_xp": 4250, "stage": "Market Detective"},
    {"level": 8, "id": "level_8", "name": "Level 8 — Read the Market", "min_xp": 4250, "next_xp": 5250, "stage": "Market Detective"},
    {"level": 9, "id": "level_9", "name": "Level 9 — Market Storm", "min_xp": 5250, "next_xp": 6500, "stage": "Market Detective"},
    {"level": 10, "id": "level_tax", "name": "Level 10 — Tax & Market Master", "min_xp": 6500, "next_xp": None, "stage": "Standalone Challenge"},
]

def get_level_info(xp: int) -> dict:
    xp_val = int(xp or 0)
    for lvl in reversed(LEVEL_PROGRESSION):
        if xp_val >= lvl["min_xp"]:
            cur_min = lvl["min_xp"]
            nxt = lvl["next_xp"]
            if nxt is not None:
                progress_pct = min(100.0, max(0.0, ((xp_val - cur_min) / (nxt - cur_min)) * 100.0))
                needed_xp = nxt - xp_val
            else:
                progress_pct = 100.0
                needed_xp = 0
            return {
                "level_number": lvl["level"],
                "level_id": lvl["id"],
                "level_name": lvl["name"],
                "stage": lvl["stage"],
                "min_xp": cur_min,
                "next_xp": nxt,
                "needed_xp": needed_xp,
                "progress_pct": progress_pct
            }
    return get_level_info(0)

DEFAULT_PROGRESS = {
    "total_xp": 0,
    "virtual_balance": 15000.0,
    "badges": [],
    "completed_levels": [],
    "completed_articles": [],
    "bookmarks": [],
    "liked_videos": [],
    "current_level": "Level 1 — First ₹1,000",
    "last_education_section": "Learning Path",
    "last_portfolio_section": "Overview"
}

def set_data_dir(data_dir: str, username: str = None):
    global _data_dir, _username
    _data_dir = data_dir
    _username = username

def _get_filepath() -> str:
    if not _data_dir:
        raise ValueError("edu_db data directory not set. Call set_data_dir first.")
    return os.path.join(_data_dir, EDU_PROGRESS_FILE)

def _get_global_likes_filepath() -> str:
    if _data_dir:
        parent = os.path.dirname(_data_dir)
        return os.path.join(parent, "global_video_likes.json")
    return "global_video_likes.json"

def _load_global_likes() -> dict:
    fp = _get_global_likes_filepath()
    with _lock:
        if os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

def _save_global_likes(data: dict) -> None:
    fp = _get_global_likes_filepath()
    with _lock:
        try:
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

def load_progress() -> dict:
    filepath = _get_filepath()
    with _lock:
        if not os.path.exists(filepath):
            return DEFAULT_PROGRESS.copy()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in DEFAULT_PROGRESS.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            return DEFAULT_PROGRESS.copy()

def get_video_likes(video_id: str) -> tuple[bool, int]:
    """Returns (is_liked_by_current_user, total_live_user_likes)."""
    prog = load_progress()
    user_liked = video_id in prog.get("liked_videos", [])
    global_likes = _load_global_likes()
    users_who_liked = global_likes.get(video_id, [])
    # Also ensure current user is synced
    if user_liked and _username and _username not in users_who_liked:
        users_who_liked.append(_username)
        global_likes[video_id] = users_who_liked
        _save_global_likes(global_likes)
    return (user_liked, len(users_who_liked))

def toggle_like(video_id: str) -> tuple[bool, int]:
    """Toggles like by current user and returns (is_now_liked, total_live_user_likes)."""
    prog = load_progress()
    liked_vids = prog.get("liked_videos", [])
    global_likes = _load_global_likes()
    users_who_liked = global_likes.get(video_id, [])
    uname = _username or "user"

    if video_id in liked_vids:
        liked_vids.remove(video_id)
        if uname in users_who_liked:
            users_who_liked.remove(uname)
        is_liked = False
    else:
        liked_vids.append(video_id)
        if uname not in users_who_liked:
            users_who_liked.append(uname)
        is_liked = True

    prog["liked_videos"] = liked_vids
    save_progress(prog)
    global_likes[video_id] = users_who_liked
    _save_global_likes(global_likes)
    return (is_liked, len(users_who_liked))

def toggle_bookmark(article_id: str) -> bool:
    """Toggles bookmark status and returns True if now bookmarked, False otherwise."""
    prog = load_progress()
    bms = prog.get("bookmarks", [])
    if article_id in bms:
        bms.remove(article_id)
        is_bookmarked = False
    else:
        bms.append(article_id)
        is_bookmarked = True
    prog["bookmarks"] = bms
    save_progress(prog)
    return is_bookmarked

def complete_article(article_id: str, xp_award: int = 50) -> int:
    """Marks article as completed and awards XP if not already completed. Returns total XP."""
    prog = load_progress()
    comp = prog.get("completed_articles", [])
    if article_id not in comp:
        comp.append(article_id)
        prog["completed_articles"] = comp
        prog["total_xp"] = prog.get("total_xp", 0) + xp_award
        save_progress(prog)
    return prog.get("total_xp", 0)

def save_progress(data: dict) -> None:
    filepath = _get_filepath()
    with _lock:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    if _username:
        try:
            firebase_sync.trigger_sync(_username, filepath)
        except Exception as e:
            print(f"Warning: Failed to sync edu progress to Firebase: {e}")

def get_last_education_section() -> str:
    """Returns the user's last visited Education sub-page, defaulting to 'Learning Path'."""
    try:
        prog = load_progress()
        sec = prog.get("last_education_section")
        valid_edu = ["Learning Path", "Library", "Virtual Trading", "Leaderboard", "Badges", "Tax Detective"]
        if sec in valid_edu:
            return sec
    except Exception:
        pass
    return "Learning Path"

def set_last_education_section(section: str) -> None:
    """Persists the user's last visited Education sub-page."""
    valid_edu = ["Learning Path", "Library", "Virtual Trading", "Leaderboard", "Badges", "Tax Detective"]
    if section in valid_edu:
        try:
            prog = load_progress()
            if prog.get("last_education_section") != section:
                prog["last_education_section"] = section
                save_progress(prog)
        except Exception:
            pass

def get_last_portfolio_section() -> str:
    """Returns the user's last visited Portfolio sub-page, defaulting to 'Overview'."""
    try:
        prog = load_progress()
        sec = prog.get("last_portfolio_section")
        valid_prof = ["Overview", "Planner", "Analytics", "Projections", "Insights", "News", "Activity", "Chat", "MICHAEL"]
        if sec in valid_prof:
            return sec
    except Exception:
        pass
    return "Overview"

def set_last_portfolio_section(section: str) -> None:
    """Persists the user's last visited Portfolio sub-page."""
    valid_prof = ["Overview", "Planner", "Analytics", "Projections", "Insights", "News", "Activity", "Chat", "MICHAEL"]
    if section in valid_prof:
        try:
            prog = load_progress()
            if prog.get("last_portfolio_section") != section:
                prog["last_portfolio_section"] = section
                save_progress(prog)
        except Exception:
            pass

def add_virtual_balance(amount: float) -> float:
    """Adds to the virtual balance and returns the new total."""
    prog = load_progress()
    current = prog.get("virtual_balance", 0.0)
    new_balance = current + amount
    prog["virtual_balance"] = new_balance
    save_progress(prog)
    return new_balance
