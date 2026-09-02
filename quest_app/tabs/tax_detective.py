import streamlit as st
import tax_detective_db
from edu_db import load_progress

# ── Shared layout helpers ────────────────────────────────────────────────────
# These accept a `practice` flag so both the real run and practice run can
# reuse the same HTML without duplicating full blocks.

def _case_card_html(case: dict, practice: bool = False) -> str:
    snap_rows = "".join([
        f'<div class="td-snap-row"><span>{r[0]}</span><b>{r[1]}</b></div>'
        for r in case["snapshot"]
    ])
    badge = (
        '<div style="font-size:10px; color:#8994a4; background:#161c23; '
        'border:1px solid #2a323c; padding:7px 10px; border-radius:8px; height:max-content;">'
        '🕵️ Practice · no retry</div>'
        if practice else
        '<div style="font-size:10px; color:#8994a4; background:#161c23; '
        'border:1px solid #2a323c; padding:7px 10px; border-radius:8px; height:max-content;">'
        '🔒 One decision · no retry</div>'
    )
    return f"""
<div class="td-case">
<div class="td-case-top">
<div>
<div class="td-case-id">{case['id']}</div>
<div class="td-case-title">{case['title']}</div>
</div>
{badge}
</div>
<div class="td-scenario">
<div class="td-person">
<div class="td-avatar">{case['avatar']}</div>
<p>{case['scenario']}</p>
</div>
<div class="td-snapshot">
<div class="td-snap-title">Case snapshot</div>
{snap_rows}
</div>
</div>
</div>
"""

def _result_panel_html(res: dict, practice: bool = False) -> str:
    is_correct = res["is_correct"]
    header_text = "Strong investigation." if is_correct else "Good attempt — here's the clue you missed."
    meta_text = (
        ("Practice hit! You got this one right." if is_correct else "Use the explanation to sharpen your approach.")
        if practice else
        ("You identified the key tax concept. +₹5,000 toward your potential reward." if is_correct else "Use the explanation to learn the rule.")
    )
    explanations_html = ""
    for n, exp in enumerate(res["all_explanations"]):
        is_good = (n == res["correct_index"])
        explanations_html += (
            f'<div class="td-why {"good" if is_good else "bad"}">'
            f'<b>Option {chr(65+n)} — {"Best choice" if is_good else "Why not"}:</b> {exp}</div>'
        )
    return f"""
<div class="td-result" style="background: linear-gradient(145deg, #11161d, #0e1319); border:1px solid #2a323d; border-radius:18px; margin-top:20px;">
<div style="display:flex; gap:12px; align-items:center; margin-bottom:13px;">
<div style="width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-weight:900; background:{'#153e2e' if is_correct else '#452028'}; color:{'#42d995' if is_correct else '#ff6877'};">
{('✓' if is_correct else '!')}
</div>
<div>
<h2 style="font-size:15px; margin:0 0 3px; color:#f4f7fb;">{header_text}</h2>
<div style="font-size:10px; color:#7c8898;">{meta_text}</div>
</div>
</div>
<div class="td-explain">
<div style="font-size:8px; letter-spacing:1.2px; color:#708095; font-weight:900; margin-bottom:6px;">CASE ANALYSIS</div>
<b>Why your choice {'works' if is_correct else "isn't the strongest"}:</b> {res['explanation']}
<div class="td-takeaway"><b>Key takeaway:</b> {res['takeaway']}</div>
</div>
<div style="margin-top:10px; display:grid; gap:7px;">
{explanations_html}
</div>
</div>
"""

# ── Practice-mode state helpers ──────────────────────────────────────────────

def _practice_init():
    """Reset all practice-mode session state to start a fresh practice run."""
    st.session_state.td_practice_case_idx = 0
    st.session_state.td_practice_correct = 0
    st.session_state.td_practice_answers = {}   # case_id -> {chosen, is_correct}
    st.session_state.td_practice_result = None  # result dict for the current case
    st.session_state.td_practice_done = False

def _practice_active() -> bool:
    return st.session_state.get("td_practice_mode", False)

