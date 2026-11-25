# === [SEC-01: IMPORTS, CONSTANTS & HTML/CSS HELPERS] ===
import html
from datetime import date, datetime, timezone
import pandas as pd
import streamlit as st
from db import (
    clear_market_cache,
    get_supabase_client,
    load_market_dataframe,
    refresh_live_prices_tv,
    sync_setup_pattern,
)
from journal_helpers import (
    compute_live_entry_indicators,
    insert_cash_tx,
    insert_trade,
    load_journal_data,
)

APP_FONT = "'Assistant', 'Rubik', sans-serif"

SETUP_OPTIONS = [
    "ללא Setup",
    "Breakout",
    "Pullback to MA",
    "VCP (Volatility Contraction)",
    "Cup & Handle",
    "Bull Flag / Pennant",
    "Double Bottom",
    "Gap & Go",
    "Support Bounce",
    "Reversal / Divergence",
    "אחר",
]

CANDLESTICK_OPTIONS = [
    "ללא",
    "Bullish Engulfing",
    "Hammer / Pin Bar",
    "Morning Star",
    "Inside Bar",
    "Breakout Marubozu",
    "Doji / Indecision",
    "אחר",
]

TRENDLINE_OPTIONS = [
    "ללא",
    "פריצת קו מגמה יורד",
    "תמיכה על קו מגמה עולה",
    "פריצת תעלה",
    "התכנסות משולש",
    "אחר",
]

GAP_OPTIONS = [
    "ללא גאפ פתוח",
    "Breakaway Gap",
    "Gap & Go",
    "מילוי גאפ (Gap Fill)",
    "Continuation Gap",
    "אחר",
]

FIBONACCI_OPTIONS = [
    "ללא",
    "תיקון 38.2% מדויק",
    "תיקון 50.0%",
    "תיקון 61.8% (Golden)",
    "הרחבת 161.8%",
    "אחר",
]


def _html(raw: str) -> None:
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _ltr(text: str) -> str:
    return f'<span dir="ltr" style="display:inline-block; unicode-bidi:isolate; font-family:{APP_FONT} !important;">{text}</span>'


def _fmt_usd(val: float | None, signed: bool = False, decimals: int = 2) -> str:
    if val is None or pd.isna(val):
        return "--"
    v = float(val)
    fmt = f"{{:,.{decimals}f}}"
    if signed:
        sign = "+" if v > 0 else ("-" if v < 0 else "")
        return f"{sign}${fmt.format(abs(v))}"
    return f"${fmt.format(v)}"


def _fmt_date_short(raw_dt) -> str:
    if raw_dt is None or pd.isna(raw_dt) or str(raw_dt).strip() in ("", "None", "nan"):
        return "--"
    dt = pd.to_datetime(raw_dt, errors="coerce")
    if pd.isna(dt):
        return str(raw_dt)
    return dt.strftime("%d/%m/%y")


def _calc_holding_days(entry_raw, close_raw=None) -> int:
    e_dt = pd.to_datetime(entry_raw, errors="coerce")
    if pd.isna(e_dt):
        return 0
    end_dt = pd.to_datetime(close_raw, errors="coerce") if close_raw is not None and pd.notna(close_raw) else pd.Timestamp.now()
    if pd.isna(end_dt):
        end_dt = pd.Timestamp.now()
    return max(0, int((end_dt.normalize() - e_dt.normalize()).days))


def _clear_all_caches() -> None:
    try:
        load_journal_data.clear()
    except Exception:
        pass
    try:
        from journal_helpers import clear_journal_cache
        clear_journal_cache()
    except Exception:
        pass
    try:
        clear_market_cache()
    except Exception:
        pass


