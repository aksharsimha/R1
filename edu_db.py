import json
import os
import threading
import firebase_sync

_data_dir = None
_username = None
_lock = threading.Lock()
EDU_PROGRESS_FILE = "edu_progress.json"

DEFAULT_PROGRESS = {
    "total_xp": 0,
    "virtual_balance": 15000.0,
    "badges": [],
    "completed_levels": [],
    "completed_articles": [],
    "bookmarks": [],
    "liked_videos": [],
    "current_level": "Level 1"
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
