import pytz
import json
import uuid
from datetime import datetime
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

"""
QUEST Chat System — Firebase Edition
======================================
Friends, DMs, group chats, portfolio sharing — all stored in Firestore.
"""


def _send_email_notification(sender_name: str, receiver_username: str, msg_text: str):
    try:
        if "SMTP_EMAIL" not in st.secrets or "SMTP_PASSWORD" not in st.secrets:
            return
            
        from firebase_db import get_db
        db = get_db()
        if not db: return
        
        user_doc = db.collection("users").document(receiver_username).get()
        if not user_doc.exists: return
        
        receiver_email = user_doc.to_dict().get("email")
        if not receiver_email: return
        
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"].replace(" ", "")
        
        # Build the email
        msg = MIMEMultipart()
        msg['From'] = f"QUEST Notifications <{sender_email}>"
        msg['To'] = receiver_email
        msg['Subject'] = f"New message from {sender_name}"
        
        # Keep it simple and clean
        body = f"You have a new message from {sender_name} on QUEST:\n\n\"{msg_text}\"\n\nLog in to reply!"
        msg.attach(MIMEText(body, 'plain'))
        
        # Send it
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def _trigger_email_bg(sender_name: str, receiver_username: str, msg_text: str):
    # Fire and forget in a background thread so it doesn't lag the UI
    t = threading.Thread(target=_send_email_notification, args=(sender_name, receiver_username, msg_text))
    t.daemon = True
    t.start()


# ──────────────────────────────────────────────────────────────────────────────
# Social data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _default_social():
    return {
        "friends": [],
        "requests_sent": [],
        "requests_received": [],
        "chat_ids": [],
    }


def _load_social(username: str) -> dict:
    from firebase_db import get_social
    data = get_social(username)
    for key, val in _default_social().items():
        data.setdefault(key, val)
    return data


def _save_social(username: str, data: dict):
    from firebase_db import save_social
    save_social(username, data)


# ──────────────────────────────────────────────────────────────────────────────
# Chat data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _generate_chat_id() -> str:
    return "chat_" + uuid.uuid4().hex[:12]


def _create_chat_file(chat_id: str, chat_type: str, participants: list,
                      name: str = "", created_by: str = "") -> dict:
    from firebase_db import create_chat
    import pytz
    chat = {
        "chat_id": chat_id,
        "type": chat_type,
        "name": name,
        "participants": sorted(participants),
        "created_by": created_by,
        "created_at": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "messages": [],
    }
    create_chat(chat_id, chat)
    return chat


def _load_chat(chat_id: str) -> dict | None:
    from firebase_db import get_chat
    return get_chat(chat_id)


def _save_chat(chat_id: str, chat: dict):
    from firebase_db import save_chat
    save_chat(chat_id, chat)


# ──────────────────────────────────────────────────────────────────────────────
# Friend System
# ──────────────────────────────────────────────────────────────────────────────

def send_friend_request(from_user: str, to_user: str) -> tuple[bool, str]:
    if from_user == to_user:
        return False, "You can't add yourself."

    from firebase_db import user_exists
    if not user_exists(to_user):
        return False, f"User '{to_user}' not found."

    from_social = _load_social(from_user)
    to_social = _load_social(to_user)

    if to_user in from_social["friends"]:
        return False, f"You're already friends with {to_user}."
    if to_user in from_social["requests_sent"]:
        return False, f"Request already sent to {to_user}."
    if from_user in to_social["requests_sent"]:
        return accept_friend_request(from_user, to_user)

    from_social["requests_sent"].append(to_user)
    to_social["requests_received"].append(from_user)
    _save_social(from_user, from_social)
    _save_social(to_user, to_social)
    return True, f"Friend request sent to {to_user}!"


def accept_friend_request(user: str, from_user: str) -> tuple[bool, str]:
    user_social = _load_social(user)
    from_social = _load_social(from_user)

    if from_user in user_social["requests_received"]:
        user_social["requests_received"].remove(from_user)
    if user in from_social["requests_sent"]:
        from_social["requests_sent"].remove(user)

    if from_user not in user_social["friends"]:
        user_social["friends"].append(from_user)
    if user not in from_social["friends"]:
        from_social["friends"].append(user)

    existing_dm = _find_direct_chat(user, from_user)
    if not existing_dm:
        chat_id = _generate_chat_id()
        _create_chat_file(chat_id, "direct", [user, from_user])
        user_social["chat_ids"].append(chat_id)
        from_social["chat_ids"].append(chat_id)

    _save_social(user, user_social)
    _save_social(from_user, from_social)
    return True, f"You and {from_user} are now friends!"