def _exit_practice():
    st.session_state.td_practice_mode = False
    st.session_state.td_practice_case_idx = 0
    st.session_state.td_practice_correct = 0
    st.session_state.td_practice_answers = {}
    st.session_state.td_practice_result = None
    st.session_state.td_practice_done = False

# ── Practice banner ──────────────────────────────────────────────────────────

PRACTICE_BANNER = """
<div style="display:flex; align-items:center; gap:8px; background:#1a1528; border:1px solid #3d2f5e;
 border-radius:8px; padding:7px 14px; margin-bottom:16px; max-width:1120px; margin-left:auto; margin-right:auto;">
<span style="font-size:10px; font-weight:900; letter-spacing:1.2px; color:#9b7ee0; text-transform:uppercase;">
🕵️ Practice Mode</span>
<span style="font-size:10px; color:#6b5e8a; margin-left:4px;">— no XP, no reward, nothing saved</span>
</div>
"""

# ── Shared page CSS ──────────────────────────────────────────────────────────

PAGE_CSS = """
<style>
.td-hero { max-width:1120px; margin: 38px auto 20px; display:flex; justify-content:space-between; align-items:flex-end; gap:25px; }
.td-eyebrow { font-size:10px; color:#70adff; letter-spacing:1.5px; text-transform:uppercase; font-weight:900; margin-bottom:9px; }
.td-hero h1 { margin:0 0 8px; font-size:36px; letter-spacing:-1.5px; color:#f4f7fb; }
.td-sub { font-size:14px; color:#8994a4; line-height:1.65; max-width:700px; }
.td-reward { white-space:nowrap; background:#17140e; border:1px solid #4b4025; color:#f2c86a; border-radius:11px; padding:10px 14px; font-size:11px; font-weight:800; }
.td-case { max-width:1120px; margin:auto; background:linear-gradient(145deg,#11161d,#0e1319); border:1px solid #2a323d; border-radius:18px; overflow:hidden; box-shadow:0 25px 70px #0007; }
.td-case-top { padding:21px 25px; border-bottom:1px solid #232b35; display:flex; justify-content:space-between; gap:20px; }
.td-case-id { font-size:10px; color:#667487; letter-spacing:1px; }
.td-case-title { font-size:21px; font-weight:800; margin-top:5px; color:#f4f7fb; }
.td-scenario { padding:23px 25px 18px; display:grid; grid-template-columns:1fr 230px; gap:25px; }
.td-person { display:flex; gap:13px; }
.td-avatar { width:45px; height:45px; border-radius:13px; background:linear-gradient(145deg,#2b3e59,#172432); border:1px solid #39485b; display:grid; place-items:center; font-weight:800; font-size:13px; flex:none; color:#f4f7fb; }
.td-scenario p { margin:0; color:#c8d0db; font-size:13px; line-height:1.75; }
.td-snapshot { background:#0a0e13; border:1px solid #232b34; border-radius:12px; padding:12px; }
.td-snap-title { font-size:9px; color:#647184; letter-spacing:1px; text-transform:uppercase; margin-bottom:8px; }
.td-snap-row { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid #1c232c; font-size:10px; }
.td-snap-row:last-child { border:0; }
.td-snap-row span { color:#748093; }
.td-snap-row b { color:#dce2e9; }
.td-result { padding:20px 25px 25px; border-top:1px solid #252d37; }
.td-explain { background:#0a0e13; border:1px solid #232b34; border-radius:12px; padding:17px; font-size:11px; line-height:1.7; color:#aeb8c5; margin-bottom:10px; }
.td-takeaway { margin-top:13px; padding-top:12px; border-top:1px solid #202730; color:#c7d0dc; }
.td-why { padding:10px 12px; border-radius:9px; border:1px solid #242c35; background:#10151b; font-size:10px; line-height:1.55; color:#8d98a6; margin-bottom:7px; }
.td-why.good { border-color:#205f47; }
.td-why.bad { border-color:#593039; }
.td-summary { max-width:1120px; margin:auto; background:#11171e; border:1px solid #2a333d; border-radius:18px; box-shadow:0 25px 70px #0007; padding:55px 30px; text-align:center; color:#f4f7fb; }
.td-summary h2 { font-size:27px; margin:0 0 7px; color:#f4f7fb; }
.td-summary p { color:#8995a5; font-size:12px; line-height:1.6; }
.td-score { display:inline-flex; gap:18px; margin:18px 0; padding:13px 18px; background:#0b1015; border:1px solid #28313b; border-radius:12px; }
.td-claim { color:#5ce3a0; font-weight:850; font-size:13px; margin:5px 0 20px; }
.td-claim.fail { color:#ff7c87; }
.td-coming { margin:25px auto 20px; max-width:600px; padding:18px; border:1px dashed #35404c; border-radius:12px; background:#0d1218; }
</style>
"""

