# === [SEC-01: PAGE CONFIG] ===
import streamlit as st

st.set_page_config(
    page_title="USMarket | Signals & Journal",
    page_icon="📈",
    layout="wide",
)

# === [SEC-02: SIDEBAR NAVIGATION STRUCTURE] ===
pages = {
    "📡 מערכת איתותים": [
        st.Page("views/screener.py", title="סורק מניות ונתוני שוק", icon="📊", default=True),
        st.Page("views/deep_dive.py", title="ניתוח עומק למניה", icon="🔍"),
        st.Page("views/signals.py", title="מנוע איתותים (בקרוב)", icon="🎯"),
    ],
    "📒 יומן מסחר": [
        st.Page("views/journal.py", title="יומן עסקאות (שלב ב')", icon="💼"),
    ],
}

pg = st.navigation(pages)
pg.run()
