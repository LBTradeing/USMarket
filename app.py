# === [SEC-01: IMPORTS & PAGE CONFIG] ===
import streamlit as st
from ui_theme import apply_global_theme

st.set_page_config(
    page_title="מצב השוק | מעקב ואנליטיקה",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",
)

apply_global_theme()

# === [SEC-01B: COMPACT TOP SPACING, NARROW SIDEBAR & CLEAN SUB-MENU] ===
st.markdown(
    """
    <style>
    /* הצמדת התוכן לחלק העליון של המסך */
    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 1.5rem !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2.2rem !important;
    }

    /* צמצום רוחב תפריט הצד */
    section[data-testid="stSidebar"] {
        width: 195px !important;
        min-width: 195px !important;
        max-width: 195px !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
        padding-left: 0.55rem !important;
        padding-right: 0.55rem !important;
    }

    /* עיצוב תתי-הקטגוריות תחת יומן מסחר (נקי, מיושר לימין, ללא מסגרות כבדות) */
    .journal-sub-anchor + div[data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
        padding-right: 12px !important;
        border-right: 2px solid #1E293B !important;
        margin-top: -4px !important;
        margin-bottom: 6px !important;
    }
    .journal-sub-anchor + div[data-testid="stVerticalBlock"] button {
        min-height: 30px !important;
        height: 30px !important;
        padding: 2px 10px !important;
        font-size: 0.82rem !important;
        border-radius: 8px !important;
        border: none !important;
        justify-content: flex-start !important;
        text-align: right !important;
        direction: rtl !important;
    }
    .journal-sub-anchor + div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        background: transparent !important;
        color: #94A3B8 !important;
    }
    .journal-sub-anchor + div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #F8FAFC !important;
    }
    .journal-sub-anchor + div[data-testid="stVerticalBlock"] button[kind="primary"] {
        background: rgba(56, 189, 248, 0.14) !important;
        color: #38BDF8 !important;
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# === [SEC-02: UNIFORM RIGHT-SIDE NAVIGATION (HEBREW ONLY + JOURNAL SUB-MENU)] ===
pages = [
    st.Page("views/market_status.py", title="מצב השוק", default=True),
    st.Page("views/screener.py", title="מעקב ואנליטיקה"),
    st.Page("views/deep_dive.py", title="ניתוח עומק"),
    st.Page("views/journal.py", title="יומן מסחר"),
]

pg = st.navigation(pages)

prev_page = st.session_state.get("_last_main_page")
if pg.title == "יומן מסחר" and prev_page != "יומן מסחר":
    st.session_state["active_page"] = "יומן מסחר - עמוד הבית"
st.session_state["_last_main_page"] = pg.title

if pg.title == "יומן מסחר":
    with st.sidebar:
        st.markdown('<div class="journal-sub-anchor"></div>', unsafe_allow_html=True)
        with st.container():
            sub_items = [
                ("עמוד הבית", "יומן מסחר - עמוד הבית"),
                ("פוזיציות ויומן עסקאות", "יומן מסחר - פוזיציות ויומן עסקאות"),
            ]
            current_sub = st.session_state.get("active_page", "יומן מסחר - עמוד הבית")
            for label, key_val in sub_items:
                is_curr = current_sub == key_val
                if st.button(
                    label,
                    key=f"journal_sub_{key_val}",
                    type="primary" if is_curr else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["active_page"] = key_val
                    st.rerun()

pg.run()