# ── Practice-run renderer ────────────────────────────────────────────────────

def _render_practice(prog: dict):
    """Full practice-mode flow. Reads/writes only st.session_state — no edu_db writes."""
    st.markdown(PRACTICE_BANNER, unsafe_allow_html=True)

    # Header (simplified — no gold reward badge, no wallet)
    wallet_bal = prog.get("virtual_balance", 0.0)
    st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; max-width:1120px; margin:auto; margin-bottom:4px;">
<div style="font-size:12px; color:#6e7b8c;">Tax Detective <span>›</span> <b style="color:#c1cad5;">Practice Run</b></div>
<div style="display:flex; gap:8px; align-items:center;">
<div style="display:flex; align-items:center; gap:9px; background:#121820; border:1px solid #29323e; border-radius:12px; padding:8px 13px;">
<div style="width:28px; height:28px; border-radius:8px; background:#18392f; color:#42d995; display:grid; place-items:center; font-weight:800;">₹</div>
<div><small style="display:block; font-size:9px; color:#718093;">VIRTUAL BALANCE</small><strong style="font-size:14px; color:#f4f7fb;">₹{wallet_bal:,.0f}</strong></div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

    # ── Practice summary screen ──────────────────────────────────────────────
    if st.session_state.get("td_practice_done", False):
        correct = st.session_state.get("td_practice_correct", 0)
        st.markdown(f"""
<div class="td-summary" style="border-color:#3d2f5e;">
<div style="font-size:10px; font-weight:900; letter-spacing:1.2px; color:#9b7ee0; text-transform:uppercase; margin-bottom:16px;">🕵️ Practice Mode — No XP · No Reward</div>
<div style="font-size:40px; margin-bottom:10px;">{'✓' if correct >= 3 else '📋'}</div>
<h2>Practice complete.</h2>
<p>{'Great recall — you got the right answer on most cases.' if correct >= 3 else 'A few cases to review. Use the explanations to sharpen your approach.'}</p>
<div class="td-score"><strong>{correct}/4</strong><span>correct in this practice run</span></div>
<div style="font-size:11px; color:#6b5e8a; margin:0 0 24px;">Practice runs are not graded and do not affect your balance or XP.</div>
</div>
""", unsafe_allow_html=True)

        st.write("")
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("← Back to Case Board", key="practice_back_summary", use_container_width=True):
                _exit_practice()
                st.rerun()
        with col_c:
            if st.button("🔄 Practice Again", key="practice_again", type="secondary", use_container_width=True):
                _practice_init()
                st.rerun()
        return

    # ── Practice case flow ───────────────────────────────────────────────────
    cases = tax_detective_db.get_public_cases()
    # get_public_cases strips c/why — but for practice we need full data for result reveal
    full_cases = [tax_detective_db.get_case(i) for i in range(len(cases))]

    case_idx = st.session_state.get("td_practice_case_idx", 0)
    answers = st.session_state.get("td_practice_answers", {})
    correct_count = st.session_state.get("td_practice_correct", 0)
    total = len(cases)

    # Exit button — always visible during practice
    col_exit, _ = st.columns([1, 4])
    with col_exit:
        if st.button("← Exit Practice", key="practice_exit_top", use_container_width=True):
            _exit_practice()
            st.rerun()

    st.write("")

    # Progress
    answered = len(answers)
    progress_val = answered / total if not st.session_state.get("td_practice_result") else (answered - 1) / total
    # When viewing result, we count the answered case as in-progress still for display
    display_idx = case_idx + 1
    st.progress(
        answered / total,
        text=f"PRACTICE · CASE {display_idx} OF {total} | {correct_count} correct"
    )

    case_pub = cases[case_idx]
    case_full = full_cases[case_idx]

    st.markdown(_case_card_html(case_pub, practice=True), unsafe_allow_html=True)
    st.write("")

    prac_result = st.session_state.get("td_practice_result")

    if prac_result is None:
        # Show choices
        cols = st.columns(3)
        for i, choice in enumerate(case_pub["choices"]):
            with cols[i]:
                st.markdown(
                    f"<div style='font-size:10px; font-weight:800; color:#697789; margin-bottom:4px;'>OPTION {chr(65+i)}</div>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<b style='font-size:14px; display:block; margin-bottom:5px; color:#edf1f6;'>{choice['t']}</b>"
                    f"<span style='font-size:11px; color:#8d98a7;'>{choice['d']}</span>",
                    unsafe_allow_html=True
                )
                if st.button("Select Option " + chr(65+i), key=f"pbtn_{case_idx}_{i}", use_container_width=True):
                    full_choices = case_full["choices"]
                    chosen = full_choices[i]
                    is_correct = chosen.get("c", False)
                    correct_index = next((n for n, c in enumerate(full_choices) if c.get("c")), -1)
                    result = {
                        "is_correct": is_correct,
                        "correct_index": correct_index,
                        "explanation": chosen.get("why", ""),
                        "all_explanations": [c.get("why", "") for c in full_choices],
                        "takeaway": case_full["takeaway"],
                    }
                    answers[case_pub["id"]] = {"chosen": i, "is_correct": is_correct}
                    if is_correct:
                        st.session_state.td_practice_correct = correct_count + 1
                    st.session_state.td_practice_answers = answers
                    st.session_state.td_practice_result = result
                    st.rerun()
    else:
        # Show result panel
        st.markdown(_result_panel_html(prac_result, practice=True), unsafe_allow_html=True)
        st.write("")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Exit Practice", key="practice_exit_result", use_container_width=True):
                _exit_practice()
                st.rerun()
        with col3:
            is_last = (case_idx >= total - 1)
            next_label = "See Practice Summary" if is_last else "Next Case →"
            if st.button(next_label, key="practice_next", type="secondary", use_container_width=True):
                if is_last:
                    st.session_state.td_practice_done = True
                else:
                    st.session_state.td_practice_case_idx = case_idx + 1
                st.session_state.td_practice_result = None
                st.rerun()


