# === [SEC-01: MARKET STATUS & BREADTH PLACEHOLDER] ===
import streamlit as st

st.markdown("## מצב השוק ומדדי רוחב")
st.markdown(
    """
    <div class="profile-box">
        <div style="font-size:1.1rem; font-weight:700; color:#F8FAFC; margin-bottom:10px;">
            מרכז הבקרה של מצב השוק — מוכן לחיבור נתונים
        </div>
        <div style="color:#CBD5E1; line-height:1.7;">
            מסך זה ירכז תמונת מאקרו ורוחב שוק בזמן אמת:
            <ul>
                <li><b>מדדים מרכזיים:</b> S&P 500, נאסד"ק (QQQ/NDX), ראסל 2000 (IWM) וסקטור השבבים (SOXX/SMH).</li>
                <li><b>תשואות אג"ח ותנודתיות:</b> תשואות אג"ח ארה"ב ל-5, 10, 20 ו-30 שנה ומדד התנודתיות VIX.</li>
                <li><b>מדדי רוחב שוק מ-TradingView:</b> אחוז המניות ב-S&P 500 הנסחרות מעל ממוצע נע 20, 50 ו-200 ימים (S5TW, S5FI, S5TH).</li>
                <li><b>סנטימנט:</b> מדד הפחד והתאווה (Fear & Greed) ואינדיקטורים משלימים למצב השוק.</li>
            </ul>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
