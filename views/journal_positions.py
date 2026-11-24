# === [SEC-01: IMPORTS & HTML RENDER HELPERS] ===
import html
from datetime import datetime, date, timezone
import pandas as pd
import streamlit as st
from db import load_market_dataframe, refresh_live_prices_tv, sync_setup_pattern
from journal_helpers import (
    SETUP_OPTIONS,
    VOLUME_TREND_OPTIONS,
    MACD_OPTIONS,
    CCI_OPTIONS,
    load_journal_data,
    insert_trade,
    update_trade,
    delete_trade,
    insert_cash_tx,
    compute_live_entry_indicators,
)
from ui_theme import render_logo_html


def _html(raw: str) -> None:
    """Renders multi-line HTML cleanly without Markdown indentation blocks."""
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _safe_float(val, default: float | None = None) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _fmt_usd(val: float | None, signed: bool = False) -> str:
    if val is None:
        return "--"
    if signed:
        sign = "+" if val > 0 else ("-" if val < 0 else "")
        return f"{sign}${abs(val):,.2f}"
    return f"${val:,.2f}"


def _fmt_pct(val: float | None, signed: bool = True) -> str:
    if val is None:
        return "--"
    if signed:
        sign = "+" if val > 0 else ("-" if val < 0 else "")
        return f"{sign}{abs(val):.2f}%"
    return f"{val:.2f}%"


def _pnl_color(val: float | None) -> str:
    if val is None or abs(val) < 1e-9:
        return "#94A3B8"
    return "#10B981" if val > 0 else "#EF4444"


def _calc_rr_str(entry_p: float | None, sl: float | None, tp: float | None, direction: str = "Long") -> str:
    if not entry_p or not sl or not tp or entry_p <= 0:
        return "--"
    if direction == "Short":
        risk = sl - entry_p
        reward = entry_p - tp
    else:
        risk = entry_p - sl
        reward = tp - entry_p
    if risk <= 0 or reward <= 0:
        return "--"
    return f"1:{(reward / risk):.2f}"


# === [SEC-02: SCOPED VISUAL STYLES (1-TO-1 OBSIDIAN POSITIONS & LOG DESIGN)] ===
def _inject_positions_css() -> None:
    _html(
        """
        <style>
        .pj-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin: 12px 0 18px 0;
            direction: rtl;
        }
        @media (max-width: 960px) {
            .pj-kpi-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        .pj-kpi-card {
            background: #111622;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 15px 18px;
            position: relative;
            overflow: hidden;
            direction: rtl;
            text-align: right;
            transition: border-color 0.2s ease;
        }
        .pj-kpi-card:hover {
            border-color: #2563EB;
        }
        .pj-kpi-top-accent {
            position: absolute;
            top: 0;
            right: 0;
            left: 0;
            height: 3px;
        }
        .pj-kpi-title {
            color: #94A3B8;
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .pj-kpi-val {
            font-size: 1.52rem;
            font-weight: 800;
            color: #F8FAFC;
            line-height: 1.2;
        }
        .pj-kpi-sub {
            font-size: 0.78rem;
            color: #64748B;
            margin-top: 6px;
        }

        /* Section Shell */
        .pj-section-box {
            background: #111622;
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 18px;
            direction: rtl;
            text-align: right;
        }
        .pj-section-hdr {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            padding-bottom: 12px;
            margin-bottom: 12px;
            border-bottom: 1px solid #1E2638;
        }
        .pj-section-title {
            font-size: 1.06rem;
            font-weight: 800;
            color: #F8FAFC;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .pj-count-pill {
            background: rgba(37, 99, 235, 0.16);
            border: 1px solid rgba(37, 99, 235, 0.42);
            color: #60A5FA;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 2px 10px;
            border-radius: 999px;
        }
        .pj-green-pill {
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #10B981;
            font-size: 0.76rem;
            font-weight: 800;
            padding: 2px 9px;
            border-radius: 6px;
            direction: ltr;
            display: inline-block;
        }
        .pj-red-pill {
            background: rgba(239, 68, 68, 0.14);
            border: 1px solid rgba(239, 68, 68, 0.4);
            color: #EF4444;
            font-size: 0.76rem;
            font-weight: 800;
            padding: 2px 9px;
            border-radius: 6px;
            direction: ltr;
            display: inline-block;
        }
        .pj-setup-pill {
            background: rgba(139, 92, 246, 0.15);
            border: 1px solid rgba(139, 92, 246, 0.42);
            color: #C4B5FD;
            font-size: 0.76rem;
            font-weight: 700;
            padding: 2px 9px;
            border-radius: 6px;
            direction: ltr;
            unicode-bidi: isolate;
            display: inline-block;
        }
        .pj-amber-pill {
            background: rgba(245, 158, 11, 0.14);
            border: 1px solid rgba(245, 158, 11, 0.4);
            color: #FBBF24;
            font-size: 0.76rem;
            font-weight: 700;
            padding: 2px 9px;
            border-radius: 6px;
            display: inline-block;
        }

        /* Active Position Row Card (Exact Visual Bar & Columns) */
        .pj-pos-row {
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 13px;
            padding: 13px 16px;
            margin-bottom: 8px;
            display: grid;
            grid-template-columns: 1.55fr 1.15fr 1.1fr 1.15fr 1.9fr;
            gap: 14px;
            align-items: center;
            direction: rtl;
            transition: border-color 0.15s ease;
        }
        .pj-pos-row:hover {
            border-color: #2B3954;
        }
        @media (max-width: 1050px) {
            .pj-pos-row {
                grid-template-columns: 1fr;
                gap: 10px;
            }
        }

        /* Visual SL-to-TP Range Track */
        .pj-range-wrap {
            background: #111622;
            border: 1px solid #1E2638;
            border-radius: 10px;
            padding: 8px 11px;
            direction: ltr;
        }
        .pj-range-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.76rem;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .pj-track-bg {
            position: relative;
            width: 100%;
            height: 7px;
            background: #1E293B;
            border-radius: 999px;
            margin: 6px 0;
        }
        .pj-track-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #EF4444 0%, #F59E0B 48%, #10B981 100%);
        }
        .pj-track-dot {
            position: absolute;
            top: 50%;
            width: 13px;
            height: 13px;
            border-radius: 50%;
            background: #FFFFFF;
            border: 2.5px solid #38BDF8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.95);
            transform: translate(-50%, -50%);
        }
        .pj-range-bot {
            display: flex;
            justify-content: space-between;
            font-size: 0.72rem;
            color: #94A3B8;
            margin-top: 4px;
        }

        /* Closed Trades Log Row */
        .pj-closed-row {
            background: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 13px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: grid;
            grid-template-columns: 1.55fr 1.15fr 1.25fr 1.1fr 1.25fr 1.15fr 0.75fr;
            gap: 12px;
            align-items: center;
            direction: rtl;
        }
        .pj-closed-row:hover {
            border-color: #2B3954;
        }
        @media (max-width: 1100px) {
            .pj-closed-row {
                grid-template-columns: 1fr;
                gap: 8px;
            }
        }
        .pj-col-hdr-active {
            display: grid;
            grid-template-columns: 1.55fr 1.15fr 1.1fr 1.15fr 1.9fr;
            gap: 14px;
            padding: 0 16px 8px 16px;
            color: #64748B;
            font-size: 0.78rem;
            font-weight: 700;
            direction: rtl;
        }
        .pj-col-hdr-closed {
            display: grid;
            grid-template-columns: 1.55fr 1.15fr 1.25fr 1.1fr 1.25fr 1.15fr 0.75fr;
            gap: 12px;
            padding: 0 16px 8px 16px;
            color: #64748B;
            font-size: 0.78rem;
            font-weight: 700;
            direction: rtl;
        }
        @media (max-width: 1100px) {
            .pj-col-hdr-active, .pj-col-hdr-closed {
                display: none;
            }
        }
        </style>
        """
    )


