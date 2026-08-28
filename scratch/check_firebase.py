import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import firebase_db

try:
    firebase_db.init_firebase()
    print("Firebase initialized successfully.", flush=True)
    for username in ["akshar", "28ryzo"]:
        h = firebase_db.get_holdings(username)
        print(f"Firestore holdings for '{username}': count = {len(h) if h else 0}", flush=True)
        if h:
            for item in h:
                print(f"   {item}", flush=True)
except Exception as e:
    print("Firebase error:", e, flush=True)
