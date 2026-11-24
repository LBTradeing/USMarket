# === [SEC-01: IMPORTS & INDICATOR / SETUP OPTION CATALOGS] ===
import os
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import yfinance as yf
import streamlit as st
from db import get_supabase_client, sync_setup_pattern

SETUP_OPTIONS = [
    "ללא Setup",
    "Darvas Box",
    "Bearish-to-Bullish Reversal",
    "Cup and Handle",
    "Bull Flag",
    "Pennant",
    "Double Bottom",
    "Inverse Head & Shoulders",
    "Ascending Triangle",
    "Symmetrical Triangle",
    "Falling Wedge",
    "VCP (Volatility Contraction)",
    "Breakout from Base",
    "Pullback to Moving Average",
    "Channel Breakout",
    "Gap & Go",
]

VOLUME_TREND_OPTIONS = [
    "לחץ קונים (איסוף)",
    "לחץ מוכרים (פיזור)",
    "מאבק / בלימה (Struggle)",
    "נפח שקט (נייטרלי)",
]

MACD_OPTIONS = [
    "חצייה שורית טרייה (כחול חוצה כתום מעלה / תחילת ירוק)",
    "אדום חלש לקראת חצייה מעלה",
    "מומנטום שורי פעיל (ירוק מתחזק)",
    "היחלשות שורית (ירוק חלש / מתקצר)",
    "חצייה דובית מטה (כחול חוצה כתום מטה / תחילת אדום)",
    "מומנטום דובי פעיל (אדום מתחזק)",
]

CCI_OPTIONS = [
    "חוצה 100- מעלה (יציאה ממכירת יתר)",
    "חוצה 0 מעלה (מעבר למומנטום חיובי)",
    "מעל 100+ (מומנטום פריצה חזק)",
    "מתחת ל-100- (מכירת יתר עמוקה)",
    "חוצה מטה / מאבד מומנטום",
]

TRENDLINE_OPTIONS = [
    "ללא קו רלוונטי",
    "הרבה מעל קו המגמה",
    "קרוב מעל (בדיקת תמיכה)",
    "נוגע בדיוק בקו המגמה",
    "פריצה כלפי מעלה",
    "קרוב מתחת (בדיקת התנגדות)",
    "הרבה מתחת לקו המגמה",
    "שבירה כלפי מטה",
]

GAPS_OPTIONS = [
    "ללא גאפ",
    "גאפ עולה פתוח (תמיכה מתחת)",
    "סגירת גאפ עולה (בדיקת תמיכה)",
    "גאפ יורד פתוח (התנגדות מעל)",
    "פריצה וסגירת גאפ יורד",
]

FIBONACCI_OPTIONS = [
    "ללא פיבונאצ'י",
    "תמיכה ב-23.6%",
    "תמיכה ב-38.2%",
    "תמיכה ב-50.0%",
    "אזור הזהב (61.8%–65%)",
    "תיקון עמוק (78.6%)",
    "התנגדות פיבונאצ'י מעל",
]

CANDLE_OPTIONS = [
    "ללא תבנית מיוחדת",
    "Bullish Engulfing (בליעה שורית)",
    "Hammer (פטיש)",
    "Inverted Hammer (פטיש הפוך)",
    "Doji / Dragonfly Doji (דוג'י)",
    "Bullish Marubozu (נר קונים מלא)",
    "Spinning Top (סביבון / מאבק)",
    "Shooting Star (כוכב נופל)",
    "Bearish Engulfing (בליעה דובית)",
]

CANDLE_TREND_OPTIONS = [
    "ללא רצף מוגדר",
    "Morning Star (כוכב בוקר)",
    "Three White Soldiers (שלושה חיילים לבנים)",
    "התכנסות נרות צרים (Tight Consolidation)",
    "רצף נרות עולים (Higher Highs & Lows)",
    "פולבק מסודר בנרות קטנים",
    "דחיית מחיר חוזרת מתמיכה (פתילים תחתונים)",
    "Evening Star / רצף יורד",
]


