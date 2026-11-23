# === [SEC-01: IMPORTS & PAGE CONFIG] ===
import streamlit as st
from ui_theme import apply_global_theme

st.set_page_config(
    page_title="Watchlist | אנליטיקת שוק ויומן מסחר",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()


# === [SEC-02: SIDEBAR BRANDING & NAVIGATION] ===
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 8px 4px 18px 4px; border-bottom: 1px solid #1E2638; margin-bottom: 14px;">
            <div class="ltr-box" style="font-size: 1.45rem; font-weight: 800; color: #F8FAFC; letter-spacing: 0.4px;">
                Watchlist <span style="color: #2563EB;">●</span>
            </div>
            <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 2px;">
                פלטפורמת אנליטיקה וניהול מסחר
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

pages = {
    "אנליטיקת שוק": [
        st.Page("views/screener.py", title="סורק מניות", icon="📊", default=True),
        st.Page("views/deep_dive.py", title="ניתוח עומק", icon="🔍"),
    ],
    "ניהול מסחר": [
        st.Page("views/journal.py", title="יומן מסחר", icon="📒"),
    ],
    "איתותים": [
        st.Page("views/signals.py", title="מנוע איתותים", icon="📡"),
    ],
}

pg = st.navigation(pages)
pg.run()
