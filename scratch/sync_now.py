import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import firebase_db
import firebase_sync

try:
    firebase_db.init_firebase()
    firebase_sync.sync_holdings("akshar", "quest_app/users/akshar/holdings.json")
    print("Successfully synced akshar holdings to Firestore!", flush=True)
except Exception as e:
    print(f"Firestore sync note: {e}", flush=True)