# ── Closed-board screen ──────────────────────────────────────────────────────

def _render_closed_board(prog: dict):
    """Terminal state: user has already completed their one real run."""
    wallet_bal = prog.get("virtual_balance", 0.0)
    st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; max-width:1120px; margin:auto;">
<div style="font-size:12px; color:#6e7b8c;">Tax Detective <span>›</span> <b style="color:#c1cad5;">Case Files</b></div>
<div style="display:flex; align-items:center; gap:9px; background:#121820; border:1px solid #29323e; border-radius:12px; padding:8px 13px;">
<div style="width:28px; height:28px; border-radius:8px; background:#18392f; color:#42d995; display:grid; place-items:center; font-weight:800;">₹</div>
<div><small style="display:block; font-size:9px; color:#718093;">VIRTUAL BALANCE</small><strong style="font-size:14px; color:#f4f7fb;">₹{wallet_bal:,.0f}</strong></div>
</div>
</div>
<div style="max-width:1120px; margin:40px auto 0; background:#11171e; border:1px solid #2a333d; border-radius:18px; box-shadow:0 25px 70px #0007; padding:50px 30px; text-align:center; color:#f4f7fb;">
<div style="font-size:48px; margin-bottom:16px;">🔒</div>
<h2 style="font-size:24px; margin:0 0 10px; color:#f4f7fb;">Case board closed</h2>
<p style="color:#8995a5; font-size:13px; line-height:1.7; max-width:520px; margin:0 auto 28px;">You've already completed this investigation. Your run is on the record — no new graded attempts are available.</p>
<div style="display:inline-block; margin:0 auto 28px; padding:18px 24px; background:#0b1015; border:1px solid #28313b; border-radius:12px;">
<div style="font-size:9px; color:#647184; letter-spacing:1px; text-transform:uppercase; margin-bottom:6px;">Investigation status</div>
<div style="font-size:15px; font-weight:800; color:#42d995;">✓ Completed</div>
</div>
<div style="margin:0 auto 28px; max-width:560px; padding:18px; border:1px dashed #35404c; border-radius:12px; background:#0d1218;">
<b style="color:#c8d0db;">🔒 New cases are coming soon</b>
<p style="margin:8px 0 0; font-size:11px; color:#748092; line-height:1.6;">New tax scenarios, trickier clues and fresh investigations will be added to the Tax Detective case board. Check back later to take on the next set of cases.</p>
</div>
</div>
""", unsafe_allow_html=True)

    # Practice Mode opt-in — visually distinct from a primary CTA
    st.write("")
    col_l, col_c, col_r = st.columns([1.5, 1, 1.5])
    with col_c:
        st.markdown(
            "<div style='text-align:center; font-size:10px; color:#6b5e8a; margin-bottom:6px;'>"
            "Want to review the cases?</div>",
            unsafe_allow_html=True
        )
        if st.button("🕵️ Enter Practice Mode", key="enter_practice", use_container_width=True):
            st.session_state.td_practice_mode = True
            _practice_init()
            st.rerun()


# ── One-time real-run summary ────────────────────────────────────────────────

def _render_completed_summary(attempt: dict, prog: dict):
    """Show the one-time pass/fail summary right after finishing. No replay button."""
    passed = attempt["correct_count"] >= 3
    icon = "✓" if passed else "!"
    title = "Case file closed. You cracked it." if passed else "Investigation incomplete."
    sub = (
        "You completed all four investigations and reached the minimum score of 3/4."
        if passed else
        "You completed all four cases, but you needed at least 3 correct. Because the reward requires a 3/4 score, no reward is unlocked this run."
    )
    claim_class = "td-claim" if passed else "td-claim fail"
    claim_text = f"✦ Reward unlocked: ₹{attempt['reward_amount']:,.0f}" if passed else "Reward unlocked: ₹0"

    st.markdown(f"""
