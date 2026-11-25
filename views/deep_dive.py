# === [SEC-01: IMPORTS & HTML RENDER HELPERS] ===
import html
import math
from datetime import datetime, date, timezone
import pandas as pd
import streamlit as st
from db import (
    load_market_dataframe,
    save_manual_levels,
    refresh_live_prices_tv,
    sync_setup_pattern,
    get_supabase_client,
    clear_market_cache,
)
from journal_helpers import (
    SETUP_OPTIONS,
    CANDLE_OPTIONS,
    TRENDLINE_OPTIONS,
    GAPS_OPTIONS,
    FIBONACCI_OPTIONS,
    compute_live_entry_indicators,
    insert_trade,
)
from ui_theme import render_logo_html, format_pct_color

APP_FONT = "'Assistant', 'Rubik', -apple-system, BlinkMacSystemFont, sans-serif"


def _html(raw: str) -> None:
    """Renders multi-line HTML cleanly without Markdown code-block indentation issues."""
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _safe_float(val, default: float | None = None) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        if pd.isna(val):
            return default
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _fmt_vol(val) -> str:
    v = _safe_float(val)
    if v is None:
        return "--"
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{int(v):,}"


# === [SEC-02: SCOPED OBSIDIAN DEEP DARK CSS (1-TO-1 HTML DESIGN)] ===
def _inject_deep_dive_css() -> None:
    _html(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Rubik:wght@400;500;700;800&display=swap');

        .dd-card, .dd-card *, .dd-split-row, .dd-split-row * {{
            font-family: {APP_FONT} !important;
        }}

        /* Prominent Primary Action Button ("פתח עסקה ביומן") */
        div[data-testid="stButton"] button[kind="primary"] {{
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
            border: 1px solid #3B82F6 !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
        }}
        div[data-testid="stButton"] button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
            border-color: #60A5FA !important;
        }}

        /* Main Section Card */
        .dd-card {{
            background: #111622;
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 18px 20px;
            margin-bottom: 16px;
            direction: rtl;
            text-align: right;
        }}
        .dd-hdr {{
            font-size: 1.06rem;
            font-weight: 800;
            color: #F8FAFC;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #1E2638;
            padding-bottom: 10px;
        }}
        .dd-hdr-en {{
            font-size: 0.78rem;
            font-weight: 700;
            color: #64748B;
            letter-spacing: 0.5px;
            direction: ltr;
        }}
        .dd-sub-lbl {{
            font-size: 0.84rem;
            font-weight: 700;
            color: #94A3B8;
            margin: 12px 0 8px 0;
        }}

        /* Responsive Grids */
        .dd-g5 {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 10px;
        }}
        .dd-g4 {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
        }}
        .dd-g3 {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
        }}
        .dd-g2 {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
        }}
        .dd-split-row {{
            display: grid;
            grid-template-columns: 1.12fr 1fr;
            gap: 16px;
            margin-bottom: 16px;
            direction: rtl;
        }}
        .dd-split-row .dd-card {{
            margin-bottom: 0;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        @media (max-width: 1024px) {{
            .dd-split-row {{
                grid-template-columns: 1fr;
            }}
            .dd-g5 {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
            .dd-g4, .dd-g3 {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}
        @media (max-width: 640px) {{
            .dd-g2, .dd-g3, .dd-g4, .dd-g5 {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Inner Tiles */
        .dd-tile {{
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 12px 10px;
            text-align: center;
            transition: border-color 0.15s ease;
        }}
        .dd-tile:hover {{
            border-color: #2B3954;
        }}
        .dd-tile-green {{
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 12px;
            padding: 12px 10px;
            text-align: center;
        }}
        .dd-tile-red {{
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.35);
            border-radius: 12px;
            padding: 12px 10px;
            text-align: center;
        }}
        .dd-tlbl {{
            font-size: 0.82rem;
            font-weight: 600;
            color: #94A3B8;
            margin-bottom: 5px;
        }}
        .dd-tval {{
            font-size: 1.24rem;
            font-weight: 800;
            line-height: 1.25;
            direction: ltr;
            unicode-bidi: isolate;
            display: inline-block;
        }}
        .dd-tsub {{
            font-size: 0.76rem;
            color: #64748B;
            margin-top: 4px;
        }}

        /* Visual SL -> Entry -> TP Range Track */
        .dd-rr-box {{
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 12px 14px;
            margin-top: 12px;
            direction: ltr;
        }}
        .dd-rr-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.84rem;
            font-weight: 800;
            margin-bottom: 8px;
        }}
        .dd-rr-pill {{
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid rgba(16, 185, 129, 0.42);
            color: #34D399;
            padding: 2px 12px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 800;
        }}
        .dd-rr-track {{
            position: relative;
            width: 100%;
            height: 7px;
            border-radius: 999px;
            background: linear-gradient(90deg, #EF4444 0%, #F59E0B 35%, #10B981 100%);
            margin: 8px 0;
        }}
        .dd-rr-dot {{
            position: absolute;
            top: 50%;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #F8FAFC;
            border: 3px solid #38BDF8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.95);
            transform: translate(-50%, -50%);
        }}
        .dd-rr-bot {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.78rem;
            font-weight: 700;
            color: #94A3B8;
            margin-top: 6px;
        }}

        /* Technical Tag Box (2x2) */
        .dd-tag-box {{
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 12px 14px;
            text-align: right;
            direction: rtl;
        }}
        .dd-tag-lbl {{
            font-size: 0.78rem;
            font-weight: 600;
            color: #64748B;
            margin-bottom: 4px;
        }}
        .dd-tag-val {{
            font-size: 0.94rem;
            font-weight: 800;
            color: #F8FAFC;
        }}

        /* Journal Notes Box (3-col) */
        .dd-note-box {{
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 14px 16px;
            text-align: right;
            direction: rtl;
            min-height: 108px;
        }}
        .dd-note-title {{
            font-size: 0.88rem;
            font-weight: 800;
            color: #F8FAFC;
            margin-bottom: 6px;
        }}
        .dd-note-body {{
            font-size: 0.86rem;
            color: #CBD5E1;
            line-height: 1.55;
            white-space: pre-wrap;
        }}

        /* S/R Pills */
        .dd-pill-res {{
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.45);
            color: #FCA5A5;
            font-size: 0.95rem;
            font-weight: 800;
            padding: 6px 14px;
            border-radius: 8px;
            direction: ltr;
            unicode-bidi: isolate;
        }}
        .dd-pill-sup {{
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.45);
            color: #6EE7B7;
            font-size: 0.95rem;
            font-weight: 800;
            padding: 6px 14px;
            border-radius: 8px;
            direction: ltr;
            unicode-bidi: isolate;
        }}
        .dd-pill-man {{
            background: rgba(37, 99, 235, 0.15);
            border: 1px solid rgba(37, 99, 235, 0.45);
            color: #93C5FD;
            font-size: 0.9rem;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 8px;
        }}
        </style>
        """
    )


# === [SEC-03: LIVE INDICATOR CACHE & PRE-TRADE PLAN PERSISTENCE] ===
@st.cache_data(ttl=900, show_spinner=False)
def _get_cached_live_indicators(symbol: str) -> dict:
    """Fetches & caches live MACD, CCI(20), Volume Trend, and RSI(14) for the selected ticker."""
    return compute_live_entry_indicators(symbol)


def _default_plan_for_row(row: pd.Series) -> dict:
    price = _safe_float(row.get("display_price"), 100.0) or 100.0
    atr = _safe_float(row.get("atr_14"))
    ds1 = _safe_float(row.get("d_s_1"))
    dr1 = _safe_float(row.get("d_r_1"))

    if ds1 is not None and 0 < ds1 < price:
        default_sl = round(ds1, 2)
    elif atr is not None and atr > 0:
        default_sl = round(max(0.01, price - 1.5 * atr), 2)
    else:
        default_sl = round(price * 0.95, 2)

    risk = max(0.01, price - default_sl)
    if dr1 is not None and dr1 > price + risk:
        default_tp = round(dr1, 2)
    else:
        default_tp = round(price + (3.0 * risk), 2)

    return {
        "entry_price": round(price, 2),
        "stop_loss": default_sl,
        "take_profit": default_tp,
        "risk_budget": 250.0,
        "candle_pattern": CANDLE_OPTIONS[0],
        "trendline_status": TRENDLINE_OPTIONS[0],
        "gap_status": GAPS_OPTIONS[0],
        "fibonacci_level": FIBONACCI_OPTIONS[0],
        "entry_rationale": "",
        "exit_plan": "",
        "watchlist_notes": "",
    }


def _load_pre_trade_plan(symbol: str, row: pd.Series) -> dict:
    state_key = f"dd_plan_{symbol}"
    defaults = _default_plan_for_row(row)

    if state_key in st.session_state and isinstance(st.session_state[state_key], dict):
        merged = {**defaults, **st.session_state[state_key]}
        return merged

    db_plan = row.get("pre_trade_plan") if "pre_trade_plan" in row.index else None
    if isinstance(db_plan, dict):
        merged = {**defaults, **db_plan}
        st.session_state[state_key] = merged
        return merged

    st.session_state[state_key] = defaults
    return defaults


def _save_pre_trade_plan(symbol: str, plan: dict) -> None:
    st.session_state[f"dd_plan_{symbol}"] = plan
    try:
        sb = get_supabase_client()
        sb.table("company_profiles").update({"pre_trade_plan": plan}).eq("symbol", symbol).execute()
        clear_market_cache()
    except Exception:
        # Fallback gracefully if optional pre_trade_plan JSONB column has not been added yet
        pass


# === [SEC-04: ONE-CLICK "OPEN TRADE IN JOURNAL" MODAL] ===
@st.dialog("פתיחת עסקה חדשה ביומן המסחר", width="large")
def _dialog_open_trade_from_deep_dive(
    row: pd.Series,
    plan: dict,
    curr_setup: str,
    live_ind: dict,
) -> None:
    sym = str(row["symbol"]).upper()
    comp_name = str(row.get("company_name") or sym)
    live_p = _safe_float(row.get("display_price"), plan["entry_price"]) or plan["entry_price"]

    default_ep = float(_safe_float(plan.get("entry_price"), live_p) or live_p)
    default_sl = float(_safe_float(plan.get("stop_loss"), round(default_ep * 0.95, 2)) or 0.0)
    default_tp = float(_safe_float(plan.get("take_profit"), round(default_ep * 1.15, 2)) or 0.0)
    risk_budget = float(_safe_float(plan.get("risk_budget"), 250.0) or 250.0)

    risk_per_share = default_ep - default_sl
    if risk_per_share > 0 and risk_budget > 0:
        rec_qty = max(1.0, float(math.floor(risk_budget / risk_per_share)))
    else:
        rec_qty = 10.0

    _html(
        f"""
        <div style="background:#0D111A; border:1px solid #1E2638; border-radius:12px; padding:10px 14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; direction:rtl;">
            <div>
                <span style="font-weight:800; color:#F8FAFC; font-size:1.05rem;">{html.escape(comp_name)}</span>
                <span style="color:#38BDF8; font-weight:800; margin-right:8px; direction:ltr; unicode-bidi:isolate;">({html.escape(sym)})</span>
            </div>
            <span style="color:#94A3B8; font-size:0.84rem;">מחיר נוכחי: <strong style="color:#F8FAFC; direction:ltr;">${live_p:,.2f}</strong></span>
        </div>
        """
    )

    c1, c2, c3 = st.columns([1.4, 1.1, 1.1])
    with c1:
        setup_idx = SETUP_OPTIONS.index(curr_setup) if curr_setup in SETUP_OPTIONS else 0
        chosen_setup = st.selectbox("תבנית טכנית (Setup)", options=SETUP_OPTIONS, index=setup_idx, key=f"dd_dlg_setup_{sym}")
    with c2:
        entry_dt = st.date_input("תאריך כניסה", value=date.today(), key=f"dd_dlg_dt_{sym}")
    with c3:
        fees_val = st.number_input("עמלת קנייה ($)", min_value=0.0, value=0.0, step=0.5, key=f"dd_dlg_fees_{sym}")

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        ep_in = st.number_input("שער כניסה ($)", min_value=0.01, value=round(default_ep, 2), step=0.1, key=f"dd_dlg_ep_{sym}")
    with p2:
        qty_in = st.number_input("כמות מניות", min_value=0.0001, value=rec_qty, step=1.0, key=f"dd_dlg_qty_{sym}")
    with p3:
        sl_in = st.number_input("Stop Loss ($)", min_value=0.0, value=round(default_sl, 2), step=0.1, key=f"dd_dlg_sl_{sym}")
    with p4:
        tp_in = st.number_input("Take Profit ($)", min_value=0.0, value=round(default_tp, 2), step=0.1, key=f"dd_dlg_tp_{sym}")

    invested_usd = round(ep_in * qty_in, 2)
    risk_unit = ep_in - sl_in
    reward_unit = tp_in - ep_in
    rr_txt = f"1:{(reward_unit / risk_unit):.2f}" if (sl_in > 0 and tp_in > 0 and risk_unit > 0 and reward_unit > 0) else "--"
    total_risk_usd = round(max(0.0, risk_unit) * qty_in, 2) if sl_in > 0 else 0.0

    _html(
        f"""
        <div style="background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:10px 14px; margin:8px 0 12px 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; direction:rtl;">
            <span>סכום השקעה: <strong style="color:#F8FAFC; direction:ltr; unicode-bidi:isolate;">${invested_usd:,.2f}</strong></span>
            <span>סיכון כספי לסטופ: <strong style="color:#F87171; direction:ltr; unicode-bidi:isolate;">${total_risk_usd:,.2f}</strong></span>
            <span>יחס R:R: <strong style="color:#10B981; direction:ltr; unicode-bidi:isolate;">{rr_txt}</strong></span>
        </div>
        """
    )

    combined_parts = []
    if plan.get("entry_rationale", "").strip():
        combined_parts.append(f"תוכנית כניסה: {plan['entry_rationale'].strip()}")
    if plan.get("exit_plan", "").strip():
        combined_parts.append(f"יעדי יציאה וניהול: {plan['exit_plan'].strip()}")
    if plan.get("watchlist_notes", "").strip():
        combined_parts.append(f"הערות מעקב: {plan['watchlist_notes'].strip()}")
    tags_summary = [
        t for t in (
            plan.get("candle_pattern"),
            plan.get("trendline_status"),
            plan.get("gap_status"),
            plan.get("fibonacci_level"),
        )
        if t and not t.startswith("ללא")
    ]
    if tags_summary:
        combined_parts.append(f"תגיות טכניות: {' | '.join(tags_summary)}")

    notes_in = st.text_area(
        "נימוקי כניסה ותוכנית ניהול (הועברו אוטומטית מניתוח העומק)",
        value="\n".join(combined_parts),
        height=95,
        key=f"dd_dlg_notes_{sym}",
    )

    if st.button("אשר ופתח עסקה ביומן", type="primary", use_container_width=True):
        ds1 = f"${float(row['d_s_1']):,.2f}" if pd.notna(row.get("d_s_1")) else "-"
        dr1 = f"${float(row['d_r_1']):,.2f}" if pd.notna(row.get("d_r_1")) else "-"
        ws1 = f"${float(row['w_s_1']):,.2f}" if pd.notna(row.get("w_s_1")) else "-"
        wr1 = f"${float(row['w_r_1']):,.2f}" if pd.notna(row.get("w_r_1")) else "-"

        payload = {
            "entry_date": entry_dt.isoformat(),
            "symbol": sym,
            "company_name": comp_name,
            "direction": "Long",
            "setup_pattern": None if chosen_setup == "ללא Setup" else chosen_setup,
            "entry_price": round(float(ep_in), 4),
            "quantity": round(float(qty_in), 4),
            "purchase_amount": invested_usd,
            "stop_loss": round(float(sl_in), 2) if sl_in > 0 else None,
            "take_profit": round(float(tp_in), 2) if tp_in > 0 else None,
            "rr_ratio": rr_txt if rr_txt != "--" else None,
            "fees": round(float(fees_val), 2),
            "status": "Open",
            "notes": notes_in.strip() or None,
            "daily_next_sr": f"S: {ds1} | R: {dr1}",
            "weekly_next_sr": f"S: {ws1} | R: {wr1}",
            "ma_20": row.get("ma_20_status"),
            "ma_50": row.get("ma_50_status"),
            "ma_150": row.get("ma_150_status"),
            "ma_200": row.get("ma_200_status"),
            "rsi": _safe_float(row.get("rsi")) or live_ind.get("rsi_live"),
            "macd_status": live_ind.get("macd_status"),
            "cci_value": live_ind.get("cci_value"),
            "cci_status": live_ind.get("cci_status"),
            "volume_trend": live_ind.get("volume_trend"),
            "rel_vol_5d": _safe_float(row.get("rel_vol_5d")),
            "rel_vol_10d": _safe_float(row.get("rel_vol_10d")),
            "rel_vol_15d": _safe_float(row.get("rel_vol_15d")),
            "rel_vol_20d": _safe_float(row.get("rel_vol_20d")),
            "rel_vol_30d": _safe_float(row.get("rel_vol_30d")),
        }
        for prefix in ("d_s", "d_r", "w_s", "w_r"):
            for idx in range(1, 6):
                col = f"{prefix}_{idx}"
                payload[col] = _safe_float(row.get(col))

        insert_trade(payload)
        st.success(f"העסקה ב-{sym} נפתחה ונשמרה ביומן המסחר!")
        st.rerun()


# === [SEC-05: TOP HEADER CARD (IDENTITY, PRICE, SIGNAL & SUMMARY)] ===
def render_top_header_card(row: pd.Series) -> None:
    sym = str(row["symbol"])
    comp_name = html.escape(str(row.get("company_name") or sym))
    exch = html.escape(str(row.get("exchange") or "US"))
    sector = html.escape(str(row.get("sector") or ""))
    industry = html.escape(str(row.get("industry") or ""))
    sub_ind = html.escape(str(row.get("sub_industry") or ""))
    curr_setup = str(row.get("setup_pattern") or "").strip() if pd.notna(row.get("setup_pattern")) else ""
    summary = html.escape(str(row.get("short_summary") or "אין תקציר עסקי זמין למניה זו."))
    logo_html = render_logo_html(sym, row.get("logo_url"), size=54)

    price_val = _safe_float(row.get("display_price"))
    price_str = f"${price_val:,.2f}" if price_val is not None else "--"
    pct_val = _safe_float(row.get("change_today_pct"))
    pct_str, pct_color = format_pct_color(pct_val)

    is_live = pd.notna(row.get("live_price"))
    mode_badge = (
        '<span class="live-pill"><span class="live-dot"></span>LIVE</span>'
        if is_live
        else '<span class="badge-pill badge-slate">EOD</span>'
    )

    setup_badge = (
        f'<span class="badge-pill" style="background:rgba(139,92,246,0.16); border:1px solid rgba(139,92,246,0.45); color:#C4B5FD; direction:ltr; unicode-bidi:isolate;">'
        f'Setup: {html.escape(curr_setup)}</span>'
        if curr_setup and curr_setup != "ללא Setup"
        else ""
    )

    earnings_badge = ""
    if pd.notna(row.get("next_earnings_date")):
        try:
            ed_date = pd.to_datetime(row["next_earnings_date"]).date()
            days_left = (ed_date - datetime.now(timezone.utc).date()).days
            if days_left >= 0:
                earnings_badge = (
                    f'<span class="badge-pill badge-amber">'
                    f'דוחות קרובים: <span style="direction:ltr; unicode-bidi:isolate;">{ed_date}</span> (בעוד {days_left} ימים)'
                    f'</span>'
                )
        except Exception:
            pass

    _html(
        f"""
        <div class="dd-card">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:18px; direction:ltr;">
                <div style="display:flex; align-items:center; gap:14px;">
                    {logo_html}
                    <div>
                        <div style="font-size:1.52rem; font-weight:800; color:#F8FAFC; line-height:1.2;">{comp_name}</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:5px;">
                            <span style="background:#1A2234; border:1px solid #2A354D; color:#F8FAFC; font-weight:800; font-size:0.86rem; padding:2px 10px; border-radius:6px;">{html.escape(sym)}</span>
                            <span style="color:#94A3B8; font-size:0.88rem; font-weight:600;">{exch}</span>
                            {mode_badge}
                        </div>
                    </div>
                </div>

                <div style="display:flex; align-items:center; gap:18px; background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:12px 24px;">
                    <span style="font-size:1.68rem; font-weight:800; color:{pct_color}; direction:ltr; unicode-bidi:isolate;">{pct_str}</span>
                    <span style="width:1px; height:28px; background:#1E2638;"></span>
                    <span style="font-size:1.68rem; font-weight:800; color:#F8FAFC; direction:ltr; unicode-bidi:isolate;">{price_str}</span>
                </div>

                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:10px 16px; min-width:215px; direction:rtl; text-align:right;">
                    <div style="font-size:0.78rem; font-weight:700; color:#64748B; margin-bottom:2px;">סטטוס איתות</div>
                    <div style="font-size:0.98rem; font-weight:800; color:#94A3B8; margin-bottom:4px;">ממתין לאיתות</div>
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#64748B;">
                        <span>ציון משוקלל</span>
                        <span style="font-weight:700; direction:ltr; unicode-bidi:isolate;">-- / 100</span>
                    </div>
                </div>
            </div>

            <div style="background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:13px 16px; margin-top:16px; color:#E2E8F0; font-size:0.96rem; line-height:1.65;">
                {summary}
            </div>

            <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
                {setup_badge}
                {f'<span class="badge-pill badge-slate">סקטור: {sector}</span>' if sector else ''}
                {f'<span class="badge-pill badge-slate">תעשייה: {industry}</span>' if industry else ''}
                {f'<span class="badge-pill badge-blue">תת-תעשייה: {sub_ind}</span>' if sub_ind else ''}
                {earnings_badge}
            </div>
        </div>
        """
    )


# === [SEC-06: INDICATORS & MOMENTUM SNAPSHOT (5-COLUMN GRID)] ===
def render_indicators_snapshot(row: pd.Series, live_ind: dict) -> None:
    rsi_v = _safe_float(row.get("rsi")) or _safe_float(live_ind.get("rsi_live"))
    if rsi_v is not None:
        rsi_str = f"{rsi_v:.1f}"
        if rsi_v >= 70:
            rsi_color, rsi_sub = "#F59E0B", "אזור קניית יתר (>70)"
        elif rsi_v >= 50:
            rsi_color, rsi_sub = "#10B981", "אזור מומנטום חיובי"
        elif rsi_v >= 35:
            rsi_color, rsi_sub = "#60A5FA", "אזור נייטרלי / תיקון"
        else:
            rsi_color, rsi_sub = "#EF4444", "מכירת יתר (<35)"
    else:
        rsi_str, rsi_color, rsi_sub = "--", "#94A3B8", "אין נתון"

    macd_raw = str(live_ind.get("macd_status") or "--")
    if "(" in macd_raw:
        macd_main = macd_raw.split("(")[0].strip()
        macd_sub = macd_raw.split("(")[1].replace(")", "").strip()
    else:
        macd_main, macd_sub = macd_raw, "MACD (12, 26, 9)"
    macd_color = "#10B981" if ("שורי" in macd_main or "שורית" in macd_main) else ("#EF4444" if "דובי" in macd_main else "#38BDF8")

    cci_v = _safe_float(live_ind.get("cci_value"))
    cci_raw = str(live_ind.get("cci_status") or "")
    cci_sub = cci_raw.split("(")[0].strip() if cci_raw else "CCI (20)"
    if cci_v is not None:
        cci_str = f"{cci_v:.1f}"
        cci_color = "#10B981" if cci_v >= 100 else ("#38BDF8" if cci_v >= 0 else ("#EF4444" if cci_v <= -100 else "#CBD5E1"))
    else:
        cci_str, cci_color = "--", "#94A3B8"

    rv5 = _safe_float(row.get("rel_vol_5d"))
    rv20 = _safe_float(row.get("rel_vol_20d"))
    if rv5 is not None or rv20 is not None:
        rv5_s = f"{rv5:.2f}x" if rv5 is not None else "--"
        rv20_s = f"{rv20:.2f}x" if rv20 is not None else "--"
        rv_combo = f"{rv5_s} / {rv20_s}"
        if (rv5 or 0) >= 1.2:
            rv_color, rv_sub = "#38BDF8", "נפח גבוה מהממוצע"
        elif (rv5 or 0) >= 0.9:
            rv_color, rv_sub = "#CBD5E1", "נפח מסחר רגיל"
        else:
            rv_color, rv_sub = "#94A3B8", "נפח שקט מהממוצע"
    else:
        rv_combo, rv_color, rv_sub = "--", "#94A3B8", "אין נתון"

    atr14 = _safe_float(row.get("atr_14"))
    atr_sq = _safe_float(row.get("atr_squeeze_pct"))
    atr_pct = _safe_float(row.get("atr_pct"))
    atr_str = f"${atr14:,.2f}" if atr14 is not None else "--"
    sq_str = f"{atr_sq:.0f}%" if atr_sq is not None else "--"
    atr_sub = f"תנודתיות יומית {atr_pct:.2f}%" if atr_pct is not None else "מדד תנודתיות יומי"

    _html(
        f"""
        <div class="dd-card">
            <div class="dd-hdr">
                <span>• תמונת מצב אינדיקטורים ומומנטום (Technical Snapshot)</span>
                <span class="dd-hdr-en">INDICATORS & MOMENTUM SNAPSHOT</span>
            </div>
            <div class="dd-g5" style="margin-bottom:0;">
                <div class="dd-tile">
                    <div class="dd-tlbl">RSI (14) נוכחי</div>
                    <div class="dd-tval" style="color:{rsi_color};">{rsi_str}</div>
                    <div class="dd-tsub">{html.escape(rsi_sub)}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">MACD Status</div>
                    <div style="font-size:1.05rem; font-weight:800; color:{macd_color}; line-height:1.3;">{html.escape(macd_main)}</div>
                    <div class="dd-tsub">{html.escape(macd_sub)}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">CCI (20)</div>
                    <div class="dd-tval" style="color:{cci_color};">{cci_str}</div>
                    <div class="dd-tsub">{html.escape(cci_sub)}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">Rel Volume (5D / 20D)</div>
                    <div class="dd-tval" style="color:{rv_color};">{rv_combo}</div>
                    <div class="dd-tsub">{html.escape(rv_sub)}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">ATR(14) • Squeeze</div>
                    <div class="dd-tval" style="color:#F8FAFC;">{atr_str} <span style="color:#64748B;">•</span> <span style="color:#F59E0B;">{sq_str}</span></div>
                    <div class="dd-tsub">{html.escape(atr_sub)}</div>
                </div>
            </div>
        </div>
        """
    )


# === [SEC-07: PRE-TRADE R:R PLANNER & TECHNICAL SETUP TAGS (2-COLUMN ROW)] ===
def render_planner_and_tags(row: pd.Series, plan: dict, edit_mode: bool) -> dict:
    sym = str(row["symbol"]).upper()
    live_p = _safe_float(row.get("display_price"), plan["entry_price"]) or plan["entry_price"]
    curr_setup = str(row.get("setup_pattern") or "").strip() if pd.notna(row.get("setup_pattern")) else "ללא Setup"

    ep = float(_safe_float(plan.get("entry_price"), live_p) or live_p)
    sl = float(_safe_float(plan.get("stop_loss"), round(ep * 0.95, 2)) or 0.0)
    tp = float(_safe_float(plan.get("take_profit"), round(ep * 1.15, 2)) or 0.0)
    rb = float(_safe_float(plan.get("risk_budget"), 250.0) or 250.0)

    risk_usd = ep - sl
    reward_usd = tp - ep
    if sl > 0 and tp > 0 and risk_usd > 0 and reward_usd > 0:
        rr_val = reward_usd / risk_usd
        rr_badge = f"R:R 1 : {rr_val:.2f}"
        sl_pct = ((sl - ep) / ep) * 100.0
        tp_pct = ((tp - ep) / ep) * 100.0
        sl_dist_txt = f"{sl_pct:.2f}% (-${abs(risk_usd):,.2f})"
        tp_dist_txt = f"+{tp_pct:.2f}% (+${abs(reward_usd):,.2f})"
        dot_pct = max(4.0, min(96.0, ((ep - sl) / (tp - sl)) * 100.0))
        rec_shares = max(1, int(math.floor(rb / risk_usd)))
        pos_cost = rec_shares * ep
        sizing_line = f"גודל פוזיציה מומלץ לסיכון ${rb:,.0f}: <strong>{rec_shares:,}</strong> מניות (<span style='direction:ltr; unicode-bidi:isolate;'>${pos_cost:,.2f}</span>)"
    else:
        rr_badge = "R:R --"
        sl_dist_txt = "--"
        tp_dist_txt = "--"
        dot_pct = 25.0
        sizing_line = "הזן Stop Loss מתחת לשער הכניסה ו-Take Profit מעליו לחישוב גודל פוזיציה"

    setup_pill_html = (
        f'<span class="badge-pill" style="background:rgba(139,92,246,0.16); border:1px solid rgba(139,92,246,0.45); color:#C4B5FD; direction:ltr; unicode-bidi:isolate;">'
        f'Setup: {html.escape(curr_setup)}</span>'
        if curr_setup and curr_setup != "ללא Setup"
        else '<span class="badge-pill badge-slate">ללא Setup</span>'
    )

    c_pat = html.escape(str(plan.get("candle_pattern") or CANDLE_OPTIONS[0]))
    t_sta = html.escape(str(plan.get("trendline_status") or TRENDLINE_OPTIONS[0]))
    g_sta = html.escape(str(plan.get("gap_status") or GAPS_OPTIONS[0]))
    f_lvl = html.escape(str(plan.get("fibonacci_level") or FIBONACCI_OPTIONS[0]))

    _html(
        f"""
        <div class="dd-split-row">
            <!-- Right Card: Pre-Trade R:R Planner -->
            <div class="dd-card">
                <div>
                    <div class="dd-hdr">
                        <span>תכנון עסקה, ניהול סיכונים ויעדי SL / TP</span>
                        <span class="dd-hdr-en">PRE-TRADE R:R PLANNER</span>
                    </div>
                    <div class="dd-g4">
                        <div class="dd-tile">
                            <div class="dd-tlbl">שער כניסה מתוכנן ($)</div>
                            <div class="dd-tval" style="color:#F8FAFC;">{ep:,.2f}</div>
                        </div>
                        <div class="dd-tile">
                            <div class="dd-tlbl">Stop Loss ($)</div>
                            <div class="dd-tval" style="color:#F87171;">{sl:,.2f}</div>
                        </div>
                        <div class="dd-tile">
                            <div class="dd-tlbl">Take Profit ($)</div>
                            <div class="dd-tval" style="color:#34D399;">{tp:,.2f}</div>
                        </div>
                        <div class="dd-tile">
                            <div class="dd-tlbl">תקציב סיכון לעסקה ($)</div>
                            <div class="dd-tval" style="color:#F8FAFC;">{rb:,.0f}</div>
                        </div>
                    </div>
                </div>

                <div>
                    <div class="dd-rr-box">
                        <div class="dd-rr-top">
                            <span style="color:#EF4444;">SL ${sl:,.2f}</span>
                            <span class="dd-rr-pill">{rr_badge}</span>
                            <span style="color:#10B981;">TP ${tp:,.2f}</span>
                        </div>
                        <div class="dd-rr-track">
                            <div class="dd-rr-dot" style="left:{dot_pct:.1f}%;"></div>
                        </div>
                        <div class="dd-rr-bot">
                            <span>{sl_dist_txt}</span>
                            <span style="color:#38BDF8;">Live: ${live_p:,.2f}</span>
                            <span>{tp_dist_txt}</span>
                        </div>
                    </div>
                    <div style="font-size:0.8rem; color:#94A3B8; margin-top:8px; text-align:right;">{sizing_line}</div>
                </div>
            </div>

            <!-- Left Card: Technical Setup Tags -->
            <div class="dd-card">
                <div>
                    <div class="dd-hdr">
                        <span>תגיות תצורה טכנית (Technical Setup Tags)</span>
                        {setup_pill_html}
                    </div>
                    <div class="dd-g2">
                        <div class="dd-tag-box">
                            <div class="dd-tag-lbl">תבנית נרות (Candlestick)</div>
                            <div class="dd-tag-val">{c_pat}</div>
                        </div>
                        <div class="dd-tag-box">
                            <div class="dd-tag-lbl">קו מגמה (Trendline)</div>
                            <div class="dd-tag-val">{t_sta}</div>
                        </div>
                        <div class="dd-tag-box">
                            <div class="dd-tag-lbl">גאפ (Gap Status)</div>
                            <div class="dd-tag-val" style="color:#38BDF8;">{g_sta}</div>
                        </div>
                        <div class="dd-tag-box">
                            <div class="dd-tag-lbl">רמת פיבונאצ'י (Fibonacci)</div>
                            <div class="dd-tag-val" style="color:#10B981;">{f_lvl}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    if edit_mode:
        with st.container(border=True):
            st.markdown("**עריכת יעדי R:R ותגיות תצורה טכנית**")
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                new_ep = st.number_input("שער כניסה ($)", min_value=0.01, value=ep, step=0.1, key=f"ed_ep_{sym}")
            with e2:
                new_sl = st.number_input("Stop Loss ($)", min_value=0.01, value=sl, step=0.1, key=f"ed_sl_{sym}")
            with e3:
                new_tp = st.number_input("Take Profit ($)", min_value=0.01, value=tp, step=0.1, key=f"ed_tp_{sym}")
            with e4:
                new_rb = st.number_input("תקציב סיכון ($)", min_value=10.0, value=rb, step=25.0, key=f"ed_rb_{sym}")

            t1, t2, t3, t4 = st.columns(4)
            with t1:
                c_idx = CANDLE_OPTIONS.index(plan["candle_pattern"]) if plan.get("candle_pattern") in CANDLE_OPTIONS else 0
                new_candle = st.selectbox("תבנית נרות", options=CANDLE_OPTIONS, index=c_idx, key=f"ed_cndl_{sym}")
            with t2:
                tr_idx = TRENDLINE_OPTIONS.index(plan["trendline_status"]) if plan.get("trendline_status") in TRENDLINE_OPTIONS else 0
                new_trend = st.selectbox("קו מגמה", options=TRENDLINE_OPTIONS, index=tr_idx, key=f"ed_trnd_{sym}")
            with t3:
                g_idx = GAPS_OPTIONS.index(plan["gap_status"]) if plan.get("gap_status") in GAPS_OPTIONS else 0
                new_gap = st.selectbox("גאפ", options=GAPS_OPTIONS, index=g_idx, key=f"ed_gap_{sym}")
            with t4:
                f_idx = FIBONACCI_OPTIONS.index(plan["fibonacci_level"]) if plan.get("fibonacci_level") in FIBONACCI_OPTIONS else 0
                new_fib = st.selectbox("פיבונאצ'י", options=FIBONACCI_OPTIONS, index=f_idx, key=f"ed_fib_{sym}")

            if st.button("שמור יעדים ותגיות טכניות", type="primary", key=f"save_plan_top_{sym}"):
                updated_plan = {
                    **plan,
                    "entry_price": round(float(new_ep), 2),
                    "stop_loss": round(float(new_sl), 2),
                    "take_profit": round(float(new_tp), 2),
                    "risk_budget": round(float(new_rb), 2),
                    "candle_pattern": new_candle,
                    "trendline_status": new_trend,
                    "gap_status": new_gap,
                    "fibonacci_level": new_fib,
                }
                _save_pre_trade_plan(sym, updated_plan)
                st.toast("נתוני התכנון והתגיות הטכניות נשמרו!")
                st.rerun()

    return plan


# === [SEC-08: PRICE PERFORMANCE (%)] ===
def render_price_performance(row: pd.Series) -> None:
    rows_spec = [
        [
            ("היום (Live)", "change_today_pct"),
            ("אתמול (T-1)", "change_1d"),
            ("לפני יומיים (T-2)", "change_2d"),
            ("לפני 3 ימים (T-3)", "change_3d"),
            ("לפני 4 ימים (T-4)", "change_4d"),
        ],
        [
            ("מתחילת שבוע (WTD)", "start_of_the_week"),
            ("שבוע (5D)", "weekly"),
            ("שבועיים (10D)", "two_weeks"),
            ("3 שבועות (15D)", "three_weeks"),
            ("חודש (1M)", "monthly"),
        ],
        [
            ("3 חודשים (3M)", "three_months"),
            ("6 חודשים (6M)", "six_months"),
            ("9 חודשים (9M)", "nine_months"),
            ("מתחילת השנה (YTD)", "ytd"),
            ("שנה (1Y)", "one_year"),
        ],
    ]

    grids_html = []
    for r_idx, group in enumerate(rows_spec):
        tiles = []
        for label, col in group:
            raw_v = _safe_float(row.get(col)) if col in row.index else None
            pct_str, color = format_pct_color(raw_v)
            tiles.append(
                f'<div class="dd-tile">'
                f'<div class="dd-tlbl">{label}</div>'
                f'<div class="dd-tval" style="color:{color};">{pct_str}</div>'
                f'</div>'
            )
        mb = "margin-bottom:0;" if r_idx == len(rows_spec) - 1 else ""
        grids_html.append(f'<div class="dd-g5" style="{mb}">{"".join(tiles)}</div>')

    _html(
        f"""
        <div class="dd-card">
            <div class="dd-hdr">
                <span>ביצועי מחיר ותשואות (%)</span>
                <span class="dd-hdr-en">PRICE PERFORMANCE</span>
            </div>
            {"".join(grids_html)}
        </div>
        """
    )


# === [SEC-09: VOLUME MOMENTUM (DAILY VOLUMES & INLINE RELATIVE VOLUME)] ===
def render_volume_momentum(row: pd.Series) -> None:
    vol_specs = [
        ("נפח היום", "daily_vol", "change_today_pct"),
        ("אתמול (T-1)", "vol_1d", "change_1d"),
        ("לפני יומיים (T-2)", "vol_2d", "change_2d"),
        ("לפני 3 ימים (T-3)", "vol_3d", "change_3d"),
        ("לפני 4 ימים (T-4)", "vol_4d", "change_4d"),
    ]

    vol_tiles = []
    for label, v_col, chg_col in vol_specs:
        v_raw = _safe_float(row.get(v_col)) if v_col in row.index else None
        chg_raw = _safe_float(row.get(chg_col)) if chg_col in row.index else None
        v_str = _fmt_vol(v_raw)

        if v_raw is None or chg_raw is None:
            tile_cls, val_color = "dd-tile", "#F8FAFC"
        elif chg_raw >= 0:
            tile_cls, val_color = "dd-tile-green", "#10B981"
        else:
            tile_cls, val_color = "dd-tile-red", "#EF4444"

        vol_tiles.append(
            f'<div class="{tile_cls}">'
            f'<div class="dd-tlbl">{label}</div>'
            f'<div class="dd-tval" style="color:{val_color};">{v_str}</div>'
            f'</div>'
        )

    today_chg = _safe_float(row.get("change_today_pct"))
    rvol_specs = [
        ("Rel Vol 5D", "rel_vol_5d"),
        ("Rel Vol 10D", "rel_vol_10d"),
        ("Rel Vol 15D", "rel_vol_15d"),
        ("Rel Vol 20D", "rel_vol_20d"),
        ("Rel Vol 30D", "rel_vol_30d"),
    ]

    rvol_tiles = []
    for label, r_col in rvol_specs:
        rv = _safe_float(row.get(r_col)) if r_col in row.index else None
        if rv is None:
            r_str, tile_cls, val_color = "--", "dd-tile", "#94A3B8"
        else:
            r_str = f"{rv:.2f}x"
            if rv >= 1.0 and today_chg is not None:
                if today_chg >= 0:
                    tile_cls, val_color = "dd-tile-green", "#10B981"
                else:
                    tile_cls, val_color = "dd-tile-red", "#EF4444"
            else:
                tile_cls, val_color = "dd-tile", "#CBD5E1"

        rvol_tiles.append(
            f'<div class="{tile_cls}" style="padding:10px 8px;">'
            f'<span style="font-size:1.12rem; font-weight:800; color:{val_color}; direction:ltr; unicode-bidi:isolate;">{r_str}</span>'
            f'<span style="font-size:0.8rem; font-weight:600; color:#94A3B8; margin-right:6px; direction:ltr; unicode-bidi:isolate;">{label}</span>'
            f'</div>'
        )

    _html(
        f"""
        <div class="dd-card">
            <div class="dd-hdr">
                <span>מומנטום ונפחי מסחר</span>
                <span class="dd-hdr-en">VOLUME MOMENTUM</span>
            </div>
            <div class="dd-sub-lbl">נפח מסחר יומי (5 ימי מסחר אחרונים — ירוק ביום עליות / אדום ביום ירידות)</div>
            <div class="dd-g5">{"".join(vol_tiles)}</div>
            <div class="dd-sub-lbl">נפח יחסי לממוצע (Rel Vol — נצבע בירוק או באדום בחריגת נפח מעל 1.00x)</div>
            <div class="dd-g5" style="margin-bottom:0;">{"".join(rvol_tiles)}</div>
        </div>
        """
    )


# === [SEC-10: MOVING AVERAGES (% AND $ DISTANCE)] ===
def render_moving_averages(row: pd.Series) -> None:
    price = _safe_float(row.get("display_price"))
    ma_specs = [
        ("MA 20", "ma_20_status", "ma_20_value", "ma_20_dist_pct"),
        ("MA 50", "ma_50_status", "ma_50_value", "ma_50_dist_pct"),
        ("MA 150", "ma_150_status", "ma_150_value", "ma_150_dist_pct"),
        ("MA 200", "ma_200_status", "ma_200_value", "ma_200_dist_pct"),
    ]

    cards = []
    for title, st_col, val_col, pct_col in ma_specs:
        st_val = str(row.get(st_col)) if st_col in row.index and pd.notna(row.get(st_col)) else ""
        ma_val = _safe_float(row.get(val_col)) if val_col in row.index else None
        dist_pct = _safe_float(row.get(pct_col)) if pct_col in row.index else None

        if ma_val is not None and price is not None:
            diff_usd = price - ma_val
            usd_sign = "+" if diff_usd > 0 else ("-" if diff_usd < 0 else "")
            usd_str = f"{usd_sign}${abs(diff_usd):,.2f}"
            pct_sign = "+" if (dist_pct or 0) > 0 else ""
            pct_str = f"{pct_sign}{dist_pct:.2f}%" if dist_pct is not None else "--"
            dist_combo = f"{pct_str}  |  {usd_str}"
            ma_price_str = f"${ma_val:,.2f}"
        else:
            dist_combo, ma_price_str = "--", "--"

        if st_val == "Above":
            tile_cls, status_html, dist_color = "dd-tile-green", '<span style="color:#10B981;">ABOVE ▲</span>', "#10B981"
        elif st_val == "Below":
            tile_cls, status_html, dist_color = "dd-tile-red", '<span style="color:#EF4444;">BELOW ▼</span>', "#EF4444"
        else:
            tile_cls, status_html, dist_color = "dd-tile", '<span style="color:#94A3B8;">--</span>', "#94A3B8"

        cards.append(
            f'<div class="{tile_cls}" style="padding:14px;">'
            f'<div style="font-size:0.88rem; font-weight:700; color:#CBD5E1; margin-bottom:4px; direction:ltr;">{title}</div>'
            f'<div style="font-size:0.96rem; font-weight:800; margin-bottom:6px; direction:ltr;">{status_html}</div>'
            f'<div style="font-size:1.18rem; font-weight:700; color:#F8FAFC; margin-bottom:8px; direction:ltr; unicode-bidi:isolate;">{ma_price_str}</div>'
            f'<div style="font-size:0.88rem; font-weight:700; padding:4px 10px; border-radius:8px; background:#111622; color:{dist_color}; direction:ltr; unicode-bidi:isolate; display:inline-block;">{dist_combo}</div>'
            f'</div>'
        )

    _html(
        f"""
        <div class="dd-card">
            <div class="dd-hdr">
                <span>ממוצעים נעים (סטטוס, שער ומרחק באחוזים ובדולרים)</span>
                <span class="dd-hdr-en">MOVING AVERAGES</span>
            </div>
            <div class="dd-g4">{"".join(cards)}</div>
        </div>
        """
    )


# === [SEC-11: TECH LEVELS, VOLATILITY & INLINE MANUAL S/R] ===
def render_tech_levels_and_manual(row: pd.Series, manual_levels: list[dict]) -> None:
    sym = str(row["symbol"]).upper()
    default_price = _safe_float(row.get("display_price"), 100.0) or 100.0

    atr_14 = _safe_float(row.get("atr_14"))
    atr_pct = _safe_float(row.get("atr_pct"))
    atr_sq = _safe_float(row.get("atr_squeeze_pct"))

    atr_14_str = f"${atr_14:,.2f}" if atr_14 is not None else "--"
    atr_pct_str = f"{atr_pct:.2f}%" if atr_pct is not None else "--"
    atr_sq_str = f"{atr_sq:.1f}%" if atr_sq is not None else "--"
    sq_width = max(0.0, min(100.0, atr_sq)) if atr_sq is not None else 0.0

    def collect_pills(prefix: str, cls_name: str) -> str:
        pills = []
        for i in range(1, 6):
            col = f"{prefix}_{i}"
            val = _safe_float(row.get(col)) if col in row.index else None
            if val is not None:
                pills.append(f'<span class="{cls_name}">${val:,.2f}</span>')
        return "".join(pills) if pills else '<span style="color:#64748B; font-size:0.86rem;">לא זוהו רמות בטווח</span>'

    d_res_html = collect_pills("d_r", "dd-pill-res")
    d_sup_html = collect_pills("d_s", "dd-pill-sup")
    w_res_html = collect_pills("w_r", "dd-pill-res")
    w_sup_html = collect_pills("w_s", "dd-pill-sup")

    lvl_box = "background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:16px; text-align:center;"
    pills_wrap = "display:flex; flex-wrap:wrap; justify-content:center; gap:8px; direction:ltr;"

    m_pills = "".join(
        f'<span class="dd-pill-man">★ {html.escape(str(lvl.get("note", "רמה ידנית")))}: '
        f'<span style="direction:ltr; unicode-bidi:isolate;">${float(lvl.get("price", 0)):,.2f}</span></span>'
        for lvl in manual_levels
        if float(lvl.get("price", 0)) > 0
    )
    manual_inner = (
        f'<div style="display:flex; flex-wrap:wrap; justify-content:center; gap:8px; direction:rtl;">{m_pills}</div>'
        if m_pills
        else '<div style="color:#64748B; font-size:0.85rem;">אין עדיין רמות ידניות שמורות למניה זו</div>'
    )

    _html(
        f"""
        <div class="dd-card" style="margin-bottom:10px;">
            <div class="dd-hdr">
                <span>רמות טכניות ומדדי תנודתיות (ATR)</span>
                <span class="dd-hdr-en">TECH LEVELS & VOLATILITY</span>
            </div>

            <div class="dd-g3" style="margin-bottom:14px;">
                <div class="dd-tile">
                    <div class="dd-tlbl">טווח תנועה יומי (ATR 14)</div>
                    <div class="dd-tval" style="color:#F8FAFC;">{atr_14_str}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">תנודתיות באחוזים (ATR %)</div>
                    <div class="dd-tval" style="color:#60A5FA;">{atr_pct_str}</div>
                </div>
                <div class="dd-tile">
                    <div class="dd-tlbl">התכווצות תנודתיות (ATR Squeeze %)</div>
                    <div class="dd-tval" style="color:#F59E0B;">{atr_sq_str}</div>
                    <div style="width:82%; height:5px; background:#1E293B; border-radius:999px; margin:8px auto 0 auto; overflow:hidden;">
                        <div style="width:{sq_width}%; height:100%; background:#F59E0B;"></div>
                    </div>
                </div>
            </div>

            <div class="dd-g2">
                <div style="{lvl_box}">
                    <div style="font-size:0.96rem; font-weight:800; color:#F8FAFC; margin-bottom:10px;">רמות יומיות (Daily Levels)</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#EF4444; margin:6px 0;">התנגדות (Resistance — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap}">{d_res_html}</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#10B981; margin:14px 0 6px 0;">תמיכה (Support — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap}">{d_sup_html}</div>
                </div>

                <div style="{lvl_box}">
                    <div style="font-size:0.96rem; font-weight:800; color:#F8FAFC; margin-bottom:10px;">רמות שבועיות (Weekly Levels)</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#EF4444; margin:6px 0;">התנגדות (Resistance — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap}">{w_res_html}</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#10B981; margin:14px 0 6px 0;">תמיכה (Support — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap}">{w_sup_html}</div>
                </div>
            </div>

            <div style="{lvl_box} margin-top:14px;">
                <div style="font-size:0.96rem; font-weight:800; color:#F8FAFC; margin-bottom:10px;">רמות ידניות שמורות</div>
                {manual_inner}
            </div>
        </div>
        """
    )

    # Inline Quick Add & Delete Row for Manual Levels
    c_price, c_note, c_add, c_del_sel, c_del_btn = st.columns([1.0, 1.8, 0.95, 1.4, 0.7])
    with c_price:
        new_lvl_p = st.number_input(
            "מחיר ($)",
            min_value=0.01,
            value=round(default_price, 2),
            step=0.25,
            label_visibility="collapsed",
            key=f"man_p_{sym}",
        )
    with c_note:
        new_lvl_n = st.text_input(
            "תווית לרמה ידנית",
            placeholder="תווית לרמה ידנית (לדוגמה: תמיכת גאפ)",
            label_visibility="collapsed",
            key=f"man_n_{sym}",
        )
    with c_add:
        if st.button("+ הוסף רמה ידנית", use_container_width=True, key=f"btn_add_lvl_{sym}"):
            updated = list(manual_levels) + [
                {"price": round(float(new_lvl_p), 2), "note": new_lvl_n.strip() or "רמה ידנית"}
            ]
            save_manual_levels(sym, updated)
            st.toast("הרמה הידנית נשמרה בהצלחה")
            st.rerun()

    if manual_levels:
        lvl_labels = [f"${float(x.get('price', 0)):,.2f} — {x.get('note', 'רמה ידנית')}" for x in manual_levels]
        with c_del_sel:
            del_idx = st.selectbox(
                "בחר רמה למחיקה",
                options=range(len(manual_levels)),
                format_func=lambda i: lvl_labels[i],
                label_visibility="collapsed",
                key=f"del_sel_{sym}",
            )
        with c_del_btn:
            if st.button("מחק", use_container_width=True, key=f"btn_del_lvl_{sym}"):
                updated = [x for i, x in enumerate(manual_levels) if i != del_idx]
                save_manual_levels(sym, updated)
                st.toast("הרמה הוסרה")
                st.rerun()


# === [SEC-12: PRE-TRADE JOURNAL & NOTES (3-COLUMN CARD)] ===
def render_pre_trade_notes(symbol: str, plan: dict, edit_mode: bool) -> None:
    ent_txt = html.escape(plan.get("entry_rationale", "").strip() or "טרם הוזנה תוכנית כניסה וטריגר.")
    ext_txt = html.escape(plan.get("exit_plan", "").strip() or "טרם הוגדרו יעדי יציאה וניהול עסקה.")
    not_txt = html.escape(plan.get("watchlist_notes", "").strip() or "אין הערות מעקב נוספות למניה זו.")

    _html(
        f"""
        <div class="dd-card" style="margin-top:14px;">
            <div class="dd-hdr">
                <span>תוכנית מסחר, נימוקי כניסה והערות מעקב (יועברו אוטומטית ליומן)</span>
                <span class="dd-hdr-en">PRE-TRADE JOURNAL & NOTES</span>
            </div>
            <div class="dd-g3">
                <div class="dd-note-box">
                    <div class="dd-note-title">תוכנית כניסה וטריגר (Entry Rationale)</div>
                    <div class="dd-note-body">{ent_txt}</div>
                </div>
                <div class="dd-note-box">
                    <div class="dd-note-title">ניהול עסקה ויעדי יציאה (Exit Plan)</div>
                    <div class="dd-note-body">{ext_txt}</div>
                </div>
                <div class="dd-note-box">
                    <div class="dd-note-title">הערות מעקב ודגשים (Watchlist Notes)</div>
                    <div class="dd-note-body">{not_txt}</div>
                </div>
            </div>
        </div>
        """
    )

    if edit_mode:
        with st.container(border=True):
            st.markdown("**עריכת תוכנית מסחר והערות (יעברו אוטומטית בעת פתיחת עסקה ביומן)**")
            nc1, nc2, nc3 = st.columns(3)
            with nc1:
                new_ent = st.text_area(
                    "תוכנית כניסה וטריגר",
                    value=plan.get("entry_rationale", ""),
                    height=100,
                    key=f"ed_ent_{symbol}",
                )
            with nc2:
                new_ext = st.text_area(
                    "ניהול עסקה ויעדי יציאה",
                    value=plan.get("exit_plan", ""),
                    height=100,
                    key=f"ed_ext_{symbol}",
                )
            with nc3:
                new_not = st.text_area(
                    "הערות מעקב ודגשים",
                    value=plan.get("watchlist_notes", ""),
                    height=100,
                    key=f"ed_not_{symbol}",
                )

            if st.button("שמור תוכנית מסחר והערות", type="primary", key=f"save_notes_{symbol}"):
                updated_plan = {
                    **plan,
                    "entry_rationale": new_ent,
                    "exit_plan": new_ext,
                    "watchlist_notes": new_not,
                }
                _save_pre_trade_plan(symbol, updated_plan)
                st.toast("תוכנית המסחר והערות המעקב נשמרו!")
                st.rerun()


# === [SEC-13: MAIN PAGE ORCHESTRATION] ===
def main() -> None:
    _inject_deep_dive_css()

    df = load_market_dataframe()
    if df.empty:
        st.info("אין נתונים להצגה.")
        return

    symbols = df["symbol"].tolist()
    comp_map = {
        str(r["symbol"]): str(r.get("company_name") or r["symbol"])
        for _, r in df.iterrows()
    }

    default_sym = st.session_state.get("selected_symbol", symbols[0])
    if default_sym not in symbols:
        default_sym = symbols[0]

    # Top Control Bar (RTL: Stock Selector -> Setup -> Refresh -> Edit Plan -> Open Trade CTA -> Back)
    c_sym, c_setup, c_ref, c_edit, c_open, c_back = st.columns([2.0, 1.45, 0.95, 1.15, 1.25, 0.95])
    with c_sym:
        selected_sym = st.selectbox(
            "בחר מניה לניתוח עומק",
            options=symbols,
            index=symbols.index(default_sym),
            format_func=lambda s: f"{s} — {comp_map.get(s, s)}",
            label_visibility="collapsed",
            key="dd_symbol_selector",
        )
        st.session_state["selected_symbol"] = selected_sym

    row = df[df["symbol"] == selected_sym].iloc[0]

    with c_setup:
        saved_setup = (
            str(row.get("setup_pattern")).strip()
            if "setup_pattern" in row.index and pd.notna(row.get("setup_pattern")) and str(row.get("setup_pattern")).strip()
            else "ללא Setup"
        )
        if saved_setup not in SETUP_OPTIONS:
            saved_setup = "ללא Setup"

        chosen_setup = st.selectbox(
            "תבנית טכנית (Setup)",
            options=SETUP_OPTIONS,
            index=SETUP_OPTIONS.index(saved_setup),
            label_visibility="collapsed",
            key=f"dd_setup_combo_{selected_sym}",
        )
        if chosen_setup != saved_setup:
            sync_setup_pattern(selected_sym, chosen_setup)
            st.toast(f"תבנית Setup עבור {selected_sym} עודכנה וסונכרנה ליומן: {chosen_setup}")
            st.rerun()

    with c_ref:
        if st.button("↻ רענן מחיר חי", use_container_width=True):
            with st.spinner("מושך מחיר חי..."):
                refresh_live_prices_tv([selected_sym])
                st.rerun()

    edit_key = f"dd_edit_mode_{selected_sym}"
    is_edit = bool(st.session_state.get(edit_key, False))
    with c_edit:
        edit_lbl = "✓ סיום עריכה" if is_edit else "✏️ עריכת נתוני תכנון"
        if st.button(edit_lbl, use_container_width=True, key=f"btn_toggle_edit_{selected_sym}"):
            st.session_state[edit_key] = not is_edit
            st.rerun()

    plan = _load_pre_trade_plan(selected_sym, row)
    live_ind = _get_cached_live_indicators(selected_sym)

    with c_open:
        if st.button("🚀 פתח עסקה ביומן", type="primary", use_container_width=True, key=f"btn_open_trade_{selected_sym}"):
            _dialog_open_trade_from_deep_dive(row, plan, chosen_setup, live_ind)

    with c_back:
        if st.button("← לסורק", use_container_width=True, key="btn_back_screener"):
            st.switch_page("views/screener.py")

    raw_manual = row.get("manual_levels")
    manual_levels = raw_manual if isinstance(raw_manual, list) else []

    render_top_header_card(row)
    render_indicators_snapshot(row, live_ind)
    render_planner_and_tags(row, plan, is_edit)
    render_price_performance(row)
    render_volume_momentum(row)
    render_moving_averages(row)
    render_tech_levels_and_manual(row, manual_levels)
    render_pre_trade_notes(selected_sym, plan, is_edit)


main()