# === [SEC-02: EDUCATIONAL INDICATOR NOTES & SIGNAL SYNERGY GUIDE] ===
INDICATOR_GUIDE_SECTIONS = [
    {
        "title": "MACD — זיהוי ויזואלי של חציות ושינויי מומנטום",
        "subtitle": "ההיסטוגרמה היא המרחק בין הקו הכחול (MACD 12,26) לקו הכתום (Signal 9)",
        "items": [
            (
                "חצייה שורית טרייה (כחול חוצה כתום מעלה / תחילת ירוק)",
                "#10B981",
                "הקו הכחול חצה את הקו הכתום מלמטה למעלה וההיסטוגרמה עברה מאדום חלש לעמודה ירוקה ראשונה. זהו אישור רשמי שהמומנטום התהפך לטובת הקונים — נקודת התזמון המרכזית לכניסה.",
            ),
            (
                "אדום חלש לקראת חצייה מעלה",
                "#38BDF8",
                "העמודות האדומות מתקצרות (אדום בהיר/חלש) והקו הכחול מתקרב אל הכתום מלמטה. לחץ המוכרים דועך — התראה מוקדמת להכין את העסקה לפני החצייה הסופית.",
            ),
            (
                "מומנטום שורי פעיל (ירוק מתחזק)",
                "#10B981",
                "הקו הכחול מעל הכתום וההיסטוגרמה ירוקה ומתארכת (במיוחד מעל קו ה-0). מעיד על מגמת עלייה בריאה ומתמשכת.",
            ),
            (
                "היחלשות שורית (ירוק חלש / מתקצר)",
                "#F59E0B",
                "העמודות הירוקות מתחילות להתקצר והקו הכחול מתעגל מטה לכיוון הכתום. קצב העליות מאט — סימן לשקול מימוש חלקי או הידוק סטופ.",
            ),
            (
                "חצייה דובית מטה / מומנטום דובי (אדום מתחזק)",
                "#EF4444",
                "הקו הכחול מתחת לכתום וההיסטוגרמה אדומה ומתארכת. המוכרים שולטים — הימנעות מכניסה ללונג.",
            ),
        ],
    },
    {
        "title": "CCI (20) — זיהוי יציאה ממכירת יתר ומעבר למומנטום",
        "subtitle": "מודד את סטיית המחיר מהממוצע הסטטיסטי שלו (קו 0 = ממוצע, גבולות מפתח: 100- ו-100+)",
        "items": [
            (
                "חוצה 100- מעלה (יציאה ממכירת יתר)",
                "#10B981",
                "המניה ירדה בחדות מתחת ל-100- וכעת חוזרת מעל 100-. מסמן את סיום גל המכירות ותחילת גל תיקון/עלייה — מצוין לכניסות פולבק בתוך מגמה ראשית עולה.",
            ),
            (
                "חוצה 0 מעלה (מעבר למומנטום חיובי)",
                "#38BDF8",
                "המחיר עובר להיסחר מעל הממוצע הסטטיסטי שלו. אישור שהקונים לקחו שליטה והמניה עוברת מהגנה להתקפה.",
            ),
            (
                "מעל 100+ (מומנטום פריצה חזק)",
                "#10B981",
                "עוצמה חזקה מעל הממוצע — אופייני לפריצות מומנטום. יש לוודא שהמניה לא מתוחה מדי ביחס ל-ATR ול-RSI.",
            ),
            (
                "מתחת ל-100- (מכירת יתר עמוקה)",
                "#EF4444",
                "לחץ מוכרים קיצוני. לא נכנסים לפני שה-CCI חוצה בחזרה את 100- כלפי מעלה.",
            ),
            (
                "חוצה מטה / מאבד מומנטום",
                "#F59E0B",
                "ירידה מתחת ל-100+ או מתחת ל-0 — סימן לאובדן תנופה או כניסה לתיקון.",
            ),
        ],
    },
    {
        "title": "Volume Trend & Struggle — זיהוי איסוף, פיזור ומאבק",
        "subtitle": "שילוב של מיקום הסגירה בתוך טווח הנר (High–Low), כיוון השינוי, וחריגת הנפח (Rel Vol 5D)",
        "items": [
            (
                "לחץ קונים (איסוף)",
                "#10B981",
                "עליית מחיר עם סגירה בחלק העליון של הנר ונפח מעל הממוצע (Rel Vol >= 1.1). מעיד על ביקוש מוסדי אמיתי.",
            ),
            (
                "לחץ מוכרים (פיזור)",
                "#EF4444",
                "ירידת מחיר עם סגירה בחלק התחתון של הנר ונפח מעל הממוצע. מעיד על היצע כבד ולחץ מכירות.",
            ),
            (
                "מאבק / בלימה (Struggle)",
                "#F59E0B",
                "נפח גבוה מהממוצע (Rel Vol >= 1.2) אך גוף נר צר או פתילים ארוכים. מסמן קרב עיקש בין קונים למוכרים או ספיגת היצע לקראת היפוך.",
            ),
            (
                "נפח שקט (נייטרלי)",
                "#94A3B8",
                "מחזור מתחת לממוצע — תנועה טכנית רגילה ללא חריגת נפח מיוחדת.",
            ),
        ],
    },
]