<div class="td-summary">
<div style="font-size:40px; margin-bottom:10px;">{icon}</div>
<h2>{title}</h2>
<p>{sub}</p>
<div class="td-score"><strong>{attempt['correct_count']}/4</strong><span>cases solved correctly</span></div>
<div class="{claim_class}">{claim_text}</div>
<div class="td-coming"><b>🔒 More cases are coming soon</b><p style="margin:6px 0 0; font-size:10px; color:#748092;">New tax scenarios, trickier clues and fresh investigations will be added to the Tax Detective case board.</p></div>
</div>
""", unsafe_allow_html=True)
    # No "Play again" button — next render() will show the closed-board screen.


# ── Main entry point ─────────────────────────────────────────────────────────

def render(user_info: dict):
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    prog = load_progress()

    # ── EARLY EXIT: user has already completed their one real run ────────────
    if tax_detective_db.has_completed_run():
        # If they opted into practice, serve that
        if _practice_active():
            _render_practice(prog)
            return

        # If they just finished (in this session), show the one-time summary
        att = st.session_state.get("td_attempt")
        if att and att.get("status") == "completed":
            _render_completed_summary(att, prog)
            return

        # Default post-completion state: locked board + Practice Mode button
        _render_closed_board(prog)
        return

    # ── First-run only: load/initialise graded attempt ───────────────────────
    if "td_attempt" not in st.session_state:
        st.session_state.td_attempt = tax_detective_db.get_current_attempt()
        st.session_state.td_result = None

    attempt = st.session_state.td_attempt

    # ── Header ───────────────────────────────────────────────────────────────
    wallet_bal = prog.get("virtual_balance", 0.0)
    st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; max-width:1120px; margin:auto;">
<div style="font-size:12px; color:#6e7b8c;">Tax Detective <span>›</span> <b style="color:#c1cad5;">Case Files</b></div>
<div style="display:flex; align-items:center; gap:9px; background:#121820; border:1px solid #29323e; border-radius:12px; padding:8px 13px;">
<div style="width:28px; height:28px; border-radius:8px; background:#18392f; color:#42d995; display:grid; place-items:center; font-weight:800;">₹</div>
<div><small style="display:block; font-size:9px; color:#718093;">VIRTUAL BALANCE</small><strong style="font-size:14px; color:#f4f7fb;">₹{wallet_bal:,.0f}</strong></div>
</div>
</div>
<div class="td-hero">
<div>
<div class="td-eyebrow">Tax Detective · Mini-Game</div>
<h1>Find the tax clue. Solve the case.</h1>
<div class="td-sub">You've learned the concepts. Now apply them to real-world situations. Attempt all four cases, review the reasoning behind every decision, and answer all four cases. Score <b>3 out of 4 or better</b> to unlock your reward.</div>
</div>
<div class="td-reward">✦ 3/4 to unlock your reward</div>
</div>
""", unsafe_allow_html=True)

    # If the in-session attempt just completed, show summary then done
    if attempt["status"] == "completed":
        _render_completed_summary(attempt, prog)
        return

    # ── In-progress graded case flow ─────────────────────────────────────────
    cases = tax_detective_db.get_public_cases()
    answered_ids = list(attempt["answers"].keys())

    if st.session_state.td_result:
        current_case_idx = len(answered_ids) - 1
    else:
        current_case_idx = len(answered_ids)

    if current_case_idx >= len(cases):
        if st.button("Submit Final Report & Claim Reward", type="primary", use_container_width=True):
            try:
                res = tax_detective_db.finish_attempt()
                st.session_state.td_attempt = res
                st.session_state.td_result = None
                st.rerun()
            except Exception as e:
                st.error(str(e))
        return

    case = cases[current_case_idx]
    attempted = len(answered_ids)
    total = len(cases)
    st.progress(attempted / total, text=f"CASE {current_case_idx+1} OF {total} | {attempt['correct_count']} correct · {total - attempted} to go")

    st.markdown(_case_card_html(case, practice=False), unsafe_allow_html=True)
    st.write("")

    if not st.session_state.td_result:
        cols = st.columns(3)
        for i, choice in enumerate(case["choices"]):
            with cols[i]:
                st.markdown(
                    f"<div style='font-size:10px; font-weight:800; color:#697789; margin-bottom:4px;'>OPTION {chr(65+i)}</div>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<b style='font-size:14px; display:block; margin-bottom:5px; color:#edf1f6;'>{choice['t']}</b>"
                    f"<span style='font-size:11px; color:#8d98a7;'>{choice['d']}</span>",
                    unsafe_allow_html=True
                )
                if st.button("Select Option " + chr(65+i), key=f"btn_{current_case_idx}_{i}", use_container_width=True):
                    res = tax_detective_db.answer_case(current_case_idx, i)
                    st.session_state.td_attempt = tax_detective_db.get_current_attempt()
                    st.session_state.td_result = res
                    st.rerun()
    else:
        st.markdown(_result_panel_html(st.session_state.td_result, practice=False), unsafe_allow_html=True)
        st.write("")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col3:
            label = "Next Case →" if current_case_idx < total - 1 else "Finish & See Final Result"
            if st.button(label, type="primary", use_container_width=True):
                if current_case_idx == total - 1:
                    finished = tax_detective_db.finish_attempt()
                    st.session_state.td_attempt = finished
                st.session_state.td_result = None
                st.rerun()
