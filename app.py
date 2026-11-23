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


# === [SEC-02: UNIFORM RIGHT-SIDE NAVIGATION (NO HEADERS, NO ICONS)] ===
pages = [
    st.Page("views/market_status.py", title="מצב השוק", default=True),
    st.Page("views/screener.py", title="מעקב ואנליטיקה"),
    st.Page("views/deep_dive.py", title="ניתוח עומק"),
    st.Page("views/journal.py", title="יומן מסחר"),
]

pg = st.navigation(pages)
pg.run()