def decline_friend_request(user: str, from_user: str) -> tuple[bool, str]:
    user_social = _load_social(user)
    from_social = _load_social(from_user)

    if from_user in user_social["requests_received"]:
        user_social["requests_received"].remove(from_user)
    if user in from_social["requests_sent"]:
        from_social["requests_sent"].remove(user)

    _save_social(user, user_social)
    _save_social(from_user, from_social)
    return True, f"Request from {from_user} declined."


def remove_friend(user: str, friend: str) -> tuple[bool, str]:
    user_social = _load_social(user)
    friend_social = _load_social(friend)

    if friend in user_social["friends"]:
        user_social["friends"].remove(friend)
    if user in friend_social["friends"]:
        friend_social["friends"].remove(user)

    _save_social(user, user_social)
    _save_social(friend, friend_social)
    return True, f"Removed {friend} from friends."


def get_friends(username: str) -> list[str]:
    return _load_social(username).get("friends", [])


def get_friend_requests(username: str) -> list[str]:
    return _load_social(username).get("requests_received", [])


def get_sent_requests(username: str) -> list[str]:
    return _load_social(username).get("requests_sent", [])


# ──────────────────────────────────────────────────────────────────────────────
# Direct Messages
# ──────────────────────────────────────────────────────────────────────────────

def _find_direct_chat(user1: str, user2: str) -> dict | None:
    social = _load_social(user1)
    for chat_id in social.get("chat_ids", []):
        chat = _load_chat(chat_id)
        if chat and chat["type"] == "direct":
            if set(chat["participants"]) == {user1, user2}:
                return chat
    return None


def get_or_create_dm(user1: str, user2: str) -> str:
    existing = _find_direct_chat(user1, user2)
    if existing:
        return existing["chat_id"]

    chat_id = _generate_chat_id()
    _create_chat_file(chat_id, "direct", [user1, user2])

    for u in [user1, user2]:
        social = _load_social(u)
        if chat_id not in social["chat_ids"]:
            social["chat_ids"].append(chat_id)
            _save_social(u, social)

    return chat_id


# ──────────────────────────────────────────────────────────────────────────────
# Group Chats
# ──────────────────────────────────────────────────────────────────────────────

def create_group_chat(creator: str, name: str, members: list[str]) -> tuple[bool, str, str]:
    if not name.strip():
        return False, "Group name cannot be empty.", ""

    all_members = list(set([creator] + members))
    if len(all_members) < 2:
        return False, "Need at least 2 members.", ""

    chat_id = _generate_chat_id()
    _create_chat_file(chat_id, "group", all_members, name=name.strip(), created_by=creator)

    for member in all_members:
        social = _load_social(member)
        if chat_id not in social["chat_ids"]:
            social["chat_ids"].append(chat_id)
            _save_social(member, social)

    return True, f"Group '{name}' created!", chat_id


def add_to_group(chat_id: str, new_member: str, added_by: str) -> tuple[bool, str]:
    chat = _load_chat(chat_id)
    if not chat or chat["type"] != "group":
        return False, "Chat not found."
    if new_member in chat["participants"]:
        return False, f"{new_member} is already in the group."

    chat["participants"].append(new_member)
    chat["participants"].sort()
    chat["messages"].append({
        "id": "msg_" + uuid.uuid4().hex[:8],
        "from": "__system__",
        "text": f"{added_by} added {new_member} to the group",
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "type": "system",
        "read_by": [],
    })
    _save_chat(chat_id, chat)

    social = _load_social(new_member)
    if chat_id not in social["chat_ids"]:
        social["chat_ids"].append(chat_id)
        _save_social(new_member, social)

    return True, f"Added {new_member} to the group."


def leave_group(chat_id: str, username: str) -> tuple[bool, str]:
    chat = _load_chat(chat_id)
    if not chat or chat["type"] != "group":
        return False, "Chat not found."
    if username in chat["participants"]:
        chat["participants"].remove(username)

    chat["messages"].append({
        "id": "msg_" + uuid.uuid4().hex[:8],
        "from": "__system__",
        "text": f"{username} left the group",
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "type": "system",
        "read_by": [],
    })
    _save_chat(chat_id, chat)

    social = _load_social(username)
    if chat_id in social["chat_ids"]:
        social["chat_ids"].remove(chat_id)
        _save_social(username, social)

    return True, "Left the group."


# ──────────────────────────────────────────────────────────────────────────────
# Messaging
# ──────────────────────────────────────────────────────────────────────────────

