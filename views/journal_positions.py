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
    CANDLE_OPTIONS,
    FIBONACCI_OPTIONS,
    GAPS_OPTIONS,
    SETUP_OPTIONS,
    TRENDLINE_OPTIONS,
    compute_live_entry_indicators,
    insert_cash_tx,
    insert_trade,
    load_journal_data,
)

APP_FONT = "'Assistant', 'Rubik', sans-serif"


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

        /* 4 Top Summary Cards */
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
            transition: border-color 0.2s ease;
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
            padding: 4px 11px !important;
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
            font-size: 0.82rem !important;
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

        /* UNIFIED SINGLE-FRAME TABLE SHELL */
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-unified-table-marker) {{
            background: #0D111A !important;
            border: 1px solid #1E2638 !important;
            border-radius: 18px !important;
            padding: 18px 20px 14px 20px !important;
            margin-bottom: 18px !important;
            gap: 0 !important;
        }}
        .jp-sec-hdr {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            padding-bottom: 14px;
            border-bottom: 1px solid #1A2234;
            margin-bottom: 0;
            direction: rtl;
        }}
        .jp-sec-title-wrap {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
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
        .jp-avg-badge {{
            background: rgba(167, 139, 250, 0.14);
            color: #C4B5FD;
            border: 1px solid rgba(167, 139, 250, 0.38);
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 0.72rem;
            font-weight: 800;
            display: inline-block;
            margin-top: 3px;
        }}
        .jp-sec-hint {{
            font-size: 0.78rem;
            color: #64748B;
        }}

        /* Active & Closed Grid Tables (Aligned Header & Rows) */
        .jp-active-grid {{
            display: grid;
            grid-template-columns: minmax(150px, 1.5fr) minmax(88px, 0.85fr) minmax(52px, 0.5fr) minmax(78px, 0.8fr) minmax(78px, 0.8fr) minmax(98px, 1.0fr) minmax(108px, 1.05fr) minmax(245px, 2.45fr);
            gap: 10px;
            align-items: center;
            direction: rtl;
            width: 100%;
            box-sizing: border-box;
        }}
        .jp-closed-grid {{
            display: grid;
            grid-template-columns: minmax(150px, 1.5fr) minmax(125px, 1.25fr) minmax(130px, 1.3fr) minmax(115px, 1.15fr) minmax(130px, 1.3fr) minmax(120px, 1.15fr);
            gap: 10px;
            align-items: center;
            direction: rtl;
            width: 100%;
            box-sizing: border-box;
        }}
        .jp-tbl-head {{
            padding: 11px 14px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #64748B;
            border-bottom: 1px solid #1E2638;
            background: rgba(17, 22, 34, 0.45);
        }}
        .jp-col-r {{
            text-align: right;
        }}
        .jp-col-c {{
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}

        /* Clickable Row Overlay Wrapper */
        div[data-testid="stVerticalBlock"]:has(> div.element-container .jp-row-wrap) {{
            position: relative !important;
            gap: 0 !important;
            margin: 0 !important;
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
            border-radius: 10px;
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
            text-align: right;
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
            max-width: 150px;
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
            min-width: 94px;
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

        /* SL / TP Range Bar & Glowing Dot */
        .jp-sltp-cell-pad {{
            width: 100%;
            padding: 0 12px;
            box-sizing: border-box;
            display: flex;
            justify-content: center;
        }}
        .jp-sltp-wrap {{
            width: 100%;
            max-width: 340px;
            direction: ltr;
        }}
        .jp-sltp-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 6px;
            font-size: 0.76rem;
            font-weight: 800;
            direction: ltr;
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
            padding: 1px 7px;
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

        /* =====================================================================
           DEEP DIVE MODAL STYLING — 1:1 VISUAL MATCH TO PROTOTYPE C82
           ===================================================================== */
        div[data-testid="stDialog"] div[role="dialog"] {{
            background: #080B12 !important;
            border: 1px solid #1E293B !important;
            border-radius: 20px !important;
            max-width: 1160px !important;
            width: 94vw !important;
        }}
        .c82-top-cards {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 10px;
            margin: 14px 0 16px 0;
            direction: rtl;
        }}
        .c82-stat-card {{
            background: #0D111A;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 13px 14px;
            text-align: right;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 86px;
        }}
        .c82-stat-lbl {{
            font-size: 0.78rem;
            font-weight: 600;
            color: #94A3B8;
            margin-bottom: 6px;
        }}
        .c82-stat-val {{
            font-size: 1.18rem;
            font-weight: 800;
            color: #F8FAFC;
            line-height: 1.2;
        }}
        .c82-stat-sub {{
            font-size: 0.73rem;
            color: #64748B;
            margin-top: 4px;
        }}

        /* Main Panel Container (Prototype C82) */
        .c82-panel {{
            background: #0D111A;
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 18px 20px;
            margin-bottom: 14px;
            direction: rtl;
            text-align: right;
        }}
        .c82-panel-hdr {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            direction: rtl;
        }}
        .c82-panel-title {{
            font-size: 1.06rem;
            font-weight: 800;
            color: #F8FAFC;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .c82-panel-sub {{
            font-size: 0.78rem;
            color: #64748B;
        }}

        /* 5 Snapshot Metric Cards */
        .c82-snap-5 {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 14px;
            direction: rtl;
        }}
        .c82-snap-tile {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 12px;
            padding: 14px 12px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 92px;
        }}
        .c82-snap-lbl {{
            font-size: 0.76rem;
            font-weight: 600;
            color: #94A3B8;
            margin-bottom: 7px;
        }}
        .c82-snap-num {{
            font-size: 1.24rem;
            font-weight: 800;
            line-height: 1.2;
        }}
        .c82-snap-note {{
            font-size: 0.72rem;
            color: #64748B;
            margin-top: 4px;
        }}

        /* 4 Moving Average Pills */
        .c82-ma-4 {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-top: 8px;
            direction: rtl;
        }}
        .c82-ma-pill {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 9px 16px;
            border-radius: 10px;
            font-size: 0.85rem;
            font-weight: 800;
        }}
        .c82-ma-above {{
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10B981;
        }}
        .c82-ma-below {{
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #EF4444;
        }}
        .c82-ma-none {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            color: #64748B;
        }}

        /* Two Side-by-Side Cards (S/R Levels & Technical Setup Tags) */
        .c82-two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 14px;
            direction: rtl;
        }}
        .c82-sr-row {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 10px;
            padding: 11px 16px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            direction: rtl;
        }}
        .c82-sr-row:last-child {{
            margin-bottom: 0;
        }}
        .c82-sr-lbl {{
            font-size: 0.84rem;
            font-weight: 700;
            color: #CBD5E1;
        }}
        .c82-sr-val {{
            font-size: 0.92rem;
            font-weight: 800;
            color: #38BDF8;
            direction: ltr;
        }}
        .c82-tags-2x2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            direction: rtl;
        }}
        .c82-tag-box {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 10px;
            padding: 11px 14px;
            text-align: right;
        }}
        .c82-tag-lbl {{
            font-size: 0.74rem;
            color: #64748B;
            margin-bottom: 4px;
        }}
        .c82-tag-val {{
            font-size: 0.9rem;
            font-weight: 800;
            color: #F8FAFC;
        }}

        /* Bottom Journal 3-Column Cards */
        .c82-journal-3 {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            direction: rtl;
        }}
        .c82-j-box {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 12px;
            padding: 14px 16px;
            min-height: 112px;
            text-align: right;
        }}
        .c82-j-title {{
            font-size: 0.84rem;
            font-weight: 800;
            color: #CBD5E1;
            margin-bottom: 8px;
        }}
        .c82-j-body {{
            font-size: 0.85rem;
            color: #94A3B8;
            line-height: 1.5;
            white-space: pre-wrap;
        }}

        /* Status & Plan Badges */
        .dd-plan-badge-ok {{
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid rgba(16, 185, 129, 0.45);
            color: #10B981;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
            display: inline-block;
        }}
        .dd-plan-badge-no {{
            background: rgba(239, 68, 68, 0.14);
            border: 1px solid rgba(239, 68, 68, 0.45);
            color: #EF4444;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
            display: inline-block;
        }}
        .dd-plan-badge-muted {{
            background: #0A0E17;
            border: 1px solid #1E2638;
            color: #64748B;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            display: inline-block;
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
        if compact:
            return '<div style="font-size:0.86rem; color:#64748B; font-weight:700;">לא הוגדר SL / TP</div>', "--"
        return (
            '<div class="jp-sltp-cell-pad">'
            '<div style="width:100%; max-width:340px; background:#0A0E17; border:1px dashed #263147; '
            'border-radius:10px; padding:8px 12px; text-align:center; font-size:0.75rem; color:#64748B;">'
            'לא הוגדר SL / TP · לחץ להגדרה</div></div>',
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

    if sl is not None and tp is not None and tp > sl:
        raw_pos = ((live_price - sl) / (tp - sl)) * 100.0
        dot_pct = max(3.0, min(97.0, raw_pos))
    elif sl is not None:
        dot_pct = 20.0 if live_price <= sl else 55.0
    else:
        dot_pct = 80.0 if live_price >= tp else 45.0

    # Compact card view (1:1 Prototype C82 clean SL | TP + slim bar)
    if compact:
        compact_html = (
            f'<div style="direction:ltr; text-align:left;">'
            f'<div style="font-size:0.9rem; font-weight:800; color:#F8FAFC; margin-bottom:6px;">'
            f'<span style="color:#EF4444;">{sl_txt}</span>'
            f'<span style="color:#475569;"> | </span>'
            f'<span style="color:#10B981;">{tp_txt}</span>'
            f'</div>'
            f'<div class="jp-range-track" style="height:5px;">'
            f'<div class="jp-range-dot" style="left:{dot_pct:.1f}%; width:9px; height:9px;"></div>'
            f'</div>'
            f'</div>'
        )
        return compact_html, rr_str

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

    wrap_inner = (
        f'<div class="jp-sltp-wrap">'
        f'<div class="jp-sltp-top">'
        f'<span class="jp-sl-lbl">{sl_txt}</span>'
        f'<span class="jp-rr-chip">R:R {rr_str}</span>'
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
    return f'<div class="jp-sltp-cell-pad">{wrap_inner}</div>', rr_str


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


# === [SEC-04: DEEP DIVE & FULL TRADE MANAGEMENT LARGE MODAL (1:1 PROTOTYPE C82)] ===
def _safe_update_trade(trade_id: int, update_dict: dict, existing_cols: set[str]) -> None:
    sb = get_supabase_client()
    filtered = {k: v for k, v in update_dict.items() if k in existing_cols}
    if not filtered:
        return
    try:
        sb.table("trade_journal").update(filtered).eq("id", trade_id).execute()
    except Exception:
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


def _pick_metric_val(trade_row: pd.Series, market_row: pd.Series | None, col_name: str):
    if pd.notna(trade_row.get(col_name)):
        return trade_row[col_name]
    if market_row is not None and pd.notna(market_row.get(col_name)):
        return market_row[col_name]
    return None


@st.dialog("כרטיסיית ניתוח עומק וניהול עסקה", width="large")
def open_trade_deep_dive_modal(
    trade_row: pd.Series,
    market_row: pd.Series | None,
    live_price: float,
    existing_cols: set[str],
) -> None:
    tid = int(trade_row["id"])
    sym = str(trade_row["symbol"]).split(":")[-1].strip().upper()
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
    edit_mode_key = f"dd_edit_mode_{tid}"
    is_edit_mode = st.session_state.get(edit_mode_key, False)

    # === TOP HEADER BAR (Matches Prototype C82 + Close & Edit Actions) ===
    hdr_right, hdr_mid, hdr_left = st.columns([2.9, 0.95, 0.95])
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

    with hdr_mid:
        edit_lbl = "👁️ סגור עריכה" if is_edit_mode else "✏️ עריכת נתונים"
        if st.button(edit_lbl, use_container_width=True, key=f"btn_toggle_edit_{tid}"):
            st.session_state[edit_mode_key] = not is_edit_mode
            st.rerun()

    with hdr_left:
        if is_open:
            close_toggle_key = f"dd_close_panel_open_{tid}"
            if st.button("🔒 סגירת עסקה", type="primary", use_container_width=True, key=f"btn_toggle_close_{tid}"):
                st.session_state[close_toggle_key] = not st.session_state.get(close_toggle_key, False)

    # Inline Close Trade Panel
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

    # === 7 ROUNDED STAT CARDS IN EXACT ORDER (Prototype C82 Style) ===
    sltp_html_card, rr_val_str = _build_sltp_html(ep, curr_p, qty, sl_curr, tp_curr, compact=True)
    price_lbl_title = "שער חי" if is_open else "שער סגירה"
    pnl_lbl_title = "רווח / הפסד נוכחי" if is_open else "רווח / הפסד נטו"

    _html(
        f"""
        <div class="c82-top-cards">
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">תאריך כניסה</div>
                <div class="c82-stat-val">{_ltr(entry_dt_str)}</div>
                <div class="c82-stat-sub">{hold_days} ימים</div>
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">שער כניסה</div>
                <div class="c82-stat-val">{_ltr(_fmt_usd(ep))}</div>
                <div class="c82-stat-sub">עלות {_ltr(_fmt_usd(cost_total, decimals=0))}</div>
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">{price_lbl_title}</div>
                <div class="c82-stat-val" style="color:#38BDF8;">{_ltr(_fmt_usd(curr_p))}</div>
                <div class="c82-stat-sub">שווי {_ltr(_fmt_usd(curr_p * qty, decimals=0))}</div>
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">כמות</div>
                <div class="c82-stat-val">{_ltr(qty_lbl)}</div>
                <div class="c82-stat-sub">מניות</div>
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">{pnl_lbl_title}</div>
                <div class="c82-stat-val" style="color:{pnl_color};">{_ltr(_fmt_usd(pnl_usd, signed=True))}</div>
                <div class="c82-stat-sub" style="color:{pnl_color}; font-weight:700;">{_ltr(f"{pnl_pct:+.2f}%")}</div>
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">SL / TP</div>
                {sltp_html_card}
            </div>
            <div class="c82-stat-card">
                <div class="c82-stat-lbl">RR</div>
                <div class="c82-stat-val" style="color:#38BDF8;">{_ltr(rr_val_str)}</div>
                <div class="c82-stat-sub">יחס סיכוי/סיכון</div>
            </div>
        </div>
        """
    )

    # === ENTRY TECHNICAL SNAPSHOT (1:1 PROTOTYPE C82) ===
    rsi_raw = _pick_metric_val(trade_row, market_row, "rsi")
    rsi_v = f"{float(rsi_raw):.1f}" if rsi_raw is not None else "--"

    macd_raw = str(trade_row.get("macd_status") or "").strip()
    if not macd_raw or macd_raw.lower() in ("nan", "none"):
        macd_v = "--"
    else:
        macd_v = macd_raw.split("(")[0].strip()

    cci_raw = trade_row.get("cci_value")
    cci_num = f"{float(cci_raw):.1f}" if pd.notna(cci_raw) else "--"
    cci_st = str(trade_row.get("cci_status") or "").strip()
    if cci_st.lower() in ("nan", "none"):
        cci_st = ""

    rv5_raw = _pick_metric_val(trade_row, market_row, "rel_vol_5d")
    rv20_raw = _pick_metric_val(trade_row, market_row, "rel_vol_20d")
    rv5 = f"{float(rv5_raw):.2f}x" if rv5_raw is not None else "--"
    rv20 = f"{float(rv20_raw):.2f}x" if rv20_raw is not None else "--"

    atr_raw = _pick_metric_val(trade_row, market_row, "atr_14")
    sqz_raw = _pick_metric_val(trade_row, market_row, "atr_squeeze_pct")
    atr_v = f"${float(atr_raw):.2f}" if atr_raw is not None else "--"
    sqz_v = f"{float(sqz_raw):.0f}%" if sqz_raw is not None else "--"

    def _ma_pill_c82(label: str, col_t: str, col_m: str) -> str:
        raw_st = trade_row.get(col_t)
        if pd.isna(raw_st) or not str(raw_st).strip():
            raw_st = market_row.get(col_m) if market_row is not None else None
        s = str(raw_st or "").strip().lower()
        if "above" in s:
            return f'<div class="c82-ma-pill c82-ma-above"><span>{label}</span><span dir="ltr">Above ▲</span></div>'
        if "below" in s:
            return f'<div class="c82-ma-pill c82-ma-below"><span>{label}</span><span dir="ltr">Below ▼</span></div>'
        return f'<div class="c82-ma-pill c82-ma-none"><span>{label}</span><span>--</span></div>'

    ma_pills_html = (
        _ma_pill_c82("MA 20", "ma_20", "ma_20_status")
        + _ma_pill_c82("MA 50", "ma_50", "ma_50_status")
        + _ma_pill_c82("MA 150", "ma_150", "ma_150_status")
        + _ma_pill_c82("MA 200", "ma_200", "ma_200_status")
    )

    _html(
        f"""
        <div class="c82-panel">
            <div class="c82-panel-hdr">
                <div class="c82-panel-title">
                    <span style="color:#38BDF8; font-size:0.9rem;">●</span>
                    <span>צילום מצב טכני ברגע הכניסה לעסקה (Entry Snapshot)</span>
                </div>
                <span class="c82-panel-sub">נשמר אוטומטית בעת פתיחת העסקה</span>
            </div>
            <div class="c82-snap-5">
                <div class="c82-snap-tile">
                    <div class="c82-snap-lbl">RSI (14) בכניסה</div>
                    <div class="c82-snap-num" style="color:#10B981;">{_ltr(rsi_v)}</div>
                </div>
                <div class="c82-snap-tile">
                    <div class="c82-snap-lbl">MACD Status</div>
                    <div class="c82-snap-num" style="color:#10B981; font-size:1.05rem;">{html.escape(macd_v)}</div>
                </div>
                <div class="c82-snap-tile">
                    <div class="c82-snap-lbl">CCI (20)</div>
                    <div class="c82-snap-num" style="color:#F8FAFC;">{_ltr(cci_num)}</div>
                    <div class="c82-snap-note">{html.escape(cci_st) if cci_st else "&nbsp;"}</div>
                </div>
                <div class="c82-snap-tile">
                    <div class="c82-snap-lbl">Rel Volume (5D / 20D)</div>
                    <div class="c82-snap-num" style="color:#38BDF8;">{_ltr(f"{rv5} / {rv20}")}</div>
                </div>
                <div class="c82-snap-tile">
                    <div class="c82-snap-lbl">ATR(14) · Squeeze</div>
                    <div class="c82-snap-num" style="color:#F8FAFC;">
                        <span dir="ltr">{atr_v} · <span style="color:#10B981;">{sqz_v}</span></span>
                    </div>
                </div>
            </div>
            <div style="font-size:0.8rem; color:#94A3B8; font-weight:600;">
                מיקום ביחס לממוצעים נעים (Moving Averages) בכניסה:
            </div>
            <div class="c82-ma-4">{ma_pills_html}</div>
        </div>
        """
    )

    # Helper to read S/R values
    def _get_sr_val(col_name: str) -> float:
        if pd.notna(trade_row.get(col_name)):
            return float(trade_row[col_name])
        if market_row is not None and pd.notna(market_row.get(col_name)):
            return float(market_row[col_name])
        return 0.0

    ds1_v, dr1_v = _get_sr_val("d_s_1"), _get_sr_val("d_r_1")
    ds2_v, dr2_v = _get_sr_val("d_s_2"), _get_sr_val("d_r_2")
    ws1_v, wr1_v = _get_sr_val("w_s_1"), _get_sr_val("w_r_1")

    cur_setup = str(trade_row.get("setup_pattern") or "").strip()
    if not cur_setup and market_row is not None and pd.notna(market_row.get("setup_pattern")):
        cur_setup = str(market_row["setup_pattern"]).strip()
    if not cur_setup:
        cur_setup = "ללא Setup"

    cur_candle = str(trade_row.get("candlestick_pattern") or "").strip()
    if not cur_candle or cur_candle.lower() in ("nan", "none"):
        cur_candle = CANDLE_OPTIONS[0]

    cur_trend = str(trade_row.get("trendline_status") or "").strip()
    if not cur_trend or cur_trend.lower() in ("nan", "none"):
        cur_trend = TRENDLINE_OPTIONS[0]

    cur_gap = str(trade_row.get("gap_status") or "").strip()
    if not cur_gap or cur_gap.lower() in ("nan", "none"):
        cur_gap = GAPS_OPTIONS[0]

    cur_fib = str(trade_row.get("fibonacci_level") or "").strip()
    if not cur_fib or cur_fib.lower() in ("nan", "none"):
        cur_fib = FIBONACCI_OPTIONS[0]

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

    # === VIEW MODE (1:1 PROTOTYPE C82 CLEAN DARK CARDS) vs EDIT MODE ===
    if not is_edit_mode:
        d1_disp = f"S1: ${ds1_v:,.2f}  |  R1: ${dr1_v:,.2f}" if (ds1_v > 0 or dr1_v > 0) else "לא הוגדר"
        d2_disp = f"S2: ${ds2_v:,.2f}  |  R2: ${dr2_v:,.2f}" if (ds2_v > 0 or dr2_v > 0) else "לא הוגדר"
        w1_disp = f"S1: ${ws1_v:,.2f}  |  R1: ${wr1_v:,.2f}" if (ws1_v > 0 or wr1_v > 0) else "לא הוגדר"

        plan_ok_cls = "dd-plan-badge-ok" if is_plan_ok else "dd-plan-badge-muted"
        plan_no_cls = "dd-plan-badge-no" if not is_plan_ok else "dd-plan-badge-muted"

        _html(
            f"""
            <div class="c82-two-col">
                <div class="c82-panel" style="margin-bottom:0;">
                    <div class="c82-panel-hdr">
                        <span class="c82-panel-title" style="font-size:0.98rem;">רמות תמיכה והתנגדות קרובות בכניסה (S1 / R1)</span>
                    </div>
                    <div class="c82-sr-row">
                        <span class="c82-sr-lbl">טווח יומי 1 (Daily S1/R1):</span>
                        <span class="c82-sr-val">{html.escape(d1_disp)}</span>
                    </div>
                    <div class="c82-sr-row">
                        <span class="c82-sr-lbl">טווח יומי 2 (Daily S2/R2):</span>
                        <span class="c82-sr-val">{html.escape(d2_disp)}</span>
                    </div>
                    <div class="c82-sr-row">
                        <span class="c82-sr-lbl">טווח שבועי (Weekly S1/R1):</span>
                        <span class="c82-sr-val">{html.escape(w1_disp)}</span>
                    </div>
                </div>

                <div class="c82-panel" style="margin-bottom:0;">
                    <div class="c82-panel-hdr">
                        <span class="c82-panel-title" style="font-size:0.98rem;">תגיות תצורה טכנית (Technical Setup Tags)</span>
                        <span style="background:rgba(56,189,248,0.12); border:1px solid rgba(56,189,248,0.35); color:#38BDF8; padding:2px 10px; border-radius:8px; font-size:0.76rem; font-weight:800;">
                            Setup: {html.escape(cur_setup)}
                        </span>
                    </div>
                    <div class="c82-tags-2x2">
                        <div class="c82-tag-box">
                            <div class="c82-tag-lbl">תבנית נרות (Candlestick)</div>
                            <div class="c82-tag-val">{html.escape(cur_candle)}</div>
                        </div>
                        <div class="c82-tag-box">
                            <div class="c82-tag-lbl">קו מגמה (Trendline)</div>
                            <div class="c82-tag-val">{html.escape(cur_trend)}</div>
                        </div>
                        <div class="c82-tag-box">
                            <div class="c82-tag-lbl">גאפ (Gap Status)</div>
                            <div class="c82-tag-val" style="color:#38BDF8;">{html.escape(cur_gap)}</div>
                        </div>
                        <div class="c82-tag-box">
                            <div class="c82-tag-lbl">רמת פיבונאצ'י (Fibonacci)</div>
                            <div class="c82-tag-val" style="color:#10B981;">{html.escape(cur_fib)}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="c82-panel" style="margin-bottom:0;">
                <div class="c82-panel-hdr">
                    <span class="c82-panel-title">יומן מסחר, נימוקי כניסה ומסקנות</span>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-size:0.8rem; color:#94A3B8;">עמידה בתוכנית:</span>
                        <span class="{plan_ok_cls}">✓ לפי תוכנית</span>
                        <span class="{plan_no_cls}">✗ חריגה</span>
                    </div>
                </div>
                <div class="c82-journal-3">
                    <div class="c82-j-box">
                        <div class="c82-j-title">נימוקי כניסה וטריגר (Entry Rationale)</div>
                        <div class="c82-j-body">{html.escape(init_rationale) if init_rationale.strip() else "לא הוזנו נימוקי כניסה — לחץ על 'עריכת נתונים' להוספה."}</div>
                    </div>
                    <div class="c82-j-box">
                        <div class="c82-j-title">ניהול עסקה והערות יציאה (Exit Notes)</div>
                        <div class="c82-j-body">{html.escape(init_exit_notes) if init_exit_notes.strip() else "אין הערות ניהול / יציאה עדיין."}</div>
                    </div>
                    <div class="c82-j-box">
                        <div class="c82-j-title">מסקנות ולקחים לעתיד (Lessons Learned)</div>
                        <div class="c82-j-body">{html.escape(init_lessons) if init_lessons.strip() else "אין מסקנות מתועדות עדיין."}</div>
                    </div>
                </div>
            </div>
            """
        )
    else:
        # === FULL EDIT MODE ===
        with st.container(border=True):
            _html('<div style="font-size:0.95rem; font-weight:800; color:#38BDF8; margin-bottom:6px; direction:rtl;">עריכת יעדי ניהול סיכון (SL / TP)</div>')
            sl_col, tp_col, rr_preview_col = st.columns([1.2, 1.2, 1.6])
            with sl_col:
                edit_sl = st.number_input(
                    "Stop Loss ($)",
                    min_value=0.0,
                    value=float(sl_curr) if sl_curr is not None else 0.0,
                    step=0.25,
                    format="%.2f",
                    key=f"dd_edit_sl_{tid}",
                )
            with tp_col:
                edit_tp = st.number_input(
                    "Take Profit ($)",
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
                    f'<div style="background:#0A0E17; border:1px solid #1E293B; border-radius:10px; padding:10px 14px; '
                    f'margin-top:22px; display:flex; justify-content:space-between; align-items:center; direction:rtl;">'
                    f'<span style="font-size:0.82rem; color:#94A3B8;">יחס R:R מעודכן לפי יעדים:</span>'
                    f'<span style="font-size:0.96rem; font-weight:800; color:#38BDF8;" dir="ltr">{live_rr}</span>'
                    f'</div>'
                )

        sr_col, tags_col = st.columns([1.05, 1.15])
        with sr_col:
            with st.container(border=True):
                _html('<div style="font-size:0.95rem; font-weight:800; color:#F8FAFC; margin-bottom:8px; direction:rtl;">עריכת רמות תמיכה והתנגדות (2 יומיים + 1 שבועי)</div>')
                d1_s_c, d1_r_c = st.columns(2)
                with d1_s_c:
                    ed_ds1 = st.number_input("טווח יומי 1 — תמיכה (S1 $)", min_value=0.0, value=ds1_v, step=0.25, format="%.2f", key=f"dd_ds1_{tid}")
                with d1_r_c:
                    ed_dr1 = st.number_input("טווח יומי 1 — התנגדות (R1 $)", min_value=0.0, value=dr1_v, step=0.25, format="%.2f", key=f"dd_dr1_{tid}")

                d2_s_c, d2_r_c = st.columns(2)
                with d2_s_c:
                    ed_ds2 = st.number_input("טווח יומי 2 — תמיכה (S2 $)", min_value=0.0, value=ds2_v, step=0.25, format="%.2f", key=f"dd_ds2_{tid}")
                with d2_r_c:
                    ed_dr2 = st.number_input("טווח יומי 2 — התנגדות (R2 $)", min_value=0.0, value=dr2_v, step=0.25, format="%.2f", key=f"dd_dr2_{tid}")

                w1_s_c, w1_r_c = st.columns(2)
                with w1_s_c:
                    ed_ws1 = st.number_input("טווח שבועי — תמיכה (W-S1 $)", min_value=0.0, value=ws1_v, step=0.25, format="%.2f", key=f"dd_ws1_{tid}")
                with w1_r_c:
                    ed_wr1 = st.number_input("טווח שבועי — התנגדות (W-R1 $)", min_value=0.0, value=wr1_v, step=0.25, format="%.2f", key=f"dd_wr1_{tid}")

        with tags_col:
            with st.container(border=True):
                _html('<div style="font-size:0.95rem; font-weight:800; color:#F8FAFC; margin-bottom:8px; direction:rtl;">עריכת תגיות תצורה טכנית (Technical Setup Tags)</div>')
                setup_list = SETUP_OPTIONS if cur_setup in SETUP_OPTIONS else [cur_setup] + SETUP_OPTIONS
                ed_setup = st.selectbox(
                    "תבנית מסחר ראשית (Setup — מסתנכרן עם ניתוח עומק)",
                    setup_list,
                    index=setup_list.index(cur_setup),
                    key=f"dd_setup_{tid}",
                )

                t_c1, t_c2 = st.columns(2)
                with t_c1:
                    c_list = CANDLE_OPTIONS if cur_candle in CANDLE_OPTIONS else [cur_candle] + CANDLE_OPTIONS
                    ed_candle = st.selectbox("תבנית נרות (Candlestick)", c_list, index=c_list.index(cur_candle), key=f"dd_candle_{tid}")

                    f_list = FIBONACCI_OPTIONS if cur_fib in FIBONACCI_OPTIONS else [cur_fib] + FIBONACCI_OPTIONS
                    ed_fib = st.selectbox("רמת פיבונאצ'י (Fibonacci)", f_list, index=f_list.index(cur_fib), key=f"dd_fib_{tid}")

                with t_c2:
                    tr_list = TRENDLINE_OPTIONS if cur_trend in TRENDLINE_OPTIONS else [cur_trend] + TRENDLINE_OPTIONS
                    ed_trend = st.selectbox("קו מגמה (Trendline)", tr_list, index=tr_list.index(cur_trend), key=f"dd_trend_{tid}")

                    g_list = GAPS_OPTIONS if cur_gap in GAPS_OPTIONS else [cur_gap] + GAPS_OPTIONS
                    ed_gap = st.selectbox("גאפ (Gap Status)", g_list, index=g_list.index(cur_gap), key=f"dd_gap_{tid}")

        with st.container(border=True):
            jh_right, jh_left = st.columns([2.2, 1.3])
            with jh_right:
                _html('<div style="font-size:1.0rem; font-weight:800; color:#F8FAFC; padding-top:4px; direction:rtl;">עריכת יומן מסחר, נימוקי כניסה ומסקנות</div>')
            with jh_left:
                plan_choice = st.radio(
                    "עמידה בתוכנית:",
                    ["✓ לפי תוכנית", "✗ חריגה"],
                    index=0 if is_plan_ok else 1,
                    horizontal=True,
                    key=f"dd_plan_{tid}",
                )

            n_c1, n_c2, n_c3 = st.columns(3)
            with n_c1:
                ed_rationale = st.text_area(
                    "נימוקי כניסה וטריגר (Entry Rationale)",
                    value=init_rationale,
                    height=115,
                    key=f"dd_rat_{tid}",
                )
            with n_c2:
                ed_exit_notes = st.text_area(
                    "ניהול עסקה והערות יציאה (Exit Notes)",
                    value=init_exit_notes,
                    height=115,
                    key=f"dd_exit_{tid}",
                )
            with n_c3:
                ed_lessons = st.text_area(
                    "מסקנות ולקחים לעתיד (Lessons Learned)",
                    value=init_lessons,
                    height=115,
                    key=f"dd_les_{tid}",
                )

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
                    "candlestick_pattern": None if ed_candle == CANDLE_OPTIONS[0] else ed_candle,
                    "trendline_status": None if ed_trend == TRENDLINE_OPTIONS[0] else ed_trend,
                    "gap_status": None if ed_gap == GAPS_OPTIONS[0] else ed_gap,
                    "fibonacci_level": None if ed_fib == FIBONACCI_OPTIONS[0] else ed_fib,
                    "according_to_plan": plan_save,
                    "entry_rationale": ed_rationale.strip() or None,
                    "exit_notes": ed_exit_notes.strip() or None,
                    "lessons_learned": ed_lessons.strip() or None,
                    "notes": combined_notes or None,
                    "updated_at": now_iso,
                }
                _safe_update_trade(tid, full_update, existing_cols)
                sync_setup_pattern(sym, clean_setup_save, trade_id=tid)
                st.session_state[edit_mode_key] = False
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


# === [SEC-05: AVERAGED POSITION LOT-BREAKDOWN MODAL] ===
@st.dialog("פירוט מנות ממוצעות (Averaged Lots)", width="large")
def open_averaged_lots_modal(
    sym: str,
    lots_df: pd.DataFrame,
    market_row: pd.Series | None,
    live_price: float,
) -> None:
    comp_name = str(lots_df.iloc[0].get("company_name") or (market_row.get("company_name") if market_row is not None else sym) or sym)
    tot_qty = float(lots_df["quantity"].sum())
    tot_cost = float((lots_df["entry_price"] * lots_df["quantity"]).sum())
    avg_ep = (tot_cost / tot_qty) if tot_qty > 0 else 0.0
    tot_val = live_price * tot_qty
    tot_pnl = tot_val - tot_cost
    tot_pct = (tot_pnl / tot_cost * 100.0) if tot_cost > 0 else 0.0
    pnl_col = "#10B981" if tot_pnl >= 0 else "#EF4444"

    _html(
        f"""
        <div class="c82-panel" style="margin-bottom:14px;">
            <div class="c82-panel-hdr">
                <span class="c82-panel-title">{html.escape(comp_name)} — {html.escape(sym)} · סיכום מיצוע ({len(lots_df)} מנות)</span>
                <span style="color:#38BDF8; font-weight:800; font-size:0.95rem;" dir="ltr">שער חי: {_fmt_usd(live_price)}</span>
            </div>
            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; direction:rtl;">
                <div class="c82-stat-card">
                    <div class="c82-stat-lbl">כמות מניות כוללת</div>
                    <div class="c82-stat-val">{_ltr(f"{tot_qty:g}")}</div>
                </div>
                <div class="c82-stat-card">
                    <div class="c82-stat-lbl">שער כניסה ממוצע</div>
                    <div class="c82-stat-val" style="color:#38BDF8;">{_ltr(_fmt_usd(avg_ep))}</div>
                </div>
                <div class="c82-stat-card">
                    <div class="c82-stat-lbl">עלות כוללת / שווי חי</div>
                    <div class="c82-stat-val">{_ltr(f"{_fmt_usd(tot_cost, decimals=0)} / {_fmt_usd(tot_val, decimals=0)}")}</div>
                </div>
                <div class="c82-stat-card">
                    <div class="c82-stat-lbl">רווח / הפסד מצטבר</div>
                    <div class="c82-stat-val" style="color:{pnl_col};">{_ltr(f"{_fmt_usd(tot_pnl, signed=True)} ({tot_pct:+.2f}%)")}</div>
                </div>
            </div>
        </div>
        """
    )

    st.caption("בחר מנה ספציפית כדי לפתוח את כרטיסיית ניתוח העומק והניהול שלה:")
    for idx, (_, lr) in enumerate(lots_df.iterrows(), start=1):
        ltid = int(lr["id"])
        lep = float(lr["entry_price"])
        lqty = float(lr["quantity"])
        lpnl = (live_price - lep) * lqty
        lpct = ((live_price - lep) / lep * 100.0) if lep > 0 else 0.0
        lcol = "#10B981" if lpnl >= 0 else "#EF4444"
        c_info, c_btn = st.columns([3.2, 1.0])
        with c_info:
            _html(
                f'<div style="background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:10px 14px; '
                f'display:flex; justify-content:space-between; align-items:center; direction:rtl;">'
                f'<span><b>מנה #{idx}</b> · כניסה: <span dir="ltr">{_fmt_date_short(lr.get("entry_date"))}</span> · '
                f'כמות: <b dir="ltr">{lqty:g}</b> · שער: <b dir="ltr">{_fmt_usd(lep)}</b></span>'
                f'<span style="color:{lcol}; font-weight:800;" dir="ltr">{_fmt_usd(lpnl, signed=True)} ({lpct:+.2f}%)</span>'
                f'</div>'
            )
        with c_btn:
            if st.button("פתח ניתוח עומק", key=f"avg_open_lot_{ltid}", use_container_width=True):
                st.session_state["jp_avg_symbol"] = None
                st.session_state["jp_selected_trade_id"] = ltid
                st.rerun()


# === [SEC-06: AVERAGING / CONSOLIDATION HELPERS] ===
def _build_averaged_open_rows(open_df: pd.DataFrame, price_map: dict[str, float]) -> list[dict]:
    """Consolidates open positions purchased in multiple tranches into weighted-average rows."""
    if open_df.empty:
        return []
    df = open_df.copy()
    df["clean_sym"] = df["symbol"].astype(str).str.split(":").str[-1].str.strip().str.upper()

    grouped_list: list[dict] = []
    for sym, grp in df.groupby("clean_sym", sort=False):
        tot_qty = float(grp["quantity"].sum())
        tot_cost = float((grp["entry_price"] * grp["quantity"]).sum())
        avg_ep = (tot_cost / tot_qty) if tot_qty > 0 else float(grp.iloc[0]["entry_price"])
        lp = price_map.get(sym, avg_ep)
        tot_val = lp * tot_qty
        tot_pnl = tot_val - tot_cost
        tot_pct = (tot_pnl / tot_cost * 100.0) if tot_cost > 0 else 0.0

        # Weighted average SL & TP across lots that have them
        sl_rows = grp[grp["stop_loss"].notna() & (grp["stop_loss"] > 0)]
        avg_sl = (
            float((sl_rows["stop_loss"] * sl_rows["quantity"]).sum() / sl_rows["quantity"].sum())
            if not sl_rows.empty
            else None
        )
        tp_rows = grp[grp["take_profit"].notna() & (grp["take_profit"] > 0)]
        avg_tp = (
            float((tp_rows["take_profit"] * tp_rows["quantity"]).sum() / tp_rows["quantity"].sum())
            if not tp_rows.empty
            else None
        )

        # Earliest entry date
        dt_series = pd.to_datetime(grp["entry_date"], errors="coerce").dropna()
        earliest_dt = dt_series.min() if not dt_series.empty else grp.iloc[0]["entry_date"]

        plan_all_ok = all(str(x or "Yes") == "Yes" for x in grp["according_to_plan"])
        grouped_list.append(
            {
                "is_grouped": len(grp) > 1,
                "lot_count": len(grp),
                "trade_id": int(grp.iloc[0]["id"]),
                "symbol": sym,
                "company_name": str(grp.iloc[0].get("company_name") or sym),
                "entry_date": earliest_dt,
                "quantity": tot_qty,
                "entry_price": avg_ep,
                "live_price": lp,
                "pos_val": tot_val,
                "cost_val": tot_cost,
                "pnl_usd": tot_pnl,
                "pnl_pct": tot_pct,
                "stop_loss": avg_sl,
                "take_profit": avg_tp,
                "according_to_plan": "Yes" if plan_all_ok else "No",
            }
        )
    return grouped_list


def _build_averaged_closed_rows(closed_df: pd.DataFrame) -> list[dict]:
    """Consolidates closed trades by ticker: averages prices on winners, sums P&L on losers."""
    if closed_df.empty:
        return []
    df = closed_df.copy()
    df["clean_sym"] = df["symbol"].astype(str).str.split(":").str[-1].str.strip().str.upper()

    grouped_list: list[dict] = []
    for sym, grp in df.groupby("clean_sym", sort=False):
        tot_qty = float(grp["quantity"].sum())
        tot_cost = float((grp["entry_price"] * grp["quantity"]).sum())
        avg_ep = (tot_cost / tot_qty) if tot_qty > 0 else float(grp.iloc[0]["entry_price"])

        exit_prices = []
        for _, r in grp.iterrows():
            cp_raw = r.get("close_price") if pd.notna(r.get("close_price")) else r.get("exit_price")
            exit_prices.append(float(cp_raw) if cp_raw is not None and pd.notna(cp_raw) else float(r["entry_price"]))
        grp = grp.assign(_eff_exit=exit_prices)
        tot_exit_val = float((grp["_eff_exit"] * grp["quantity"]).sum())
        avg_cp = (tot_exit_val / tot_qty) if tot_qty > 0 else avg_ep

        gross_sum = float(
            sum(
                float(r["gross_pnl"]) if pd.notna(r.get("gross_pnl")) else (r["_eff_exit"] - float(r["entry_price"])) * float(r["quantity"])
                for _, r in grp.iterrows()
            )
        )
        tax_sum = float(grp["tax_paid"].fillna(0).sum()) if "tax_paid" in grp.columns else 0.0
        fee_sum = float(grp["fees"].fillna(0).sum()) if "fees" in grp.columns else 0.0
        net_sum = float(
            sum(
                float(r["net_pnl"]) if pd.notna(r.get("net_pnl")) else (r["_eff_exit"] - float(r["entry_price"])) * float(r["quantity"])
                for _, r in grp.iterrows()
            )
        )
        ret_pct = (net_sum / tot_cost * 100.0) if tot_cost > 0 else 0.0

        dt_e = pd.to_datetime(grp["entry_date"], errors="coerce").dropna()
        dt_c = pd.to_datetime(grp["close_date"], errors="coerce").dropna() if "close_date" in grp.columns else pd.Series(dtype="datetime64[ns]")
        min_e = dt_e.min() if not dt_e.empty else grp.iloc[0]["entry_date"]
        max_c = dt_c.max() if not dt_c.empty else grp.iloc[0].get("close_date")

        setups = [str(x).strip() for x in grp["setup_pattern"].dropna() if str(x).strip()]
        setup_lbl = setups[0] if setups else "ללא Setup"
        plan_all_ok = all(str(x or "Yes") == "Yes" for x in grp["according_to_plan"])

        grouped_list.append(
            {
                "is_grouped": len(grp) > 1,
                "lot_count": len(grp),
                "trade_id": int(grp.iloc[0]["id"]),
                "symbol": sym,
                "company_name": str(grp.iloc[0].get("company_name") or sym),
                "entry_date": min_e,
                "close_date": max_c,
                "quantity": tot_qty,
                "entry_price": avg_ep,
                "close_price": avg_cp,
                "net_pnl": net_sum,
                "gross_pnl": gross_sum,
                "tax_paid": tax_sum,
                "fees": fee_sum,
                "ret_pct": ret_pct,
                "setup_pattern": setup_lbl,
                "according_to_plan": "Yes" if plan_all_ok else "No",
            }
        )
    return grouped_list


# === [SEC-07: MAIN POSITIONS & TRADE JOURNAL PAGE RENDERER] ===
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

    # === TOP ACTION BAR ===
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

    # === 4 TOP SUMMARY CARDS ===
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

    # === UNIFIED FILTER & SEARCH BAR (WITH 'מיצוע' IN STATUS SECTION) ===
    with st.container():
        _html('<div class="jp-filter-marker" style="display:none;"></div>')
        f_search, f_status, f_outcome, f_plan = st.columns([1.35, 1.55, 1.05, 1.05])
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
                ["הכל", "פתוחות בלבד", "סגורות בלבד", "מיצוע"],
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

    is_averaging_mode = flt_status == "מיצוע"

    def _matches_item(sym: str, comp: str, val_pnl: float, plan_flag: str) -> bool:
        if q_search:
            if q_search not in sym.upper() and q_search not in comp.upper():
                return False
        if flt_outcome == "רווחיות" and val_pnl <= 0:
            return False
        if flt_outcome == "מפסידות" and val_pnl >= 0:
            return False
        if flt_plan == "לפי תוכנית" and plan_flag != "Yes":
            return False
        if flt_plan == "חריגה" and plan_flag == "Yes":
            return False
        return True

    # === ACTIVE POSITIONS TABLE ===
    if flt_status in ("הכל", "פתוחות בלבד", "מיצוע"):
        if is_averaging_mode:
            raw_open_items = _build_averaged_open_rows(open_df, price_map)
        else:
            raw_open_items = []
            for _, r in open_df.iterrows():
                s_up = str(r["symbol"]).split(":")[-1].strip().upper()
                ep = float(r["entry_price"])
                q = float(r["quantity"])
                lp = price_map.get(s_up, ep)
                u_pnl = (lp - ep) * q
                u_pct = ((lp - ep) / ep * 100.0) if ep > 0 else 0.0
                raw_open_items.append(
                    {
                        "is_grouped": False,
                        "lot_count": 1,
                        "trade_id": int(r["id"]),
                        "symbol": s_up,
                        "company_name": str(r.get("company_name") or s_up),
                        "entry_date": r.get("entry_date"),
                        "quantity": q,
                        "entry_price": ep,
                        "live_price": lp,
                        "pos_val": lp * q,
                        "cost_val": ep * q,
                        "pnl_usd": u_pnl,
                        "pnl_pct": u_pct,
                        "stop_loss": float(r["stop_loss"]) if pd.notna(r.get("stop_loss")) and float(r["stop_loss"]) > 0 else None,
                        "take_profit": float(r["take_profit"]) if pd.notna(r.get("take_profit")) and float(r["take_profit"]) > 0 else None,
                        "according_to_plan": str(r.get("according_to_plan") or "Yes"),
                    }
                )

        filtered_open = [
            it
            for it in raw_open_items
            if _matches_item(it["symbol"], it["company_name"], it["pnl_usd"], it["according_to_plan"])
        ]

        sum_open_filtered = sum(it["pnl_usd"] for it in filtered_open)
        sum_open_col = "#10B981" if sum_open_filtered >= 0 else "#EF4444"
        avg_hdr_extra = (
            f'<span style="background:rgba(167,139,250,0.14); border:1px solid rgba(167,139,250,0.38); '
            f'color:#C4B5FD; border-radius:999px; padding:2px 11px; font-size:0.76rem; font-weight:800;">'
            f'מצב מיצוע פעיל · סה"כ רווח/הפסד מסוכם: <span style="color:{sum_open_col};" dir="ltr">{_fmt_usd(sum_open_filtered, signed=True)}</span></span>'
            if is_averaging_mode
            else ""
        )

        with st.container():
            _html(
                f"""
                <div class="jp-unified-table-marker" style="display:none;"></div>
                <div class="jp-sec-hdr">
                    <div class="jp-sec-title-wrap">
                        <span style="color:#38BDF8; font-size:0.9rem;">●</span>
                        <span class="jp-sec-title">פוזיציות פתוחות - Active Positions</span>
                        <span class="jp-count-circle">{len(filtered_open)}</span>
                        {avg_hdr_extra}
                    </div>
                    <span class="jp-sec-hint">לחץ על שורת מניה לניהול עסקה, עריכת SL/TP וניתוח עומק</span>
                </div>
                <div class="jp-active-grid jp-tbl-head">
                    <div class="jp-col-r">מניה</div>
                    <div class="jp-col-r">תאריך פתיחה</div>
                    <div class="jp-col-c">כמות</div>
                    <div class="jp-col-r">שער חי</div>
                    <div class="jp-col-r">{'שער כניסה ממוצע' if is_averaging_mode else 'שער כניסה'}</div>
                    <div class="jp-col-r">שווי פוזיציה</div>
                    <div class="jp-col-c">רווח / הפסד צף</div>
                    <div class="jp-col-c">יעדי SL / TP וטווח סיכון-סיכוי</div>
                </div>
                """
            )

            if not filtered_open:
                st.info("אין פוזיציות פתוחות התואמות לסינון הנוכחי.")
            else:
                for idx_row, it in enumerate(filtered_open):
                    tid = it["trade_id"]
                    sym = it["symbol"]
                    m_row = market_by_sym.get(sym)
                    comp = str(it["company_name"] or (m_row.get("company_name") if m_row is not None else sym) or sym)
                    logo = str(m_row.get("logo_url") or "") if m_row is not None and pd.notna(m_row.get("logo_url")) else ""

                    ep = it["entry_price"]
                    qty = it["quantity"]
                    lp = it["live_price"]
                    pos_val = it["pos_val"]
                    cost_val = it["cost_val"]
                    u_pnl = it["pnl_usd"]
                    u_pct = it["pnl_pct"]

                    sltp_cell_html, _ = _build_sltp_html(ep, lp, qty, it["stop_loss"], it["take_profit"], compact=False)

                    logo_box = (
                        f'<img src="{html.escape(logo)}" alt="{html.escape(sym)}"/>'
                        if logo.startswith("http")
                        else html.escape(sym[:4])
                    )
                    pnl_cls = "jp-pnl-win" if u_pnl >= 0 else "jp-pnl-loss"
                    qty_txt = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}"
                    hold_d = _calc_holding_days(it["entry_date"])
                    lot_pill = (
                        f'<span class="jp-avg-badge">מיצוע {it["lot_count"]} מנות</span>'
                        if it["is_grouped"]
                        else ""
                    )

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
                                            {lot_pill}
                                        </div>
                                    </div>
                                    <div class="jp-col-r">
                                        <div class="jp-cell-main">{_ltr(_fmt_date_short(it["entry_date"]))}</div>
                                        <div class="jp-cell-sub">{hold_d} ימים</div>
                                    </div>
                                    <div class="jp-col-c jp-cell-main">{_ltr(qty_txt)}</div>
                                    <div class="jp-col-r jp-cell-main" style="color:#38BDF8;">{_ltr(_fmt_usd(lp))}</div>
                                    <div class="jp-col-r jp-cell-main">{_ltr(_fmt_usd(ep))}</div>
                                    <div class="jp-col-r">
                                        <div class="jp-cell-main">{_ltr(_fmt_usd(pos_val))}</div>
                                        <div class="jp-cell-sub">עלות: {_ltr(_fmt_usd(cost_val))}</div>
                                    </div>
                                    <div class="jp-col-c">
                                        <div class="jp-pnl-box {pnl_cls}">
                                            <span style="font-size:0.9rem; font-weight:800;">{_fmt_usd(u_pnl, signed=True)}</span>
                                            <span style="font-size:0.75rem; font-weight:700;">{u_pct:+.2f}%</span>
                                        </div>
                                    </div>
                                    <div class="jp-col-c">{sltp_cell_html}</div>
                                </div>
                            </div>
                            """
                        )
                        if st.button(" ", key=f"jp_open_row_btn_{sym}_{tid}_{idx_row}", use_container_width=True):
                            if it["is_grouped"]:
                                st.session_state["jp_avg_symbol"] = sym
                            else:
                                st.session_state["jp_selected_trade_id"] = tid
                                st.session_state[f"dd_close_panel_open_{tid}"] = False
                                st.session_state[f"dd_edit_mode_{tid}"] = False
                            st.rerun()

    # === CLOSED TRADES TABLE (SUPPORTS AVERAGING & LOSS SUMMATION) ===
    if flt_status in ("הכל", "סגורות בלבד", "מיצוע"):
        if is_averaging_mode:
            raw_closed_items = _build_averaged_closed_rows(closed_df)
        else:
            raw_closed_items = []
            for _, r in closed_df.iterrows():
                s_up = str(r["symbol"]).split(":")[-1].strip().upper()
                ep = float(r["entry_price"])
                cp_raw = r.get("close_price") if pd.notna(r.get("close_price")) else r.get("exit_price")
                cp = float(cp_raw) if cp_raw is not None and pd.notna(cp_raw) else ep
                q = float(r["quantity"])
                net_p = float(r["net_pnl"]) if pd.notna(r.get("net_pnl")) else (cp - ep) * q
                gross_p = float(r["gross_pnl"]) if pd.notna(r.get("gross_pnl")) else (cp - ep) * q
                tax_p = float(r["tax_paid"]) if pd.notna(r.get("tax_paid")) else 0.0
                fee_p = float(r["fees"]) if pd.notna(r.get("fees")) else 0.0
                ret_pct = ((cp - ep) / ep * 100.0) if ep > 0 else 0.0
                raw_closed_items.append(
                    {
                        "is_grouped": False,
                        "lot_count": 1,
                        "trade_id": int(r["id"]),
                        "symbol": s_up,
                        "company_name": str(r.get("company_name") or s_up),
                        "entry_date": r.get("entry_date"),
                        "close_date": r.get("close_date"),
                        "quantity": q,
                        "entry_price": ep,
                        "close_price": cp,
                        "net_pnl": net_p,
                        "gross_pnl": gross_p,
                        "tax_paid": tax_p,
                        "fees": fee_p,
                        "ret_pct": ret_pct,
                        "setup_pattern": str(r.get("setup_pattern") or "").strip() or "ללא Setup",
                        "according_to_plan": str(r.get("according_to_plan") or "Yes"),
                    }
                )

        filtered_closed = [
            it
            for it in raw_closed_items
            if _matches_item(it["symbol"], it["company_name"], it["net_pnl"], it["according_to_plan"])
        ]

        sum_closed_filtered = sum(it["net_pnl"] for it in filtered_closed)
        sum_cl_col = "#10B981" if sum_closed_filtered >= 0 else "#EF4444"
        closed_sum_badge = (
            f'<span style="background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.32); '
            f'color:#CBD5E1; border-radius:999px; padding:2px 11px; font-size:0.76rem; font-weight:800;">'
            f'סה"כ רווח / הפסד מסוכם: <span style="color:{sum_cl_col};" dir="ltr">{_fmt_usd(sum_closed_filtered, signed=True)}</span></span>'
            if (is_averaging_mode or flt_outcome != "הכל")
            else ""
        )

        with st.container():
            _html(
                f"""
                <div class="jp-unified-table-marker" style="display:none;"></div>
                <div class="jp-sec-hdr">
                    <div class="jp-sec-title-wrap">
                        <span style="color:#10B981; font-size:0.9rem;">●</span>
                        <span class="jp-sec-title">יומן עסקאות סגורות - Closed Trade Log</span>
                        <span class="jp-count-circle" style="color:#10B981; border-color:rgba(16,185,129,0.35); background:rgba(16,185,129,0.12);">{len(filtered_closed)}</span>
                        {closed_sum_badge}
                    </div>
                    <span class="jp-sec-hint">לחץ על שורת עסקה לצפייה בצילום המצב הטכני ועריכת מסקנות</span>
                </div>
                <div class="jp-closed-grid jp-tbl-head">
                    <div class="jp-col-r">מניה</div>
                    <div class="jp-col-r">תאריכים ומשך החזקה</div>
                    <div class="jp-col-r">כמות ושערי ביצוע</div>
                    <div class="jp-col-c">רווח / הפסד נטו</div>
                    <div class="jp-col-r">גולמי · מס ועמלות</div>
                    <div class="jp-col-r">Setup ומשמעת</div>
                </div>
                """
            )

            if not filtered_closed:
                st.info("אין עסקאות סגורות התואמות לסינון הנוכחי.")
            else:
                for idx_c, it in enumerate(filtered_closed):
                    tid = it["trade_id"]
                    sym = it["symbol"]
                    m_row = market_by_sym.get(sym)
                    comp = str(it["company_name"] or (m_row.get("company_name") if m_row is not None else sym) or sym)
                    logo = str(m_row.get("logo_url") or "") if m_row is not None and pd.notna(m_row.get("logo_url")) else ""

                    ep = it["entry_price"]
                    cp = it["close_price"]
                    qty = it["quantity"]
                    qty_txt = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}"

                    net_p = it["net_pnl"]
                    gross_p = it["gross_pnl"]
                    tax_p = it["tax_paid"]
                    fee_p = it["fees"]
                    ret_pct = it["ret_pct"]

                    hold_d = _calc_holding_days(it["entry_date"], it["close_date"])
                    dt_range = f"{_fmt_date_short(it['entry_date'])} ← {_fmt_date_short(it['close_date'])}"

                    setup_txt = it["setup_pattern"]
                    plan_ok = it["according_to_plan"] == "Yes"
                    plan_pill = (
                        '<span class="dd-plan-badge-ok" style="font-size:0.72rem; padding:2px 8px;">✓ לפי תוכנית</span>'
                        if plan_ok
                        else '<span class="dd-plan-badge-no" style="font-size:0.72rem; padding:2px 8px;">✗ חריגה</span>'
                    )

                    # In averaging mode: losing trades sum P&L without averaging price; winners show averaged prices
                    is_losing_avg = is_averaging_mode and net_p < 0
                    if is_losing_avg:
                        exec_main = f'<span style="color:#EF4444;">סיכום הפסד ({it["lot_count"]} עסקאות)</span>'
                        exec_sub = f"סה\"כ {qty_txt} מניות נסחרו"
                        lot_pill = (
                            f'<span class="jp-avg-badge" style="color:#FCA5A5; border-color:rgba(239,68,68,0.4); background:rgba(239,68,68,0.12);">'
                            f'סכום {it["lot_count"]} מנות</span>'
                            if it["is_grouped"]
                            else ""
                        )
                    else:
                        exec_main = _ltr(f"{_fmt_usd(ep)} → {_fmt_usd(cp)}")
                        exec_sub = f"{qty_txt} מניות" + (" (ממוצע)" if it["is_grouped"] else "")
                        lot_pill = (
                            f'<span class="jp-avg-badge">מיצוע {it["lot_count"]} מנות</span>'
                            if it["is_grouped"]
                            else ""
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
                                            {lot_pill}
                                        </div>
                                    </div>
                                    <div class="jp-col-r">
                                        <div class="jp-cell-main">{_ltr(dt_range)}</div>
                                        <div class="jp-cell-sub">{hold_d} ימים</div>
                                    </div>
                                    <div class="jp-col-r">
                                        <div class="jp-cell-main">{exec_main}</div>
                                        <div class="jp-cell-sub">{exec_sub}</div>
                                    </div>
                                    <div class="jp-col-c">
                                        <div class="jp-pnl-box {pnl_cls}">
                                            <span style="font-size:0.9rem; font-weight:800;">{_fmt_usd(net_p, signed=True)}</span>
                                            <span style="font-size:0.75rem; font-weight:700;">{ret_pct:+.2f}%</span>
                                        </div>
                                    </div>
                                    <div class="jp-col-r">
                                        <div class="jp-cell-main">גולמי: {_ltr(_fmt_usd(gross_p, signed=True))}</div>
                                        <div class="jp-cell-sub">מס: {_ltr(_fmt_usd(tax_p))} | עמלות: {_ltr(_fmt_usd(fee_p))}</div>
                                    </div>
                                    <div class="jp-col-r">
                                        <div style="font-size:0.8rem; font-weight:700; color:#CBD5E1; margin-bottom:4px;">{html.escape(setup_txt)}</div>
                                        {plan_pill}
                                    </div>
                                </div>
                            </div>
                            """
                        )
                        if st.button(" ", key=f"jp_closed_row_btn_{sym}_{tid}_{idx_c}", use_container_width=True):
                            st.session_state["jp_selected_trade_id"] = tid
                            st.session_state[f"dd_edit_mode_{tid}"] = False
                            st.rerun()

    # === OPEN AVERAGED LOT-BREAKDOWN MODAL IF AN AVERAGED MULTI-LOT ROW WAS CLICKED ===
    avg_sym = st.session_state.get("jp_avg_symbol")
    if avg_sym and not open_df.empty:
        sym_lots = open_df[
            open_df["symbol"].astype(str).str.split(":").str[-1].str.strip().str.upper() == avg_sym
        ]
        if len(sym_lots) > 1:
            m_row = market_by_sym.get(avg_sym)
            lp_avg = price_map.get(avg_sym, float(sym_lots.iloc[0]["entry_price"]))
            open_averaged_lots_modal(avg_sym, sym_lots, m_row, lp_avg)
        else:
            st.session_state["jp_avg_symbol"] = None

    # === OPEN DEEP DIVE MODAL IF A TRADE ROW WAS CLICKED ===
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
