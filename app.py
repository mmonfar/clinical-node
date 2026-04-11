"""
app.py
------
Clinical Intelligence Node – Streamlit frontend v1.4.
360-degree MDT roundtable with Risk Heatmap, Gap-Finder, and EPR export.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

import clinical_engine
import cron_refine
import state_manager

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Clinical Intelligence Node",
    page_icon="⚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — all colors explicit; theme-independent
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global ───────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
[data-testid="stAppViewContainer"] { background-color: #EEF1F6 !important; }
[data-testid="stHeader"]           { background: transparent !important; }

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child { background: #002868 !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label   { color: #D6E0F5 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3      { color: #FFFFFF !important; }
[data-testid="stSidebar"] hr      { border-color: rgba(255,255,255,0.15) !important; margin: 0.6rem 0 !important; }
[data-testid="stSidebar"] .stButton > button {
    background-color: rgba(255,255,255,0.10) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.22) !important;
    border-radius: 5px !important;
    width: 100% !important;
    text-align: left !important;
    padding: 0.35rem 0.65rem !important;
    font-size: 0.82rem !important;
    font-weight: 400 !important;
    transition: background 0.12s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: rgba(255,255,255,0.20) !important;
}
/* Badge sidebar overrides — beat the span rule with higher specificity */
[data-testid="stSidebar"] .badge-active { background-color: #D4EDDA !important; color: #155724 !important; border-color: #C3E6CB !important; }
[data-testid="stSidebar"] .badge-review { background-color: #FFF3CD !important; color: #856404 !important; border-color: #FFEEBA !important; }
[data-testid="stSidebar"] .badge-open   { background-color: #D1E3F8 !important; color: #004085 !important; border-color: #B8D4F1 !important; }
/* Multiselect on dark sidebar */
[data-testid="stSidebar"] .stMultiSelect > div { background-color: rgba(255,255,255,0.12) !important; border-color: rgba(255,255,255,0.25) !important; }
[data-testid="stSidebar"] .stMultiSelect span  { color: #FFFFFF !important; }

/* ── Page header ──────────────────────────────────────────────────────────── */
.cin-header {
    background: #002868; color: #FFFFFF;
    padding: 1.1rem 1.75rem; border-radius: 8px;
    margin-bottom: 1.25rem; display: flex; align-items: center; gap: 1rem;
}
.cin-header-title { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.02em; }
.cin-header-sub   { font-size: 0.78rem; opacity: 0.75; margin-top: 0.15rem; }

/* ── Chat messages ────────────────────────────────────────────────────────── */
.msg-user {
    background-color: #DDEEFF; color: #0A1F44;
    border-radius: 12px 12px 4px 12px;
    padding: 0.75rem 1rem; margin: 0.4rem 0; font-size: 0.9rem;
    max-width: 88%; margin-left: auto; border: 1px solid #B8D0EE;
}
.msg-assistant {
    background-color: #FFFFFF; color: #1A2332;
    border-radius: 12px 12px 12px 4px;
    padding: 0.75rem 1rem; margin: 0.4rem 0; font-size: 0.88rem;
    max-width: 92%; border: 1px solid #D6DDE8;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.msg-role-label {
    font-size: 0.68rem; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase;
    margin-bottom: 0.3rem; opacity: 0.6;
}
.msg-user .msg-role-label      { color: #003580; }
.msg-assistant .msg-role-label { color: #002868; }
.chat-scroll { max-height: 58vh; overflow-y: auto; padding-right: 4px; }

/* ── Cards ────────────────────────────────────────────────────────────────── */
.card {
    background-color: #FFFFFF; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 0.85rem;
    border: 1px solid #D6DDE8; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.card-blue  { border-left: 4px solid #0057A8; }
.card-green { border-left: 4px solid #1E8449; }
.card-amber { border-left: 4px solid #C87400; }
.card-red   { border-left: 4px solid #C0392B; }

/* ── Badges ───────────────────────────────────────────────────────────────── */
.badge { display: inline-block; padding: 2px 9px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
.badge-active  { background-color: #D4EDDA; color: #155724; border: 1px solid #C3E6CB; }
.badge-review  { background-color: #FFF3CD; color: #856404; border: 1px solid #FFEEBA; }
.badge-open    { background-color: #D1E3F8; color: #004085; border: 1px solid #B8D4F1; }
.badge-overdue { background-color: #F8D7DA; color: #721C24; border: 1px solid #F5C6CB; }

/* ── Sidebar section labels ───────────────────────────────────────────────── */
.sidebar-section {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: rgba(255,255,255,0.45) !important;
    margin: 0.8rem 0 0.3rem;
}

/* ── Refinement status ────────────────────────────────────────────────────── */
.refine-box { border-radius: 5px; padding: 0.5rem 0.7rem; font-size: 0.76rem; line-height: 1.5; margin: 0.3rem 0 0.5rem; }
.refine-ok      { background-color: rgba(30,132,73,0.18);  color: #A8DFBA !important; border: 1px solid rgba(30,132,73,0.35); }
.refine-overdue { background-color: rgba(200,116,0,0.18);  color: #FFCF80 !important; border: 1px solid rgba(200,116,0,0.40); }
.refine-never   { background-color: rgba(255,255,255,0.08); color: #B0BCCF !important; border: 1px solid rgba(255,255,255,0.15); }

/* ── Evidence pills ───────────────────────────────────────────────────────── */
.tier-rct  { background-color: #002868; color: #FFFFFF; padding: 2px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }
.tier-mid  { background-color: #5A6A80; color: #FFFFFF; padding: 2px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }
.tier-case { background-color: #C87400; color: #FFFFFF; padding: 2px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }
.chip      { background-color: #EBF0F8; color: #1A2332; border: 1px solid #C8D4E6; padding: 2px 9px; border-radius: 10px; font-size: 0.75rem; font-weight: 500; margin: 2px; display: inline-block; }

/* ── List items ───────────────────────────────────────────────────────────── */
.rec-item   { background-color: #F0F5FF; border-left: 3px solid #0057A8; color: #1A2332; padding: 0.45rem 0.75rem; border-radius: 0 5px 5px 0; margin-bottom: 0.35rem; font-size: 0.87rem; }
.caveat-item{ background-color: #FFFBF0; border-left: 3px solid #C87400; color: #1A2332; padding: 0.45rem 0.75rem; border-radius: 0 5px 5px 0; margin-bottom: 0.35rem; font-size: 0.87rem; }
.limit-item { background-color: #FFF8F8; border-left: 3px solid #C0392B; color: #1A2332; padding: 0.45rem 0.75rem; border-radius: 0 5px 5px 0; margin-bottom: 0.35rem; font-size: 0.87rem; }
.gap-item   { background-color: #FFF0F0; border-left: 3px solid #8B0000; color: #1A2332; padding: 0.5rem 0.75rem; border-radius: 0 5px 5px 0; margin-bottom: 0.4rem; font-size: 0.87rem; }

/* ── Critical info gap banner ─────────────────────────────────────────────── */
.critical-gap-banner {
    background-color: #7B0000; color: #FFFFFF;
    border-radius: 6px; padding: 0.75rem 1rem;
    font-size: 0.88rem; font-weight: 600;
    margin-bottom: 1rem; border: 2px solid #C0392B;
}
.critical-gap-banner ul { margin: 0.4rem 0 0 1.2rem; font-weight: 400; }

/* ── Risk heatmap ─────────────────────────────────────────────────────────── */
.risk-row {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.35rem 0; border-bottom: 1px solid #EEF1F6;
}
.risk-label { font-size: 0.84rem; color: #1A2332; flex: 1; }
.risk-pill  { padding: 2px 12px; border-radius: 10px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; min-width: 62px; text-align: center; }
.risk-high   { background-color: #F8D7DA; color: #721C24; border: 1px solid #F5C6CB; }
.risk-medium { background-color: #FFF3CD; color: #856404; border: 1px solid #FFEEBA; }
.risk-low    { background-color: #D4EDDA; color: #155724; border: 1px solid #C3E6CB; }

/* ── HOD specialist header ────────────────────────────────────────────────── */
.hod-header {
    background-color: #EEF1F6; border-radius: 6px;
    padding: 0.4rem 0.75rem; margin-bottom: 0.3rem;
    display: flex; align-items: center; gap: 0.5rem;
}
.hod-name     { font-weight: 700; color: #002868; font-size: 0.88rem; }
.hod-priority { font-size: 0.75rem; color: #5A6A80; font-style: italic; }
.hod-position { font-size: 0.75rem; font-weight: 600; color: #1E8449; }

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { background-color: #FFFFFF !important; border-radius: 7px 7px 0 0; padding: 5px 5px 0; border-bottom: 2px solid #D6DDE8; gap: 3px; }
.stTabs [data-baseweb="tab"]      { background-color: transparent !important; color: #5A6A80 !important; border-radius: 5px 5px 0 0; font-size: 0.82rem; font-weight: 500; padding: 7px 16px; }
.stTabs [aria-selected="true"]    { background-color: #002868 !important; color: #FFFFFF !important; }
.stTabs [data-baseweb="tab-panel"]{ background-color: #FFFFFF !important; border-radius: 0 0 7px 7px; padding: 1rem 1.25rem; border: 1px solid #D6DDE8; border-top: none; }

/* ── Audit trail ──────────────────────────────────────────────────────────── */
.audit-scroll {
    background-color: #F7F9FC; border: 1px solid #D6DDE8; border-radius: 6px;
    padding: 1rem; max-height: 420px; overflow-y: auto;
    font-size: 0.82rem; line-height: 1.7; color: #1A2332; white-space: pre-wrap;
}
.audit-compare-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #5A6A80;
    padding: 0.3rem 0.6rem; background: #EEF1F6;
    border-radius: 5px; margin-bottom: 0.4rem;
}

/* ── Inputs ───────────────────────────────────────────────────────────────── */
.stTextArea textarea, .stTextInput input {
    border-color: #C8D4E6 !important; border-radius: 6px !important;
    color: #1A2332 !important; background-color: #FFFFFF !important; font-size: 0.9rem !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #0057A8 !important; box-shadow: 0 0 0 2px rgba(0,87,168,0.14) !important;
}
.stButton > button[kind="primary"] {
    background: #002868 !important; color: #FFFFFF !important;
    border: none !important; border-radius: 6px !important; font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover { background: #003DA5 !important; }

/* ── Evidence Matrix ──────────────────────────────────────────────────────── */
.pillar-card {
    border-radius: 8px; padding: 0.85rem 1.1rem; margin-bottom: 1rem;
    border: 1px solid #D6DDE8;
}
.pillar-gold    { border-left: 5px solid #002868; background-color: #F0F4FB; }
.pillar-compass { border-left: 5px solid #1E8449; background-color: #F0F8F2; }
.pillar-context { border-left: 5px solid #C87400; background-color: #FFF9F0; }
.pillar-header  {
    display: flex; align-items: center; gap: 0.6rem;
    margin-bottom: 0.5rem;
}
.pillar-title   { font-weight: 700; font-size: 0.88rem; color: #1A2332; }
.pillar-query   { font-size: 0.72rem; color: #5A6A80; font-style: italic; margin-bottom: 0.5rem; }
.evidence-gap-note {
    background-color: #FFF8E1; border: 1px dashed #C87400; border-radius: 6px;
    padding: 0.65rem 1rem; color: #7A4A00; font-size: 0.84rem;
    font-style: italic; margin-top: 0.3rem;
}
.article-card {
    background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px;
    padding: 0.75rem 1rem; margin-bottom: 0.5rem;
    transition: box-shadow 0.12s;
}
.article-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.article-title { font-weight: 600; font-size: 0.87rem; color: #002868; line-height: 1.4; }
.article-title a { color: #0057A8 !important; text-decoration: none; }
.article-title a:hover { text-decoration: underline; }
.article-meta  { font-size: 0.74rem; color: #5A6A80; margin: 0.25rem 0; }
.article-abstract { font-size: 0.83rem; color: #3A4A60; line-height: 1.55; margin-top: 0.3rem; }
.article-link { font-size: 0.78rem; font-weight: 600; color: #0057A8 !important;
    text-decoration: none; display: inline-block; margin-top: 0.35rem; }
.article-link:hover { text-decoration: underline; }

/* ── Scrollbar ────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #EEF1F6; }
::-webkit-scrollbar-thumb { background: #A8B4C8; border-radius: 3px; }

/* ── Empty state ──────────────────────────────────────────────────────────── */
.empty-state {
    background-color: #FFFFFF; border: 1px dashed #C8D4E6;
    border-radius: 8px; padding: 2rem;
    text-align: center; color: #5A6A80; font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages"           not in st.session_state: st.session_state.messages           = []
if "active_output"      not in st.session_state: st.session_state.active_output      = None
if "active_case_id"     not in st.session_state: st.session_state.active_case_id     = None
if "invited_specialists" not in st.session_state: st.session_state.invited_specialists = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_case_id() -> str:
    return "CIN-" + str(uuid.uuid4()).split("-")[0].upper()


def _status_badge_html(status: str) -> str:
    s = (status or "").lower()
    if s == "active":
        return '<span class="badge badge-active">Active</span>'
    if s in ("needs_review", "needs review"):
        return '<span class="badge badge-review">Needs Review</span>'
    return '<span class="badge badge-open">Open</span>'


def _load_minutes(case_id: str) -> str:
    p = Path(__file__).parent / "minutes" / f"{case_id}.md"
    return p.read_text(encoding="utf-8") if p.exists() else "_No minutes on record._"


def _parse_minutes_blocks(text: str) -> list[str]:
    """
    Split a minutes file into individual review blocks.

    state_manager.append_minutes() always prepends \\n---\\n, so block[0]
    is always empty. We filter it out and return non-empty blocks in
    chronological order (oldest first).
    """
    return [b.strip() for b in re.split(r"\n---\n", text) if b.strip()]


def _tier_css(tier: str) -> str:
    if "RCT" in tier or "Systematic" in tier:
        return "tier-rct"
    if "Clinical Trial" in tier or "Observational" in tier:
        return "tier-mid"
    return "tier-case"


def _specialty_avatar(specialty: str) -> str:
    s = specialty.lower()
    if "cardio" in s:                           return "❤️"
    if "nephro" in s or "renal" in s:           return "🫘"
    if "onco" in s or "radiation" in s:         return "🎗️"
    if "orthop" in s:                           return "🦴"
    if "cardiothorac" in s or "thorac" in s:    return "🫀"
    if "vascular" in s:                         return "🩸"
    if "neuro" in s and "surge" in s:           return "🧠"
    if "anesth" in s:                           return "💉"
    if "icu" in s or "intensiv" in s:           return "🏥"
    if "pharmac" in s:                          return "💊"
    if "hematol" in s:                          return "🩸"
    if "infect" in s:                           return "🦠"
    if "neurol" in s:                           return "🧠"
    if "pulmon" in s:                           return "🫁"
    if "endo" in s:                             return "🔬"
    if "gastro" in s:                           return "🫄"
    if "emergency" in s or " ed" in s:          return "🚨"
    if "radio" in s:                            return "📡"
    if "pathol" in s:                           return "🔬"
    if "palliat" in s:                          return "🕊️"
    if "geriat" in s:                           return "👴"
    if "surge" in s:                            return "🔪"
    if "ob-gyn" in s or "obstet" in s:          return "🤱"
    if "urol" in s:                             return "🫁"
    if "rheumat" in s:                          return "🦴"
    return "⚕️"


def _risk_pill_html(level: str) -> str:
    cls = {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}.get(level, "risk-low")
    return f'<span class="risk-pill {cls}">{level}</span>'


def _summary_for_chat(output: dict) -> str:
    recs   = output.get("recommendations", [])
    caveats = output.get("caveats", [])
    tier   = output.get("evidence", {}).get("tier", "")
    n      = output.get("evidence", {}).get("article_count", 0)
    case_id = output.get("case_id", "")
    specs  = output.get("selected_specialists", [])
    gaps   = output.get("critical_info_missing", [])

    lines = [
        f"**MDT analysis complete — Case `{case_id}`**",
        "",
        f"**Evidence:** {tier} | {n} article{'s' if n != 1 else ''}",
    ]
    if specs:
        lines += ["", f"**Panel:** {', '.join(specs)}"]
    if gaps:
        lines += ["", f"⚠️ **Critical gaps:** {', '.join(gaps[:3])}"]
    lines += ["", f"**Rationale:** {output.get('rationale', '')}"]
    if recs:
        lines += ["", "**Recommendations:**"] + [f"- {r}" for r in recs[:4]]
    if caveats:
        lines += ["", "**Key caveats:**"] + [f"- {c}" for c in caveats[:3]]
    lines += ["", "_Full MDT analysis in the panel to the right._"]
    return "\n".join(lines)


def _load_case_output(case_id: str):
    case = state_manager.get_case(case_id)
    return case.get("committee_output") if case else None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="padding:0.4rem 0 0.2rem;font-size:1rem;font-weight:700;color:#FFFFFF;">'
        "⚕ Clinical Intelligence Node</div>"
        '<div style="font-size:0.72rem;color:rgba(255,255,255,0.55);">360° MDT Committee Platform</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Case registry ────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">Case Registry</div>', unsafe_allow_html=True)

    cases = state_manager.load_cases()
    if not cases:
        st.markdown(
            '<div style="font-size:0.78rem;color:rgba(255,255,255,0.45);padding:0.3rem 0;">No cases yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        for cid, case in sorted(
            cases.items(), key=lambda x: x[1].get("last_update", ""), reverse=True
        ):
            status = case.get("status", "open")
            icon = "🔴 " if status == "needs_review" else "🟢 "
            if st.button(f"{icon}{cid}", key=f"sb_{cid}"):
                output = _load_case_output(cid)
                st.session_state.active_case_id  = cid
                st.session_state.active_output   = output
                if output:
                    existing = any(m.get("case_id") == cid for m in st.session_state.messages)
                    if not existing:
                        sbar_s = output.get("sbar", {})
                        st.session_state.messages.append({"role": "user", "content": sbar_s.get("situation", cid)})
                        st.session_state.messages.append({"role": "assistant", "content": _summary_for_chat(output), "case_id": cid})
                st.rerun()

    st.divider()

    if st.button("＋ New Case", key="new_case"):
        st.session_state.active_case_id = None
        st.session_state.active_output  = None
        st.session_state.messages       = []
        st.rerun()

    # ── Invite specialists ───────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="sidebar-section">Invite Specialists</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.72rem;color:rgba(255,255,255,0.5);margin-bottom:0.3rem;">'
        "Force into next roundtable:</div>",
        unsafe_allow_html=True,
    )
    invited = st.multiselect(
        "invite",
        options=clinical_engine.ALL_SPECIALTIES,
        default=st.session_state.invited_specialists,
        key="invited_specialists",
        label_visibility="collapsed",
    )

    # ── Status key ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="sidebar-section">Status</div>', unsafe_allow_html=True)
    st.markdown(
        '<span class="badge badge-active">Active</span>&nbsp;'
        '<span class="badge badge-review">Needs Review</span>',
        unsafe_allow_html=True,
    )

    # ── 72-hour refinement ───────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="sidebar-section">72-Hour Refinement</div>', unsafe_allow_html=True)

    last_iso = cron_refine.get_last_run()
    if last_iso is None:
        st.markdown(
            '<div class="refine-box refine-never">Never run.<br>Click below to start.</div>',
            unsafe_allow_html=True,
        )
    else:
        last_dt = datetime.fromisoformat(last_iso)
        hrs = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        label = last_dt.strftime("%d %b %H:%M UTC")
        if hrs >= 72:
            st.markdown(
                f'<div class="refine-box refine-overdue">⚠ Overdue ({hrs:.0f}h ago)<br>'
                f'<span style="opacity:0.75;">Last: {label}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            left = round(72 - hrs, 1)
            st.markdown(
                f'<div class="refine-box refine-ok">✓ Next in {left}h<br>'
                f'<span style="opacity:0.75;">Last: {label}</span></div>',
                unsafe_allow_html=True,
            )

    if st.button("Run Refinement Now", key="run_refine"):
        with st.spinner("Scanning active cases..."):
            try:
                cron_refine.refine_all_cases()
                st.rerun()
            except Exception as exc:
                st.error(f"Refinement error: {exc}")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="cin-header"><div>'
    '<div class="cin-header-title">Clinical Intelligence Node</div>'
    '<div class="cin-header-sub">360° Virtual MDT · Evidence-Based Clinical Review · JCI-Grade Audit</div>'
    '</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Two-column layout
# ---------------------------------------------------------------------------

col_chat, col_panel = st.columns([5, 4], gap="medium")

# ── Left: chat ────────────────────────────────────────────────────────────────

with col_chat:
    st.markdown(
        '<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#5A6A80;margin-bottom:0.5rem;">Case Consultation</div>',
        unsafe_allow_html=True,
    )

    # Render messages
    chat_html = '<div class="chat-scroll">'
    for msg in st.session_state.messages:
        role    = msg["role"]
        content = msg["content"]
        if role == "user":
            chat_html += (
                f'<div class="msg-user"><div class="msg-role-label">You</div>{content}</div>'
            )
        else:
            html_c = content
            html_c = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_c)
            html_c = re.sub(r"`(.+?)`",        r"<code>\1</code>",     html_c)
            html_c = html_c.replace("\n- ", "<br>• ")
            html_c = html_c.replace("\n\n", "<br><br>")
            html_c = html_c.replace("\n",   "<br>")
            chat_html += (
                f'<div class="msg-assistant">'
                f'<div class="msg-role-label">⚕ MDT Committee</div>'
                f'{html_c}</div>'
            )
    chat_html += "</div>"
    st.markdown(chat_html, unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown(
            '<div class="empty-state">'
            "<strong>Describe a clinical case below.</strong><br>"
            "Free text or SBAR format accepted.<br>"
            "<span style='font-size:0.8rem;'>The MDT will search PubMed, debate the case, "
            "and identify systemic gaps.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
    user_input = st.chat_input("Describe the case (SBAR or free text)...")

    if user_input:
        case_id = _gen_case_id()
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.active_case_id = case_id
        st.session_state["_pending_input"]   = user_input
        st.session_state["_pending_case_id"] = case_id
        st.rerun()


# ── Right: analysis panel ─────────────────────────────────────────────────────

with col_panel:
    st.markdown(
        '<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#5A6A80;margin-bottom:0.5rem;">Analysis &amp; Evidence</div>',
        unsafe_allow_html=True,
    )

    # ── Processing pipeline with live status ──────────────────────────────────
    if "_pending_input" in st.session_state:
        pending_text = st.session_state.pop("_pending_input")
        pending_id   = st.session_state.pop("_pending_case_id")
        invited_now  = st.session_state.get("invited_specialists", [])

        with st.status("MDT Committee convening...", expanded=True) as status:
            try:
                st.write("📋 Parsing clinical case (SBAR extraction)...")
                sbar = clinical_engine.parse_sbar_from_text(pending_text)

                st.write("🔬 Researcher: building focused PubMed query...")
                query = clinical_engine.build_pubmed_query(sbar)
                st.caption(f"Query: `{query}`")

                st.write("📚 Researcher: searching PubMed (evidence ladder)...")
                evidence = clinical_engine.researcher_search(query, sbar=sbar)
                n_art  = len(evidence.get("articles", []))
                tier_l = evidence.get("tier", "")
                if evidence.get("is_multi_pillar"):
                    st.write(f"   ↳ Multi-Pillar Matrix triggered — {n_art} deduplicated article{'s' if n_art != 1 else ''}")
                    for p in evidence.get("pillars", []):
                        p_n = len(p.get("articles", []))
                        st.caption(f"     {p['display']}: {p_n} article{'s' if p_n != 1 else ''} ({p['tier']})")
                else:
                    st.write(f"   ↳ {n_art} article{'s' if n_art != 1 else ''} — {tier_l}")

                st.write("🧠 Researcher: synthesizing abstracts...")
                synthesis = clinical_engine.researcher_synthesize(sbar, evidence)

                ref_list = clinical_engine._build_ref_list(evidence.get("articles", []))

                mdt_label = "🏥 MDT Roundtable: assembling specialists"
                if invited_now:
                    mdt_label += f" (+ {', '.join(invited_now[:2])}{'...' if len(invited_now) > 2 else ''})"
                mdt_label += "..."
                st.write(mdt_label)

                mdt_result = clinical_engine.mdt_roundtable_review(
                    sbar, synthesis, ref_list, invited_now or None
                )

                specs = mdt_result.get("selected_specialists", [])
                if specs:
                    st.write(f"   ↳ Panel: {', '.join(specs)}")
                conflicts = mdt_result.get("conflicts", [])
                if conflicts:
                    st.write(f"   ↳ {len(conflicts)} systemic gap{'s' if len(conflicts) > 1 else ''} identified")
                gaps_missing = mdt_result.get("critical_info_missing", [])
                if gaps_missing:
                    st.write(f"   ⚠️ Critical gaps: {', '.join(gaps_missing[:3])}")

                st.write("📝 Auditor: drafting formal MDT minutes...")
                output = clinical_engine.build_output(
                    pending_id, sbar, evidence, synthesis, mdt_result, invited_now or None
                )
                clinical_engine.auditor_record(pending_id, output)
                st.write(f"   ↳ Minutes → /minutes/{pending_id}.md")

                st.session_state.active_output = output
                status.update(label="MDT analysis complete ✓", state="complete", expanded=False)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": _summary_for_chat(output),
                    "case_id": pending_id,
                })
                st.rerun()

            except Exception as exc:
                status.update(label="Error during analysis", state="error", expanded=True)
                st.error(f"{exc}")
                st.session_state.active_output = None

    # ── Analysis tabs ──────────────────────────────────────────────────────────
    output   = st.session_state.active_output
    case_id  = st.session_state.active_case_id

    if output is None:
        st.markdown(
            '<div class="empty-state" style="margin-top:1rem;">'
            "Submit a case on the left<br>or select one from the registry."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        sbar         = output.get("sbar", {})
        evidence_meta = output.get("evidence", {})
        tier          = evidence_meta.get("tier", "")
        n_articles    = evidence_meta.get("article_count", len(evidence_meta.get("articles", [])))
        articles      = evidence_meta.get("articles", [])

        case_record  = state_manager.get_case(case_id) or {}
        status_str   = case_record.get("status", "open")

        # Case header
        st.markdown(
            f'<div class="card card-blue" style="padding:0.75rem 1rem;margin-bottom:0.75rem;">'
            f'<span style="font-weight:700;color:#002868;">{case_id}</span>'
            f'&nbsp;&nbsp;{_status_badge_html(status_str)}'
            f'<span style="font-size:0.75rem;color:#5A6A80;float:right;">'
            f'{output.get("timestamp","")[:10]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        tab1, tab2, tab3, tab4 = st.tabs([
            "Executive Summary",
            "MDT Discussion",
            "Evidence Matrix",
            "Audit Trail",
        ])

        # ── TAB 1: Executive Summary ──────────────────────────────────────────
        with tab1:
            # Critical info gap banner — top of everything
            gaps_missing = output.get("critical_info_missing", [])
            if gaps_missing:
                items_html = "".join(f"<li>{g}</li>" for g in gaps_missing)
                st.markdown(
                    f'<div class="critical-gap-banner">'
                    f"⚠️ CRITICAL INFORMATION GAP — management may change once resolved:"
                    f"<ul>{items_html}</ul></div>",
                    unsafe_allow_html=True,
                )

            # SBAR
            st.markdown(
                '<div class="card card-blue">'
                '<div style="font-weight:600;color:#002868;font-size:0.85rem;margin-bottom:0.5rem;">SBAR</div>'
                f'<div style="font-size:0.87rem;color:#1A2332;">'
                f'<strong>S</strong>&nbsp;{sbar.get("situation","")}<br><br>'
                f'<strong>B</strong>&nbsp;{sbar.get("background","")}<br><br>'
                f'<strong>A</strong>&nbsp;{sbar.get("assessment","")}<br><br>'
                f'<strong>R</strong>&nbsp;{sbar.get("recommendation","")}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            # Evidence tier + query
            tier_cls = _tier_css(tier)
            st.markdown(
                f'<span class="{tier_cls}">{tier}</span>'
                f'&nbsp;<span class="chip">{n_articles} articles</span>'
                f'&nbsp;<span class="chip" title="{evidence_meta.get("query","")}">'
                f'Query: {evidence_meta.get("query","")[:38]}…</span>',
                unsafe_allow_html=True,
            )

            # Risk heatmap
            risk_heatmap = output.get("risk_heatmap", {})
            if risk_heatmap:
                st.markdown(
                    '<div style="font-weight:600;color:#1A2332;font-size:0.82rem;'
                    'text-transform:uppercase;letter-spacing:0.05em;margin:0.75rem 0 0.3rem;">Risk Assessment</div>',
                    unsafe_allow_html=True,
                )
                heatmap_rows = "".join(
                    f'<div class="risk-row">'
                    f'<span class="risk-label">{name}</span>'
                    f'{_risk_pill_html(level)}'
                    f'</div>'
                    for name, level in risk_heatmap.items()
                )
                st.markdown(
                    f'<div class="card" style="padding:0.5rem 1rem;">{heatmap_rows}</div>',
                    unsafe_allow_html=True,
                )

            # Rationale
            rationale = output.get("rationale", "")
            if rationale:
                st.markdown(
                    f'<div class="card card-green">'
                    f'<div style="font-size:0.75rem;font-weight:700;color:#1E8449;'
                    f'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.35rem;">Rationale</div>'
                    f'<div style="font-size:0.88rem;color:#1A2332;">{rationale}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Final recommendation
            final_rec = output.get("final_recommendation", "")
            if final_rec:
                st.markdown(
                    f'<div class="card card-blue">'
                    f'<div style="font-size:0.75rem;font-weight:700;color:#0057A8;'
                    f'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.35rem;">MDT Final Recommendation</div>'
                    f'<div style="font-size:0.88rem;color:#1A2332;">{final_rec}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Recommendations list
            recs = output.get("recommendations", [])
            if recs:
                st.markdown(
                    '<div style="font-weight:600;color:#1A2332;font-size:0.82rem;'
                    'text-transform:uppercase;letter-spacing:0.05em;margin:0.5rem 0 0.3rem;">Action Recommendations</div>',
                    unsafe_allow_html=True,
                )
                for r in recs:
                    st.markdown(f'<div class="rec-item">{r}</div>', unsafe_allow_html=True)

            # Caveats
            caveats = output.get("caveats", [])
            if caveats:
                st.markdown(
                    '<div style="font-weight:600;color:#1A2332;font-size:0.82rem;'
                    'text-transform:uppercase;letter-spacing:0.05em;margin:0.5rem 0 0.3rem;">Caveats</div>',
                    unsafe_allow_html=True,
                )
                for c in caveats:
                    st.markdown(f'<div class="caveat-item">{c}</div>', unsafe_allow_html=True)

        # ── TAB 2: MDT Discussion ─────────────────────────────────────────────
        with tab2:
            # Critical info banner here too
            if gaps_missing:
                st.error(
                    f"⚠️ Critical data missing: {', '.join(gaps_missing)}. "
                    "Some recommendations are conditional."
                )

            # Specialist panel chips
            specs = output.get("selected_specialists", [])
            invited_specs = output.get("invited_specialists", [])
            if specs:
                chips = " ".join(
                    f'<span class="chip" style="background:#EBF0F8;">{s}</span>'
                    + (f'<span class="chip" style="background:#FFF3CD;color:#856404;">invited</span>' if s in invited_specs else "")
                    for s in specs
                )
                st.markdown(
                    f'<div style="margin-bottom:0.75rem;"><strong style="font-size:0.8rem;color:#5A6A80;">MDT Panel:</strong> {chips}</div>',
                    unsafe_allow_html=True,
                )

            # HOD roundtable transcript using st.chat_message
            roundtable = output.get("roundtable", [])
            if roundtable:
                st.markdown(
                    '<div style="font-size:0.72rem;font-weight:700;color:#002868;'
                    'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.5rem;">'
                    "Roundtable Transcript</div>",
                    unsafe_allow_html=True,
                )
                for entry in roundtable:
                    spec     = entry.get("specialist", "Unknown")
                    priority = entry.get("priority", "")
                    statement = entry.get("statement", "")
                    position = entry.get("position", "")
                    citations = entry.get("citations", [])
                    avatar = _specialty_avatar(spec)

                    with st.chat_message("user", avatar=avatar):
                        st.markdown(
                            f'<div class="hod-header">'
                            f'<span class="hod-name">{spec}</span>'
                            + (f'<span class="hod-priority"> — {priority}</span>' if priority else "")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(statement)
                        footer_parts = []
                        if position:
                            footer_parts.append(f"**Position:** {position}")
                        if citations:
                            footer_parts.append(f"Cites: {' '.join(f'[{c}]' for c in citations)}")
                        if footer_parts:
                            st.caption(" · ".join(footer_parts))

            else:
                st.info("No roundtable data. Re-submit to run the MDT.")

            # Researcher synthesis
            synthesis_text = output.get("researcher_synthesis", "")
            if synthesis_text:
                with st.expander("📚 Researcher Evidence Synthesis", expanded=False):
                    st.markdown(synthesis_text)

            # Limitations
            limitations = output.get("limitations", [])
            if limitations:
                st.markdown(
                    '<div style="font-weight:600;color:#1A2332;font-size:0.82rem;'
                    'text-transform:uppercase;letter-spacing:0.05em;margin:0.75rem 0 0.3rem;">Evidence Limitations</div>',
                    unsafe_allow_html=True,
                )
                for lim in limitations:
                    st.markdown(f'<div class="limit-item">{lim}</div>', unsafe_allow_html=True)

            # Systemic gaps (conflicts)
            conflicts = output.get("conflicts", [])
            if conflicts:
                st.divider()
                st.markdown(
                    '<div style="font-weight:700;color:#8B0000;font-size:0.85rem;'
                    'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.4rem;">'
                    "⚡ Systemic Gaps Identified</div>",
                    unsafe_allow_html=True,
                )
                for c in conflicts:
                    parties = " vs ".join(c.get("parties", []))
                    issue   = c.get("issue", "")
                    desc    = c.get("description", "")
                    st.markdown(
                        f'<div class="gap-item">'
                        f'<strong>{parties}</strong>'
                        + (f' — {issue}' if issue else "")
                        + f'<br><span style="font-weight:400;">{desc}</span>'
                        + "</div>",
                        unsafe_allow_html=True,
                    )

        # ── TAB 3: Evidence Matrix ─────────────────────────────────────────────
        with tab3:
            is_multi  = evidence_meta.get("is_multi_pillar", False)
            pillars   = evidence_meta.get("pillars", [])

            # ── Header row ──────────────────────────────────────────────────
            tier_cls = _tier_css(tier)
            st.markdown(
                f'<span class="{tier_cls}">{tier}</span>&nbsp;'
                f'<span class="chip">{n_articles} article{"s" if n_articles != 1 else ""} total</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="font-size:0.74rem;color:#5A6A80;margin:0.25rem 0 0.75rem;">'
                f'Initial query: <em>{evidence_meta.get("query","")}</em></div>',
                unsafe_allow_html=True,
            )

            def _render_article(a: dict, ref_num: int) -> None:
                """Render one article card with clickable title and PubMed link."""
                title   = a.get("title", "Untitled")
                url     = a.get("url", "")
                journal = a.get("journal", "")
                year    = a.get("year", "")
                authors = a.get("authors", "")
                abstract = (a.get("abstract") or "")[:420]
                if len(a.get("abstract","")) > 420:
                    abstract += "…"

                title_html = (
                    f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
                    if url else title
                )
                link_html = (
                    f'<a class="article-link" href="{url}" target="_blank" rel="noopener">'
                    f'Open on PubMed ↗</a>'
                    if url else ""
                )
                st.markdown(
                    f'<div class="article-card">'
                    f'<div class="article-title">[{ref_num}] {title_html}</div>'
                    f'<div class="article-meta">{journal} &middot; {year}'
                    + (f' &middot; {authors[:80]}{"…" if len(authors) > 80 else ""}' if authors else "")
                    + f'</div>'
                    f'<div class="article-abstract">{abstract}</div>'
                    f'{link_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if is_multi and pillars:
                # ── Multi-Pillar Evidence Matrix ─────────────────────────────
                PILLAR_CSS = {"A": "pillar-gold", "B": "pillar-compass", "C": "pillar-context"}
                ref_offset = 1

                for p in pillars:
                    pid      = p.get("id", "A")
                    display  = p.get("display", "")
                    plabel   = p.get("label", display)
                    pquery   = p.get("query", "")
                    p_tier   = p.get("tier", "")
                    p_arts   = p.get("articles", [])
                    css_cls  = PILLAR_CSS.get(pid, "pillar-gold")
                    tier_cls_p = _tier_css(p_tier)

                    st.markdown(
                        f'<div class="pillar-card {css_cls}">'
                        f'<div class="pillar-header">'
                        f'<span class="pillar-title">{display}</span>'
                        f'&nbsp;<span class="{tier_cls_p}" style="font-size:0.7rem;">{p_tier}</span>'
                        f'&nbsp;<span class="chip">{len(p_arts)} article{"s" if len(p_arts) != 1 else ""}</span>'
                        f'</div>'
                        f'<div class="pillar-query">Query: {pquery}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    if not p_arts:
                        is_tier1_empty = p_tier in (
                            "RCT / Meta-analysis / Systematic Review",
                            "Practice Guidelines (Society Consensus)",
                            "Practice Guidelines",
                        )
                        gap_msg = (
                            "⚠️ No Tier 1 (RCT/Guideline) evidence exists for this intersection. "
                            "Management relies on Tier 2 data and MDT Consensus."
                            if is_tier1_empty else
                            "No published evidence retrieved for this pillar. "
                            "This represents a genuine evidence gap requiring expert consensus."
                        )
                        st.markdown(
                            f'<div class="evidence-gap-note">{gap_msg}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        for a in p_arts:
                            _render_article(a, ref_offset)
                            ref_offset += 1

                    st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

            else:
                # ── Single-pillar display ────────────────────────────────────
                if not articles:
                    st.markdown(
                        '<div class="evidence-gap-note">'
                        "⚠️ No articles stored for this query. "
                        "Re-submit the case to fetch evidence."
                        "</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    for i, a in enumerate(articles, 1):
                        _render_article(a, i)

        # ── TAB 4: Audit Trail ─────────────────────────────────────────────────
        with tab4:
            minutes_text = _load_minutes(case_id)
            blocks       = _parse_minutes_blocks(minutes_text)

            # ── Action row: path + download ─────────────────────────────────
            col_path, col_dl = st.columns([3, 1])
            with col_path:
                st.markdown(
                    f'<div style="font-size:0.78rem;font-weight:600;color:#002868;">'
                    f'minutes/{case_id}.md'
                    f'<span style="font-weight:400;color:#5A6A80;margin-left:0.6rem;">'
                    f'{len(blocks)} revision{"s" if len(blocks) != 1 else ""}'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )
            with col_dl:
                p = Path(__file__).parent / "minutes" / f"{case_id}.md"
                if p.exists():
                    st.download_button(
                        "⬇ Download",
                        data=p.read_bytes(),
                        file_name=f"{case_id}.md",
                        mime="text/markdown",
                        key=f"dl_{case_id}",
                    )

            if not blocks:
                st.info("No minutes on record for this case.")
            else:
                # ── Latest review — always shown in full ────────────────────
                latest = blocks[-1]
                is_refined = len(blocks) > 1

                st.markdown(
                    '<div class="audit-compare-header" '
                    + ('style="background:#FFF3CD;color:#856404;"'
                       if is_refined else '')
                    + f'>{("🔄 Latest Review — Updated" if is_refined else "📋 MDT Minutes")}'
                    + '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(latest)

                # ── Previous revisions — each in a collapsible expander ─────
                if len(blocks) > 1:
                    st.divider()
                    st.markdown(
                        '<div style="font-size:0.72rem;font-weight:700;color:#5A6A80;'
                        'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.4rem;">'
                        f'Previous Revisions ({len(blocks) - 1})</div>',
                        unsafe_allow_html=True,
                    )
                    # Show oldest-to-second-last in reverse (newest first)
                    for idx, block in enumerate(reversed(blocks[:-1])):
                        rev_num  = len(blocks) - 1 - idx
                        # Try to extract the timestamp line for the expander label
                        first_line = next(
                            (ln.strip() for ln in block.splitlines() if ln.strip()),
                            f"Revision {rev_num}"
                        )
                        label = first_line[:80] + ("…" if len(first_line) > 80 else "")
                        with st.expander(f"Rev {rev_num} — {label}", expanded=False):
                            st.markdown(block)

            # ── EPR Copy-Paste Buffer ────────────────────────────────────────
            st.divider()
            st.markdown(
                '<div style="font-size:0.78rem;font-weight:600;color:#002868;margin-bottom:0.3rem;">'
                "EPR Copy-Paste Buffer</div>",
                unsafe_allow_html=True,
            )
            st.text_area(
                "epr_buf",
                value=minutes_text,
                height=180,
                label_visibility="collapsed",
                key=f"epr_{case_id}",
                help="Select all and paste directly into your EPR system.",
            )
            if st.button("📋 Prepare for EPR", key=f"epr_btn_{case_id}"):
                st.success(
                    "Minutes ready. Select all text above (Ctrl+A / Cmd+A) and paste into your EPR system."
                )