def send_message(chat_id: str, from_user: str, text: str,
                 msg_type: str = "text", portfolio_data: dict = None) -> tuple[bool, str]:
    chat = _load_chat(chat_id)
    if not chat:
        return False, "Chat not found."
    if from_user not in chat["participants"]:
        return False, "You're not in this chat."
    if msg_type == "text" and not text.strip():
        return False, "Message cannot be empty."

    import pytz
    msg = {
        "id": "msg_" + uuid.uuid4().hex[:8],
        "from": from_user,
        "text": text.strip() if text else "",
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "type": msg_type,
        "read_by": [from_user],
    }
    if msg_type == "portfolio_share" and portfolio_data:
        msg["portfolio_data"] = portfolio_data

    chat["messages"].append(msg)
    
    from firebase_db import save_chat
    success = save_chat(chat_id, chat)
    
    if success:
        # Get the sender's display name for the email
        from firebase_db import get_user_display_name
        sender_display = get_user_display_name(from_user) or from_user
        
        # Fire off an email notification to everyone else in the chat
        for participant in chat["participants"]:
            if participant != from_user:
                # Fire and forget
                _trigger_email_bg(sender_display, participant, msg["text"])
                
    return success, "Message sent."


def get_messages(chat_id: str, limit: int = 100) -> list[dict]:
    chat = _load_chat(chat_id)
    if not chat:
        return []
    return chat.get("messages", [])[-limit:]


def get_chat_info(chat_id: str) -> dict | None:
    chat = _load_chat(chat_id)
    if not chat:
        return None
    return {
        "chat_id": chat["chat_id"],
        "type": chat["type"],
        "name": chat.get("name", ""),
        "participants": chat["participants"],
        "created_by": chat.get("created_by", ""),
        "message_count": len(chat.get("messages", [])),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Unread tracking
# ──────────────────────────────────────────────────────────────────────────────

def get_unread_count(chat_id: str, username: str) -> int:
    chat = _load_chat(chat_id)
    if not chat:
        return 0
    count = 0
    for msg in chat.get("messages", []):
        if msg.get("from") != username and username not in msg.get("read_by", []):
            count += 1
    return count


def mark_as_read(chat_id: str, username: str):
    chat = _load_chat(chat_id)
    if not chat:
        return
    changed = False
    for msg in chat.get("messages", []):
        if username not in msg.get("read_by", []):
            msg.setdefault("read_by", []).append(username)
            changed = True
    if changed:
        _save_chat(chat_id, chat)


# ──────────────────────────────────────────────────────────────────────────────
# User's chat list
# ──────────────────────────────────────────────────────────────────────────────

def get_user_chats(username: str) -> list[dict]:
    social = _load_social(username)
    chats = []

    for chat_id in social.get("chat_ids", []):
        chat = _load_chat(chat_id)
        if not chat:
            continue
        if username not in chat.get("participants", []):
            continue

        messages = chat.get("messages", [])
        last_msg = messages[-1] if messages else None

        if chat["type"] == "direct":
            other = [p for p in chat["participants"] if p != username]
            display_name = other[0] if other else "Unknown"
        else:
            display_name = chat.get("name", "Group Chat")

        chats.append({
            "chat_id": chat["chat_id"],
            "type": chat["type"],
            "display_name": display_name,
            "participants": chat["participants"],
            "last_message": last_msg.get("text", "") if last_msg else "",
            "last_from": last_msg.get("from", "") if last_msg else "",
            "last_time": last_msg.get("timestamp", "") if last_msg else chat.get("created_at", ""),
            "unread": get_unread_count(chat["chat_id"], username),
        })

    chats.sort(key=lambda c: c["last_time"], reverse=True)
    return chats


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio sharing helper
# ──────────────────────────────────────────────────────────────────────────────

def build_portfolio_snapshot(df, summary: dict, username: str) -> dict:
    if df is None or df.empty:
        return {
            "username": username,
            "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            "total_value": 0, "total_pnl": 0, "pnl_pct": 0,
            "n_assets": 0, "risk_score": 0, "risk_bucket": "N/A",
            "top_holdings": [],
        }

    total_invested = float(df["Invested (₹)"].sum())
    total_pnl = float(df["P&L (₹)"].sum())

    top = df.nlargest(5, "Current Value (₹)")
    top_holdings = []
    for _, row in top.iterrows():
        top_holdings.append({
            "name": str(row["Name"]),
            "value": float(row["Current Value (₹)"]),
            "pnl_pct": float(row["P&L %"]) if "P&L %" in row else 0,
        })

    return {
        "username": username,
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "total_value": float(summary.get("total_value", 0)),
        "total_invested": total_invested,
        "total_pnl": total_pnl,
        "pnl_pct": (total_pnl / total_invested * 100) if total_invested > 0 else 0,
        "n_assets": int(summary.get("n_assets", 0)),
        "risk_score": float(summary.get("portfolio_risk_score", 0)),
        "risk_bucket": str(summary.get("portfolio_risk_bucket", "N/A")),
        "top_holdings": top_holdings,
    }
