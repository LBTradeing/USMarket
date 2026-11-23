# === [SEC-01: IMPORTS & PAGE CONFIG] ===
import streamlit as st
from ui_theme import apply_global_theme

st.set_page_config(
    page_title="Watchlist | מעקב, אנליטיקה ויומן מסחר",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_theme()


# === [SEC-02: SIDEBAR BRANDING & NAVIGATION] ===
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 4px 6px 14px 6px; border-bottom: 1px solid #1E2638; margin-bottom: 8px;">
            <div class="ltr-box" style="font-size: 1.5rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.4px;">
                Watchlist <span style="color: #2563EB;">●</span>
            </div>
            <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 2px;">
                מעקב שוק, אנליטיקה וניהול מסחר
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

pages = {
    "מצב השוק": [
        st.Page("views/market_status.py", title="סקירת שוק ומדדים"),
    ],
    "מעקב ואנליטיקה": [
        st.Page("views/screener.py", title="מעקב מניות", default=True),
        st.Page("views/deep_dive.py", title="ניתוח עומק"),
    ],
    "יומן מסחר": [
        st.Page("views/journal.py", title="לוח בקרה"),
        st.Page("views/trades.py", title="עסקאות"),
        st.Page("views/trade_analytics.py", title="ניתוח עסקאות"),
    ],
    "איתותים": [
        st.Page("views/signals.py", title="מנוע איתותים"),
    ],
}

pg = st.navigation(pages)
pg.run()
