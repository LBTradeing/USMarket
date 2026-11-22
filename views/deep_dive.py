# === [SEC-01: IMPORTS & TICKER SELECTION] ===
import streamlit as st
import plotly.graph_objects as go
from db import load_market_data

st.title("🔍 ניתוח עומק למניה (Ticker Deep Dive)")

df = load_market_data()
if df.empty:
    st.warning("אין נתונים זמינים.")
    st.stop()

symbols = df["symbol"].tolist()
selected_sym = st.selectbox("בחר מניה לניתוח:", symbols, index=0)
row = df[df["symbol"] == selected_sym].iloc[0]

# === [SEC-02: HEADER & KEY METRICS] ===
st.subheader(f"{row['symbol']} — {row.get('company_name') or ''}")
st.caption(f"סקטור: {row.get('sector') or '-'} | תעשייה: {row.get('industry') or '-'}")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("מחיר סגירה", f"${row['price']:.2f}" if row["price"] else "-", f"{row['change_today_pct']}%")
m2.metric("RSI (14)", row["rsi"] if row["rsi"] is not None else "-")
m3.metric("ATR (14)", f"${row['atr_14']}" if row["atr_14"] else "-", f"{row['atr_pct']}% מהמחיר")
m4.metric("Rel Vol 5D", f"{row['rel_vol_5d']}x" if row["rel_vol_5d"] else "-")
m5.metric("מתחילת שבוע (WTD)", f"{row['start_of_the_week']}%" if row["start_of_the_week"] is not None else "-")

st.divider()

# === [SEC-03: VISUAL PRICE & SUPPORT/RESISTANCE MAP] ===
st.markdown("#### מפת מחיר, ממוצעים נעים ורמות תמיכה/התנגדות (D & W)")
tf_choice = st.radio("בחר מסגרת זמן לרמות:", ["יומי (Daily S/R)", "שבועי (Weekly S/R)"], horizontal=True)
prefix = "d" if tf_choice.startswith("יומי") else "w"

fig = go.Figure()
price = float(row["price"])

# Current price line
fig.add_hline(y=price, line_color="#2962FF", line_width=2.5, annotation_text=f"Price: ${price:.2f}", annotation_position="right")

# Moving averages
for ma_col, label, color in [
    ("ma_20_value", "SMA 20", "#00BFA5"),
    ("ma_50_value", "SMA 50", "#FF9100"),
    ("ma_150_value", "SMA 150", "#AA00FF"),
    ("ma_200_value", "SMA 200", "#D50000"),
]:
    val = row.get(ma_col)
    if val is not None:
        fig.add_hline(y=float(val), line_dash="dot", line_color=color, line_width=1.2, annotation_text=f"{label}: ${val:.2f}", annotation_position="left")

# Support & Resistance levels (1..5)
for i in range(1, 6):
    s_val = row.get(f"{prefix}_s_{i}")
    if s_val is not None:
        fig.add_hline(y=float(s_val), line_dash="dash", line_color="#2E7D32", line_width=1.3, annotation_text=f"{prefix.upper()}_S{i}: ${s_val:.2f}", annotation_position="right")
    r_val = row.get(f"{prefix}_r_{i}")
    if r_val is not None:
        fig.add_hline(y=float(r_val), line_dash="dash", line_color="#C62828", line_width=1.3, annotation_text=f"{prefix.upper()}_R{i}: ${r_val:.2f}", annotation_position="right")

fig.update_yaxes(range=[price * 0.75, price * 1.25], title="מחיר ($)")
fig.update_xaxes(visible=False)
fig.update_layout(height=480, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# === [SEC-04: FULL METRICS BREAKDOWN] ===
c1, c2 = st.columns(2)
with c1:
    st.markdown("**ממוצעים נעים (ערכים ומרחקים)**")
    st.table({
        "ממוצע": ["SMA 20", "SMA 50", "SMA 150", "SMA 200"],
        "סטטוס": [row["ma_20"], row["ma_50"], row["ma_150"], row["ma_200"]],
        "מחיר": [row["ma_20_value"], row["ma_50_value"], row["ma_150_value"], row["ma_200_value"]],
        "מרחק %": [row["ma_20_dist_pct"], row["ma_50_dist_pct"], row["ma_150_dist_pct"], row["ma_200_dist_pct"]],
    })
with c2:
    st.markdown("**תשואות תקופתיות (%)**")
    st.table({
        "תקופה": ["יום אחרון", "מתחילת שבוע", "שבוע (5D)", "חודש (1M)", "3 חודשים", "6 חודשים", "YTD", "שנה"],
        "תשואה %": [
            row["change_today_pct"], row["start_of_the_week"], row["weekly"],
            row["monthly"], row["three_months"], row["six_months"], row["ytd"], row["one_year"],
        ],
    })
