# === [SEC-01: IMPORTS & PAGE HEADER] ===
import streamlit as st
import pandas as pd
from db import load_market_data

st.title("📡 סורק מניות ונתוני שוק (EOD)")

df = load_market_data()
if df.empty:
    st.warning("לא נמצאו נתונים בטבלת stocks_snapshot. הרץ תחילה את סנכרון ה-EOD.")
    st.stop()

# === [SEC-02: TOP KPI SUMMARY] ===
col1, col2, col3, col4 = st.columns(4)
col1.metric("מניות מסונכרנות", len(df))
col2.metric("מעל ממוצע 200", int((df["ma_200"] == "Above").sum()) if "ma_200" in df else 0)
col3.metric("מעל ממוצע 50", int((df["ma_50"] == "Above").sum()) if "ma_50" in df else 0)
last_upd = str(df["updated_at"].max())[:16].replace("T", " ") if "updated_at" in df else "-"
col4.metric("עדכון אחרון (UTC)", last_upd)

st.divider()

# === [SEC-03: FILTERS BAR] ===
f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
with f1:
    search_q = st.text_input("חיפוש טיקר / שם חברה", placeholder="לדוגמה: AAPL, NVDA...").strip().upper()
with f2:
    sectors = ["הכל"] + sorted(df["sector"].dropna().unique().tolist()) if "sector" in df else ["הכל"]
    selected_sector = st.selectbox("סקטור", sectors)
with f3:
    ma200_filter = st.selectbox("מצב מול MA 200", ["הכל", "Above", "Below"])
with f4:
    min_rel_vol = st.number_input("מינימום Rel Vol 5D", min_value=0.0, value=0.0, step=0.2)

filtered = df.copy()
if search_q:
    filtered = filtered[
        filtered["symbol"].str.contains(search_q, na=False)
        | filtered["company_name"].fillna("").str.upper().str.contains(search_q, na=False)
    ]
if selected_sector != "הכל":
    filtered = filtered[filtered["sector"] == selected_sector]
if ma200_filter != "הכל":
    filtered = filtered[filtered["ma_200"] == ma200_filter]
if min_rel_vol > 0:
    filtered = filtered[filtered["rel_vol_5d"].fillna(0) >= min_rel_vol]

# === [SEC-04: VIEW SELECTOR & DATA TABLE] ===
view_mode = st.radio(
    "תצוגת עמודות:",
    ["מבט על (מחיר, ממוצעים, נפח)", "תשואות רב-תקופתיות", "נפחי מסחר (5 ימים + Rel Vol)", "תמיכה והתנגדות (D / W)"],
    horizontal=True,
)

column_groups = {
    "מבט על (מחיר, ממוצעים, נפח)": [
        "symbol", "company_name", "sector", "price", "change_today_pct",
        "daily_vol", "rel_vol_5d", "rel_vol_20d",
        "ma_20", "ma_50", "ma_150", "ma_200",
        "ma_20_dist_pct", "ma_50_dist_pct", "ma_200_dist_pct",
        "rsi", "atr_14", "atr_pct",
    ],
    "תשואות רב-תקופתיות": [
        "symbol", "price", "change_today_pct", "change_1d", "change_2d", "change_3d", "change_4d",
        "start_of_the_week", "weekly", "two_weeks", "three_weeks",
        "monthly", "three_months", "six_months", "nine_months", "ytd", "one_year",
    ],
    "נפחי מסחר (5 ימים + Rel Vol)": [
        "symbol", "price", "daily_vol", "vol_1d", "vol_2d", "vol_3d", "vol_4d",
        "rel_vol_5d", "rel_vol_10d", "rel_vol_15d", "rel_vol_20d", "rel_vol_30d",
    ],
    "תמיכה והתנגדות (D / W)": [
        "symbol", "price",
        "d_s_1", "d_s_2", "d_s_3", "d_r_1", "d_r_2", "d_r_3",
        "w_s_1", "w_s_2", "w_s_3", "w_r_1", "w_r_2", "w_r_3",
    ],
}

display_cols = [c for c in column_groups[view_mode] if c in filtered.columns]

st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    hide_index=True,
    height=520,
)