# === [SEC-03: DIALOG MODALS (NEW TRADE, DEPOSIT, CLOSE TRADE, QUICK SL/TP)] ===
@st.dialog("פתיחת עסקה חדשה", width="large")
def _dialog_new_trade(df_market: pd.DataFrame) -> None:
    watch_symbols = df_market["symbol"].tolist() if not df_market.empty else []
    mode_src = st.radio(
        "בחירת מניה",
        options=["מתוך רשימת המעקב", "הזנת טיקר ידני"],
        horizontal=True,
        key="nt_src_mode",
    )

    c1, c2, c3 = st.columns([1.3, 1.7, 1.1])
    with c1:
        if mode_src == "מתוך רשימת המעקב" and watch_symbols:
            sym = st.selectbox("סימול (Ticker)", options=watch_symbols, key="nt_sym_sel")
        else:
            sym = st.text_input("סימול (Ticker)", placeholder="לדוגמה: NVDA", key="nt_sym_txt").strip().upper()

    m_row = df_market[df_market["symbol"] == sym].iloc[0] if (sym and not df_market.empty and sym in watch_symbols) else None
    default_comp = str(m_row.get("company_name") or sym) if m_row is not None else sym
    default_price = _safe_float(m_row.get("display_price"), 100.0) if m_row is not None else 100.0
    default_setup = (
        str(m_row.get("setup_pattern")).strip()
        if (m_row is not None and "setup_pattern" in m_row.index and pd.notna(m_row.get("setup_pattern")) and str(m_row.get("setup_pattern")).strip())
        else "ללא Setup"
    )
    if default_setup not in SETUP_OPTIONS:
        default_setup = "ללא Setup"

    with c2:
        comp_name = st.text_input("שם חברה", value=default_comp, key=f"nt_comp_{sym}")
    with c3:
        direction = st.selectbox("כיוון עסקה", ["Long", "Short"], key="nt_dir")

    c4, c5, c6 = st.columns([1.5, 1.1, 1.1])
    with c4:
        setup_choice = st.selectbox(
            "תבנית טכנית (Setup)",
            options=SETUP_OPTIONS,
            index=SETUP_OPTIONS.index(default_setup),
            key=f"nt_setup_{sym}",
        )
    with c5:
        entry_date_val = st.date_input("תאריך כניסה", value=date.today(), key="nt_entry_date")
    with c6:
        fees_entry = st.number_input("עמלת קנייה ($)", min_value=0.0, value=0.0, step=0.5, key="nt_fees")

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        entry_price = st.number_input("שער כניסה ($)", min_value=0.01, value=float(default_price or 100.0), step=0.1, key=f"nt_ep_{sym}")
    with p2:
        quantity = st.number_input("כמות מניות", min_value=0.0001, value=10.0, step=1.0, key="nt_qty")
    with p3:
        default_sl = round(entry_price * (0.95 if direction == "Long" else 1.05), 2)
        stop_loss = st.number_input("Stop Loss ($)", min_value=0.0, value=default_sl, step=0.1, key=f"nt_sl_{sym}")
    with p4:
        default_tp = round(entry_price * (1.15 if direction == "Long" else 0.85), 2)
        take_profit = st.number_input("Take Profit ($)", min_value=0.0, value=default_tp, step=0.1, key=f"nt_tp_{sym}")

    purchase_amt = round(entry_price * quantity, 2)
    rr_live = _calc_rr_str(entry_price, stop_loss if stop_loss > 0 else None, take_profit if take_profit > 0 else None, direction)
    _html(
        f"""
        <div style="background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:10px 14px; margin:8px 0; display:flex; justify-content:space-between; align-items:center; direction:rtl;">
            <span>סכום השקעה כולל: <strong style="color:#F8FAFC; direction:ltr; unicode-bidi:isolate;">${purchase_amt:,.2f}</strong></span>
            <span>יחס סיכוי / סיכון (R:R): <strong style="color:#38BDF8; direction:ltr; unicode-bidi:isolate;">{rr_live}</strong></span>
        </div>
        """
    )

    notes_txt = st.text_area("נימוקי כניסה ותוכנית ניהול", placeholder="למה נכנסתי, היכן ממוקם הסטופ, ומה היעד...", height=80, key="nt_notes")

    if st.button("שמור ופתח פוזיציה", type="primary", use_container_width=True):
        if not sym:
            st.error("יש להזין סימול מניה תקין.")
            return
        with st.spinner("שומר עסקה ומצלם נתונים טכניים מרגע הכניסה..."):
            live_ind = compute_live_entry_indicators(sym)
            payload = {
                "entry_date": entry_date_val.isoformat(),
                "symbol": sym,
                "company_name": comp_name.strip() or sym,
                "direction": direction,
                "setup_pattern": None if setup_choice == "ללא Setup" else setup_choice,
                "entry_price": round(float(entry_price), 4),
                "quantity": round(float(quantity), 4),
                "purchase_amount": purchase_amt,
                "stop_loss": round(float(stop_loss), 2) if stop_loss > 0 else None,
                "take_profit": round(float(take_profit), 2) if take_profit > 0 else None,
                "rr_ratio": rr_live if rr_live != "--" else None,
                "fees": round(float(fees_entry), 2),
                "status": "Open",
                "notes": notes_txt.strip() or None,
                "macd_status": live_ind.get("macd_status"),
                "cci_value": live_ind.get("cci_value"),
                "cci_status": live_ind.get("cci_status"),
                "volume_trend": live_ind.get("volume_trend"),
                "rsi": live_ind.get("rsi_live"),
            }
            if m_row is not None:
                for col in (
                    "ma_20_status", "ma_50_status", "ma_150_status", "ma_200_status",
                    "rel_vol_5d", "rel_vol_10d", "rel_vol_15d", "rel_vol_20d", "rel_vol_30d",
                    "d_s_1", "d_s_2", "d_s_3", "d_s_4", "d_s_5",
                    "d_r_1", "d_r_2", "d_r_3", "d_r_4", "d_r_5",
                    "w_s_1", "w_s_2", "w_s_3", "w_s_4", "w_s_5",
                    "w_r_1", "w_r_2", "w_r_3", "w_r_4", "w_r_5",
                ):
                    if col in m_row.index and pd.notna(m_row.get(col)):
                        target_col = col.replace("_status", "") if col.startswith("ma_") else col
                        payload[target_col] = m_row[col]
                if payload.get("rsi") is None and "rsi" in m_row.index and pd.notna(m_row.get("rsi")):
                    payload["rsi"] = float(m_row["rsi"])

            insert_trade(payload)
            st.success(f"הפוזיציה ב-{sym} נפתחה ונשמרה בהצלחה!")
            st.rerun()


