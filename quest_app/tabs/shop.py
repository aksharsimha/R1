import streamlit as st
import datetime as dt
from datetime import datetime, timezone
import edu_db

try:
    import razorpay
except ImportError:
    razorpay = None


def _cached_all_users() -> list:
    """Cache firebase_db.get_all_users() in session_state so the gift dialog
    does not refetch the full user list on every rerun."""
    if "_shop_all_users_cache" not in st.session_state:
        try:
            import firebase_db
            st.session_state._shop_all_users_cache = firebase_db.get_all_users()
        except Exception:
            st.session_state._shop_all_users_cache = []
    return st.session_state._shop_all_users_cache


@st.dialog("🎁 Send a Gift")
def _gift_dialog(sender: str, sender_coins: int, key: str, title: str, cost: int, duration_days: int, icon: str):
    st.markdown(
        f"""
        <div style="text-align:center;padding:4px 0 12px;">
            <div style="font-size:2.2rem;margin-bottom:4px;">{icon}</div>
            <h3 style="margin:0 0 6px;color:var(--q-text, #f1f3f5);font-weight:700;">Gift {title}</h3>
            <p style="font-size:0.86rem;color:var(--q-text-2, #b7bcc4);margin:0;line-height:1.4;">
                Send {duration_days} days of {title} to a friend, on you.
            </p>
        </div>
        <div style="background:var(--q-surface-2, #18191c);border:1px solid var(--q-border, #262a31);border-radius:12px;padding:14px;margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;">
                <span style="color:var(--q-text-2, #b7bcc4);">Cost</span>
                <span style="font-weight:700;color:#fbbf24;">🪙 {cost:,} Quest Coins</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;border-top:1px solid var(--q-border, rgba(255,255,255,0.08));margin-top:6px;padding-top:6px;">
                <span style="color:var(--q-text-2, #b7bcc4);">Your Coin Balance</span>
                <span style="font-weight:600;color:var(--q-text, #f1f3f5);">🪙 {sender_coins:,}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if sender_coins < cost:
        st.error("⚠️ Insufficient Quest Coins. Top up your coins to continue.")
        if st.button("Close", use_container_width=True, key=f"dlg_gift_close_insufficient_{key}"):
            st.rerun()
        return

    query = st.text_input("Search a username to gift", placeholder="Type a username...", key=f"gift_search_{key}").strip().lower()

    import chat_system
    friends = chat_system.get_friends(sender) or []
    all_users = _cached_all_users()

    # Friends first, then every other known user, de-duplicated, sender excluded.
    ordered_candidates = []
    seen = set()
    for u in list(friends) + list(all_users):
        if u and u != sender and u not in seen:
            seen.add(u)
            ordered_candidates.append(u)

    if query:
        matches = [u for u in ordered_candidates if query in u.lower()][:8]
    else:
        matches = ordered_candidates[:8]

    recipient = None
    if matches:
        recipient = st.selectbox("Select recipient", matches, key=f"gift_recipient_{key}")
    else:
        st.caption("No matching users found.")

    if query and recipient is None:
        st.error(f"No user matching '{query}' found.")

    if recipient == sender:
        st.error("You can't gift yourself.")
        recipient = None

    col_y, col_n = st.columns(2)
    with col_y:
        if st.button("🎁 Send Gift", type="primary", use_container_width=True, key=f"dlg_gift_confirm_{key}"):
            if not recipient:
                st.error("Please select a valid recipient first.")
            else:
                import firebase_db
                if not firebase_db.user_exists(recipient):
                    st.error(f"User '@{recipient}' not found.")
                elif recipient == sender:
                    st.error("You can't gift yourself.")
                else:
                    ok, new_bal, ded_msg = firebase_db.deduct_user_quest_coins(sender, cost)
                    if not ok:
                        st.error(ded_msg)
                    else:
                        g_ok, g_msg, _ = firebase_db.grant_entitlement(recipient, key, duration_days=duration_days, cost_coins=0)
                        if not g_ok:
                            st.error(
                                f"⚠️ Coins were deducted but the gift could not be granted to @{recipient}: {g_msg}. "
                                "No automatic refund is available — please contact support."
                            )
                        else:
                            st.toast(f"🎁 Gifted {title} to @{recipient}!", icon=icon)
                            st.balloons()
                            st.rerun()
    with col_n:
        if st.button("❌ Cancel", use_container_width=True, key=f"dlg_gift_cancel_{key}"):
            st.rerun()


@st.dialog("Confirm QUEST Nitro Purchase")
def _confirm_nitro_dialog(username: str, user_coins: int, is_extend: bool):
    cost = 2500
    st.markdown(
        f"""
        <div style="text-align:center;padding:4px 0 12px;">
            <div style="font-size:2.2rem;margin-bottom:4px;">✨</div>
            <h3 style="margin:0 0 6px;color:#D4A843;font-weight:700;">{'Extend' if is_extend else 'Upgrade to'} QUEST Nitro</h3>
            <p style="font-size:0.86rem;color:var(--q-text-2, #b7bcc4);margin:0;line-height:1.4;">
                Unlock custom image/GIF banners, glowing profile animations, themes, and the PRO badge for <strong>30 Days</strong>.
            </p>
        </div>
        <div style="background:var(--q-surface-2, #18191c);border:1px solid rgba(212,168,67,0.3);border-radius:12px;padding:14px;margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;">
                <span style="color:var(--q-text-2, #b7bcc4);">Subscription Plan</span>
                <span style="font-weight:700;color:var(--q-text, #f1f3f5);">30 Days Nitro</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;">
                <span style="color:var(--q-text-2, #b7bcc4);">Cost</span>
                <span style="font-weight:700;color:#fbbf24;">🪙 {cost:,} Quest Coins</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;border-top:1px solid var(--q-border, rgba(255,255,255,0.08));margin-top:6px;padding-top:6px;">
                <span style="color:var(--q-text-2, #b7bcc4);">Current Coin Balance</span>
                <span style="font-weight:600;color:var(--q-text, #f1f3f5);">🪙 {user_coins:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;border-top:1px dashed var(--q-border, rgba(255,255,255,0.08));margin-top:6px;padding-top:6px;">
                <span style="color:var(--q-text-2, #b7bcc4);">Balance After Payment</span>
                <span style="font-weight:700;color:{'#22c55e' if user_coins >= cost else '#ef4444'};">🪙 {max(0, user_coins - cost):,}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user_coins < cost:
        st.error("⚠️ Insufficient Quest Coins. Top up your coins to continue.")
        if st.button("Close", use_container_width=True, key="dlg_close_nitro"):
            st.rerun()
    else:
        col_y, col_n = st.columns(2)
        with col_y:
            btn_txt = "✅ Yes, Extend (+30 Days)" if is_extend else "✅ Yes, Upgrade (2,500 Coins)"
            if st.button(btn_txt, type="primary", use_container_width=True, key="dlg_confirm_nitro"):
                import firebase_db
                ok, msg, res = firebase_db.upgrade_user_to_premium(username, duration_days=30, cost_coins=cost)
                if ok:
                    st.session_state.pop("_cached_profile", None)
                    st.session_state.pop("_user_profiles_cache", None)
                    if "user_info" in st.session_state and isinstance(st.session_state.user_info, dict):
                        st.session_state.user_info["is_pro"] = True
                        st.session_state.user_info["is_premium"] = True
                    st.toast("🎉 QUEST Nitro activated for 30 days!", icon="👑")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        with col_n:
            if st.button("❌ Cancel", use_container_width=True, key="dlg_cancel_nitro"):
                st.rerun()


@st.dialog("Confirm Entitlement Purchase")
def _confirm_entitlement_dialog(username: str, user_coins: int, key: str, title: str, cost: int, duration_days: int, icon: str, desc: str, is_extend: bool):
    st.markdown(
        f"""
        <div style="text-align:center;padding:4px 0 12px;">
            <div style="font-size:2.2rem;margin-bottom:4px;">{icon}</div>
            <h3 style="margin:0 0 6px;color:var(--q-text, #f1f3f5);font-weight:700;">{'Extend' if is_extend else 'Unlock'} {title}</h3>
            <p style="font-size:0.86rem;color:var(--q-text-2, #b7bcc4);margin:0;line-height:1.4;">
                {desc}
            </p>
        </div>
        <div style="background:var(--q-surface-2, #18191c);border:1px solid var(--q-border, #262a31);border-radius:12px;padding:14px;margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;">
                <span style="color:var(--q-text-2, #b7bcc4);">Duration</span>
                <span style="font-weight:700;color:var(--q-text, #f1f3f5);">{duration_days} Days</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;">
                <span style="color:var(--q-text-2, #b7bcc4);">Cost</span>
                <span style="font-weight:700;color:#fbbf24;">🪙 {cost:,} Quest Coins</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;border-top:1px solid var(--q-border, rgba(255,255,255,0.08));margin-top:6px;padding-top:6px;">
                <span style="color:var(--q-text-2, #b7bcc4);">Current Coin Balance</span>
                <span style="font-weight:600;color:var(--q-text, #f1f3f5);">🪙 {user_coins:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:0.86rem;border-top:1px dashed var(--q-border, rgba(255,255,255,0.08));margin-top:6px;padding-top:6px;">
                <span style="color:var(--q-text-2, #b7bcc4);">Balance After Payment</span>
                <span style="font-weight:700;color:{'#22c55e' if user_coins >= cost else '#ef4444'};">🪙 {max(0, user_coins - cost):,}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user_coins < cost:
        st.error("⚠️ Insufficient Quest Coins. Top up your coins to continue.")
        if st.button("Close", use_container_width=True, key=f"dlg_close_{key}"):
            st.rerun()
    else:
        col_y, col_n = st.columns(2)
        with col_y:
            btn_txt = f"✅ Yes, Extend (+{duration_days} Days)" if is_extend else f"✅ Yes, Unlock ({cost:,} Coins)"
            if st.button(btn_txt, type="primary", use_container_width=True, key=f"dlg_confirm_{key}"):
                import firebase_db
                ok, msg, res = firebase_db.grant_entitlement(username, key, duration_days=duration_days, cost_coins=cost)
                if ok:
                    st.toast(f"🎉 Successfully activated {title} for {duration_days} days!", icon="✨")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        with col_n:
            if st.button("❌ Cancel", use_container_width=True, key=f"dlg_cancel_{key}"):
                st.rerun()


def _get_entitlement_info(username: str, key: str) -> tuple[bool, int, str]:
    """Returns (is_active, remaining_days, formatted_expiry)."""
    if not username:
        return False, 0, ""
    try:
        import firebase_db
        if key == "premium":
            prem = firebase_db.get_premium_status(username)
            return (
                bool(prem.get("is_active")),
                int(prem.get("remaining_days", 0)),
                str(prem.get("formatted_expiry", ""))
            )

        if not firebase_db.has_entitlement(username, key):
            return False, 0, ""

        ents = firebase_db.get_user_entitlements(username)
        exp_raw = ents.get(key)
        if not exp_raw:
            return False, 0, ""
        if str(exp_raw).lower() in ["active", "lifetime", "true"]:
            return True, 999, "Active"

        exp_dt = None
        if hasattr(exp_raw, "date"):
            exp_dt = exp_raw
        elif isinstance(exp_raw, (int, float)):
            ts = exp_raw / 1000.0 if exp_raw > 1e11 else exp_raw
            exp_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(exp_raw, str):
            exp_dt = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))

        if exp_dt:
            if getattr(exp_dt, "tzinfo", None) is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            rem = max(1, (exp_dt.date() - now.date()).days)
            return True, rem, exp_dt.strftime("%b %d, %Y")

        return True, 30, "Active"
    except Exception:
        return False, 0, ""


def render(user_info):
    username = user_info.get("username", "") if isinstance(user_info, dict) else ""
    progress = edu_db.load_progress()
    workspace = st.query_params.get("workspace", "education")

    # Check if we just returned from a successful payment
    if st.query_params.get("success") == "true":
        if not st.session_state.get("payment_credited", False):
            url_amt = st.query_params.get("amt")
            if url_amt:
                try:
                    amount_paid_inr = float(url_amt)
                except ValueError:
                    amount_paid_inr = float(st.session_state.get("pending_payment_amount", 500.0))
            else:
                amount_paid_inr = float(st.session_state.get("pending_payment_amount", 500.0))

            coins_awarded = int(amount_paid_inr * 10)  # 10x Multiplier!

            current_coins = int(progress.get("quest_coins", 0))
            try:
                import firebase_db
                fb_coins = firebase_db.get_user_quest_coins(username)
                if fb_coins:
                    current_coins = fb_coins
            except Exception:
                pass

            new_coins = current_coins + coins_awarded
            progress["quest_coins"] = new_coins
            edu_db.save_progress(progress)

            if username:
                try:
                    import firebase_db
                    db = firebase_db.get_db()
                    if db:
                        db.collection("users").document(username).set({
                            "quest_coins": new_coins
                        }, merge=True)
                        edu_prog = firebase_db.get_edu_progress(username) or {}
                        edu_prog["quest_coins"] = new_coins
                        firebase_db.save_edu_progress(username, edu_prog)
                except Exception:
                    pass

            st.session_state.payment_credited = True
            st.session_state.pending_payment_amount = 0.0

            st.balloons()
            st.success(f"🎉 Payment Successful! You received {coins_awarded:,} Quest Coins!")

            st.query_params.pop("success", None)
            st.query_params.pop("amt", None)
        else:
            st.success("Payment already processed.")
            st.query_params.pop("success", None)
            st.query_params.pop("amt", None)

    # Fetch live coins balance
    quest_coins = None
    if username:
        try:
            import firebase_db
            quest_coins = firebase_db.get_user_quest_coins(username)
        except Exception:
            quest_coins = None

    if quest_coins is None or quest_coins == 0:
        prog = edu_db.load_progress()
        quest_coins = int(prog.get("quest_coins", 0))

    # Header Row with Shop Title and Top-Right Coin Counter Pill
    header_html = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem;">
        <h1 style="margin:0; padding:0; color:var(--q-text, #f8fafc); font-size:1.9rem; font-weight:700; display:flex; align-items:center; gap:0.5rem;">
            🛒 Shop
        </h1>
        <div style="background:var(--q-surface-2, #1c1f25); border:1px solid var(--q-border, #262a31); border-radius:9999px; padding:6px 16px; font-weight:600; font-size:0.95rem; color:var(--q-text, #f1f3f5); display:inline-flex; align-items:center; gap:8px; box-shadow:0 1px 3px rgba(0,0,0,0.25);">
            <span>🪙</span><span style="color:#fbbf24; font-weight:700;">{quest_coins:,}</span>
        </div>
    </div>
    <p style="color:var(--q-text-3, #94a3b8); margin-top:0.15rem; margin-bottom:1.5rem; font-size:0.92rem;">
        Purchase digital passes, subscriptions, and power-ups using your Quest Coins.
    </p>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # STORE SECTION (CARD GRID)
    # ──────────────────────────────────────────────────────────────────────────
    st.markdown("### 🛍️ Store")
    st.markdown("<p style='font-size:0.9rem; color:var(--q-text-3, #94a3b8); margin-bottom:1rem;'>Unlock premium subscriptions and exclusive features with your Quest Coins.</p>", unsafe_allow_html=True)

    # Entitlement statuses
    nitro_active, nitro_rem_days, _ = _get_entitlement_info(username, "premium")
    adfree_active, adfree_rem_days, _ = _get_entitlement_info(username, "ad_free")
    news_active, news_rem_days, _ = _get_entitlement_info(username, "news_access")
    intl_active, intl_rem_days, _ = _get_entitlement_info(username, "intl_stocks")

    # Grid columns (4 columns in professional workspace, 3 columns in education workspace)
    is_prof = (workspace == "professional")
    if is_prof:
        c_nitro, c_adfree, c_news, c_intl = st.columns(4)
    else:
        c_nitro, c_adfree, c_intl = st.columns(3)
        c_news = None

    # 1. QUEST Nitro Card
    with c_nitro:
        with st.container(border=True):
            if nitro_active:
                badge_html = f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>👑</span><span style='font-size:0.72rem;font-weight:700;color:#D4A843;background:rgba(212,168,67,0.15);padding:2px 8px;border-radius:12px;border:1px solid #D4A84355;'>ACTIVE • {nitro_rem_days}d left</span></div>"
            else:
                badge_html = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>👑</span><span style='font-size:0.72rem;font-weight:700;color:#fbbf24;background:rgba(251,191,36,0.12);padding:2px 8px;border-radius:12px;border:1px solid #fbbf2444;'>PRO PASS</span></div>"

            st.markdown(badge_html, unsafe_allow_html=True)
            st.markdown("<h4 style='margin:0 0 4px;font-size:1.05rem;color:var(--q-text);'>QUEST Nitro</h4>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.8rem;color:var(--q-text-3);line-height:1.35;min-height:48px;margin-bottom:8px;'>Custom GIF banners, glowing effects, themes & PRO badge.</p>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight:700;font-size:0.95rem;color:#fbbf24;margin-bottom:12px;'>🪙 2,500 Coins <span style='font-size:0.75rem;color:var(--q-text-3);font-weight:400;'>/ 30 Days</span></div>", unsafe_allow_html=True)

            nitro_act_col, nitro_gift_col = st.columns([4, 1])
            if nitro_active:
                with nitro_act_col:
                    if st.button("➕ Extend (+30d)", key="btn_store_nitro_ext", use_container_width=True):
                        _confirm_nitro_dialog(username, quest_coins, is_extend=True)
            else:
                if quest_coins >= 2500:
                    with nitro_act_col:
                        if st.button("Upgrade (2,500 🪙)", type="primary", key="btn_store_nitro_buy", use_container_width=True):
                            _confirm_nitro_dialog(username, quest_coins, is_extend=False)
                else:
                    with nitro_act_col:
                        st.button(f"Need {2500 - quest_coins:,} more coins", disabled=True, key="btn_store_nitro_dis", use_container_width=True)
                    st.markdown('<div style="text-align:center;margin-top:4px;"><a href="#top-up-coins" style="color:var(--q-accent, #5DCAA5);font-size:0.78rem;text-decoration:none;font-weight:600;">🪙 Buy Coins ↓</a></div>', unsafe_allow_html=True)
            with nitro_gift_col:
                if st.button("🎁", key="btn_gift_nitro", help="Gift to another user", use_container_width=True):
                    _gift_dialog(username, quest_coins, "premium", "QUEST Nitro", 2500, 30, "👑")

    # 2. Ad Free Tier Card
    with c_adfree:
        with st.container(border=True):
            if adfree_active:
                badge_html = f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>🛡️</span><span style='font-size:0.72rem;font-weight:700;color:#22c55e;background:rgba(34,197,94,0.15);padding:2px 8px;border-radius:12px;border:1px solid #22c55e55;'>ACTIVE • {adfree_rem_days}d left</span></div>"
            else:
                badge_html = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>🛡️</span><span style='font-size:0.72rem;font-weight:700;color:#38bdf8;background:rgba(56,189,248,0.12);padding:2px 8px;border-radius:12px;border:1px solid #38bdf844;'>AD-FREE</span></div>"

            st.markdown(badge_html, unsafe_allow_html=True)
            st.markdown("<h4 style='margin:0 0 4px;font-size:1.05rem;color:var(--q-text);'>Ad-Free Tier</h4>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.8rem;color:var(--q-text-3);line-height:1.35;min-height:48px;margin-bottom:8px;'>Removes all sponsor banners & promotions across learning modules.</p>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight:700;font-size:0.95rem;color:#fbbf24;margin-bottom:12px;'>🪙 1,000 Coins <span style='font-size:0.75rem;color:var(--q-text-3);font-weight:400;'>/ 30 Days</span></div>", unsafe_allow_html=True)

            adfree_act_col, adfree_gift_col = st.columns([4, 1])
            if adfree_active:
                with adfree_act_col:
                    if st.button("➕ Extend (+30d)", key="btn_store_adfree_ext", use_container_width=True):
                        _confirm_entitlement_dialog(username, quest_coins, "ad_free", "Ad-Free Tier", 1000, 30, "🛡️", "Removes all sponsored ad banners and promotions across modules.", is_extend=True)
            else:
                if quest_coins >= 1000:
                    with adfree_act_col:
                        if st.button("Get Ad-Free (1,000 🪙)", type="primary", key="btn_store_adfree_buy", use_container_width=True):
                            _confirm_entitlement_dialog(username, quest_coins, "ad_free", "Ad-Free Tier", 1000, 30, "🛡️", "Removes all sponsored ad banners and promotions across modules.", is_extend=False)
                else:
                    with adfree_act_col:
                        st.button(f"Need {1000 - quest_coins:,} more coins", disabled=True, key="btn_store_adfree_dis", use_container_width=True)
                    st.markdown('<div style="text-align:center;margin-top:4px;"><a href="#top-up-coins" style="color:var(--q-accent, #5DCAA5);font-size:0.78rem;text-decoration:none;font-weight:600;">🪙 Buy Coins ↓</a></div>', unsafe_allow_html=True)
            with adfree_gift_col:
                if st.button("🎁", key="btn_gift_adfree", help="Gift to another user", use_container_width=True):
                    _gift_dialog(username, quest_coins, "ad_free", "Ad-Free Tier", 1000, 30, "🛡️")

    # 3. News Section Card (Professional Workspace only)
    if is_prof and c_news is not None:
        with c_news:
            with st.container(border=True):
                if news_active:
                    badge_html = f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>📰</span><span style='font-size:0.72rem;font-weight:700;color:#38bdf8;background:rgba(56,189,248,0.15);padding:2px 8px;border-radius:12px;border:1px solid #38bdf855;'>ACTIVE • {news_rem_days}d left</span></div>"
                else:
                    badge_html = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>📰</span><span style='font-size:0.72rem;font-weight:700;color:#a855f7;background:rgba(168,85,247,0.12);padding:2px 8px;border-radius:12px;border:1px solid #a855f744;'>PRO INTEL</span></div>"

                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown("<h4 style='margin:0 0 4px;font-size:1.05rem;color:var(--q-text);'>News Intelligence</h4>", unsafe_allow_html=True)
                st.markdown("<p style='font-size:0.8rem;color:var(--q-text-3);line-height:1.35;min-height:48px;margin-bottom:8px;'>Institutional sentiment tracking, earnings calendar & 2-yr news archive.</p>", unsafe_allow_html=True)
                st.markdown("<div style='font-weight:700;font-size:0.95rem;color:#fbbf24;margin-bottom:12px;'>🪙 1,500 Coins <span style='font-size:0.75rem;color:var(--q-text-3);font-weight:400;'>/ 30 Days</span></div>", unsafe_allow_html=True)

                if news_active:
                    if st.button("➕ Extend (+30d)", key="btn_store_news_ext", use_container_width=True):
                        _confirm_entitlement_dialog(username, quest_coins, "news_access", "News Intelligence", 1500, 30, "📰", "Unlocks real-time institutional sentiment tracking, corporate filings, and market intelligence feeds.", is_extend=True)
                else:
                    if quest_coins >= 1500:
                        if st.button("Unlock News (1,500 🪙)", type="primary", key="btn_store_news_buy", use_container_width=True):
                            _confirm_entitlement_dialog(username, quest_coins, "news_access", "News Intelligence", 1500, 30, "📰", "Unlocks real-time institutional sentiment tracking, corporate filings, and market intelligence feeds.", is_extend=False)
                    else:
                        st.button(f"Need {1500 - quest_coins:,} more coins", disabled=True, key="btn_store_news_dis", use_container_width=True)
                        st.markdown('<div style="text-align:center;margin-top:4px;"><a href="#top-up-coins" style="color:var(--q-accent, #5DCAA5);font-size:0.78rem;text-decoration:none;font-weight:600;">🪙 Buy Coins ↓</a></div>', unsafe_allow_html=True)

    # 4. International Stock Access Card (Global Markets)
    with c_intl:
        with st.container(border=True):
            intl_unlocked = edu_db.is_module_completed("module_5")

            if intl_active:
                badge_html = f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>🌐</span><span style='font-size:0.72rem;font-weight:700;color:#22c55e;background:rgba(34,197,94,0.15);padding:2px 8px;border-radius:12px;border:1px solid #22c55e55;'>ACTIVE • {intl_rem_days}d left</span></div>"
            elif not intl_unlocked:
                badge_html = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>🌐</span><span style='font-size:0.72rem;font-weight:700;color:var(--q-text-3);background:var(--q-surface-2);padding:2px 8px;border-radius:12px;border:1px solid var(--q-border);'>LOCKED</span></div>"
            else:
                badge_html = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'><span style='font-size:1.2rem;'>🌐</span><span style='font-size:0.72rem;font-weight:700;color:#a855f7;background:rgba(168,85,247,0.12);padding:2px 8px;border-radius:12px;border:1px solid #a855f744;'>NEW</span></div>"

            st.markdown(badge_html, unsafe_allow_html=True)
            st.markdown("<h4 style='margin:0 0 4px;font-size:1.05rem;color:var(--q-text);'>US & Global Stocks</h4>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.8rem;color:var(--q-text-3);line-height:1.35;min-height:48px;margin-bottom:8px;'>Direct trading access to NASDAQ, NYSE, and international equities.</p>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight:700;font-size:0.95rem;color:#fbbf24;margin-bottom:12px;'>🪙 3,500 Coins <span style='font-size:0.75rem;color:var(--q-text-3);font-weight:400;'>/ 30 Days</span></div>", unsafe_allow_html=True)

            if intl_active:
                if st.button("➕ Extend (+30d)", key="btn_store_intl_ext", use_container_width=True):
                    _confirm_entitlement_dialog(username, quest_coins, "intl_stocks", "US & Global Stocks", 3500, 30, "🌐", "Unlocks direct paper-trading access to NASDAQ, NYSE, and international equities in the Global Markets Simulator.", is_extend=True)
            elif not intl_unlocked:
                st.button("🔒 Complete Module 5 to unlock", disabled=True, key="btn_store_intl_locked", use_container_width=True)
                st.markdown("<p style='font-size:0.75rem;color:var(--q-text-3);text-align:center;margin-top:6px;line-height:1.35;'>Finish Module 5 — Build Your Portfolio in the Learning Path first.</p>", unsafe_allow_html=True)
            else:
                if quest_coins >= 3500:
                    if st.button("Unlock (3,500 🪙)", type="primary", key="btn_store_intl_buy", use_container_width=True):
                        _confirm_entitlement_dialog(username, quest_coins, "intl_stocks", "US & Global Stocks", 3500, 30, "🌐", "Unlocks direct paper-trading access to NASDAQ, NYSE, and international equities in the Global Markets Simulator.", is_extend=False)
                else:
                    st.button(f"Need {3500 - quest_coins:,} more coins", disabled=True, key="btn_store_intl_dis", use_container_width=True)
                    st.markdown('<div style="text-align:center;margin-top:4px;"><a href="#top-up-coins" style="color:var(--q-accent, #5DCAA5);font-size:0.78rem;text-decoration:none;font-weight:600;">🪙 Buy Coins ↓</a></div>', unsafe_allow_html=True)

    st.markdown("<div id='top-up-coins' style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown("---")

    # ──────────────────────────────────────────────────────────────────────────
    # TOP UP COINS SECTION (RAZORPAY)
    # ──────────────────────────────────────────────────────────────────────────
    st.markdown("### 🪙 Top up your coins")
    st.markdown("<p style='font-size:0.9rem; color:var(--q-text-3, #94a3b8); margin-bottom:1rem;'>Use Quest Coins to unlock Discord Nitro Themes, US Stocks, and Premium Badges!</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center; margin-top:0.25rem;'>Starter</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#38bdf8; margin:0.3rem 0;'>5,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:var(--q-text-3, #94a3b8); font-size:0.9rem;'>for ₹ 500</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 500", key="buy_500", use_container_width=True):
                _create_payment_link(500, user_info)

    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center; margin-top:0.25rem;'>Pro</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#a855f7; margin:0.3rem 0;'>10,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:var(--q-text-3, #94a3b8); font-size:0.9rem;'>for ₹ 1,000</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 1,000", key="buy_1000", type="primary", use_container_width=True):
                _create_payment_link(1000, user_info)

    with col3:
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center; margin-top:0.25rem;'>Whale</h3>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align:center; color:#fbbf24; margin:0.3rem 0;'>50,000 Coins</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:var(--q-text-3, #94a3b8); font-size:0.9rem;'>for ₹ 5,000</p>", unsafe_allow_html=True)
            if st.button("Pay ₹ 5,000", key="buy_5000", use_container_width=True):
                _create_payment_link(5000, user_info)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🎛️ Custom Amount")
    st.markdown("<p style='font-size:0.9rem; color:var(--q-text-3, #94a3b8);'>Need a specific amount? Enter it below. (Min: ₹500 | Max: ₹1,00,000)</p>", unsafe_allow_html=True)

    custom_col1, custom_col2 = st.columns([2, 1])
    with custom_col1:
        custom_amt = st.number_input("Amount (INR)", min_value=500, max_value=100000, value=1500, step=100)
        st.markdown(f"<p style='color:#34d399;'>You will receive: <b>{int(custom_amt * 10):,} Quest Coins</b></p>", unsafe_allow_html=True)
    with custom_col2:
        st.markdown("<br>", unsafe_allow_html=True)  # padding for alignment
        if st.button(f"Pay ₹ {custom_amt:,}", key="buy_custom", type="primary", use_container_width=True):
            _create_payment_link(custom_amt, user_info)


def _create_payment_link(amount_inr, user_info):
    if razorpay is None:
        st.error("Razorpay SDK is not installed. Please run: pip install razorpay")
        return
    try:
        # Initialize Razorpay Client with provided test keys
        client = razorpay.Client(auth=("rzp_test_TaNK4SlVzf5jfB", "9vb4dFfdUSxs9sZ9PH66XMDc"))

        # Setup redirect URL - preserve current workspace and redirect to page=Shop
        current_ws = st.query_params.get("workspace", "education")
        redirect_url = f"http://localhost:8501/?workspace={current_ws}&page=Shop&success=true&amt={amount_inr}"

        user_info_dict = user_info if isinstance(user_info, dict) else {}
        data = {
            "amount": amount_inr * 100,  # Razorpay expects paise (multiply by 100)
            "currency": "INR",
            "description": f"Top-Up QUEST Coins (₹{amount_inr})",
            "customer": {
                "name": user_info_dict.get("display_name", "Test User"),
                "email": user_info_dict.get("email", "test@example.com"),
                "contact": "9876543210",
            },
            "notify": {
                "sms": False,
                "email": False,
            },
            "reminder_enable": False,
            "callback_url": redirect_url,
            "callback_method": "get",
        }

        # Save pending amount in session state to credit upon return
        st.session_state.pending_payment_amount = float(amount_inr)
        st.session_state.payment_credited = False

        # Generate link
        payment_link = client.payment_link.create(data)
        checkout_url = payment_link.get("short_url")

        if checkout_url:
            st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
            st.info(f"Redirecting to secure Razorpay checkout... [Click here if not redirected]({checkout_url})")

    except Exception as e:
        st.error(f"Failed to create payment link: {str(e)}")