SIGNAL_SYNERGY_MATRIX = [
    {
        "setup": "פולבק במגמת עלייה (Pullback Reversal)",
        "macd": "אדום חלש מתקצר או חצייה שורית טרייה (תחילת ירוק)",
        "cci": "חוצה 100- כלפי מעלה (יציאה ראשונה ממכירת יתר)",
        "rsi": "באזור 35–48 ומתחיל להתעקל כלפי מעלה",
        "meaning": "איתות כניסה איכותי ביחס סיכוי-סיכון גבוה: התיקון הסתיים והמומנטום מתהפך מעלה.",
    },
    {
        "setup": "פריצת מומנטום (Breakout Continuation)",
        "macd": "חצייה שורית טרייה מעל קו האפס / ירוק מתחזק",
        "cci": "חוצה 0 או 100+ כלפי מעלה",
        "rsi": "באזור 55–68 (עוצמה ברורה, אך עדיין לא מתוח מדי)",
        "meaning": "אישור לפריצת התנגדות בליווי כניסת כסף חדש (רצוי יחד עם Rel Vol >= 1.2).",
    },
    {
        "setup": "הימנעות / סינון סכין נופלת (Falling Knife)",
        "macd": "אדום כהה מתרחב (כחול מתרחק מטה מהכתום)",
        "cci": "מתחת ל-100- ללא סימן חזרה מעלה",
        "rsi": "מתחת ל-35 ובמגמת ירידה",
        "meaning": "אין תחתית מאושרת — ממתינים ל-CCI שיחצה 100- מעלה ול-MACD שיעבור לאדום חלש.",
    },
    {
        "setup": "זהירות מתיחת יתר (Momentum Climax)",
        "macd": "ירוק מתחיל להתקצר אחרי ריצה חדה",
        "cci": "מעל 200+ ומתחיל לרדת",
        "rsi": "מעל 75 (קניית יתר קיצונית)",
        "meaning": "סיכון גבוה למימוש מיידי — לא רודפים אחרי המחיר; ממתינים לפולבק.",
    },
]


