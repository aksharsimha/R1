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