@st.dialog("הפקדה / משיכה לחשבון")
def _dialog_cash_tx() -> None:
    tx_type = st.radio("סוג תנועה", ["Deposit (הפקדה)", "Withdrawal (משיכה)"], horizontal=True, key="cash_tx_type")
    c1, c2 = st.columns(2)
    with c1:
        tx_dt = st.date_input("תאריך", value=date.today(), key="cash_tx_dt")
    with c2:
        amt = st.number_input("סכום ($)", min_value=1.0, value=1000.0, step=100.0, key="cash_tx_amt")
    note = st.text_input("הערה", placeholder="לדוגמה: הפקדה חודשית לחשבון המסחר", key="cash_tx_note")
    if st.button("רשום תנועת מזומן", type="primary", use_container_width=True):
        clean_type = "Deposit" if "Deposit" in tx_type else "Withdrawal"
        insert_cash_tx(tx_dt.isoformat(), clean_type, amt, note)
        st.success("התנועה נרשמה בהצלחה")
        st.rerun()


@st.dialog("סגירת עסקה (מלאה או חלקית)", width="large")
def _dialog_close_trade(trade_row: pd.Series, live_price: float | None) -> None:
    tid = int(trade_row["id"])
    sym = str(trade_row["symbol"])
    direction = str(trade_row.get("direction") or "Long")
    entry_p = float(trade_row["entry_price"])
    open_qty = float(trade_row["quantity"])
    prev_fees = float(_safe_float(trade_row.get("fees"), 0.0) or 0.0)
    default_exit = float(live_price) if (live_price and live_price > 0) else entry_p

    st.markdown(f"**{sym}** | כיוון: **{direction}** | כמות פתוחה: **{open_qty:g}** | שער כניסה: **${entry_p:,.2f}**")

    close_mode = st.radio(
        "היקף סגירה",
        options=["סגירה מלאה (100%)", "מימוש חלקי (50%)", "כמות מותאמת אישית"],
        horizontal=True,
        key=f"cl_mode_{tid}",
    )

    if close_mode == "סגירה מלאה (100%)":
        sell_qty = open_qty
    elif close_mode == "מימוש חלקי (50%)":
        sell_qty = round(open_qty * 0.5, 4)
    else:
        sell_qty = st.number_input(
            "כמות מניות למכירה",
            min_value=0.0001,
            max_value=float(open_qty),
            value=float(open_qty),
            step=1.0,
            key=f"cl_qty_{tid}",
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        exit_price = st.number_input("שער יציאה ($)", min_value=0.01, value=default_exit, step=0.1, key=f"cl_ep_{tid}")
    with c2:
        close_dt = st.date_input("תאריך סגירה", value=date.today(), key=f"cl_dt_{tid}")
    with c3:
        close_fees = st.number_input("עמלות כוללות ($)", min_value=0.0, value=prev_fees, step=0.5, key=f"cl_fees_{tid}")

    gross_pnl = (entry_p - exit_price) * sell_qty if direction == "Short" else (exit_price - entry_p) * sell_qty
    cost_sold = entry_p * sell_qty
    gross_pct = (gross_pnl / cost_sold * 100.0) if cost_sold > 0 else 0.0

    t1, t2 = st.columns([1.4, 1.0])
    with t1:
        auto_tax_on = st.checkbox("חשב מס רווחי הון אוטומטי (25% על רווח נקי מעמלות)", value=True, key=f"cl_autotax_{tid}")
    suggested_tax = round(max(0.0, gross_pnl - close_fees) * 0.25, 2) if auto_tax_on else 0.0
    with t2:
        tax_paid = st.number_input("מס ששולם ($)", min_value=0.0, value=float(suggested_tax), step=1.0, key=f"cl_tax_{tid}")

    net_pnl = round(gross_pnl - close_fees - tax_paid, 2)
    net_col = _pnl_color(net_pnl)

    _html(
        f"""
        <div style="background:#0D111A; border:1px solid #1E2638; border-radius:12px; padding:12px 16px; margin:10px 0; display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; text-align:center; direction:rtl;">
            <div>
                <div style="font-size:0.75rem; color:#94A3B8;">רווח/הפסד גולמי</div>
                <div style="font-size:1.05rem; font-weight:800; color:{_pnl_color(gross_pnl)}; direction:ltr; unicode-bidi:isolate;">{_fmt_usd(gross_pnl, True)} ({_fmt_pct(gross_pct)})</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:#94A3B8;">עמלות</div>
                <div style="font-size:1.05rem; font-weight:700; color:#CBD5E1; direction:ltr; unicode-bidi:isolate;">${close_fees:,.2f}</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:#94A3B8;">מס ששולם</div>
                <div style="font-size:1.05rem; font-weight:700; color:#FBBF24; direction:ltr; unicode-bidi:isolate;">${tax_paid:,.2f}</div>
            </div>
            <div>
                <div style="font-size:0.75rem; color:#94A3B8;">רווח/הפסד נטו</div>
                <div style="font-size:1.15rem; font-weight:800; color:{net_col}; direction:ltr; unicode-bidi:isolate;">{_fmt_usd(net_pnl, True)}</div>
            </div>
        </div>
        """
    )

    p1, p2 = st.columns([1.1, 2.2])
    with p1:
        plan_choice = st.selectbox("עמידה בתוכנית (Plan)", ["Yes", "No", "Partial"], key=f"cl_plan_{tid}")
    with p2:
        close_note = st.text_input("הערת סגירה / הפקת לקחים", value=str(trade_row.get("notes") or ""), key=f"cl_note_{tid}")

    if st.button("אשר וסגור עסקה", type="primary", use_container_width=True):
        is_full = sell_qty >= (open_qty - 1e-6)
        if is_full:
            update_trade(
                tid,
                {
                    "symbol": sym,
                    "exit_price": round(float(exit_price), 4),
                    "sell_quantity": round(float(sell_qty), 4),
                    "close_date": close_dt.isoformat(),
                    "fees": round(float(close_fees), 2),
                    "tax_paid": round(float(tax_paid), 2),
                    "net_pnl": net_pnl,
                    "status": "Closed",
                    "according_to_plan": plan_choice,
                    "notes": close_note.strip() or None,
                },
            )
        else:
            rem_qty = round(open_qty - sell_qty, 4)
            update_trade(
                tid,
                {
                    "symbol": sym,
                    "quantity": rem_qty,
                    "purchase_amount": round(entry_p * rem_qty, 2),
                    "fees": 0.0,
                },
            )
            closed_copy = {
                "entry_date": str(trade_row["entry_date"]),
                "symbol": sym,
                "company_name": trade_row.get("company_name"),
                "direction": direction,
                "setup_pattern": trade_row.get("setup_pattern"),
                "entry_price": entry_p,
                "quantity": round(float(sell_qty), 4),
                "purchase_amount": round(entry_p * sell_qty, 2),
                "stop_loss": _safe_float(trade_row.get("stop_loss")),
                "take_profit": _safe_float(trade_row.get("take_profit")),
                "rr_ratio": trade_row.get("rr_ratio"),
                "exit_price": round(float(exit_price), 4),
                "sell_quantity": round(float(sell_qty), 4),
                "close_date": close_dt.isoformat(),
                "fees": round(float(close_fees), 2),
                "tax_paid": round(float(tax_paid), 2),
                "net_pnl": net_pnl,
                "status": "Closed",
                "according_to_plan": plan_choice,
                "notes": close_note.strip() or None,
                "rsi": _safe_float(trade_row.get("rsi")),
                "macd_status": trade_row.get("macd_status"),
                "cci_value": _safe_float(trade_row.get("cci_value")),
                "cci_status": trade_row.get("cci_status"),
                "volume_trend": trade_row.get("volume_trend"),
                "ma_20": trade_row.get("ma_20"),
                "ma_50": trade_row.get("ma_50"),
                "ma_150": trade_row.get("ma_150"),
                "ma_200": trade_row.get("ma_200"),
            }
            insert_trade(closed_copy)

        st.success(f"העסקה ב-{sym} נסגרה ותועדה בהצלחה!")
        st.rerun()


@st.dialog("עריכת SL / TP ותבנית Setup")
def _dialog_edit_sl_tp(trade_row: pd.Series) -> None:
    tid = int(trade_row["id"])
    sym = str(trade_row["symbol"])
    direction = str(trade_row.get("direction") or "Long")
    entry_p = float(trade_row["entry_price"])
    curr_sl = float(_safe_float(trade_row.get("stop_loss"), round(entry_p * 0.95, 2)) or 0.0)
    curr_tp = float(_safe_float(trade_row.get("take_profit"), round(entry_p * 1.15, 2)) or 0.0)
    curr_setup = str(trade_row.get("setup_pattern") or "").strip()
    if curr_setup not in SETUP_OPTIONS:
        curr_setup = "ללא Setup"

    st.markdown(f"**{sym}** | כניסה: **${entry_p:,.2f}** | כיוון: **{direction}**")

    new_setup = st.selectbox(
        "תבנית טכנית (Setup — מסונכרנת אוטומטית לניתוח עומק)",
        options=SETUP_OPTIONS,
        index=SETUP_OPTIONS.index(curr_setup),
        key=f"ed_setup_{tid}",
    )
    c1, c2 = st.columns(2)
    with c1:
        new_sl = st.number_input("Stop Loss ($)", min_value=0.0, value=curr_sl, step=0.1, key=f"ed_sl_{tid}")
    with c2:
        new_tp = st.number_input("Take Profit ($)", min_value=0.0, value=curr_tp, step=0.1, key=f"ed_tp_{tid}")

    rr_str = _calc_rr_str(entry_p, new_sl if new_sl > 0 else None, new_tp if new_tp > 0 else None, direction)
    st.caption(f"יחס סיכוי/סיכון מעודכן (R:R): **{rr_str}**")

    if st.button("שמור שינויים", type="primary", use_container_width=True):
        update_trade(
            tid,
            {
                "symbol": sym,
                "setup_pattern": None if new_setup == "ללא Setup" else new_setup,
                "stop_loss": round(float(new_sl), 2) if new_sl > 0 else None,
                "take_profit": round(float(new_tp), 2) if new_tp > 0 else None,
                "rr_ratio": rr_str if rr_str != "--" else None,
            },
        )
        st.success("היעדים ותבנית ה-Setup עודכנו וסונכרנו!")
        st.rerun()


# === [SEC-04: TRADE DEEP DIVE VIEW (FULL TECHNICAL SNAPSHOT & EDITABLE JOURNAL)] ===
def render_trade_deep_dive(df_trades: pd.DataFrame, df_market: pd.DataFrame) -> None:
    trade_ids = df_trades["id"].tolist()
    sel_id = st.session_state.get("selected_journal_trade_id")
    if sel_id not in trade_ids:
        sel_id = trade_ids[0]
        st.session_state["selected_journal_trade_id"] = sel_id

    labels_map = {
        int(r["id"]): f"{r['symbol']}  |  {r['entry_date']}  |  {r['status']}  |  ${float(r['entry_price']):,.2f}"
        for _, r in df_trades.iterrows()
    }

    top1, top2 = st.columns([1.4, 2.6])
    with top1:
        if st.button("← חזרה לרשימת הפוזיציות והעסקאות", use_container_width=True):
            st.session_state["selected_journal_trade_id"] = None
            st.rerun()
    with top2:
        chosen_id = st.selectbox(
            "בחר עסקה",
            options=trade_ids,
            index=trade_ids.index(sel_id),
            format_func=lambda x: labels_map.get(int(x), str(x)),
            label_visibility="collapsed",
            key="tdd_trade_switcher",
        )
        if chosen_id != sel_id:
            st.session_state["selected_journal_trade_id"] = chosen_id
            st.rerun()

    tr = df_trades[df_trades["id"] == sel_id].iloc[0]
    sym = str(tr["symbol"])
    comp_name = html.escape(str(tr.get("company_name") or sym))
    status = str(tr.get("status") or "Open")
    direction = str(tr.get("direction") or "Long")
    entry_p = float(tr["entry_price"])
    qty = float(tr["quantity"])
    sl_val = _safe_float(tr.get("stop_loss"))
    tp_val = _safe_float(tr.get("take_profit"))
    exit_p = _safe_float(tr.get("exit_price"))

    m_match = df_market[df_market["symbol"] == sym] if not df_market.empty else pd.DataFrame()
    logo_url = m_match.iloc[0].get("logo_url") if not m_match.empty else None
    live_p = _safe_float(m_match.iloc[0].get("display_price")) if not m_match.empty else None
    logo_html = render_logo_html(sym, logo_url, size=50)

    if status == "Closed" and exit_p is not None:
        pnl_val = _safe_float(tr.get("net_pnl"))
        if pnl_val is None:
            gross = (entry_p - exit_p) * qty if direction == "Short" else (exit_p - entry_p) * qty
            pnl_val = gross - float(_safe_float(tr.get("fees"), 0.0) or 0.0) - float(_safe_float(tr.get("tax_paid"), 0.0) or 0.0)
        pnl_lbl = "רווח/הפסד נטו (סגור)"
        ref_price_str = f"יציאה: ${exit_p:,.2f}"
    else:
        curr_p = live_p if live_p is not None else entry_p
        pnl_val = (entry_p - curr_p) * qty if direction == "Short" else (curr_p - entry_p) * qty
        pnl_lbl = "רווח/הפסד פתוח (Live)"
        ref_price_str = f"נוכחי: ${curr_p:,.2f}"

    status_pill = (
        '<span class="pj-count-pill">OPEN POSITION</span>'
        if status == "Open"
        else '<span class="pj-amber-pill">CLOSED TRADE</span>'
    )
    dir_pill = '<span class="pj-green-pill">LONG</span>' if direction == "Long" else '<span class="pj-red-pill">SHORT</span>'

    _html(
        f"""
        <div class="pj-section-box">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; direction:ltr;">
                <div style="display:flex; align-items:center; gap:14px;">
                    {logo_html}
                    <div>
                        <div style="font-size:1.42rem; font-weight:800; color:#F8FAFC;">{comp_name} ({html.escape(sym)})</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:5px;">
                            {dir_pill}
                            {status_pill}
                            <span style="color:#94A3B8; font-size:0.84rem;">Entry: {html.escape(str(tr['entry_date']))}</span>
                        </div>
                    </div>
                </div>

                <div style="display:flex; gap:14px; flex-wrap:wrap; direction:rtl;">
                    <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:10px 16px; text-align:center;">
                        <div style="font-size:0.75rem; color:#94A3B8;">כניסה / {ref_price_str.split(':')[0]}</div>
                        <div style="font-size:1.1rem; font-weight:800; color:#F8FAFC; direction:ltr; unicode-bidi:isolate;">${entry_p:,.2f} → {ref_price_str.split(':')[1].strip()}</div>
                    </div>
                    <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:10px 16px; text-align:center;">
                        <div style="font-size:0.75rem; color:#94A3B8;">SL / TP / R:R</div>
                        <div style="font-size:1.05rem; font-weight:800; color:#38BDF8; direction:ltr; unicode-bidi:isolate;">
                            {f'${sl_val:,.2f}' if sl_val else '--'} / {f'${tp_val:,.2f}' if tp_val else '--'} ({_calc_rr_str(entry_p, sl_val, tp_val, direction)})
                        </div>
                    </div>
                    <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:10px 16px; text-align:center;">
                        <div style="font-size:0.75rem; color:#94A3B8;">{pnl_lbl}</div>
                        <div style="font-size:1.2rem; font-weight:800; color:{_pnl_color(pnl_val)}; direction:ltr; unicode-bidi:isolate;">{_fmt_usd(pnl_val, True)}</div>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    # Technical Snapshot at Entry
    rsi_v = _safe_float(tr.get("rsi"))
    cci_v = _safe_float(tr.get("cci_value"))
    macd_s = html.escape(str(tr.get("macd_status") or "--"))
    cci_s = html.escape(str(tr.get("cci_status") or (f"{cci_v:.1f}" if cci_v is not None else "--")))
    vol_t = html.escape(str(tr.get("volume_trend") or "--"))

    ma_badges = []
    for p in (20, 50, 150, 200):
        mv = str(tr.get(f"ma_{p}") or "").strip()
        if mv == "Above":
            ma_badges.append(f'<span class="pj-green-pill">MA{p}: ABOVE ▲</span>')
        elif mv == "Below":
            ma_badges.append(f'<span class="pj-red-pill">MA{p}: BELOW ▼</span>')
        else:
            ma_badges.append(f'<span style="background:#1A2234; color:#94A3B8; padding:2px 9px; border-radius:6px; font-size:0.76rem;">MA{p}: --</span>')

    rvol_items = []
    for d_win in (5, 10, 15, 20, 30):
        rv = _safe_float(tr.get(f"rel_vol_{d_win}d"))
        rvol_items.append(f"<span>{d_win}D: <strong>{f'{rv:.2f}x' if rv is not None else '--'}</strong></span>")

    _html(
        f"""
        <div class="pj-section-box">
            <div class="pj-section-hdr">
                <div class="pj-section-title">צילום מצב טכני ברגע הכניסה לעסקה</div>
                <span style="font-size:0.8rem; color:#64748B; direction:ltr;">ENTRY TECHNICAL SNAPSHOT</span>
            </div>
            <div style="display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:12px; margin-bottom:12px; direction:rtl;">
                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:12px; text-align:center;">
                    <div style="font-size:0.78rem; color:#94A3B8; margin-bottom:4px;">RSI (14) בכניסה</div>
                    <div style="font-size:1.25rem; font-weight:800; color:#F8FAFC; direction:ltr;">{f'{rsi_v:.1f}' if rsi_v is not None else '--'}</div>
                </div>
                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:12px; text-align:center;">
                    <div style="font-size:0.78rem; color:#94A3B8; margin-bottom:4px;">MACD Status</div>
                    <div style="font-size:0.88rem; font-weight:700; color:#38BDF8;">{macd_s}</div>
                </div>
                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:12px; text-align:center;">
                    <div style="font-size:0.78rem; color:#94A3B8; margin-bottom:4px;">CCI (20)</div>
                    <div style="font-size:0.88rem; font-weight:700; color:#10B981;">{cci_s}</div>
                </div>
                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:12px; text-align:center;">
                    <div style="font-size:0.78rem; color:#94A3B8; margin-bottom:4px;">Volume Trend</div>
                    <div style="font-size:0.88rem; font-weight:700; color:#FBBF24;">{vol_t}</div>
                </div>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; background:#0D111A; border:1px solid #1A2233; border-radius:11px; padding:11px 14px;">
                <div style="display:flex; gap:8px; flex-wrap:wrap; direction:ltr;">{"".join(ma_badges)}</div>
                <div style="display:flex; gap:14px; flex-wrap:wrap; font-size:0.82rem; color:#CBD5E1; direction:ltr;">
                    <span style="color:#64748B;">Rel Vol:</span>
                    {"".join(rvol_items)}
                </div>
            </div>
        </div>
        """
    )

    # Editable Setup, Plan Discipline & Journal Notes
    st.markdown("### תיעוד, תבנית Setup והפקת לקחים")
    curr_setup = str(tr.get("setup_pattern") or "").strip()
    if curr_setup not in SETUP_OPTIONS:
        curr_setup = "ללא Setup"

    curr_plan = str(tr.get("according_to_plan") or "").strip()
    plan_opts = ["ממתין", "Yes", "No", "Partial"]
    if curr_plan not in plan_opts:
        curr_plan = "ממתין"

    ec1, ec2, ec3 = st.columns([1.4, 1.0, 1.4])
    with ec1:
        edit_setup = st.selectbox(
            "תבנית טכנית (Setup — מסתנכרן אוטומטית לניתוח עומק באנליטיקה)",
            options=SETUP_OPTIONS,
            index=SETUP_OPTIONS.index(curr_setup),
            key=f"tdd_setup_{sel_id}",
        )
    with ec2:
        edit_plan = st.selectbox(
            "עמידה בתוכנית (Plan)",
            options=plan_opts,
            index=plan_opts.index(curr_plan),
            key=f"tdd_plan_{sel_id}",
        )
    with ec3:
        edit_signal = st.text_input(
            "תגית איתות / הערה קצרה",
            value=str(tr.get("signal_status") or ""),
            key=f"tdd_sig_{sel_id}",
        )

    edit_notes = st.text_area(
        "יומן עסקה מפורט (נימוקי כניסה, ניהול פוזיציה ומסקנות)",
        value=str(tr.get("notes") or ""),
        height=130,
        key=f"tdd_notes_{sel_id}",
    )

    b_save, _, b_del = st.columns([1.5, 2.5, 1.0])
    with b_save:
        if st.button("שמור עדכונים וסנכרן Setup", type="primary", use_container_width=True):
            update_trade(
                int(sel_id),
                {
                    "symbol": sym,
                    "setup_pattern": None if edit_setup == "ללא Setup" else edit_setup,
                    "according_to_plan": None if edit_plan == "ממתין" else edit_plan,
                    "signal_status": edit_signal.strip() or None,
                    "notes": edit_notes.strip() or None,
                },
            )
            st.success("העסקה נשמרה ותבנית ה-Setup סונכרנה מול ניתוח העומק!")
            st.rerun()
    with b_del:
        if st.button("מחק עסקה", use_container_width=True):
            delete_trade(int(sel_id))
            st.session_state["selected_journal_trade_id"] = None
            st.toast("העסקה נמחקה")
            st.rerun()


# === [SEC-05: MAIN POSITIONS & TRADE LOG PAGE] ===
def render_positions_and_log_page() -> None:
    _inject_positions_css()

    df_trades, _ = load_journal_data()
    df_market = load_market_dataframe()

    # If user clicked "ניתוח עומק" on any trade row, open Trade Deep Dive view
    if st.session_state.get("selected_journal_trade_id") is not None and not df_trades.empty:
        render_trade_deep_dive(df_trades, df_market)
        return

    # --- Top Header & Action Buttons ---
    hdr_col, btn_new_col, btn_cash_col, btn_ref_col = st.columns([2.6, 1.15, 1.05, 0.95])
    with hdr_col:
        _html(
            """
            <div style="direction:rtl; text-align:right;">
                <div style="font-size:1.45rem; font-weight:800; color:#F8FAFC; line-height:1.2;">פוזיציות ויומן עסקאות</div>
                <div style="font-size:0.84rem; color:#94A3B8; margin-top:3px;">ניהול פוזיציות פתוחות, מעקב יעדי SL/TP ויזואלי ותיעוד עסקאות סגורות כולל הפרדת מס ועמלות</div>
            </div>
            """
        )
    with btn_new_col:
        if st.button("+ פתיחת עסקה חדשה", type="primary", use_container_width=True):
            _dialog_new_trade(df_market)
    with btn_cash_col:
        if st.button("+ הפקדה לחשבון", use_container_width=True):
            _dialog_cash_tx()
    with btn_ref_col:
        if st.button("רענן מחירים", use_container_width=True):
            open_syms = (
                df_trades[df_trades["status"] == "Open"]["symbol"].dropna().unique().tolist()
                if not df_trades.empty
                else []
            )
            if open_syms:
                with st.spinner("מעדכן שערים חיים..."):
                    refresh_live_prices_tv(open_syms)
                    st.rerun()

    if df_trades.empty:
        st.info("אין עדיין עסקאות ביומן. לחץ על '+ פתיחת עסקה חדשה' כדי לתעד את העסקה הראשונה שלך.")
        return

    # Build live price & logo lookup from market dataframe
    live_price_map: dict[str, float] = {}
    logo_map: dict[str, str] = {}
    profile_setup_map: dict[str, str] = {}
    if not df_market.empty:
        for _, mr in df_market.iterrows():
            s = str(mr["symbol"]).upper()
            if pd.notna(mr.get("display_price")):
                live_price_map[s] = float(mr["display_price"])
            if pd.notna(mr.get("logo_url")):
                logo_map[s] = str(mr["logo_url"])
            if "setup_pattern" in mr.index and pd.notna(mr.get("setup_pattern")):
                profile_setup_map[s] = str(mr["setup_pattern"]).strip()

    open_df = df_trades[df_trades["status"] == "Open"].copy()
    closed_df = df_trades[df_trades["status"] == "Closed"].copy()

    # --- Compute Top 4 KPI Metrics ---
    total_invested_open = 0.0
    total_unrealized_pnl = 0.0
    for _, r in open_df.iterrows():
        s = str(r["symbol"]).upper()
        ep = float(r["entry_price"])
        q = float(r["quantity"])
        inv = _safe_float(r.get("purchase_amount"), ep * q) or (ep * q)
        total_invested_open += inv
        cp = live_price_map.get(s, ep)
        if str(r.get("direction") or "Long") == "Short":
            total_unrealized_pnl += (ep - cp) * q
        else:
            total_unrealized_pnl += (cp - ep) * q

    unrealized_pct = (total_unrealized_pnl / total_invested_open * 100.0) if total_invested_open > 0 else 0.0

    total_realized_net = 0.0
    total_realized_gross = 0.0
    total_fees_tax = 0.0
    wins_cnt = 0
    plan_yes_cnt = 0
    plan_total_cnt = 0

    for _, r in closed_df.iterrows():
        ep = float(r["entry_price"])
        ex = _safe_float(r.get("exit_price"), ep) or ep
        q = float(_safe_float(r.get("sell_quantity")) or r["quantity"])
        gross = (ep - ex) * q if str(r.get("direction") or "Long") == "Short" else (ex - ep) * q
        fees_v = float(_safe_float(r.get("fees"), 0.0) or 0.0)
        tax_v = float(_safe_float(r.get("tax_paid"), 0.0) or 0.0)
        net_v = _safe_float(r.get("net_pnl"))
        if net_v is None:
            net_v = gross - fees_v - tax_v

        total_realized_gross += gross
        total_fees_tax += (fees_v + tax_v)
        total_realized_net += net_v
        if net_v > 0:
            wins_cnt += 1

        pl_txt = str(r.get("according_to_plan") or "").strip()
        if pl_txt in ("Yes", "No", "Partial"):
            plan_total_cnt += 1
            if pl_txt == "Yes":
                plan_yes_cnt += 1

    win_rate_pct = (wins_cnt / len(closed_df) * 100.0) if len(closed_df) > 0 else 0.0
    plan_rate_pct = (plan_yes_cnt / plan_total_cnt * 100.0) if plan_total_cnt > 0 else 0.0

    _html(
        f"""
        <div class="pj-kpi-grid">
            <div class="pj-kpi-card">
                <div class="pj-kpi-top-accent" style="background:linear-gradient(90deg, #2563EB, #38BDF8);"></div>
                <div class="pj-kpi-title">פוזיציות פתוחות</div>
                <div class="pj-kpi-val">{len(open_df)} עסקאות</div>
                <div class="pj-kpi-sub">הון מושקע: <span class="ltr-num">${total_invested_open:,.2f}</span></div>
            </div>
            <div class="pj-kpi-card">
                <div class="pj-kpi-top-accent" style="background:{_pnl_color(total_unrealized_pnl)};"></div>
                <div class="pj-kpi-title">רווח / הפסד לא ממומש (Live)</div>
                <div class="pj-kpi-val" style="color:{_pnl_color(total_unrealized_pnl)};"><span class="ltr-num">{_fmt_usd(total_unrealized_pnl, True)}</span></div>
                <div class="pj-kpi-sub">תשואה פתוחה: <span class="ltr-num" style="color:{_pnl_color(unrealized_pct)};">{_fmt_pct(unrealized_pct)}</span></div>
            </div>
            <div class="pj-kpi-card">
                <div class="pj-kpi-top-accent" style="background:{_pnl_color(total_realized_net)};"></div>
                <div class="pj-kpi-title">רווח נטו ממומש (אחרי מס ועמלות)</div>
                <div class="pj-kpi-val" style="color:{_pnl_color(total_realized_net)};"><span class="ltr-num">{_fmt_usd(total_realized_net, True)}</span></div>
                <div class="pj-kpi-sub">גולמי: <span class="ltr-num">{_fmt_usd(total_realized_gross, True)}</span> | מס ועמלות: <span class="ltr-num">${total_fees_tax:,.2f}</span></div>
            </div>
            <div class="pj-kpi-card">
                <div class="pj-kpi-top-accent" style="background:#8B5CF6;"></div>
                <div class="pj-kpi-title">אחוז הצלחה ועמידה בתוכנית</div>
                <div class="pj-kpi-val"><span class="ltr-num">{win_rate_pct:.1f}%</span> <span style="font-size:0.9rem; color:#94A3B8; font-weight:600;">({wins_cnt}/{len(closed_df)})</span></div>
                <div class="pj-kpi-sub">עמידה בתוכנית: <span class="ltr-num">{plan_rate_pct:.0f}%</span></div>
            </div>
        </div>
        """
    )

    # --- Search & Filter Toolbar ---
    f1, f2, f3, f4 = st.columns([1.6, 1.2, 1.1, 1.1])
    with f1:
        q_search = st.text_input(
            "חיפוש",
            placeholder="חיפוש לפי טיקר, שם חברה או Setup...",
            label_visibility="collapsed",
            key="pj_flt_search",
        ).strip().lower()
    with f2:
        flt_setup = st.selectbox(
            "Setup",
            options=["כל ה-Setups"] + SETUP_OPTIONS[1:],
            label_visibility="collapsed",
            key="pj_flt_setup",
        )
    with f3:
        flt_outcome = st.selectbox(
            "תוצאה",
            options=["כל התוצאות (סגורות)", "מרוויחות בלבד (Win)", "מפסידות בלבד (Loss)"],
            label_visibility="collapsed",
            key="pj_flt_outcome",
        )
    with f4:
        flt_plan = st.selectbox(
            "תוכנית",
            options=["עמידה בתוכנית: הכל", "Yes", "No", "Partial"],
            label_visibility="collapsed",
            key="pj_flt_plan",
        )

    def _matches_common_filters(r: pd.Series) -> bool:
        s = str(r.get("symbol") or "").lower()
        cn = str(r.get("company_name") or "").lower()
        stp = str(r.get("setup_pattern") or profile_setup_map.get(str(r.get("symbol") or "").upper(), "")).strip()
        if q_search and (q_search not in s and q_search not in cn and q_search not in stp.lower()):
            return False
        if flt_setup != "כל ה-Setups" and stp != flt_setup:
            return False
        if flt_plan != "עמידה בתוכנית: הכל" and str(r.get("according_to_plan") or "").strip() != flt_plan:
            return False
        return True

    # =========================================================================
    # SECTION 1: ACTIVE POSITIONS (פוזיציות פתוחות)
    # =========================================================================
    filtered_open = [r for _, r in open_df.iterrows() if _matches_common_filters(r)]

    _html(
        f"""
        <div class="pj-section-box" style="margin-bottom:8px; padding-bottom:10px;">
            <div class="pj-section-hdr" style="margin-bottom:8px;">
                <div class="pj-section-title">
                    <span>פוזיציות פתוחות (Active Positions)</span>
                    <span class="pj-count-pill">{len(filtered_open)} פוזיציות פעילות</span>
                </div>
                <span style="font-size:0.8rem; color:#94A3B8;">לחץ על <strong style="color:#F8FAFC;">סגירת עסקה</strong>, <strong style="color:#F8FAFC;">SL / TP</strong> או <strong style="color:#F8FAFC;">ניתוח עומק</strong> מתחת לכל שורה</span>
            </div>
            <div class="pj-col-hdr-active">
                <div>מניה ותאריך כניסה</div>
                <div>כיוון ו-Setup</div>
                <div>כמות ושער כניסה</div>
                <div>מחיר נוכחי ורווח פתוח</div>
                <div>טווח Stop Loss ←→ Take Profit ויחס R:R</div>
            </div>
        </div>
        """
    )

    if not filtered_open:
        st.caption("אין פוזיציות פתוחות התואמות לסינון הנוכחי.")
    else:
        for r in filtered_open:
            tid = int(r["id"])
            sym = str(r["symbol"]).upper()
            comp_name = html.escape(str(r.get("company_name") or sym))
            direction = str(r.get("direction") or "Long")
            entry_p = float(r["entry_price"])
            qty = float(r["quantity"])
            inv_amt = _safe_float(r.get("purchase_amount"), entry_p * qty) or (entry_p * qty)
            curr_p = live_price_map.get(sym, entry_p)
            unrl_pnl = (entry_p - curr_p) * qty if direction == "Short" else (curr_p - entry_p) * qty
            unrl_pct = (unrl_pnl / inv_amt * 100.0) if inv_amt > 0 else 0.0

            sl_v = _safe_float(r.get("stop_loss"))
            tp_v = _safe_float(r.get("take_profit"))
            rr_txt = _calc_rr_str(entry_p, sl_v, tp_v, direction)

            setup_val = str(r.get("setup_pattern") or "").strip() or profile_setup_map.get(sym, "")
            setup_html = (
                f'<span class="pj-setup-pill">{html.escape(setup_val)}</span>'
                if setup_val and setup_val != "ללא Setup"
                else '<span style="color:#64748B; font-size:0.78rem;">ללא Setup</span>'
            )
            dir_html = '<span class="pj-green-pill">LONG</span>' if direction == "Long" else '<span class="pj-red-pill">SHORT</span>'

            # Compute exact visual range bar position
            if sl_v and tp_v and abs(tp_v - sl_v) > 1e-6:
                if direction == "Short":
                    pos_pct = max(0.0, min(100.0, ((sl_v - curr_p) / (sl_v - tp_v)) * 100.0))
                    dist_sl_pct = ((curr_p - sl_v) / curr_p) * 100.0
                    dist_tp_pct = ((curr_p - tp_v) / curr_p) * 100.0
                else:
                    pos_pct = max(0.0, min(100.0, ((curr_p - sl_v) / (tp_v - sl_v)) * 100.0))
                    dist_sl_pct = ((sl_v - curr_p) / curr_p) * 100.0
                    dist_tp_pct = ((tp_v - curr_p) / curr_p) * 100.0

                range_html = f"""
                <div class="pj-range-wrap">
                    <div class="pj-range-top">
                        <span style="color:#EF4444;">SL ${sl_v:,.2f}</span>
                        <span style="color:#38BDF8; background:rgba(56,189,248,0.12); padding:1px 7px; border-radius:5px;">R:R {rr_txt}</span>
                        <span style="color:#10B981;">TP ${tp_v:,.2f}</span>
                    </div>
                    <div class="pj-track-bg">
                        <div class="pj-track-fill" style="width:{pos_pct:.1f}%;"></div>
                        <div class="pj-track-dot" style="left:{pos_pct:.1f}%;"></div>
                    </div>
                    <div class="pj-range-bot">
                        <span>{dist_sl_pct:+.1f}% to SL</span>
                        <span>{dist_tp_pct:+.1f}% to TP</span>
                    </div>
                </div>
                """
            else:
                range_html = """
                <div class="pj-range-wrap" style="text-align:center; color:#64748B; font-size:0.8rem;">
                    לא הוגדרו יעדי SL / TP לעסקה זו
                </div>
                """

            logo_html = render_logo_html(sym, logo_map.get(sym), size=36)

            _html(
                f"""
                <div class="pj-pos-row">
                    <div style="display:flex; align-items:center; gap:10px; direction:ltr;">
                        {logo_html}
                        <div style="min-width:0;">
                            <div style="font-weight:800; color:#F8FAFC; font-size:0.96rem;">{html.escape(sym)} <span style="font-weight:500; color:#94A3B8; font-size:0.8rem;">• {comp_name}</span></div>
                            <div style="font-size:0.76rem; color:#64748B;">כניסה: {html.escape(str(r['entry_date']))}</div>
                        </div>
                    </div>

                    <div style="display:flex; flex-direction:column; gap:5px; align-items:flex-start;">
                        {dir_html}
                        {setup_html}
                    </div>

                    <div>
                        <div style="font-weight:800; color:#F8FAFC; font-size:0.95rem;"><span class="ltr-num">${entry_p:,.2f}</span></div>
                        <div style="font-size:0.78rem; color:#94A3B8;"><span class="ltr-num">{qty:g}</span> מניות (<span class="ltr-num">${inv_amt:,.0f}</span>)</div>
                    </div>

                    <div>
                        <div style="font-weight:800; color:#F8FAFC; font-size:0.95rem;"><span class="ltr-num">${curr_p:,.2f}</span></div>
                        <div style="font-weight:800; font-size:0.86rem; color:{_pnl_color(unrl_pnl)};">
                            <span class="ltr-num">{_fmt_usd(unrl_pnl, True)} ({_fmt_pct(unrl_pct)})</span>
                        </div>
                    </div>

                    <div>{range_html}</div>
                </div>
                """
            )

            ac1, ac2, ac3, _ = st.columns([1.05, 0.95, 1.05, 3.2])
            with ac1:
                if st.button("סגירת עסקה", key=f"btn_close_{tid}", type="primary", use_container_width=True):
                    _dialog_close_trade(r, live_price_map.get(sym))
            with ac2:
                if st.button("SL / TP / Setup", key=f"btn_sltp_{tid}", use_container_width=True):
                    _dialog_edit_sl_tp(r)
            with ac3:
                if st.button("ניתוח עומק", key=f"btn_tdd_open_{tid}", use_container_width=True):
                    st.session_state["selected_journal_trade_id"] = tid
                    st.rerun()

            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # SECTION 2: CLOSED TRADES LOG (יומן עסקאות סגורות)
    # =========================================================================
    filtered_closed = []
    for _, r in closed_df.iterrows():
        if not _matches_common_filters(r):
            continue
        ep = float(r["entry_price"])
        ex = _safe_float(r.get("exit_price"), ep) or ep
        q = float(_safe_float(r.get("sell_quantity")) or r["quantity"])
        gross = (ep - ex) * q if str(r.get("direction") or "Long") == "Short" else (ex - ep) * q
        net_v = _safe_float(r.get("net_pnl"))
        if net_v is None:
            net_v = gross - float(_safe_float(r.get("fees"), 0.0) or 0.0) - float(_safe_float(r.get("tax_paid"), 0.0) or 0.0)
        if flt_outcome == "מרוויחות בלבד (Win)" and net_v <= 0:
            continue
        if flt_outcome == "מפסידות בלבד (Loss)" and net_v > 0:
            continue
        filtered_closed.append(r)

    _html(
        f"""
        <div class="pj-section-box" style="margin-top:18px; margin-bottom:8px; padding-bottom:10px;">
            <div class="pj-section-hdr" style="margin-bottom:8px;">
                <div class="pj-section-title">
                    <span>יומן עסקאות סגורות (Closed Trades Log)</span>
                    <span class="pj-count-pill">{len(filtered_closed)} עסקאות סגורות</span>
                </div>
                <span style="font-size:0.8rem; color:#94A3B8;">פירוט מלא כולל הפרדה בין רווח גולמי, עמלות ומס ששולם</span>
            </div>
            <div class="pj-col-hdr-closed">
                <div>מניה ותאריכים</div>
                <div>כיוון ו-Setup</div>
                <div>כניסה ←→ יציאה</div>
                <div>רווח/הפסד גולמי</div>
                <div>עמלות ומס ששולם</div>
                <div>רווח/הפסד נטו</div>
                <div>תוכנית</div>
            </div>
        </div>
        """
    )

    if not filtered_closed:
        st.caption("אין עסקאות סגורות התואמות לסינון הנוכחי.")
    else:
        for r in filtered_closed:
            tid = int(r["id"])
            sym = str(r["symbol"]).upper()
            comp_name = html.escape(str(r.get("company_name") or sym))
            direction = str(r.get("direction") or "Long")
            ep = float(r["entry_price"])
            ex = _safe_float(r.get("exit_price"), ep) or ep
            q = float(_safe_float(r.get("sell_quantity")) or r["quantity"])
            cost_b = ep * q
            gross = (ep - ex) * q if direction == "Short" else (ex - ep) * q
            gross_pct = (gross / cost_b * 100.0) if cost_b > 0 else 0.0
            fees_v = float(_safe_float(r.get("fees"), 0.0) or 0.0)
            tax_v = float(_safe_float(r.get("tax_paid"), 0.0) or 0.0)
            net_v = _safe_float(r.get("net_pnl"))
            if net_v is None:
                net_v = gross - fees_v - tax_v

            setup_val = str(r.get("setup_pattern") or "").strip() or profile_setup_map.get(sym, "")
            setup_html = (
                f'<span class="pj-setup-pill">{html.escape(setup_val)}</span>'
                if setup_val and setup_val != "ללא Setup"
                else '<span style="color:#64748B; font-size:0.78rem;">ללא Setup</span>'
            )
            dir_html = '<span class="pj-green-pill">LONG</span>' if direction == "Long" else '<span class="pj-red-pill">SHORT</span>'

            plan_txt = str(r.get("according_to_plan") or "--").strip()
            if plan_txt == "Yes":
                plan_badge = '<span class="pj-green-pill">Yes</span>'
            elif plan_txt == "No":
                plan_badge = '<span class="pj-red-pill">No</span>'
            elif plan_txt == "Partial":
                plan_badge = '<span class="pj-amber-pill">Partial</span>'
            else:
                plan_badge = '<span style="color:#64748B; font-size:0.8rem;">--</span>'

            close_dt_txt = str(r.get("close_date") or "--")
            logo_html = render_logo_html(sym, logo_map.get(sym), size=34)

            _html(
                f"""
                <div class="pj-closed-row">
                    <div style="display:flex; align-items:center; gap:10px; direction:ltr;">
                        {logo_html}
                        <div style="min-width:0;">
                            <div style="font-weight:800; color:#F8FAFC; font-size:0.94rem;">{html.escape(sym)} <span style="font-weight:500; color:#94A3B8; font-size:0.78rem;">• {comp_name}</span></div>
                            <div style="font-size:0.74rem; color:#64748B;">{html.escape(str(r['entry_date']))} → {html.escape(close_dt_txt)}</div>
                        </div>
                    </div>

                    <div style="display:flex; flex-direction:column; gap:4px; align-items:flex-start;">
                        {dir_html}
                        {setup_html}
                    </div>

                    <div>
                        <div style="font-weight:700; color:#E2E8F0; font-size:0.88rem;"><span class="ltr-num">${ep:,.2f} → ${ex:,.2f}</span></div>
                        <div style="font-size:0.76rem; color:#64748B;">כמות: <span class="ltr-num">{q:g}</span></div>
                    </div>

                    <div>
                        <div style="font-weight:700; color:{_pnl_color(gross)}; font-size:0.9rem;"><span class="ltr-num">{_fmt_usd(gross, True)}</span></div>
                        <div style="font-size:0.76rem; color:{_pnl_color(gross_pct)};"><span class="ltr-num">{_fmt_pct(gross_pct)}</span></div>
                    </div>

                    <div style="font-size:0.8rem; color:#CBD5E1;">
                        <div>עמלות: <span class="ltr-num" style="color:#94A3B8;">${fees_v:,.2f}</span></div>
                        <div>מס: <span class="ltr-num" style="color:#FBBF24;">${tax_v:,.2f}</span></div>
                    </div>

                    <div>
                        <span style="display:inline-block; padding:4px 10px; border-radius:8px; font-weight:800; font-size:0.94rem; background:{'rgba(16,185,129,0.12)' if net_v > 0 else 'rgba(239,68,68,0.12)'}; border:1px solid {'rgba(16,185,129,0.4)' if net_v > 0 else 'rgba(239,68,68,0.4)'}; color:{_pnl_color(net_v)};">
                            <span class="ltr-num">{_fmt_usd(net_v, True)}</span>
                        </span>
                    </div>

                    <div>{plan_badge}</div>
                </div>
                """
            )

            _, c_dd = st.columns([5.2, 1.0])
            with c_dd:
                if st.button("ניתוח עומק", key=f"btn_tdd_closed_{tid}", use_container_width=True):
                    st.session_state["selected_journal_trade_id"] = tid
                    st.rerun()
