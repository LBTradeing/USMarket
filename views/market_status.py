# === [SEC-01: IMPORTS & BREADTH METRICS] ===
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from db import load_market_dataframe


def render_kpi_box(title: str, value_html: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value_html}</div>
            <div class="kpi-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# === [SEC-02: WATCHLIST BREADTH & MOVING AVERAGES CARDS] ===
def render_internal_breadth(df: pd.DataFrame) -> None:
    total = len(df)
    if total == 0:
        st.info("אין עדיין נתונים להצגה.")
        return

    def pct_above(col: str) -> float:
        if col not in df.columns:
            return 0.0
        valid = df[col].dropna()
        return round((valid == "Above").mean() * 100, 1) if len(valid) > 0 else 0.0

    above_20 = pct_above("ma_20_status")
    above_50 = pct_above("ma_50_status")
    above_150 = pct_above("ma_150_status")
    above_200 = pct_above("ma_200_status")

    green_today = (
        round((df["change_today_pct"].dropna() > 0).mean() * 100, 1)
        if "change_today_pct" in df.columns and len(df["change_today_pct"].dropna()) > 0
        else 0.0
    )

    upcoming_7d = 0
    if "next_earnings_date" in df.columns:
        today_dt = datetime.now(timezone.utc).date()
        for dt_val in df["next_earnings_date"].dropna():
            try:
                d_parsed = pd.to_datetime(dt_val).date()
                if 0 <= (d_parsed - today_dt).days <= 7:
                    upcoming_7d += 1
            except Exception:
                pass

    # Row 1: General Breadth & Earnings
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    with r1_c1:
        render_kpi_box(
            "סה״כ מניות במעקב",
            f'<span class="ltr-num">{total}</span>',
            "מניות פעילות במאגר",
        )
    with r1_c2:
        render_kpi_box(
            "מניות ירוקות היום",
            f'<span class="ltr-num" style="color:#10B981;">{green_today}%</span>',
            "שינוי יומי חיובי",
        )
    with r1_c3:
        render_kpi_box(
            "דוחות ב-7 הימים הקרובים",
            f'<span class="ltr-num" style="color:#F59E0B;">{upcoming_7d}</span>',
            "מניות המפרסמות דוחות השבוע",
        )

    # Row 2: Moving Averages Breadth (MA 20 / 50 / 150 / 200)
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    with r2_c1:
        render_kpi_box(
            "מעל ממוצע 20 (MA20)",
            f'<span class="ltr-num" style="color:#38BDF8;">{above_20}%</span>',
            "מומנטום קצר טווח",
        )
    with r2_c2:
        render_kpi_box(
            "מעל ממוצע 50 (MA50)",
            f'<span class="ltr-num" style="color:#818CF8;">{above_50}%</span>',
            "מגמה בינונית",
        )
    with r2_c3:
        render_kpi_box(
            "מעל ממוצע 150 (MA150)",
            f'<span class="ltr-num" style="color:#C084FC;">{above_150}%</span>',
            "מגמה משנית ארוכה",
        )
    with r2_c4:
        render_kpi_box(
            "מעל ממוצע 200 (MA200)",
            f'<span class="ltr-num" style="color:#10B981;">{above_200}%</span>',
            "מגמה ראשית ארוכת טווח",
        )


# === [SEC-03: MACRO & MARKET INDICES PLACEHOLDER] ===
def render_macro_placeholders() -> None:
    st.markdown(
        """
        <div class="profile-box" style="margin-top:8px;">
            <div style="font-size:1.05rem; font-weight:700; color:#F8FAFC; margin-bottom:10px;">
                מדדי שוק מרכזיים, תשואות אג״ח ורוחב שוק (להמשך חיבור)
            </div>
            <div style="color:#CBD5E1; line-height:1.75; font-size:0.92rem;">
                בחלק זה נוסיף בהמשך משיכה אוטומטית של מדדי המאקרו ורוחב השוק:
                <ul>
                    <li><b>מדדים מובילים:</b> S&P 500, נאסד״ק (QQQ / NDX), ראסל 2000 (IWM) וסקטור השבבים (SOXX / SMH).</li>
                    <li><b>תשואות אג״ח ארה״ב ותנודתיות:</b> תשואות ל-5, 10, 20 ו-30 שנה ומדד הפחד VIX.</li>
                    <li><b>רוחב שוק ב-S&P 500 (מתוך TradingView):</b> אחוז המניות מעל ממוצע 20, 50 ו-200 ימים (S5TW, S5FI, S5TH).</li>
                    <li><b>סנטימנט שוק:</b> מדד הפחד והתאווה (Fear & Greed) ונקודות ייחוס למצב השוק.</li>
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    df = load_market_dataframe()
    render_internal_breadth(df)
    render_macro_placeholders()


main()