def inject_positions_css() -> None:
    _html(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700;800&family=Rubik:wght@400;500;700;800&display=swap');

        /* Global Font & RTL Enforcement */
        .stApp, .stApp * {{
            font-family: {APP_FONT} !important;
        }}

        /* Top Status Bar */
        .jp-status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: #0D111A;
            border: 1px solid #1E2638;
            border-radius: 12px;
            padding: 8px 16px;
            font-size: 0.84rem;
            color: #94A3B8;
            direction: rtl;
        }}
        .jp-live-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10B981;
            box-shadow: 0 0 8px #10B981;
            display: inline-block;
        }}

        /* 4 Top Summary Cards (Prototype 1:1) */
        .jp-kpi-card {{
            background: linear-gradient(180deg, #111622 0%, #0C1018 100%);
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 18px 20px;
            min-height: 112px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            direction: rtl;
            transition: border-color 0.2s ease, transform 0.15s ease;
        }}
        .jp-kpi-card:hover {{
            border-color: #334155;
        }}
        .jp-kpi-right {{
            text-align: right;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .jp-kpi-title {{
            font-size: 0.88rem;
            font-weight: 600;
            color: #94A3B8;
        }}
        .jp-kpi-main-row {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .jp-kpi-val {{
            font-size: 1.72rem;
            font-weight: 800;
            line-height: 1.15;
            color: #F8FAFC;
        }}
        .jp-kpi-sub-inline {{
            font-size: 0.88rem;
            font-weight: 700;
        }}
        .jp-kpi-badge {{
            padding: 5px 12px;
            border-radius: 10px;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.4px;
            white-space: nowrap;
        }}
        .jp-badge-open {{
            color: #38BDF8;
            background: rgba(56, 189, 248, 0.10);
            border: 1px solid rgba(56, 189, 248, 0.35);
        }}
        .jp-badge-live {{
            color: #CBD5E1;
            background: #131926;
            border: 1px solid #263147;
        }}
        .jp-badge-wl {{
            color: #10B981;
            background: rgba(16, 185, 129, 0.10);
            border: 1px solid rgba(16, 185, 129, 0.35);
            direction: ltr;
        }}
        .jp-badge-cash {{
            color: #A78BFA;
            background: rgba(167, 139, 250, 0.10);
            border: 1px solid rgba(167, 139, 250, 0.35);
        }}

        /* Filter Bar Container & Pill Radios */
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) {{
            background: #0D111A !important;
            border: 1px solid #1E2638 !important;
            border-radius: 16px !important;
            padding: 12px 18px !important;
            margin: 12px 0 18px 0 !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] {{
            display: flex !important;
            flex-direction: row !important;
            gap: 6px !important;
            flex-wrap: wrap !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label {{
            background: #111622 !important;
            border: 1px solid #1E2638 !important;
            border-radius: 10px !important;
            padding: 4px 12px !important;
            margin: 0 !important;
            cursor: pointer !important;
            transition: all 0.15s ease !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label > div:first-child {{
            display: none !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label[data-checked="true"],
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label:has(input:checked) {{
            background: rgba(14, 165, 233, 0.16) !important;
            border-color: #38BDF8 !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label:has(input:checked) p {{
            color: #38BDF8 !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-filter-marker) div[role="radiogroup"] label p {{
            color: #94A3B8 !important;
            font-size: 0.83rem !important;
            font-weight: 600 !important;
        }}
        .jp-filter-lbl {{
            font-size: 0.82rem;
            color: #64748B;
            font-weight: 700;
            margin-bottom: 4px;
            text-align: right;
            direction: rtl;
        }}

        /* Section Box (Active & Closed Tables) */
        .jp-section-shell {{
            background: #0D111A;
            border: 1px solid #1E2638;
            border-radius: 18px;
            padding: 18px 20px 8px 20px;
            margin-bottom: 18px;
            direction: rtl;
        }}
        .jp-sec-hdr {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 14px;
            border-bottom: 1px solid #1A2234;
            margin-bottom: 8px;
        }}
        .jp-sec-title-wrap {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .jp-sec-title {{
            font-size: 1.06rem;
            font-weight: 800;
            color: #F8FAFC;
        }}
        .jp-count-circle {{
            background: rgba(56, 189, 248, 0.14);
            color: #38BDF8;
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 999px;
            padding: 1px 10px;
            font-size: 0.8rem;
            font-weight: 800;
        }}
        .jp-sec-hint {{
            font-size: 0.78rem;
            color: #64748B;
        }}

        /* Active Positions Grid Table (8 Columns RTL) */
        .jp-active-grid {{
            display: grid;
            grid-template-columns: 1.55fr 0.85fr 0.55fr 0.85fr 0.85fr 1.05fr 1.05fr 1.85fr;
            gap: 10px;
            align-items: center;
            direction: rtl;
        }}
        .jp-closed-grid {{
            display: grid;
            grid-template-columns: 1.5fr 1.25fr 1.15fr 1.15fr 1.25fr 1.2fr;
            gap: 10px;
            align-items: center;
            direction: rtl;
        }}
        .jp-tbl-head {{
            padding: 8px 14px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #64748B;
            border-bottom: 1px solid #1A2234;
            text-align: right;
        }}

        /* Clickable Row Overlay Wrapper */
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-row-wrap) {{
            position: relative !important;
            gap: 0 !important;
            margin-bottom: 4px !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-row-wrap) > div.element-container:last-child {{
            position: absolute !important;
            inset: 0 !important;
            z-index: 10 !important;
            margin: 0 !important;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-row-wrap) > div.element-container:last-child button {{
            width: 100% !important;
            height: 100% !important;
            min-height: 68px !important;
            opacity: 0 !important;
            cursor: pointer !important;
            border: none !important;
            background: transparent !important;
        }}
        .jp-row-card {{
            padding: 13px 14px;
            border-radius: 12px;
            border: 1px solid transparent;
            border-bottom: 1px solid #161D2E;
            background: transparent;
            transition: all 0.16s ease;
        }}
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-row-wrap):hover .jp-row-card {{
            background: #131A29 !important;
            border-color: rgba(56, 189, 248, 0.45) !important;
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
        }}

        /* Stock Cell */
        .jp-stock-cell {{
            display: flex;
            align-items: center;
            gap: 11px;
        }}
        .jp-logo-circle {{
            width: 38px;
            height: 38px;
            border-radius: 11px;
            background: #11192A;
            border: 1px solid #23304A;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.72rem;
            font-weight: 800;
            color: #38BDF8;
            flex-shrink: 0;
            overflow: hidden;
        }}
        .jp-logo-circle img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .jp-ticker-txt {{
            font-size: 0.96rem;
            font-weight: 800;
            color: #F8FAFC;
            line-height: 1.2;
        }}
        .jp-comp-txt {{
            font-size: 0.76rem;
            color: #64748B;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 155px;
        }}
        .jp-cell-main {{
            font-size: 0.92rem;
            font-weight: 700;
            color: #E2E8F0;
        }}
        .jp-cell-sub {{
            font-size: 0.75rem;
            color: #64748B;
            margin-top: 2px;
        }}

        /* P/L Pill Box */
        .jp-pnl-box {{
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 6px 12px;
            border-radius: 10px;
            min-width: 92px;
            direction: ltr;
        }}
        .jp-pnl-win {{
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10B981;
        }}
        .jp-pnl-loss {{
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #EF4444;
        }}

        /* SL / TP Range Bar & Glowing Dot (Prototype 2F9 1:1) */
        .jp-sltp-wrap {{
            width: 100%;
            direction: rtl;
        }}
        .jp-sltp-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 4px;
            font-size: 0.76rem;
            font-weight: 800;
        }}
        .jp-sl-lbl {{
            color: #EF4444;
            direction: ltr;
        }}
        .jp-tp-lbl {{
            color: #10B981;
            direction: ltr;
        }}
        .jp-rr-chip {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.32);
            color: #38BDF8;
            border-radius: 6px;
            padding: 1px 6px;
            font-size: 0.7rem;
            font-weight: 800;
            direction: ltr;
        }}
        .jp-sltp-mid {{
            display: flex;
            justify-content: space-between;
            font-size: 0.7rem;
            color: #64748B;
            margin: 2px 0 5px 0;
            direction: ltr;
        }}
        .jp-range-track {{
            position: relative;
            width: 100%;
            height: 6px;
            border-radius: 999px;
            background: linear-gradient(90deg, #EF4444 0%, #F59E0B 45%, #10B981 100%);
            direction: ltr;
        }}
        .jp-range-dot {{
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 11px;
            height: 11px;
            border-radius: 50%;
            background: #F8FAFC;
            border: 2.5px solid #38BDF8;
            box-shadow: 0 0 8px #38BDF8, 0 0 2px #FFFFFF;
        }}

        /* Deep Dive Modal Styling (Prototype 9E0 & AB4) */
        div[data-testid="stDialog"] div[role="dialog"] {{
            background: #0B0F19 !important;
            border: 1px solid #1E293B !important;
            border-radius: 20px !important;
            max-width: 1180px !important;
            width: 94vw !important;
        }}
        .dd-top-cards-grid {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0 16px 0;
            direction: rtl;
        }}
        .dd-mini-card {{
            background: #101624;
            border: 1px solid #1E293B;
            border-radius: 14px;
            padding: 12px 12px;
            text-align: right;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .dd-mini-title {{
            font-size: 0.75rem;
            color: #94A3B8;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .dd-mini-val {{
            font-size: 1.06rem;
            font-weight: 800;
            color: #F8FAFC;
        }}
        .dd-panel-box {{
            background: #0F1522;
            border: 1px solid #1E293B;
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 14px;
            direction: rtl;
        }}
        .dd-snap-5grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0;
            direction: rtl;
        }}
        .dd-snap-card {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 12px;
            padding: 11px 12px;
            text-align: center;
        }}
        .dd-ma-4grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 8px;
            direction: rtl;
        }}
        .dd-ma-pill {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 14px;
            border-radius: 10px;
            font-size: 0.82rem;
            font-weight: 800;
        }}
        .dd-ma-above {{
            background: rgba(16, 185, 129, 0.10);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10B981;
        }}
        .dd-ma-below {{
            background: rgba(239, 68, 68, 0.10);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #EF4444;
        }}
        .dd-ma-neutral {{
            background: #0A0E17;
            border: 1px solid #1E293B;
            color: #64748B;
        }}
        .dd-plan-badge-ok {{
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #10B981;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }}
        .dd-plan-badge-no {{
            background: rgba(239, 68, 68, 0.14);
            border: 1px solid rgba(239, 68, 68, 0.4);
            color: #EF4444;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }}
        .dd-status-badge-open {{
            background: rgba(56, 189, 248, 0.14);
            border: 1px solid rgba(56, 189, 248, 0.4);
            color: #38BDF8;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }}
        .dd-status-badge-closed {{
            background: rgba(148, 163, 184, 0.14);
            border: 1px solid rgba(148, 163, 184, 0.35);
            color: #CBD5E1;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }}
        </style>
        """
    )


# === [SEC-02: SL / TP & R:R HTML BUILDER] ===
def _build_sltp_html(
    entry_price: float,
    live_price: float,
    qty: float,
    sl_val: float | None,
    tp_val: float | None,
    compact: bool = False,
) -> tuple[str, str]:
    """Returns (sltp_widget_html, rr_text)."""
    has_sl = sl_val is not None and pd.notna(sl_val) and float(sl_val) > 0
    has_tp = tp_val is not None and pd.notna(tp_val) and float(tp_val) > 0

    if not has_sl and not has_tp:
        return (
            '<div style="background:#0A0E17; border:1px dashed #263147; border-radius:10px; padding:7px 10px; '
            'text-align:center; font-size:0.75rem; color:#64748B;">לא הוגדר SL / TP · לחץ להגדרה</div>',
            "--",
        )

    sl = float(sl_val) if has_sl else None
    tp = float(tp_val) if has_tp else None

    rr_str = "--"
    if sl is not None and tp is not None and entry_price > sl and tp > entry_price:
        rr = (tp - entry_price) / (entry_price - sl)
        rr_str = f"1:{rr:.2f}"

    sl_txt = f"SL ${sl:,.2f}" if sl is not None else "SL --"
    tp_txt = f"TP ${tp:,.2f}" if tp is not None else "TP --"

    if sl is not None and live_price > 0:
        sl_pct = ((sl - live_price) / live_price) * 100.0
        sl_usd = (sl - entry_price) * qty
        sl_sub = f"{sl_pct:+.1f}% ({_fmt_usd(sl_usd, signed=True, decimals=0)})"
    else:
        sl_sub = "--"

    if tp is not None and live_price > 0:
        tp_pct = ((tp - live_price) / live_price) * 100.0
        tp_usd = (tp - entry_price) * qty
        tp_sub = f"{tp_pct:+.1f}% ({_fmt_usd(tp_usd, signed=True, decimals=0)})"
    else:
        tp_sub = "--"

    if sl is not None and tp is not None and tp > sl:
        raw_pos = ((live_price - sl) / (tp - sl)) * 100.0
        dot_pct = max(3.0, min(97.0, raw_pos))
    elif sl is not None:
        dot_pct = 20.0 if live_price <= sl else 55.0
    else:
        dot_pct = 80.0 if live_price >= tp else 45.0

    rr_badge = f'<span class="jp-rr-chip">R:R {rr_str}</span>' if not compact else ""

    html_block = (
        f'<div class="jp-sltp-wrap">'
        f'<div class="jp-sltp-top">'
        f'<span class="jp-sl-lbl">{sl_txt}</span>'
        f'{rr_badge}'
        f'<span class="jp-tp-lbl">{tp_txt}</span>'
        f'</div>'
        f'<div class="jp-sltp-mid">'
        f'<span>{sl_sub}</span>'
        f'<span>{tp_sub}</span>'
        f'</div>'
        f'<div class="jp-range-track">'
        f'<div class="jp-range-dot" style="left:{dot_pct:.1f}%;"></div>'
        f'</div>'
        f'</div>'
    )
    return html_block, rr_str


# === [SEC-03: TOP ACTION MODALS (NEW TRADE & DEPOSIT)] ===
@st.dialog("הפקדה לחשבון המסחר", width="small")
def _open_deposit_modal() -> None:
    st.caption("תיעוד הפקדת מזומן חדשה לחשבון המסחר")
    dep_amount = st.number_input(
        "סכום הפקדה בדולרים ($)",
        min_value=1.0,
        value=1000.0,
        step=100.0,
        format="%.2f",
        key="jp_dlg_dep_amt",
    )
    dep_date = st.date_input("תאריך הפקדה", value=date.today(), key="jp_dlg_dep_date")
    if st.button("שמור הפקדה", type="primary", use_container_width=True):
        insert_cash_tx(dep_date.isoformat(), "Deposit", dep_amount, "הפקדה דרך פוזיציות ויומן עסקאות")
        _clear_all_caches()
        st.success(f"הופקדו ${dep_amount:,.2f} בהצלחה!")
        st.rerun()


@st.dialog("פתיחת עסקה חדשה", width="small")
def _open_new_trade_modal(df_market: pd.DataFrame) -> None:
    raw_ticker = st.text_input("Ticker (סימול מניה)", placeholder="לדוגמה: MSFT", key="jp_dlg_new_ticker")
    clean_ticker = "".join(ch for ch in raw_ticker.strip().upper() if ch.isalnum() or ch in (".", "-"))

    snap_row = None
    default_price = 100.0
    comp_name = clean_ticker
    existing_setup = "ללא Setup"

    if clean_ticker and not df_market.empty:
        exact = df_market[df_market["symbol"].str.upper() == clean_ticker]
        matches = df_market[df_market["symbol"].str.upper().str.endswith(clean_ticker)]
        chosen_df = exact if not exact.empty else matches
        if not chosen_df.empty:
            snap_row = chosen_df.iloc[0]
            comp_name = str(snap_row.get("company_name") or clean_ticker)
            if pd.notna(snap_row.get("display_price")):
                default_price = float(snap_row["display_price"])
            if pd.notna(snap_row.get("setup_pattern")) and str(snap_row["setup_pattern"]).strip():
                existing_setup = str(snap_row["setup_pattern"]).strip()

    if clean_ticker:
        _html(
            f'<div style="background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:8px 12px; '
            f'margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">'
            f'<span style="color:#94A3B8; font-size:0.82rem;">{html.escape(comp_name)}</span>'
            f'<span style="color:#38BDF8; font-weight:800; font-size:0.95rem; direction:ltr;">{html.escape(clean_ticker)}</span>'
            f'</div>'
        )

    entry_dt = st.date_input("תאריך כניסה", value=date.today(), key="jp_dlg_new_date")
    c1, c2 = st.columns(2)
    with c1:
        qty = st.number_input("כמות מניות", min_value=0.0001, value=1.0, step=1.0, format="%.4f", key="jp_dlg_new_qty")
    with c2:
        buy_price = st.number_input(
            "שער קנייה ($)", min_value=0.01, value=round(default_price, 2), step=0.1, format="%.2f", key="jp_dlg_new_price"
        )

    c_sl, c_tp = st.columns(2)
    with c_sl:
        sl_in = st.number_input("Stop Loss ($)", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="jp_dlg_new_sl")
    with c_tp:
        tp_in = st.number_input("Take Profit ($)", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="jp_dlg_new_tp")

    setup_choices = SETUP_OPTIONS if existing_setup in SETUP_OPTIONS else [existing_setup] + SETUP_OPTIONS
    chosen_setup = st.selectbox("תבנית טכנית (Setup)", setup_choices, index=setup_choices.index(existing_setup), key="jp_dlg_new_setup")

    invested_total = round(qty * buy_price, 2)
    _html(
        f'<div style="background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.35); border-radius:12px; '
        f'padding:10px 14px; margin:8px 0 12px 0; display:flex; justify-content:space-between; align-items:center;">'
        f'<span style="color:#CBD5E1; font-size:0.85rem; font-weight:700;">סכום השקעה מחושב</span>'
        f'<span style="color:#10B981; font-size:1.2rem; font-weight:800; direction:ltr;">${invested_total:,.2f}</span>'
        f'</div>'
    )

    if st.button("פתח עסקה ושמור", type="primary", use_container_width=True):
        if not clean_ticker:
            st.error("יש להזין סימול מניה (Ticker).")
            return
        with st.spinner(f"שומר עסקה ב-{clean_ticker} ומושך נתונים טכניים..."):
            live_ind = compute_live_entry_indicators(clean_ticker)
            snap_fields: dict = {}
            if snap_row is not None:
                ds1 = f"${float(snap_row['d_s_1']):,.2f}" if pd.notna(snap_row.get("d_s_1")) else "-"
                dr1 = f"${float(snap_row['d_r_1']):,.2f}" if pd.notna(snap_row.get("d_r_1")) else "-"
                ws1 = f"${float(snap_row['w_s_1']):,.2f}" if pd.notna(snap_row.get("w_s_1")) else "-"
                wr1 = f"${float(snap_row['w_r_1']):,.2f}" if pd.notna(snap_row.get("w_r_1")) else "-"
                snap_fields = {
                    "daily_next_sr": f"S: {ds1} | R: {dr1}",
                    "weekly_next_sr": f"S: {ws1} | R: {wr1}",
                    "ma_20": snap_row.get("ma_20_status"),
                    "ma_50": snap_row.get("ma_50_status"),
                    "ma_150": snap_row.get("ma_150_status"),
                    "ma_200": snap_row.get("ma_200_status"),
                    "rsi": float(snap_row["rsi"]) if pd.notna(snap_row.get("rsi")) else live_ind.get("rsi_live"),
                    "atr_14": float(snap_row["atr_14"]) if pd.notna(snap_row.get("atr_14")) else None,
                    "atr_pct": float(snap_row["atr_pct"]) if pd.notna(snap_row.get("atr_pct")) else None,
                    "atr_squeeze_pct": float(snap_row["atr_squeeze_pct"]) if pd.notna(snap_row.get("atr_squeeze_pct")) else None,
                    "rel_vol_5d": float(snap_row["rel_vol_5d"]) if pd.notna(snap_row.get("rel_vol_5d")) else None,
                    "rel_vol_10d": float(snap_row["rel_vol_10d"]) if pd.notna(snap_row.get("rel_vol_10d")) else None,
                    "rel_vol_15d": float(snap_row["rel_vol_15d"]) if pd.notna(snap_row.get("rel_vol_15d")) else None,
                    "rel_vol_20d": float(snap_row["rel_vol_20d"]) if pd.notna(snap_row.get("rel_vol_20d")) else None,
                    "rel_vol_30d": float(snap_row["rel_vol_30d"]) if pd.notna(snap_row.get("rel_vol_30d")) else None,
                }
                for prefix in ("d_s", "d_r", "w_s", "w_r"):
                    for idx in range(1, 6):
                        col = f"{prefix}_{idx}"
                        snap_fields[col] = float(snap_row[col]) if pd.notna(snap_row.get(col)) else None
            else:
                snap_fields["rsi"] = live_ind.get("rsi_live")

            clean_setup_val = None if chosen_setup == "ללא Setup" else chosen_setup
            payload = {
                "entry_date": entry_dt.isoformat(),
                "symbol": clean_ticker,
                "company_name": comp_name,
                "direction": "Long",
                "entry_price": round(float(buy_price), 4),
                "quantity": round(float(qty), 4),
                "purchase_amount": invested_total,
                "stop_loss": round(float(sl_in), 4) if sl_in > 0 else None,
                "take_profit": round(float(tp_in), 4) if tp_in > 0 else None,
                "setup_pattern": clean_setup_val,
                "status": "Open",
                "according_to_plan": "Yes",
                "volume_trend": live_ind.get("volume_trend"),
                "macd_status": live_ind.get("macd_status"),
                "cci_value": live_ind.get("cci_value"),
                "cci_status": live_ind.get("cci_status"),
                **snap_fields,
            }
            insert_trade(payload)
            if clean_setup_val:
                sync_setup_pattern(clean_ticker, clean_setup_val)
            _clear_all_caches()
        st.success(f"עסקה ב-{clean_ticker} נפתחה בהצלחה!")
        st.rerun()


# === [SEC-04: DEEP DIVE & FULL TRADE MANAGEMENT LARGE MODAL] ===
def _safe_update_trade(trade_id: int, update_dict: dict, existing_cols: set[str]) -> None:
    sb = get_supabase_client()
    filtered = {k: v for k, v in update_dict.items() if k in existing_cols}
    if not filtered:
        return
    try:
        sb.table("trade_journal").update(filtered).eq("id", trade_id).execute()
    except Exception:
        # Fallback: update core fields if any optional column isn't created yet
        core_keys = {
            "stop_loss", "take_profit", "setup_pattern", "according_to_plan",
            "d_s_1", "d_r_1", "d_s_2", "d_r_2", "w_s_1", "w_r_1",
            "daily_next_sr", "weekly_next_sr", "notes", "status",
            "close_date", "close_price", "exit_price", "net_pnl", "gross_pnl",
            "tax_paid", "fees", "updated_at",
        }
        fallback = {k: v for k, v in filtered.items() if k in core_keys}
        if fallback:
            sb.table("trade_journal").update(fallback).eq("id", trade_id).execute()


@st.dialog("כרטיסיית ניתוח עומק וניהול עסקה", width="large")
def open_trade_deep_dive_modal(
    trade_row: pd.Series,
    market_row: pd.Series | None,
    live_price: float,
    existing_cols: set[str],
) -> None:
    tid = int(trade_row["id"])
    sym = str(trade_row["symbol"]).upper()
    comp_name = str(trade_row.get("company_name") or (market_row.get("company_name") if market_row is not None else sym) or sym)
    logo_url = str(market_row.get("logo_url") or "") if market_row is not None and pd.notna(market_row.get("logo_url")) else ""
    status = str(trade_row.get("status") or "Open")
    is_open = status == "Open"

    entry_dt_raw = trade_row.get("entry_date")
    close_dt_raw = trade_row.get("close_date")
    entry_dt_str = _fmt_date_short(entry_dt_raw)
    close_dt_str = _fmt_date_short(close_dt_raw)
    hold_days = _calc_holding_days(entry_dt_raw, None if is_open else close_dt_raw)

    ep = float(trade_row["entry_price"])
    qty = float(trade_row["quantity"])
    cost_total = ep * qty
    qty_lbl = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.4f}"

    if is_open:
        curr_p = live_price
        pnl_usd = (curr_p - ep) * qty
        pnl_pct = ((curr_p - ep) / ep * 100.0) if ep > 0 else 0.0
    else:
        cp_raw = trade_row.get("close_price") if pd.notna(trade_row.get("close_price")) else trade_row.get("exit_price")
        curr_p = float(cp_raw) if cp_raw is not None and pd.notna(cp_raw) else ep
        pnl_usd = float(trade_row["net_pnl"]) if pd.notna(trade_row.get("net_pnl")) else (curr_p - ep) * qty
        pnl_pct = ((curr_p - ep) / ep * 100.0) if ep > 0 else 0.0

    pnl_color = "#10B981" if pnl_usd >= 0 else "#EF4444"
    sl_curr = float(trade_row["stop_loss"]) if pd.notna(trade_row.get("stop_loss")) and float(trade_row["stop_loss"]) > 0 else None
    tp_curr = float(trade_row["take_profit"]) if pd.notna(trade_row.get("take_profit")) and float(trade_row["take_profit"]) > 0 else None

    plan_val = str(trade_row.get("according_to_plan") or "Yes")
    is_plan_ok = plan_val == "Yes"

    # === TOP HEADER BAR (Matches Prototype AB4: Company Info Right, Close Trade Button Left) ===
    hdr_right, hdr_left = st.columns([3.3, 1.1])
    with hdr_right:
        logo_inner = (
            f'<img src="{html.escape(logo_url)}" alt="{html.escape(sym)}"/>'
            if logo_url.startswith("http")
            else html.escape(sym[:4])
        )
        status_badge = (
            '<span class="dd-status-badge-open">פוזיציה פתוחה</span>'
            if is_open
            else '<span class="dd-status-badge-closed">עסקה סגורה</span>'
        )
        plan_badge = (
            '<span class="dd-plan-badge-ok">✓ לפי תוכנית</span>'
            if is_plan_ok
            else '<span class="dd-plan-badge-no">✗ חריגה</span>'
        )
        sub_meta = (
            f"כניסה: {entry_dt_str} · כמות: {qty_lbl} מניות · משך החזקה: {hold_days} ימים"
            if is_open
            else f"כניסה: {entry_dt_str} · סגירה: {close_dt_str} · כמות: {qty_lbl} מניות · משך החזקה: {hold_days} ימים"
        )
        _html(
            f"""
            <div style="display:flex; align-items:center; gap:14px; direction:rtl; text-align:right;">
                <div class="jp-logo-circle" style="width:46px; height:46px; font-size:0.85rem;">{logo_inner}</div>
                <div>
                    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                        <span style="font-size:1.35rem; font-weight:800; color:#F8FAFC;">{html.escape(comp_name)} — {html.escape(sym)}</span>
                        {status_badge}
                        {plan_badge}
                    </div>
                    <div style="font-size:0.82rem; color:#64748B; margin-top:3px;">{sub_meta}</div>
                </div>
            </div>
            """
        )

    with hdr_left:
        if is_open:
            close_toggle_key = f"dd_close_panel_open_{tid}"
            if st.button("🔒 סגירת עסקה", type="primary", use_container_width=True, key=f"btn_toggle_close_{tid}"):
                st.session_state[close_toggle_key] = not st.session_state.get(close_toggle_key, False)

    # Inline Close Trade Panel (Triggered by "סגירת עסקה" in header)
    if is_open and st.session_state.get(f"dd_close_panel_open_{tid}", False):
        with st.container(border=True):
            _html('<div style="font-size:0.98rem; font-weight:800; color:#F8FAFC; margin-bottom:8px; direction:rtl;">סגירת פוזיציה ותיעוד מס / עמלות</div>')
            cc1, cc2, cc3, cc4 = st.columns(4)
            with cc1:
                c_date = st.date_input("תאריך סגירה", value=date.today(), key=f"dd_c_date_{tid}")
            with cc2:
                c_price = st.number_input("שער מכירה ($)", min_value=0.01, value=round(curr_p, 2), step=0.1, format="%.2f", key=f"dd_c_price_{tid}")
            with cc3:
                c_tax = st.number_input("מס ששולם ($)", min_value=0.0, value=0.0, step=1.0, format="%.2f", key=f"dd_c_tax_{tid}")
            with cc4:
                c_fees = st.number_input("עמלות ($)", min_value=0.0, value=float(trade_row.get("fees") or 0.0), step=0.5, format="%.2f", key=f"dd_c_fees_{tid}")

            gross_est = (c_price - ep) * qty
            net_est = gross_est - c_tax - c_fees
            net_col = "#10B981" if net_est >= 0 else "#EF4444"
            _html(
                f'<div style="display:flex; justify-content:space-between; align-items:center; background:#0A0E17; '
                f'border:1px solid #1E293B; border-radius:10px; padding:8px 14px; margin:6px 0 10px 0; direction:rtl;">'
                f'<span style="font-size:0.84rem; color:#94A3B8;">רווח גולמי: <b style="color:#E2E8F0;" dir="ltr">{_fmt_usd(gross_est, signed=True)}</b></span>'
                f'<span style="font-size:0.96rem; font-weight:800; color:{net_col};" dir="ltr">נטו לאחר מס ועמלות: {_fmt_usd(net_est, signed=True)}</span>'
                f'</div>'
            )
            b_confirm, b_cancel = st.columns([2, 1])
            with b_confirm:
                if st.button("✅ אשר וסגור עסקה", type="primary", use_container_width=True, key=f"dd_confirm_close_{tid}"):
                    now_iso = datetime.now(timezone.utc).isoformat()
                    close_payload = {
                        "status": "Closed",
                        "close_date": c_date.isoformat(),
                        "close_price": round(float(c_price), 4),
                        "exit_price": round(float(c_price), 4),
                        "gross_pnl": round(float(gross_est), 2),
                        "net_pnl": round(float(net_est), 2),
                        "tax_paid": round(float(c_tax), 2),
                        "fees": round(float(c_fees), 2),
                        "updated_at": now_iso,
                    }
                    _safe_update_trade(tid, close_payload, existing_cols)
                    st.session_state[f"dd_close_panel_open_{tid}"] = False
                    st.session_state["jp_selected_trade_id"] = None
                    _clear_all_caches()
                    st.success(f"העסקה ב-{sym} נסגרה בהצלחה!")
                    st.rerun()
            with b_cancel:
                if st.button("ביטול", use_container_width=True, key=f"dd_cancel_close_{tid}"):
                    st.session_state[f"dd_close_panel_open_{tid}"] = False
                    st.rerun()

    # === ROUNDED METRIC CARDS IN USER'S EXACT ORDER ===
    # Order: תאריך כניסה | שער כניסה | שער חי | כמות | רווח / הפסד נוכחי | SL / TP (with bar) | RR
    sltp_html_card, rr_val_str = _build_sltp_html(ep, curr_p, qty, sl_curr, tp_curr, compact=True)
    price_lbl_title = "שער חי" if is_open else "שער סגירה"
    pnl_lbl_title = "רווח / הפסד נוכחי" if is_open else "רווח / הפסד נטו"

    _html(
        f"""
        <div class="dd-top-cards-grid">
            <div class="dd-mini-card">
                <div class="dd-mini-title">תאריך כניסה</div>
                <div class="dd-mini-val">{_ltr(entry_dt_str)}</div>
                <div style="font-size:0.74rem; color:#64748B;">{hold_days} ימים</div>
            </div>
            <div class="dd-mini-card">
                <div class="dd-mini-title">שער כניסה</div>
                <div class="dd-mini-val">{_ltr(_fmt_usd(ep))}</div>
                <div style="font-size:0.74rem; color:#64748B;">עלות ${_fmt_usd(cost_total, decimals=0).replace('$','')}</div>
            </div>
            <div class="dd-mini-card">
                <div class="dd-mini-title">{price_lbl_title}</div>
                <div class="dd-mini-val" style="color:#38BDF8;">{_ltr(_fmt_usd(curr_p))}</div>
                <div style="font-size:0.74rem; color:#64748B;">שווי {_ltr(_fmt_usd(curr_p * qty, decimals=0))}</div>
            </div>
            <div class="dd-mini-card">
                <div class="dd-mini-title">כמות</div>
                <div class="dd-mini-val">{_ltr(qty_lbl)}</div>
                <div style="font-size:0.74rem; color:#64748B;">מניות</div>
            </div>
            <div class="dd-mini-card">
                <div class="dd-mini-title">{pnl_lbl_title}</div>
                <div class="dd-mini-val" style="color:{pnl_color};">{_ltr(_fmt_usd(pnl_usd, signed=True))}</div>
                <div style="font-size:0.76rem; font-weight:700; color:{pnl_color};">{_ltr(f"{pnl_pct:+.2f}%")}</div>
            </div>
            <div class="dd-mini-card" style="grid-column: span 1;">
                <div class="dd-mini-title">SL / TP</div>
                {sltp_html_card}
            </div>
            <div class="dd-mini-card">
                <div class="dd-mini-title">RR</div>
                <div class="dd-mini-val" style="color:#38BDF8;">{_ltr(rr_val_str)}</div>
                <div style="font-size:0.74rem; color:#64748B;">יחס סיכוי/סיכון</div>
            </div>
        </div>
        """
    )

    # === EDITABLE SL / TP BAR ===
    sl_col, tp_col, rr_preview_col = st.columns([1.2, 1.2, 1.6])
    with sl_col:
        edit_sl = st.number_input(
            "עריכת Stop Loss ($)",
            min_value=0.0,
            value=float(sl_curr) if sl_curr is not None else 0.0,
            step=0.25,
            format="%.2f",
            key=f"dd_edit_sl_{tid}",
        )
    with tp_col:
        edit_tp = st.number_input(
            "עריכת Take Profit ($)",
            min_value=0.0,
            value=float(tp_curr) if tp_curr is not None else 0.0,
            step=0.25,
            format="%.2f",
            key=f"dd_edit_tp_{tid}",
        )
    with rr_preview_col:
        live_rr = "--"
        if edit_sl > 0 and edit_tp > 0 and ep > edit_sl and edit_tp > ep:
            live_rr = f"1 : {(edit_tp - ep) / (ep - edit_sl):.2f}"
        _html(
            f'<div style="background:#101624; border:1px solid #1E293B; border-radius:12px; padding:10px 14px; '
            f'margin-top:22px; display:flex; justify-content:space-between; align-items:center; direction:rtl;">'
            f'<span style="font-size:0.82rem; color:#94A3B8;">יחס R:R מעודכן לפי יעדים:</span>'
            f'<span style="font-size:0.96rem; font-weight:800; color:#38BDF8;" dir="ltr">{live_rr}</span>'
            f'</div>'
        )

    # === TECHNICAL SNAPSHOT AT ENTRY (Prototype 9E0 1:1) ===
    rsi_v = f"{float(trade_row['rsi']):.1f}" if pd.notna(trade_row.get("rsi")) else "--"
    macd_v = str(trade_row.get("macd_status") or "--")
    cci_num = f"{float(trade_row['cci_value']):.1f}" if pd.notna(trade_row.get("cci_value")) else "--"
    cci_st = str(trade_row.get("cci_status") or "")
    rv5 = f"{float(trade_row['rel_vol_5d']):.2f}x" if pd.notna(trade_row.get("rel_vol_5d")) else "--"
    rv20 = f"{float(trade_row['rel_vol_20d']):.2f}x" if pd.notna(trade_row.get("rel_vol_20d")) else "--"
    atr_v = f"${float(trade_row['atr_14']):.2f}" if pd.notna(trade_row.get("atr_14")) else "--"
    sqz_v = f"{float(trade_row['atr_squeeze_pct']):.0f}%" if pd.notna(trade_row.get("atr_squeeze_pct")) else "--"

    def _ma_pill_html(label: str, raw_st) -> str:
        s = str(raw_st or "").strip()
        if s.lower() == "above":
            return f'<div class="dd-ma-pill dd-ma-above"><span>{label}</span><span>Above ▲</span></div>'
        if s.lower() == "below":
            return f'<div class="dd-ma-pill dd-ma-below"><span>{label}</span><span>Below ▼</span></div>'
        return f'<div class="dd-ma-pill dd-ma-neutral"><span>{label}</span><span>--</span></div>'

    ma_pills = (
        _ma_pill_html("MA 20", trade_row.get("ma_20"))
        + _ma_pill_html("MA 50", trade_row.get("ma_50"))
        + _ma_pill_html("MA 150", trade_row.get("ma_150"))
        + _ma_pill_html("MA 200", trade_row.get("ma_200"))
    )

    _html(
        f"""
        <div class="dd-panel-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-size:1.02rem; font-weight:800; color:#F8FAFC;">
                    <span style="color:#38BDF8;">●</span> צילום מצב טכני ברגע הכניסה לעסקה (Entry Snapshot)
                </span>
                <span style="font-size:0.78rem; color:#64748B;">נשמר אוטומטית בעת פתיחת העסקה</span>
            </div>
            <div class="dd-snap-5grid">
                <div class="dd-snap-card">
                    <div class="dd-mini-title">RSI (14) בכניסה</div>
                    <div style="font-size:1.25rem; font-weight:800; color:#10B981;">{_ltr(rsi_v)}</div>
                </div>
                <div class="dd-snap-card">
                    <div class="dd-mini-title">MACD Status</div>
                    <div style="font-size:1.05rem; font-weight:800; color:#10B981;">{_ltr(html.escape(macd_v))}</div>
                </div>
                <div class="dd-snap-card">
                    <div class="dd-mini-title">CCI (20)</div>
                    <div style="font-size:1.15rem; font-weight:800; color:#F8FAFC;">{_ltr(cci_num)}</div>
                    <div style="font-size:0.72rem; color:#64748B;">{html.escape(cci_st)}</div>
                </div>
                <div class="dd-snap-card">
                    <div class="dd-mini-title">Rel Volume (5D / 20D)</div>
                    <div style="font-size:1.05rem; font-weight:800; color:#38BDF8;">{_ltr(f"{rv5} / {rv20}")}</div>
                </div>
                <div class="dd-snap-card">
                    <div class="dd-mini-title">ATR(14) · Squeeze</div>
                    <div style="font-size:1.05rem; font-weight:800; color:#F8FAFC;">{_ltr(f"{atr_v} · {sqz_v}")}</div>
                </div>
            </div>
            <div style="font-size:0.8rem; color:#94A3B8; font-weight:600; margin-top:8px;">
                מיקום ביחס לממוצעים נעים (Moving Averages) בכניסה:
            </div>
            <div class="dd-ma-4grid">{ma_pills}</div>
        </div>
        """
    )

    # === EDITABLE S/R LEVELS (2 DAILY + 1 WEEKLY) & TECHNICAL SETUP TAGS ===
    sr_col, tags_col = st.columns([1.05, 1.15])

    # Pre-populate S/R from trade_row or fallback to market_row
    def _get_sr_init(col_name: str) -> float:
        if pd.notna(trade_row.get(col_name)):
            return float(trade_row[col_name])
        if market_row is not None and pd.notna(market_row.get(col_name)):
            return float(market_row[col_name])
        return 0.0

    with sr_col:
        with st.container(border=True):
            _html('<div style="font-size:0.95rem; font-weight:800; color:#F8FAFC; margin-bottom:8px; direction:rtl;">רמות תמיכה והתנגדות קרובות בכניסה (ניתנות לעריכה)</div>')
            d1_s_c, d1_r_c = st.columns(2)
            with d1_s_c:
                ed_ds1 = st.number_input("טווח יומי 1 — תמיכה (S1 $)", min_value=0.0, value=_get_sr_init("d_s_1"), step=0.25, format="%.2f", key=f"dd_ds1_{tid}")
            with d1_r_c:
                ed_dr1 = st.number_input("טווח יומי 1 — התנגדות (R1 $)", min_value=0.0, value=_get_sr_init("d_r_1"), step=0.25, format="%.2f", key=f"dd_dr1_{tid}")

            d2_s_c, d2_r_c = st.columns(2)
            with d2_s_c:
                ed_ds2 = st.number_input("טווח יומי 2 — תמיכה (S2 $)", min_value=0.0, value=_get_sr_init("d_s_2"), step=0.25, format="%.2f", key=f"dd_ds2_{tid}")
            with d2_r_c:
                ed_dr2 = st.number_input("טווח יומי 2 — התנגדות (R2 $)", min_value=0.0, value=_get_sr_init("d_r_2"), step=0.25, format="%.2f", key=f"dd_dr2_{tid}")

            w1_s_c, w1_r_c = st.columns(2)
            with w1_s_c:
                ed_ws1 = st.number_input("טווח שבועי — תמיכה (W-S1 $)", min_value=0.0, value=_get_sr_init("w_s_1"), step=0.25, format="%.2f", key=f"dd_ws1_{tid}")
            with w1_r_c:
                ed_wr1 = st.number_input("טווח שבועי — התנגדות (W-R1 $)", min_value=0.0, value=_get_sr_init("w_r_1"), step=0.25, format="%.2f", key=f"dd_wr1_{tid}")

    with tags_col:
        with st.container(border=True):
            _html('<div style="font-size:0.95rem; font-weight:800; color:#F8FAFC; margin-bottom:8px; direction:rtl;">תגיות תצורה טכנית (Technical Setup Tags — ניתנות לעריכה)</div>')

            cur_setup = str(trade_row.get("setup_pattern") or "").strip()
            if not cur_setup and market_row is not None and pd.notna(market_row.get("setup_pattern")):
                cur_setup = str(market_row["setup_pattern"]).strip()
            if not cur_setup:
                cur_setup = "ללא Setup"
            setup_list = SETUP_OPTIONS if cur_setup in SETUP_OPTIONS else [cur_setup] + SETUP_OPTIONS
            ed_setup = st.selectbox(
                "תבנית מסחר ראשית (Setup — מסתנכרן עם ניתוח עומק)",
                setup_list,
                index=setup_list.index(cur_setup),
                key=f"dd_setup_{tid}",
            )

            t_c1, t_c2 = st.columns(2)
            with t_c1:
                cur_candle = str(trade_row.get("candlestick_pattern") or "ללא").strip() or "ללא"
                c_list = CANDLESTICK_OPTIONS if cur_candle in CANDLESTICK_OPTIONS else [cur_candle] + CANDLESTICK_OPTIONS
                ed_candle = st.selectbox("תבנית נרות (Candlestick)", c_list, index=c_list.index(cur_candle), key=f"dd_candle_{tid}")

                cur_fib = str(trade_row.get("fibonacci_level") or "ללא").strip() or "ללא"
                f_list = FIBONACCI_OPTIONS if cur_fib in FIBONACCI_OPTIONS else [cur_fib] + FIBONACCI_OPTIONS
                ed_fib = st.selectbox("רמת פיבונאצ'י (Fibonacci)", f_list, index=f_list.index(cur_fib), key=f"dd_fib_{tid}")

            with t_c2:
                cur_trend = str(trade_row.get("trendline_status") or "ללא").strip() or "ללא"
                tr_list = TRENDLINE_OPTIONS if cur_trend in TRENDLINE_OPTIONS else [cur_trend] + TRENDLINE_OPTIONS
                ed_trend = st.selectbox("קו מגמה (Trendline)", tr_list, index=tr_list.index(cur_trend), key=f"dd_trend_{tid}")

                cur_gap = str(trade_row.get("gap_status") or "ללא גאפ פתוח").strip() or "ללא גאפ פתוח"
                g_list = GAP_OPTIONS if cur_gap in GAP_OPTIONS else [cur_gap] + GAP_OPTIONS
                ed_gap = st.selectbox("גאפ (Gap Status)", g_list, index=g_list.index(cur_gap), key=f"dd_gap_{tid}")

    # === JOURNAL: RATIONALE, EXIT NOTES & LESSONS LEARNED (FULL EDITING) ===
    with st.container(border=True):
        jh_right, jh_left = st.columns([2.2, 1.3])
        with jh_right:
            _html('<div style="font-size:1.0rem; font-weight:800; color:#F8FAFC; padding-top:4px; direction:rtl;">יומן מסחר, נימוקי כניסה ומסקנות</div>')
        with jh_left:
            plan_choice = st.radio(
                "עמידה בתוכנית:",
                ["✓ לפי תוכנית", "✗ חריגה"],
                index=0 if is_plan_ok else 1,
                horizontal=True,
                key=f"dd_plan_{tid}",
            )

        raw_legacy_notes = str(trade_row.get("notes") or "")
        if raw_legacy_notes.lower() in ("nan", "none"):
            raw_legacy_notes = ""

        init_rationale = str(trade_row.get("entry_rationale") or "")
        if init_rationale.lower() in ("nan", "none") or not init_rationale.strip():
            init_rationale = raw_legacy_notes

        init_exit_notes = str(trade_row.get("exit_notes") or "")
        if init_exit_notes.lower() in ("nan", "none"):
            init_exit_notes = ""

        init_lessons = str(trade_row.get("lessons_learned") or "")
        if init_lessons.lower() in ("nan", "none"):
            init_lessons = ""

        n_c1, n_c2, n_c3 = st.columns(3)
        with n_c1:
            ed_rationale = st.text_area(
                "נימוקי כניסה וטריגר (Entry Rationale)",
                value=init_rationale,
                height=115,
                placeholder="לדוגמה: בדיקה חוזרת מעל MA20 ו-MA50 לאחר דוחות חזקים...",
                key=f"dd_rat_{tid}",
            )
        with n_c2:
            ed_exit_notes = st.text_area(
                "ניהול עסקה והערות יציאה (Exit Notes)",
                value=init_exit_notes,
                height=115,
                placeholder="לדוגמה: העלאת סטופ ל-$438 לאחר מעבר מעל $460...",
                key=f"dd_exit_{tid}",
            )
        with n_c3:
            ed_lessons = st.text_area(
                "מסקנות ולקחים לעתיד (Lessons Learned)",
                value=init_lessons,
                height=115,
                placeholder="לדוגמה: כניסה סבלנית בפולבק מייצרת יחס סיכוי/סיכון מעולה...",
                key=f"dd_les_{tid}",
            )

    # === SAVE & DELETE BUTTONS ===
    act_save, act_del = st.columns([3.2, 1.0])
    with act_save:
        if st.button("💾 שמור את כל השינויים וסנכרן Setup", type="primary", use_container_width=True, key=f"dd_save_all_{tid}"):
            now_iso = datetime.now(timezone.utc).isoformat()
            clean_setup_save = None if ed_setup == "ללא Setup" else ed_setup
            plan_save = "Yes" if "לפי תוכנית" in plan_choice else "No"

            ds1_str = f"${ed_ds1:,.2f}" if ed_ds1 > 0 else "-"
            dr1_str = f"${ed_dr1:,.2f}" if ed_dr1 > 0 else "-"
            ws1_str = f"${ed_ws1:,.2f}" if ed_ws1 > 0 else "-"
            wr1_str = f"${ed_wr1:,.2f}" if ed_wr1 > 0 else "-"

            combined_notes = "\n\n".join(
                part for part in [ed_rationale.strip(), ed_exit_notes.strip(), ed_lessons.strip()] if part
            )

            full_update = {
                "stop_loss": round(float(edit_sl), 4) if edit_sl > 0 else None,
                "take_profit": round(float(edit_tp), 4) if edit_tp > 0 else None,
                "d_s_1": round(float(ed_ds1), 4) if ed_ds1 > 0 else None,
                "d_r_1": round(float(ed_dr1), 4) if ed_dr1 > 0 else None,
                "d_s_2": round(float(ed_ds2), 4) if ed_ds2 > 0 else None,
                "d_r_2": round(float(ed_dr2), 4) if ed_dr2 > 0 else None,
                "w_s_1": round(float(ed_ws1), 4) if ed_ws1 > 0 else None,
                "w_r_1": round(float(ed_wr1), 4) if ed_wr1 > 0 else None,
                "daily_next_sr": f"S: {ds1_str} | R: {dr1_str}",
                "weekly_next_sr": f"S: {ws1_str} | R: {wr1_str}",
                "setup_pattern": clean_setup_save,
                "candlestick_pattern": None if ed_candle == "ללא" else ed_candle,
                "trendline_status": None if ed_trend == "ללא" else ed_trend,
                "gap_status": None if ed_gap == "ללא גאפ פתוח" else ed_gap,
                "fibonacci_level": None if ed_fib == "ללא" else ed_fib,
                "according_to_plan": plan_save,
                "entry_rationale": ed_rationale.strip() or None,
                "exit_notes": ed_exit_notes.strip() or None,
                "lessons_learned": ed_lessons.strip() or None,
                "notes": combined_notes or None,
                "updated_at": now_iso,
            }
            _safe_update_trade(tid, full_update, existing_cols)
            sync_setup_pattern(sym, clean_setup_save, trade_id=tid)
            _clear_all_caches()
            st.success("כל נתוני העסקה נשמרו וסונכרנו בהצלחה!")
            st.rerun()

    with act_del:
        del_confirm_key = f"dd_del_confirm_{tid}"
        if not st.session_state.get(del_confirm_key, False):
            if st.button("🗑️ מחק עסקה", use_container_width=True, key=f"dd_del_btn_{tid}"):
                st.session_state[del_confirm_key] = True
                st.rerun()
        else:
            if st.button("⚠️ אשר מחיקה סופית", type="primary", use_container_width=True, key=f"dd_del_yes_{tid}"):
                sb = get_supabase_client()
                sb.table("trade_journal").delete().eq("id", tid).execute()
                st.session_state[del_confirm_key] = False
                st.session_state["jp_selected_trade_id"] = None
                _clear_all_caches()
                st.rerun()


# === [SEC-05: MAIN POSITIONS & TRADE JOURNAL PAGE RENDERER] ===
def render_positions_and_log_page() -> None:
    inject_positions_css()

    df_market = load_market_dataframe()
    market_by_sym: dict[str, pd.Series] = {}
    price_map: dict[str, float] = {}
    if not df_market.empty:
        for _, r in df_market.iterrows():
            s_clean = str(r["symbol"]).split(":")[-1].strip().upper()
            market_by_sym[s_clean] = r
            if pd.notna(r.get("display_price")):
                price_map[s_clean] = float(r["display_price"])

    df_trades, df_cash = load_journal_data()

    # === TOP ACTION BAR (Prototype CCDC) ===
    act_r1, act_r2, act_r3, _sp, act_status = st.columns([1.15, 1.05, 0.95, 1.1, 1.85])
    with act_r1:
        if st.button("＋ פתיחת עסקה חדשה", type="primary", use_container_width=True, key="jp_btn_new_trade"):
            _open_new_trade_modal(df_market)
    with act_r2:
        if st.button("＋ הפקדה לחשבון", use_container_width=True, key="jp_btn_deposit"):
            _open_deposit_modal()
    with act_r3:
        if st.button("↻ רענן מחירים", use_container_width=True, key="jp_btn_refresh"):
            open_syms = (
                df_trades[df_trades["status"] == "Open"]["symbol"].dropna().astype(str).unique().tolist()
                if not df_trades.empty
                else []
            )
            with st.spinner("מרענן שערי מסחר חיים..."):
                refresh_live_prices_tv(open_syms)
                _clear_all_caches()
            st.rerun()
    with act_status:
        month_lbl = datetime.now().strftime("%b %Y")
        _html(
            f'<div style="display:flex; justify-content:flex-end;">'
            f'<div class="jp-status-pill">'
            f'<span class="jp-live-dot"></span>'
            f'<span>שערי שוק חיים מסונכרנים</span>'
            f'<span style="color:#334155;">|</span>'
            f'<span>חודש נוכחי: <b style="color:#F8FAFC;" dir="ltr">{month_lbl}</b></span>'
            f'</div></div>'
        )

    # === KPI CALCULATIONS ===
    total_deposits = (
        float(df_cash[df_cash["tx_type"] == "Deposit"]["amount_usd"].sum())
        - float(df_cash[df_cash["tx_type"] == "Withdrawal"]["amount_usd"].sum())
        if not df_cash.empty
        else 0.0
    )

    open_df = df_trades[df_trades["status"] == "Open"].copy() if not df_trades.empty else pd.DataFrame()
    closed_df = df_trades[df_trades["status"] == "Closed"].copy() if not df_trades.empty else pd.DataFrame()

    invested_open = 0.0
    open_pnl = 0.0
    for _, r in open_df.iterrows():
        s_up = str(r["symbol"]).split(":")[-1].strip().upper()
        ep = float(r["entry_price"])
        q = float(r["quantity"])
        lp = price_map.get(s_up, ep)
        invested_open += ep * q
        open_pnl += (lp - ep) * q

    open_pnl_pct = (open_pnl / invested_open * 100.0) if invested_open > 0 else 0.0
    realized_all = float(closed_df["net_pnl"].fillna(0).sum()) if not closed_df.empty else 0.0
    available_cash = total_deposits + realized_all - invested_open

    now_ym = datetime.now().strftime("%Y-%m")
    if not closed_df.empty and "close_date" in closed_df.columns:
        m_closed = closed_df[closed_df["close_date"].astype(str).str.startswith(now_ym)]
    else:
        m_closed = pd.DataFrame()

    m_cnt = len(m_closed)
    m_wins = int((m_closed["net_pnl"].fillna(0) > 0).sum()) if m_cnt > 0 else 0
    m_losses = int((m_closed["net_pnl"].fillna(0) < 0).sum()) if m_cnt > 0 else 0
    m_wr = (m_wins / m_cnt * 100.0) if m_cnt > 0 else 0.0

    # === 4 TOP SUMMARY CARDS IN USER'S EXACT ORDER ===
    # 1. פוזיציות פתוחות | 2. מזומן פנוי | 3. רווח / הפסד פוזיציות פתוחות | 4. עסקאות סגורות החודש
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _html(
            f"""
            <div class="jp-kpi-card">
                <div class="jp-kpi-right">
                    <div class="jp-kpi-title">פוזיציות פתוחות</div>
                    <div class="jp-kpi-main-row">
                        <span class="jp-kpi-val">{len(open_df)} פוזיציות</span>
                        <span class="jp-kpi-sub-inline" style="color:#38BDF8;">מושקע {_ltr(_fmt_usd(invested_open, decimals=0))} •</span>
                    </div>
                </div>
                <span class="jp-kpi-badge jp-badge-open">OPEN</span>
            </div>
            """
        )

    with k2:
        cash_col = "#38BDF8" if available_cash >= 0 else "#EF4444"
        _html(
            f"""
            <div class="jp-kpi-card">
                <div class="jp-kpi-right">
                    <div class="jp-kpi-title">מזומן פנוי</div>
                    <div class="jp-kpi-main-row">
                        <span class="jp-kpi-val" style="color:{cash_col};">{_ltr(_fmt_usd(available_cash))}</span>
                    </div>
                </div>
                <span class="jp-kpi-badge jp-badge-cash">CASH</span>
            </div>
            """
        )

    with k3:
        op_col = "#10B981" if open_pnl >= 0 else "#EF4444"
        _html(
            f"""
            <div class="jp-kpi-card">
                <div class="jp-kpi-right">
                    <div class="jp-kpi-title">רווח / הפסד פוזיציות פתוחות</div>
                    <div class="jp-kpi-main-row">
                        <span class="jp-kpi-val" style="color:{op_col};">{_ltr(_fmt_usd(open_pnl, signed=True))}</span>
                        <span class="jp-kpi-sub-inline" style="color:{op_col};">{_ltr(f"{open_pnl_pct:+.2f}%")}</span>
                    </div>
                </div>
                <span class="jp-kpi-badge jp-badge-live">בזמן אמת</span>
            </div>
            """
        )

    with k4:
        wr_col = "#10B981" if m_wr >= 50 else ("#F59E0B" if m_cnt > 0 else "#94A3B8")
        _html(
            f"""
            <div class="jp-kpi-card">
                <div class="jp-kpi-right">
                    <div class="jp-kpi-title">עסקאות סגורות החודש</div>
                    <div class="jp-kpi-main-row">
                        <span class="jp-kpi-val">{m_cnt} עסקאות</span>
                        <span class="jp-kpi-sub-inline" style="color:{wr_col};">הצלחה {_ltr(f"{m_wr:.1f}%")} •</span>
                    </div>
                </div>
                <span class="jp-kpi-badge jp-badge-wl">{m_wins}W / {m_losses}L</span>
            </div>
            """
        )

    # === UNIFIED FILTER & SEARCH BAR (Prototype 0BB) ===
    with st.container():
        _html('<div class="jp-filter-marker" style="display:none;"></div>')
        f_search, f_status, f_outcome, f_plan = st.columns([1.45, 1.25, 1.15, 1.15])
        with f_search:
            _html('<div class="jp-filter-lbl">חיפוש מהיר:</div>')
            q_search = st.text_input(
                "חיפוש",
                placeholder="🔍 חיפוש לפי טיקר או שם חברה...",
                label_visibility="collapsed",
                key="jp_filter_search",
            ).strip().upper()
        with f_status:
            _html('<div class="jp-filter-lbl">סטטוס:</div>')
            flt_status = st.radio(
                "סטטוס",
                ["הכל", "פתוחות בלבד", "סגורות בלבד"],
                horizontal=True,
                label_visibility="collapsed",
                key="jp_filter_status",
            )
        with f_outcome:
            _html('<div class="jp-filter-lbl">תוצאה:</div>')
            flt_outcome = st.radio(
                "תוצאה",
                ["הכל", "רווחיות", "מפסידות"],
                horizontal=True,
                label_visibility="collapsed",
                key="jp_filter_outcome",
            )
        with f_plan:
            _html('<div class="jp-filter-lbl">משמעת:</div>')
            flt_plan = st.radio(
                "משמעת",
                ["הכל", "לפי תוכנית", "חריגה"],
                horizontal=True,
                label_visibility="collapsed",
                key="jp_filter_plan",
            )

    def _matches_filters(row: pd.Series, is_row_open: bool) -> bool:
        if q_search:
            s_txt = str(row.get("symbol") or "").upper()
            c_txt = str(row.get("company_name") or "").upper()
            if q_search not in s_txt and q_search not in c_txt:
                return False

        if flt_outcome != "הכל":
            if is_row_open:
                s_up = str(row["symbol"]).split(":")[-1].strip().upper()
                lp = price_map.get(s_up, float(row["entry_price"]))
                val_pnl = (lp - float(row["entry_price"])) * float(row["quantity"])
            else:
                val_pnl = float(row["net_pnl"]) if pd.notna(row.get("net_pnl")) else 0.0
            if flt_outcome == "רווחיות" and val_pnl <= 0:
                return False
            if flt_outcome == "מפסידות" and val_pnl >= 0:
                return False

        if flt_plan != "הכל":
            p_flag = str(row.get("according_to_plan") or "Yes")
            if flt_plan == "לפי תוכנית" and p_flag != "Yes":
                return False
            if flt_plan == "חריגה" and p_flag == "Yes":
                return False

        return True

    # === ACTIVE POSITIONS TABLE (Prototype 2F9 — Click Row to Open Deep Dive) ===
    if flt_status in ("הכל", "פתוחות בלבד"):
        filtered_open = [r for _, r in open_df.iterrows() if _matches_filters(r, True)] if not open_df.empty else []

        _html(
            f"""
            <div class="jp-section-shell" style="padding-bottom:14px;">
                <div class="jp-sec-hdr">
                    <div class="jp-sec-title-wrap">
                        <span style="color:#38BDF8; font-size:0.9rem;">●</span>
                        <span class="jp-sec-title">פוזיציות פתוחות - Active Positions</span>
                        <span class="jp-count-circle">{len(filtered_open)}</span>
                    </div>
                    <span class="jp-sec-hint">מסודר אוטומטית בראש הדף · לחץ על שורת מניה לניהול עסקה, עריכת SL/TP וניתוח עומק</span>
                </div>
                <div class="jp-active-grid jp-tbl-head">
                    <div>מניה</div>
                    <div>תאריך פתיחה</div>
                    <div>כמות</div>
                    <div>שער חי</div>
                    <div>שער כניסה</div>
                    <div>שווי פוזיציה</div>
                    <div>רווח / הפסד צף</div>
                    <div>יעדי SL / TP וטווח סיכון-סיכוי</div>
                </div>
            </div>
            """
        )

        if not filtered_open:
            st.info("אין פוזיציות פתוחות התואמות לסינון הנוכחי.")
        else:
            for r in filtered_open:
                tid = int(r["id"])
                sym = str(r["symbol"]).split(":")[-1].strip().upper()
                m_row = market_by_sym.get(sym)
                comp = str(r.get("company_name") or (m_row.get("company_name") if m_row is not None else sym) or sym)
                logo = str(m_row.get("logo_url") or "") if m_row is not None and pd.notna(m_row.get("logo_url")) else ""

                ep = float(r["entry_price"])
                qty = float(r["quantity"])
                lp = price_map.get(sym, ep)
                pos_val = lp * qty
                cost_val = ep * qty
                u_pnl = (lp - ep) * qty
                u_pct = ((lp - ep) / ep * 100.0) if ep > 0 else 0.0

                sl_v = float(r["stop_loss"]) if pd.notna(r.get("stop_loss")) and float(r["stop_loss"]) > 0 else None
                tp_v = float(r["take_profit"]) if pd.notna(r.get("take_profit")) and float(r["take_profit"]) > 0 else None
                sltp_cell_html, _ = _build_sltp_html(ep, lp, qty, sl_v, tp_v, compact=False)

                logo_box = (
                    f'<img src="{html.escape(logo)}" alt="{html.escape(sym)}"/>'
                    if logo.startswith("http")
                    else html.escape(sym[:4])
                )
                pnl_cls = "jp-pnl-win" if u_pnl >= 0 else "jp-pnl-loss"
                qty_txt = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}"
                hold_d = _calc_holding_days(r.get("entry_date"))

                with st.container():
                    _html(
                        f"""
                        <div class="jp-row-wrap">
                            <div class="jp-active-grid jp-row-card">
                                <div class="jp-stock-cell">
                                    <div class="jp-logo-circle">{logo_box}</div>
                                    <div>
                                        <div class="jp-ticker-txt">{html.escape(sym)}</div>
                                        <div class="jp-comp-txt">{html.escape(comp)}</div>
                                    </div>
                                </div>
                                <div>
                                    <div class="jp-cell-main">{_ltr(_fmt_date_short(r.get("entry_date")))}</div>
                                    <div class="jp-cell-sub">{hold_d} ימים</div>
                                </div>
                                <div class="jp-cell-main">{_ltr(qty_txt)}</div>
                                <div class="jp-cell-main" style="color:#38BDF8;">{_ltr(_fmt_usd(lp))}</div>
                                <div class="jp-cell-main">{_ltr(_fmt_usd(ep))}</div>
                                <div>
                                    <div class="jp-cell-main">{_ltr(_fmt_usd(pos_val))}</div>
                                    <div class="jp-cell-sub">עלות: {_ltr(_fmt_usd(cost_val))}</div>
                                </div>
                                <div>
                                    <div class="jp-pnl-box {pnl_cls}">
                                        <span style="font-size:0.9rem; font-weight:800;">{_fmt_usd(u_pnl, signed=True)}</span>
                                        <span style="font-size:0.75rem; font-weight:700;">{u_pct:+.2f}%</span>
                                    </div>
                                </div>
                                <div>{sltp_cell_html}</div>
                            </div>
                        </div>
                        """
                    )
                    if st.button(" ", key=f"jp_open_row_btn_{tid}", use_container_width=True):
                        st.session_state["jp_selected_trade_id"] = tid
                        st.session_state[f"dd_close_panel_open_{tid}"] = False
                        st.rerun()

    # === CLOSED TRADES TABLE (Click Row to Open Deep Dive — No Extra Button Column) ===
    if flt_status in ("הכל", "סגורות בלבד"):
        filtered_closed = [r for _, r in closed_df.iterrows() if _matches_filters(r, False)] if not closed_df.empty else []

        _html(
            f"""
            <div class="jp-section-shell" style="margin-top:16px; padding-bottom:14px;">
                <div class="jp-sec-hdr">
                    <div class="jp-sec-title-wrap">
                        <span style="color:#10B981; font-size:0.9rem;">●</span>
                        <span class="jp-sec-title">יומן עסקאות סגורות - Closed Trade Log</span>
                        <span class="jp-count-circle" style="color:#10B981; border-color:rgba(16,185,129,0.35); background:rgba(16,185,129,0.12);">{len(filtered_closed)}</span>
                    </div>
                    <span class="jp-sec-hint">לחץ על שורת עסקה לצפייה בצילום המצב הטכני ועריכת מסקנות</span>
                </div>
                <div class="jp-closed-grid jp-tbl-head">
                    <div>מניה</div>
                    <div>תאריכים ומשך החזקה</div>
                    <div>כמות ושערי ביצוע</div>
                    <div>רווח / הפסד נטו</div>
                    <div>גולמי · מס ועמלות</div>
                    <div>Setup ומשמעת</div>
                </div>
            </div>
            """
        )

        if not filtered_closed:
            st.info("אין עסקאות סגורות התואמות לסינון הנוכחי.")
        else:
            for r in filtered_closed:
                tid = int(r["id"])
                sym = str(r["symbol"]).split(":")[-1].strip().upper()
                m_row = market_by_sym.get(sym)
                comp = str(r.get("company_name") or (m_row.get("company_name") if m_row is not None else sym) or sym)
                logo = str(m_row.get("logo_url") or "") if m_row is not None and pd.notna(m_row.get("logo_url")) else ""

                ep = float(r["entry_price"])
                cp_raw = r.get("close_price") if pd.notna(r.get("close_price")) else r.get("exit_price")
                cp = float(cp_raw) if cp_raw is not None and pd.notna(cp_raw) else ep
                qty = float(r["quantity"])
                qty_txt = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}"

                net_p = float(r["net_pnl"]) if pd.notna(r.get("net_pnl")) else (cp - ep) * qty
                gross_p = float(r["gross_pnl"]) if pd.notna(r.get("gross_pnl")) else (cp - ep) * qty
                tax_p = float(r["tax_paid"]) if pd.notna(r.get("tax_paid")) else 0.0
                fee_p = float(r["fees"]) if pd.notna(r.get("fees")) else 0.0
                ret_pct = ((cp - ep) / ep * 100.0) if ep > 0 else 0.0

                hold_d = _calc_holding_days(r.get("entry_date"), r.get("close_date"))
                dt_range = f"{_fmt_date_short(r.get('entry_date'))} ← {_fmt_date_short(r.get('close_date'))}"

                setup_txt = str(r.get("setup_pattern") or "").strip() or "ללא Setup"
                plan_ok = str(r.get("according_to_plan") or "Yes") == "Yes"
                plan_pill = (
                    '<span class="dd-plan-badge-ok" style="font-size:0.72rem; padding:2px 8px;">✓ לפי תוכנית</span>'
                    if plan_ok
                    else '<span class="dd-plan-badge-no" style="font-size:0.72rem; padding:2px 8px;">✗ חריגה</span>'
                )

                logo_box = (
                    f'<img src="{html.escape(logo)}" alt="{html.escape(sym)}"/>'
                    if logo.startswith("http")
                    else html.escape(sym[:4])
                )
                pnl_cls = "jp-pnl-win" if net_p >= 0 else "jp-pnl-loss"

                with st.container():
                    _html(
                        f"""
                        <div class="jp-row-wrap">
                            <div class="jp-closed-grid jp-row-card">
                                <div class="jp-stock-cell">
                                    <div class="jp-logo-circle">{logo_box}</div>
                                    <div>
                                        <div class="jp-ticker-txt">{html.escape(sym)}</div>
                                        <div class="jp-comp-txt">{html.escape(comp)}</div>
                                    </div>
                                </div>
                                <div>
                                    <div class="jp-cell-main">{_ltr(dt_range)}</div>
                                    <div class="jp-cell-sub">{hold_d} ימים</div>
                                </div>
                                <div>
                                    <div class="jp-cell-main">{_ltr(f"{_fmt_usd(ep)} → {_fmt_usd(cp)}")}</div>
                                    <div class="jp-cell-sub">{qty_txt} מניות</div>
                                </div>
                                <div>
                                    <div class="jp-pnl-box {pnl_cls}">
                                        <span style="font-size:0.9rem; font-weight:800;">{_fmt_usd(net_p, signed=True)}</span>
                                        <span style="font-size:0.75rem; font-weight:700;">{ret_pct:+.2f}%</span>
                                    </div>
                                </div>
                                <div>
                                    <div class="jp-cell-main">גולמי: {_ltr(_fmt_usd(gross_p, signed=True))}</div>
                                    <div class="jp-cell-sub">מס: {_ltr(_fmt_usd(tax_p))} | עמלות: {_ltr(_fmt_usd(fee_p))}</div>
                                </div>
                                <div>
                                    <div style="font-size:0.8rem; font-weight:700; color:#CBD5E1; margin-bottom:4px;">{html.escape(setup_txt)}</div>
                                    {plan_pill}
                                </div>
                            </div>
                        </div>
                        """
                    )
                    if st.button(" ", key=f"jp_closed_row_btn_{tid}", use_container_width=True):
                        st.session_state["jp_selected_trade_id"] = tid
                        st.rerun()

    # === OPEN DEEP DIVE MODAL IF A ROW WAS CLICKED ===
    selected_tid = st.session_state.get("jp_selected_trade_id")
    if selected_tid is not None and not df_trades.empty:
        matched_rows = df_trades[df_trades["id"] == selected_tid]
        if not matched_rows.empty:
            t_row = matched_rows.iloc[0]
            s_clean = str(t_row["symbol"]).split(":")[-1].strip().upper()
            m_row = market_by_sym.get(s_clean)
            lp_modal = price_map.get(s_clean, float(t_row["entry_price"]))
            open_trade_deep_dive_modal(t_row, m_row, lp_modal, set(df_trades.columns))
        else:
            st.session_state["jp_selected_trade_id"] = None