# === [SEC-03: LIVE TECHNICAL COMPUTATIONS FOR NEW TRADE ENTRY] ===
def _clean_float(val, decimals: int = 4) -> float | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        s = str(val).strip()
        if not s or s in ("--", "nan", "None", "null"):
            return None
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def compute_live_entry_indicators(symbol: str) -> dict:
    """Computes live MACD status, CCI(20) value+status, Volume Trend, and RSI(14) from recent bars."""
    yf_sym = symbol.split(":")[-1].strip().upper().replace(".", "-")
    out = {
        "macd_status": MACD_OPTIONS[0],
        "cci_value": None,
        "cci_status": CCI_OPTIONS[1],
        "volume_trend": VOLUME_TREND_OPTIONS[3],
        "rsi_live": None,
    }
    try:
        df = yf.download(yf_sym, period="6mo", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            return out
        if isinstance(df.columns, pd.MultiIndex):
            df = df[yf_sym].copy()
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if len(df) < 35:
            return out

        closes = df["Close"]
        highs = df["High"]
        lows = df["Low"]
        opens = df["Open"]
        vols = df["Volume"]

        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        sig_line = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - sig_line

        h_curr = float(hist.iloc[-1])
        h_prev = float(hist.iloc[-2])
        if h_curr >= 0 and h_prev < 0:
            out["macd_status"] = "חצייה שורית טרייה (כחול חוצה כתום מעלה / תחילת ירוק)"
        elif h_curr < 0 and h_curr > h_prev:
            out["macd_status"] = "אדום חלש לקראת חצייה מעלה"
        elif h_curr >= 0 and h_curr >= h_prev:
            out["macd_status"] = "מומנטום שורי פעיל (ירוק מתחזק)"
        elif h_curr >= 0 and h_curr < h_prev:
            out["macd_status"] = "היחלשות שורית (ירוק חלש / מתקצר)"
        elif h_curr < 0 and h_prev >= 0:
            out["macd_status"] = "חצייה דובית מטה (כחול חוצה כתום מטה / תחילת אדום)"
        else:
            out["macd_status"] = "מומנטום דובי פעיל (אדום מתחזק)"

        tp = (highs + lows + closes) / 3.0
        sma_tp = tp.rolling(20).mean()
        mad_tp = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        cci_series = (tp - sma_tp) / (0.015 * mad_tp.replace(0, np.nan))
        if pd.notna(cci_series.iloc[-1]) and pd.notna(cci_series.iloc[-2]):
            c_curr = float(cci_series.iloc[-1])
            c_prev = float(cci_series.iloc[-2])
            out["cci_value"] = round(c_curr, 1)
            if c_prev < -100 <= c_curr:
                out["cci_status"] = "חוצה 100- מעלה (יציאה ממכירת יתר)"
            elif c_prev < 0 <= c_curr:
                out["cci_status"] = "חוצה 0 מעלה (מעבר למומנטום חיובי)"
            elif c_curr >= 100:
                out["cci_status"] = "מעל 100+ (מומנטום פריצה חזק)"
            elif c_curr < -100:
                out["cci_status"] = "מתחת ל-100- (מכירת יתר עמוקה)"
            elif c_curr < c_prev:
                out["cci_status"] = "חוצה מטה / מאבד מומנטום"
            else:
                out["cci_status"] = "חוצה 0 מעלה (מעבר למומנטום חיובי)"

        hi = float(highs.iloc[-1])
        lo = float(lows.iloc[-1])
        cl = float(closes.iloc[-1])
        op = float(opens.iloc[-1])
        prev_cl = float(closes.iloc[-2])
        avg_v5 = float(vols.iloc[-6:-1].mean())
        rvol5 = float(vols.iloc[-1]) / avg_v5 if avg_v5 > 0 else 1.0
        rng = hi - lo
        close_pos = (cl - lo) / rng if rng > 0 else 0.5
        body_ratio = abs(cl - op) / rng if rng > 0 else 0.5

        if rvol5 >= 1.2 and body_ratio <= 0.35:
            out["volume_trend"] = "מאבק / בלימה (Struggle)"
        elif rvol5 >= 1.1 and cl >= prev_cl and close_pos >= 0.55:
            out["volume_trend"] = "לחץ קונים (איסוף)"
        elif rvol5 >= 1.1 and cl < prev_cl and close_pos <= 0.45:
            out["volume_trend"] = "לחץ מוכרים (פיזור)"
        else:
            out["volume_trend"] = "נפח שקט (נייטרלי)"

        delta = closes.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        if float(loss.iloc[-1]) > 0:
            rs = float(gain.iloc[-1]) / float(loss.iloc[-1])
            out["rsi_live"] = round(100.0 - (100.0 / (1.0 + rs)), 2)

    except Exception:
        pass

    return out


def analyze_candles_with_gemini(symbol: str, custom_candle_notes: str = "") -> tuple[bool, str, str, str]:
    """Uses Gemini API + user's personal candle summary to classify last candle & candle trend."""
    api_key = ""
    try:
        api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return (
            False,
            CANDLE_OPTIONS[0],
            CANDLE_TREND_OPTIONS[0],
            "מפתח GEMINI_API_KEY עדיין לא הוגדר ב-Secrets של Streamlit. ניתן לבחור ידנית מתיבות הבחירה.",
        )

    yf_sym = symbol.split(":")[-1].strip().upper().replace(".", "-")
    df = yf.download(yf_sym, period="1mo", interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return False, CANDLE_OPTIONS[0], CANDLE_TREND_OPTIONS[0], "לא נמצאו נתוני נרות אחרונים."
    if isinstance(df.columns, pd.MultiIndex):
        df = df[yf_sym].copy()

    recent = df[["Open", "High", "Low", "Close", "Volume"]].dropna().tail(12)
    bars_txt = "\n".join(
        f"{idx.strftime('%Y-%m-%d')}: O={r['Open']:.2f}, H={r['High']:.2f}, L={r['Low']:.2f}, C={r['Close']:.2f}, V={int(r['Volume'])}"
        for idx, r in recent.iterrows()
    )

    prompt = (
        f"אתה אנליסט טכני מומחה לנרות יפניים. נתח את 12 הנרות האחרונים של {symbol}:\n"
        f"{bars_txt}\n\n"
        f"הנחיות וסיכום נרות אישי של הסוחר:\n{custom_candle_notes[:3000]}\n\n"
        f"בחר אך ורק מתוך הרשימות הבאות:\n"
        f"אפשרויות לנר אחרון (CANDLE): {CANDLE_OPTIONS}\n"
        f"אפשרויות למגמת נרות (TREND): {CANDLE_TREND_OPTIONS}\n\n"
        f"החזר תשובה ב-3 שורות בלבד:\n"
        f"CANDLE: <הבחירה המדויקת מהרשימה>\n"
        f"TREND: <הבחירה המדויקת מהרשימה>\n"
        f"REASON: <הסבר קצר בעברית של משפט אחד>"
    )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        c_choice = CANDLE_OPTIONS[0]
        t_choice = CANDLE_TREND_OPTIONS[0]
        reason = text.strip()
        for line in text.splitlines():
            if line.startswith("CANDLE:"):
                cand = line.replace("CANDLE:", "").strip()
                if cand in CANDLE_OPTIONS:
                    c_choice = cand
            elif line.startswith("TREND:"):
                trd = line.replace("TREND:", "").strip()
                if trd in CANDLE_TREND_OPTIONS:
                    t_choice = trd
            elif line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()
        return True, c_choice, t_choice, reason
    except Exception as e:
        return False, CANDLE_OPTIONS[0], CANDLE_TREND_OPTIONS[0], f"שגיאה בפנייה ל-Gemini: {e}"


# === [SEC-04: DATABASE CRUD & CSV IMPORTER] ===
@st.cache_data(ttl=20, show_spinner=False)
def load_journal_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads trade_journal and cash_transactions from Supabase."""
    sb = get_supabase_client()
    t_resp = sb.table("trade_journal").select("*").order("entry_date", desc=True).order("id", desc=True).execute()
    c_resp = sb.table("cash_transactions").select("*").order("tx_date", desc=True).order("id", desc=True).execute()
    return pd.DataFrame(t_resp.data or []), pd.DataFrame(c_resp.data or [])


def clear_journal_cache() -> None:
    load_journal_data.clear()


def _sanitize_trade_payload(payload: dict) -> dict:
    """Drops unknown columns safely if DB migration hasn't been executed yet."""
    df_t, _ = load_journal_data()
    if df_t.empty:
        return dict(payload)
    valid_cols = set(df_t.columns)
    return {k: v for k, v in payload.items() if k in valid_cols}


def insert_trade(payload: dict) -> None:
    sb = get_supabase_client()
    clean_p = _sanitize_trade_payload(payload)
    sb.table("trade_journal").insert(clean_p).execute()
    if "setup_pattern" in payload and payload.get("symbol"):
        sync_setup_pattern(str(payload["symbol"]), payload.get("setup_pattern"))
    clear_journal_cache()


def update_trade(trade_id: int, payload: dict) -> None:
    sb = get_supabase_client()
    payload_copy = dict(payload)
    payload_copy["updated_at"] = datetime.now(timezone.utc).isoformat()
    clean_p = _sanitize_trade_payload(payload_copy)
    sb.table("trade_journal").update(clean_p).eq("id", trade_id).execute()
    if "setup_pattern" in payload and payload.get("symbol"):
        sync_setup_pattern(str(payload["symbol"]), payload.get("setup_pattern"), trade_id=trade_id)
    clear_journal_cache()


def delete_trade(trade_id: int) -> None:
    sb = get_supabase_client()
    sb.table("trade_journal").delete().eq("id", trade_id).execute()
    clear_journal_cache()


def insert_cash_tx(tx_date: str, tx_type: str, amount_usd: float, notes: str = "", related_symbol: str | None = None) -> None:
    sb = get_supabase_client()
    sb.table("cash_transactions").insert(
        {
            "tx_date": tx_date,
            "tx_type": tx_type,
            "amount_usd": round(float(amount_usd), 2),
            "related_symbol": related_symbol,
            "notes": notes.strip() or None,
        }
    ).execute()
    clear_journal_cache()


def _normalize_ma_text(val) -> str | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    if "Above" in s:
        return "Above"
    if "Below" in s:
        return "Below"
    return None


def import_journal_csv(df_csv: pd.DataFrame) -> tuple[int, int]:
    """Imports historical trades and Cash deposits from Google Sheets Journal CSV export."""
    sb = get_supabase_client()

    existing_t = sb.table("trade_journal").select("entry_date, symbol, entry_price, quantity").execute().data or []
    existing_keys = {
        (str(r["entry_date"]), str(r["symbol"]).upper(), round(float(r["entry_price"]), 2), round(float(r["quantity"]), 4))
        for r in existing_t
    }

    existing_c = sb.table("cash_transactions").select("tx_date, amount_usd").execute().data or []
    existing_cash_keys = {
        (str(r["tx_date"]), round(float(r["amount_usd"]), 2))
        for r in existing_c
    }

    trades_to_insert: list[dict] = []
    cash_to_insert: list[dict] = []

    for _, r in df_csv.iterrows():
        dt_parsed = pd.to_datetime(r.get("Date"), errors="coerce")
        sym = str(r.get("Symbol") or "").strip().upper()
        ep = _clean_float(r.get("Entry Price"), 4)
        qty = _clean_float(r.get("Quantity"), 4)
        if pd.isna(dt_parsed) or not sym or ep is None or qty is None:
            continue

        entry_date_str = dt_parsed.strftime("%Y-%m-%d")
        key = (entry_date_str, sym, round(ep, 2), round(qty, 4))

        cash_val = _clean_float(r.get("Cash"), 2)
        if cash_val is not None and cash_val > 0:
            c_key = (entry_date_str, round(cash_val, 2))
            if c_key not in existing_cash_keys:
                existing_cash_keys.add(c_key)
                cash_to_insert.append(
                    {
                        "tx_date": entry_date_str,
                        "tx_type": "Deposit",
                        "amount_usd": round(cash_val, 2),
                        "related_symbol": sym,
                        "notes": f"יובא מגיליון (שורת {sym})",
                    }
                )

        if key in existing_keys:
            continue
        existing_keys.add(key)

        close_dt_parsed = pd.to_datetime(r.get("Close Date"), errors="coerce")
        close_date_str = close_dt_parsed.strftime("%Y-%m-%d") if pd.notna(close_dt_parsed) else None

        purchase_amt = _clean_float(r.get("Purchase amount"), 2)
        if purchase_amt is None:
            purchase_amt = round(ep * qty, 2)

        row_payload = {
            "entry_date": entry_date_str,
            "symbol": sym,
            "company_name": str(r.get("Company Name") or "").strip() or None,
            "direction": str(r.get("Direction") or "Long").strip(),
            "setup_pattern": str(r.get("Setup") or "").strip() or None,
            "entry_price": ep,
            "quantity": qty,
            "purchase_amount": purchase_amt,
            "stop_loss": _clean_float(r.get("Stop Loss"), 2),
            "take_profit": _clean_float(r.get("Take Profit"), 2),
            "daily_next_sr": str(r.get("Daily Next Supp / Res Level") or "").strip() or None,
            "weekly_next_sr": str(r.get("Weekly Next Supp / Res Level") or "").strip() or None,
            "rr_ratio": str(r.get("R:R Ratio") or "").strip() or None,
            "exit_price": _clean_float(r.get("Exit Price"), 4),
            "sell_quantity": _clean_float(r.get("Sell Quantity"), 4),
            "close_date": close_date_str,
            "fees": _clean_float(r.get("עמלות"), 2) or 0.0,
            "tax_paid": _clean_float(r.get("Tax Paid"), 4) or 0.0,
            "net_pnl": _clean_float(r.get("Net P/L ($)"), 4),
            "status": str(r.get("Status") or "Open").strip(),
            "according_to_plan": str(r.get("According to the Plan") or "").strip() or None,
            "notes": str(r.get("Notes") or "").strip() or None,
            "ma_20": _normalize_ma_text(r.get("MA20")),
            "ma_50": _normalize_ma_text(r.get("MA50")),
            "ma_150": _normalize_ma_text(r.get("MA150")),
            "ma_200": _normalize_ma_text(r.get("MA200")),
            "rsi": _clean_float(r.get("RSI"), 2),
            "d_s_1": _clean_float(r.get("D_S_1"), 2),
            "d_s_2": _clean_float(r.get("D_S_2"), 2),
            "d_s_3": _clean_float(r.get("D_S_3"), 2),
            "d_s_4": _clean_float(r.get("D_S_4"), 2),
            "d_s_5": _clean_float(r.get("D_S_5"), 2),
            "d_r_1": _clean_float(r.get("D_R_1"), 2),
            "d_r_2": _clean_float(r.get("D_R_2"), 2),
            "d_r_3": _clean_float(r.get("D_R_3"), 2),
            "d_r_4": _clean_float(r.get("D_R_4"), 2),
            "d_r_5": _clean_float(r.get("D_R_5"), 2),
            "w_s_1": _clean_float(r.get("W_S_1"), 2),
            "w_s_2": _clean_float(r.get("W_S_2"), 2),
            "w_s_3": _clean_float(r.get("W_S_3"), 2),
            "w_s_4": _clean_float(r.get("W_S_4"), 2),
            "w_s_5": _clean_float(r.get("W_S_5"), 2),
            "w_r_1": _clean_float(r.get("W_R_1"), 2),
            "w_r_2": _clean_float(r.get("W_R_2"), 2),
            "w_r_3": _clean_float(r.get("W_R_3"), 2),
            "w_r_4": _clean_float(r.get("W_R_4"), 2),
            "w_r_5": _clean_float(r.get("W_R_5"), 2),
            "rel_vol_5d": _clean_float(r.get("Rel Vol 5D"), 2),
            "rel_vol_10d": _clean_float(r.get("Rel Vol 10D"), 2),
            "rel_vol_15d": _clean_float(r.get("Rel Vol 15D"), 2),
            "rel_vol_20d": _clean_float(r.get("Rel Vol 20D"), 2),
            "rel_vol_30d": _clean_float(r.get("Rel Vol 30D"), 2),
            "signal_status": str(r.get("Signal") or "").strip() or None,
        }
        trades_to_insert.append(_sanitize_trade_payload(row_payload))

    if trades_to_insert:
        for i in range(0, len(trades_to_insert), 50):
            sb.table("trade_journal").insert(trades_to_insert[i : i + 50]).execute()

    if cash_to_insert:
        sb.table("cash_transactions").insert(cash_to_insert).execute()

    clear_journal_cache()
    return len(trades_to_insert), len(cash_to_insert)
