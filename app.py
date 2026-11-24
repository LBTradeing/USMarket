# === [SEC-01: IMPORTS & PAGE CONFIG] ===
import streamlit as st
from ui_theme import apply_global_theme

st.set_page_config(
    page_title="מצב השוק | מעקב ואנליטיקה",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()


# === [SEC-02: UNIFORM RIGHT-SIDE NAVIGATION (HEBREW ONLY + JOURNAL SUB-MENU)] ===
pages = [
    st.Page("views/market_status.py", title="מצב השוק", default=True),
    st.Page("views/screener.py", title="מעקב ואנליטיקה"),
    st.Page("views/deep_dive.py", title="ניתוח עומק"),
    st.Page("views/journal.py", title="יומן מסחר"),
]

pg = st.navigation(pages)

# Reset to Journal Home whenever entering "יומן מסחר" from another page
prev_page = st.session_state.get("_last_main_page")
if pg.title == "יומן מסחר" and prev_page != "יומן מסחר":
    st.session_state["active_page"] = "יומן מסחר - עמוד הבית"
st.session_state["_last_main_page"] = pg.title

# Show sub-categories in the right sidebar only while inside "יומן מסחר"
if pg.title == "יומן מסחר":
    with st.sidebar:
        st.markdown(
            '<div style="border-top:1px solid #1E2638; margin:8px 10px 10px 10px; padding-top:10px; '
            'color:#94A3B8; font-size:0.8rem; font-weight:700; padding-right:6px;">'
            'תתי-קטגוריות יומן מסחר'
            '</div>',
            unsafe_allow_html=True,
        )
        sub_items = [
            ("עמוד הבית", "יומן מסחר - עמוד הבית"),
            ("פוזיציות ויומן עסקאות", "יומן מסחר - פוזיציות ויומן עסקאות"),
        ]
        current_sub = st.session_state.get("active_page", "יומן מסחר - עמוד הבית")
        for label, key_val in sub_items:
            is_curr = current_sub == key_val
            prefix = "◂ " if is_curr else "• "
            if st.button(
                f"{prefix}{label}",
                key=f"journal_sub_{key_val}",
                type="primary" if is_curr else "secondary",
                use_container_width=True,
            ):
                st.session_state["active_page"] = key_val
                st.rerun()

pg.run()
