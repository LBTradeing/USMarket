# === [SEC-01: IMPORTS & HELPERS] ===
import html
from datetime import date
import pandas as pd
import streamlit as st
from db import load_market_dataframe
from journal_helpers import (
    VOLUME_TREND_OPTIONS,
    MACD_OPTIONS,
    CCI_OPTIONS,
    TRENDLINE_OPTIONS,
    GAPS_OPTIONS,
    FIBONACCI_OPTIONS,
    CANDLE_OPTIONS,
    CANDLE_TREND_OPTIONS,
    INDICATOR_GUIDE_SECTIONS,
    SIGNAL_SYNERGY_MATRIX,
    compute_live_entry_indicators,
    analyze_candles_with_gemini,
    load_journal_data,
    insert_trade,
    update_trade,
    delete_trade,
    insert_cash_tx,
    import_journal_csv,
)


def _html(raw: str) -> None:
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _fmt_usd(val: float | None, signed: bool = False) -> str:
    if val is None or pd.isna(val):
        return "--"
    v = float(val)
    if signed:
        sign = "+" if v > 0 else ("-" if v < 0 else "")
        return f"{sign}${abs(v):,.2f}"
    return f"${v:,.2f}"


# === [SEC-02: TOP PORTFOLIO & JOURNAL KPI SUMMARY] ===
def render_journal_kpis(df_trades: pd.DataFrame, df_cash: pd.DataFrame, price_map: dict[str, float]) -> None:
    total_deposits = (
        float(df_cash[df_cash["tx_type"] == "Deposit"]["amount_usd"].sum())
        - float(df_cash[df_cash["tx_type"] == "Withdrawal"]["amount_usd"].sum())
        if not df_cash.empty
        else 0.0
    )

    if df_trades.empty:
        open_df = pd.DataFrame()
        closed_df = pd.DataFrame()
    else:
        open_df = df_trades[df_trades["status"] == "Open"].copy()
        closed_df = df_trades[df_trades["status"] == "Closed"].copy()

    invested_open = 0.0
    unrealized_pnl = 0.0
    for _, r in open_df.iterrows():
        sym = str(r["symbol"]).upper()
        ep = float(r["entry_price"])
        qty = float(r["quantity"])
        cost = ep * qty
        invested_open += cost
        live_p = price_map.get(sym)
        if live_p is not None:
            mult = 1.0 if str(r.get("direction", "Long")) == "Long" else -1.0
            unrealized_pnl += (live_p - ep) * qty * mult

    realized_pnl = float(closed_df["net_pnl"].fillna(0).sum()) if not closed_df.empty else 0.0
    total_tax = float(closed_df["tax_paid"].fillna(0).sum()) if not closed_df.empty else 0.0
    total_fees = float(df_trades["fees"].fillna(0).sum()) if not df_trades.empty else 0.0

    wins = len(closed_df[closed_df["net_pnl"].fillna(0) > 0]) if not closed_df.empty else 0
    total_closed = len(closed_df)
    win_rate = round((wins / total_closed) * 100, 1) if total_closed > 0 else 0.0

    est_cash_avail = total_deposits + realized_pnl - invested_open - total_fees

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        ("סה״כ הפקדות (Cash)", _fmt_usd(total_deposits), "#F8FAFC", f"מזומן פנוי משוער: {_fmt_usd(est_cash_avail)}"),
        ("מושקע בפוזיציות פתוחות", _fmt_usd(invested_open), "#60A5FA", f"{len(open_df)} פוזיציות פתוחות"),
        (
            "רווח/הפסד לא-ממומש",
            _fmt_usd(unrealized_pnl, signed=True),
            "#10B981" if unrealized_pnl >= 0 else "#EF4444",
            "מחושב לפי שער חי / אחרון",
        ),
        (
            "רווח/הפסד ממומש נטו",
            _fmt_usd(realized_pnl, signed=True),
            "#10B981" if realized_pnl >= 0 else "#EF4444",
            f"מס ששולם: {_fmt_usd(total_tax)}",
        ),
        (
            "אחוז הצלחה (Win Rate)",
            f"{win_rate}%",
            "#F59E0B",
            f"{wins} רווחיות מתוך {total_closed} סגורות",
        ),
    ]

    for col, (title, val_str, color, sub) in zip([c1, c2, c3, c4, c5], cards):
        with col:
            _html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">{title}</div>
                    <div class="kpi-value" style="color:{color}; direction:ltr; text-align:right;">{val_str}</div>
                    <div class="kpi-sub">{sub}</div>
                </div>
                """
            )


# === [SEC-03: TAB 1 - TRADES VIEW (CONSOLIDATED VS DETAILED) & CLOSE/EDIT] ===
def render_trades_tab(df_trades: pd.DataFrame, price_map: dict[str, float]) -> None:
    if df_trades.empty:
        st.info("אין עדיין עסקאות ביומן. ניתן להוסיף עסקה חדשה בטאב 'פתיחת עסקה' או לייבא את הגיליון בטאב 'הפקדות וייבוא CSV'.")
        return

    f1, f2, f3 = st.columns([1.6, 1.2, 1.6])
    with f1:
        view_mode = st.radio(
            "אופן תצוגה",
            options=["תצוגה מאוחדת לפי מניה (Consolidated)", "תצוגת פעולות מפורטת (Detailed)"],
            horizontal=True,
            key="journal_view_mode",
        )
    with f2:
        status_flt = st.selectbox("סטטוס עסקאות", ["הכל", "פתוחות (Open)", "סגורות (Closed)"], key="j_status_flt")
    with f3:
        sym_q = st.text_input("חיפוש לפי טיקר", placeholder="לדוגמה: MSFT, GOOGL...", key="j_sym_flt").strip().upper()

    df_view = df_trades.copy()
    if status_flt == "פתוחות (Open)":
        df_view = df_view[df_view["status"] == "Open"]
    elif status_flt == "סגורות (Closed)":
        df_view = df_view[df_view["status"] == "Closed"]

    if sym_q:
        df_view = df_view[df_view["symbol"].str.upper().str.contains(sym_q, regex=False)]

    if df_view.empty:
        st.warning("לא נמצאו עסקאות התואמות לסינון.")
        return

    # Enrich rows with live P&L
    live_prices = []
    pnl_list = []
    pnl_pct_list = []
    for _, r in df_view.iterrows():
        sym = str(r["symbol"]).upper()
        ep = float(r["entry_price"])
        qty = float(r["quantity"])
        cost = ep * qty
        st_val = str(r.get("status", "Open"))
        curr_p = price_map.get(sym)
        live_prices.append(curr_p)

        if st_val == "Closed" and pd.notna(r.get("net_pnl")):
            pnl = float(r["net_pnl"])
        elif curr_p is not None:
            mult = 1.0 if str(r.get("direction", "Long")) == "Long" else -1.0
            pnl = (curr_p - ep) * qty * mult
        else:
            pnl = None

        pnl_list.append(round(pnl, 2) if pnl is not None else None)
        pnl_pct_list.append(round((pnl / cost) * 100, 2) if (pnl is not None and cost > 0) else None)

    df_view["live_price"] = live_prices
    df_view["calc_pnl"] = pnl_list
    df_view["calc_pnl_pct"] = pnl_pct_list

    if "מאוחדת" in view_mode:
        # Group by Symbol + Status for clean aggregated view
        grouped_rows = []
        for (sym, st_val), grp in df_view.groupby(["symbol", "status"], sort=False):
            tot_qty = float(grp["quantity"].sum())
            tot_cost = float((grp["entry_price"] * grp["quantity"]).sum())
            avg_entry = tot_cost / tot_qty if tot_qty > 0 else 0.0
            curr_p = price_map.get(sym)
            tot_pnl = float(grp["calc_pnl"].dropna().sum()) if grp["calc_pnl"].notna().any() else None
            tot_pnl_pct = round((tot_pnl / tot_cost) * 100, 2) if (tot_pnl is not None and tot_cost > 0) else None
            grouped_rows.append(
                {
                    "סימול": sym,
                    "חברה": grp["company_name"].dropna().iloc[0] if grp["company_name"].notna().any() else sym,
                    "סטטוס": "פתוחה" if st_val == "Open" else "סגורה",
                    "מס׳ כניסות": len(grp),
                    "כמות מצטברת": round(tot_qty, 4),
                    "מחיר כניסה ממוצע": round(avg_entry, 2),
                    "עלות כוללת ($)": round(tot_cost, 2),
                    "מחיר נוכחי ($)": round(curr_p, 2) if curr_p is not None else None,
                    "רווח/הפסד ($)": round(tot_pnl, 2) if tot_pnl is not None else None,
                    "תשואה (%)": tot_pnl_pct,
                }
            )
        st.dataframe(pd.DataFrame(grouped_rows), use_container_width=True, hide_index=True)
    else:
        disp_cols = {
            "id": "מזהה",
            "entry_date": "תאריך כניסה",
            "symbol": "סימול",
            "status": "סטטוס",
            "entry_price": "מחיר כניסה",
            "quantity": "כמות",
            "stop_loss": "סטופ",
            "take_profit": "יעד",
            "rr_ratio": "R:R",
            "exit_price": "מחיר יציאה",
            "close_date": "תאריך סגירה",
            "calc_pnl": "רווח/הפסד ($)",
            "calc_pnl_pct": "תשואה (%)",
            "macd_status": "MACD",
            "cci_status": "CCI",
            "volume_trend": "Volume Trend",
            "according_to_plan": "לפי התוכנית",
        }
        avail = [c for c in disp_cols if c in df_view.columns]
        st.dataframe(df_view[avail].rename(columns=disp_cols), use_container_width=True, hide_index=True)

    # --- Manage / Close / Inspect Single Execution ---
    st.markdown("---")
    with st.expander("עדכון, סגירת עסקה או צפייה בפרטי Snapshot והערות", expanded=False):
        options_map = {
            f"#{int(r['id'])} | {r['entry_date']} | {r['symbol']} ({r['quantity']} @ ${r['entry_price']}) [{r['status']}]": int(r["id"])
            for _, r in df_trades.iterrows()
        }
        sel_label = st.selectbox("בחר פעולה לעריכה / סגירה", options=list(options_map.keys()), key="edit_trade_sel")
        sel_id = options_map[sel_label]
        tr = df_trades[df_trades["id"] == sel_id].iloc[0]

        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1:
            new_status = st.selectbox(
                "סטטוס",
                ["Open", "Closed"],
                index=0 if tr["status"] == "Open" else 1,
                key=f"ed_st_{sel_id}",
            )
        with ec2:
            def_exit = float(tr["exit_price"]) if pd.notna(tr.get("exit_price")) else float(tr["entry_price"])
            new_exit = st.number_input("מחיר יציאה ($)", min_value=0.0, value=def_exit, step=0.1, key=f"ed_ex_{sel_id}")
        with ec3:
            def_sqty = float(tr["sell_quantity"]) if pd.notna(tr.get("sell_quantity")) else float(tr["quantity"])
            new_sqty = st.number_input("כמות נמכרת", min_value=0.0, value=def_sqty, step=0.1, key=f"ed_sq_{sel_id}")
        with ec4:
            def_cdt = pd.to_datetime(tr["close_date"]).date() if pd.notna(tr.get("close_date")) else date.today()
            new_cdt = st.date_input("תאריך סגירה", value=def_cdt, key=f"ed_cd_{sel_id}")

        ec5, ec6, ec7 = st.columns([1.0, 1.0, 1.2])
        with ec5:
            new_tax = st.number_input(
                "מס ששולם ($)",
                min_value=0.0,
                value=float(tr["tax_paid"]) if pd.notna(tr.get("tax_paid")) else 0.0,
                step=1.0,
                key=f"ed_tx_{sel_id}",
            )
        with ec6:
            new_fees = st.number_input(
                "עמלות ($)",
                min_value=0.0,
                value=float(tr["fees"]) if pd.notna(tr.get("fees")) else 0.0,
                step=0.5,
                key=f"ed_fe_{sel_id}",
            )
        with ec7:
            plan_opts = ["", "Yes", "No"]
            cur_plan = str(tr.get("according_to_plan") or "")
            new_plan = st.selectbox(
                "עמידה בתוכנית (According to Plan)",
                plan_opts,
                index=plan_opts.index(cur_plan) if cur_plan in plan_opts else 0,
                key=f"ed_pl_{sel_id}",
            )

        new_notes = st.text_area(
            "הערות ותחקור עסקה",
            value=str(tr.get("notes") or ""),
            key=f"ed_nt_{sel_id}",
        )

        b_save, b_del = st.columns([3.0, 1.0])
        with b_save:
            if st.button("שמור עדכון עסקה", type="primary", use_container_width=True):
                ep = float(tr["entry_price"])
                mult = 1.0 if str(tr.get("direction", "Long")) == "Long" else -1.0
                calc_net = round(((new_exit - ep) * new_sqty * mult) - new_tax - new_fees, 4) if new_status == "Closed" else None
                update_trade(
                    sel_id,
                    {
                        "status": new_status,
                        "exit_price": new_exit if new_status == "Closed" else None,
                        "sell_quantity": new_sqty if new_status == "Closed" else None,
                        "close_date": new_cdt.isoformat() if new_status == "Closed" else None,
                        "tax_paid": new_tax,
                        "fees": new_fees,
                        "net_pnl": calc_net,
                        "according_to_plan": new_plan or None,
                        "notes": new_notes.strip() or None,
                    },
                )
                st.success("העסקה עודכנה בהצלחה!")
                st.rerun()

        with b_del:
            if st.button("מחק שורה", use_container_width=True):
                delete_trade(sel_id)
                st.warning("השורה נמחקה.")
                st.rerun()


# === [SEC-04: TAB 2 - NEW TRADE ENTRY WITH AUTO-SNAPSHOT & INDICATOR COMBOS] ===
def render_new_trade_tab(df_market: pd.DataFrame) -> None:
    st.markdown("**פתיחת עסקה חדשה — משיכה אוטומטית של צילום המצב הטכני (Auto-Snapshot) וניתוח אינדיקטורים**")

    symbols = df_market["symbol"].tolist() if not df_market.empty else []
    c_sym, c_btn_auto, c_btn_ai = st.columns([2.2, 1.4, 1.6])

    with c_sym:
        if symbols:
            chosen_sym = st.selectbox("בחר מניה מהמאגר", options=symbols, key="nt_symbol_sel")
        else:
            chosen_sym = st.text_input("הזן טיקר", value="MSFT", key="nt_symbol_txt").strip().upper()

    with c_btn_auto:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("חשב MACD / CCI / Volume חי", use_container_width=True):
            with st.spinner("מחשב אינדיקטורים טכניים..."):
                ind = compute_live_entry_indicators(chosen_sym)
                st.session_state["nt_macd"] = ind["macd_status"]
                st.session_state["nt_cci_val"] = ind["cci_value"] if ind["cci_value"] is not None else 0.0
                st.session_state["nt_cci_st"] = ind["cci_status"]
                st.session_state["nt_vol_tr"] = ind["volume_trend"]
                st.toast("האינדיקטורים עודכנו אוטומטית!")

    with c_btn_ai:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("זהה נרות עם Gemini AI", use_container_width=True):
            with st.spinner("מנתח 12 נרות אחרונים..."):
                ok, c_pat, c_trd, reason = analyze_candles_with_gemini(
                    chosen_sym, st.session_state.get("user_candle_summary", "")
                )
                if ok:
                    st.session_state["nt_candle"] = c_pat
                    st.session_state["nt_candle_tr"] = c_trd
                    st.success(f"זיהוי AI: {reason}")
                else:
                    st.info(reason)

    with st.expander("סיכום הנרות האישי שלך (עבור זיהוי Gemini AI)", expanded=False):
        st.text_area(
            "הדבק כאן את כללי זיהוי הנרות מהסיכום שלך (לדוגמה: הגדרות Doji, Hammer, Morning Star וכו')",
            height=110,
            key="user_candle_summary",
        )

    # Pull snapshot defaults from stocks_snapshot
    snap_row = df_market[df_market["symbol"] == chosen_sym].iloc[0] if (not df_market.empty and chosen_sym in symbols) else None
    def_price = float(snap_row["display_price"]) if (snap_row is not None and pd.notna(snap_row.get("display_price"))) else 100.0
    def_atr = float(snap_row["atr_14"]) if (snap_row is not None and pd.notna(snap_row.get("atr_14"))) else 2.0
    comp_name = str(snap_row.get("company_name") or chosen_sym) if snap_row is not None else chosen_sym

    # Core Execution Fields
    r1_1, r1_2, r1_3, r1_4 = st.columns(4)
    with r1_1:
        entry_dt = st.date_input("תאריך כניסה", value=date.today(), key="nt_date")
    with r1_2:
        direction = st.selectbox("כיוון עסקה", ["Long", "Short"], key="nt_dir")
    with r1_3:
        entry_p = st.number_input("מחיר כניסה ($)", min_value=0.01, value=round(def_price, 2), step=0.1, key="nt_ep")
    with r1_4:
        qty = st.number_input("כמות מניות", min_value=0.0001, value=1.0, step=0.5, format="%.4f", key="nt_qty")

    r2_1, r2_2, r2_3, r2_4 = st.columns(4)
    with r2_1:
        def_sl = round(max(0.01, entry_p - (1.5 * def_atr)), 2)
        stop_loss = st.number_input("Stop Loss ($)", min_value=0.0, value=def_sl, step=0.1, key="nt_sl")
    with r2_2:
        def_tp = round(entry_p + (4.5 * def_atr), 2)
        take_profit = st.number_input("Take Profit ($)", min_value=0.0, value=def_tp, step=0.1, key="nt_tp")
    with r2_3:
        fees_in = st.number_input("עמלת קנייה ($)", min_value=0.0, value=0.0, step=0.5, key="nt_fees")
    with r2_4:
        risk = abs(entry_p - stop_loss)
        reward = abs(take_profit - entry_p)
        rr_str = f"1:{(reward / risk):.2f}" if risk > 0 and reward > 0 else "--"
        purchase_amt = round(entry_p * qty, 2)
        st.markdown(
            f"<div style='background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:10px; margin-top:22px; text-align:center;'>"
            f"<span style='color:#94A3B8; font-size:0.82rem;'>עלות: <b>${purchase_amt:,.2f}</b> | יחס R:R: <b style='color:#10B981;'>{rr_str}</b></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("**אינדיקטורי הסטאפ והתזמון (בחירה מובנית לניתוח סטטיסטי)**")

    s1_1, s1_2, s1_3, s1_4 = st.columns([1.4, 1.6, 0.9, 1.5])
    with s1_1:
        vol_trend = st.selectbox("Volume Trend", VOLUME_TREND_OPTIONS, key="nt_vol_tr")
    with s1_2:
        macd_st = st.selectbox("MACD (ויזואלי)", MACD_OPTIONS, key="nt_macd")
    with s1_3:
        cci_val = st.number_input("ערך CCI (20)", value=0.0, step=5.0, key="nt_cci_val")
    with s1_4:
        cci_st = st.selectbox("מצב CCI", CCI_OPTIONS, key="nt_cci_st")

    s2_1, s2_2, s2_3, s2_4 = st.columns(4)
    with s2_1:
        maj_tl = st.selectbox("Major Trend Line", TRENDLINE_OPTIONS, key="nt_maj_tl")
    with s2_2:
        min_tl = st.selectbox("Minor Trend Line", TRENDLINE_OPTIONS, key="nt_min_tl")
    with s2_3:
        gaps_st = st.selectbox("Gaps", GAPS_OPTIONS, key="nt_gaps")
    with s2_4:
        fib_st = st.selectbox("Fibonacci", FIBONACCI_OPTIONS, key="nt_fib")

    s3_1, s3_2, s3_3 = st.columns([1.4, 1.4, 1.8])
    with s3_1:
        candle_pat = st.selectbox("Candle (נר אחרון)", CANDLE_OPTIONS, key="nt_candle")
    with s3_2:
        candle_tr = st.selectbox("Candle Trend (מגמת נרות)", CANDLE_TREND_OPTIONS, key="nt_candle_tr")
    with s3_3:
        trade_notes = st.text_input("הערות כניסה / סיבת סטאפ", placeholder="לדוגמה: פולבק ל-MA50 + חציית MACD מעלה", key="nt_notes")

    if st.button("תעד עסקה חדשה + שמור Snapshot טכני מלא", type="primary", use_container_width=True):
        # Build snapshot dictionary from stocks_snapshot
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
                "rsi": float(snap_row["rsi"]) if pd.notna(snap_row.get("rsi")) else None,
                "atr_14": float(snap_row["atr_14"]) if pd.notna(snap_row.get("atr_14")) else None,
                "atr_pct": float(snap_row["atr_pct"]) if pd.notna(snap_row.get("atr_pct")) else None,
                "atr_squeeze_pct": float(snap_row["atr_squeeze_pct"]) if pd.notna(snap_row.get("atr_squeeze_pct")) else None,
                "rel_vol_5d": float(snap_row["rel_vol_5d"]) if pd.notna(snap_row.get("rel_vol_5d")) else None,
                "rel_vol_10d": float(snap_row["rel_vol_10d"]) if pd.notna(snap_row.get("rel_vol_10d")) else None,
                "rel_vol_15d": float(snap_row["rel_vol_15d"]) if pd.notna(snap_row.get("rel_vol_15d")) else None,
                "rel_vol_20d": float(snap_row["rel_vol_20d"]) if pd.notna(snap_row.get("rel_vol_20d")) else None,
                "rel_vol_30d": float(snap_row["rel_vol_30d"]) if pd.notna(snap_row.get("rel_vol_30d")) else None,
                "signal_status": "Neutral",
            }
            for prefix in ("d_s", "d_r", "w_s", "w_r"):
                for idx in range(1, 6):
                    col = f"{prefix}_{idx}"
                    snap_fields[col] = float(snap_row[col]) if pd.notna(snap_row.get(col)) else None

        payload = {
            "entry_date": entry_dt.isoformat(),
            "symbol": chosen_sym,
            "company_name": comp_name,
            "direction": direction,
            "entry_price": round(float(entry_p), 4),
            "quantity": round(float(qty), 4),
            "purchase_amount": purchase_amt,
            "stop_loss": round(float(stop_loss), 2) if stop_loss > 0 else None,
            "take_profit": round(float(take_profit), 2) if take_profit > 0 else None,
            "rr_ratio": rr_str if rr_str != "--" else None,
            "fees": round(float(fees_in), 2),
            "status": "Open",
            "notes": trade_notes.strip() or None,
            "volume_trend": vol_trend,
            "macd_status": macd_st,
            "cci_value": round(float(cci_val), 1),
            "cci_status": cci_st,
            "major_trend_line": maj_tl,
            "minor_trend_line": min_tl,
            "gaps_status": gaps_st,
            "fibonacci_status": fib_st,
            "candle_pattern": candle_pat,
            "candle_trend": candle_tr,
            **snap_fields,
        }
        insert_trade(payload)
        st.success(f"העסקה ב-{chosen_sym} נשמרה בהצלחה יחד עם צילום המצב הטכני המלא!")
        st.rerun()


# === [SEC-05: TAB 3 - EDUCATIONAL INDICATOR & SIGNAL SYNERGY GUIDE] ===
def render_indicator_guide_tab() -> None:
    st.markdown("### שילוב MACD + CCI (20) + RSI (14) לבניית איתותי מסחר")
    st.caption("טבלת הייחוס המהירה לבדיקת איכות הסטאפ לפני כניסה לעסקה (ובהמשך בבסיס מנוע הציון של שלב 5):")

    syn_df = pd.DataFrame(SIGNAL_SYNERGY_MATRIX).rename(
        columns={
            "setup": "תרחיש / סוג איתות",
            "macd": "מצב MACD",
            "cci": "מצב CCI (20)",
            "rsi": "טווח RSI (14)",
            "meaning": "משמעות ופעולה מומלצת",
        }
    )
    st.dataframe(syn_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    for sec in INDICATOR_GUIDE_SECTIONS:
        cards_html = []
        for item_title, color, desc in sec["items"]:
            cards_html.append(
                f'<div style="background:#0D111A; border:1px solid #1E2638; border-right:4px solid {color}; border-radius:10px; padding:12px 14px; margin-bottom:8px;">'
                f'<div style="font-size:0.95rem; font-weight:800; color:{color}; margin-bottom:4px;">{html.escape(item_title)}</div>'
                f'<div style="font-size:0.9rem; color:#E2E8F0; line-height:1.55;">{html.escape(desc)}</div>'
                f'</div>'
            )

        _html(
            f"""
            <div class="profile-box">
                <div style="font-size:1.08rem; font-weight:800; color:#F8FAFC; margin-bottom:4px;">{html.escape(sec["title"])}</div>
                <div style="font-size:0.84rem; color:#94A3B8; margin-bottom:12px;">{html.escape(sec["subtitle"])}</div>
                {"".join(cards_html)}
            </div>
            """
        )


# === [SEC-06: TAB 4 - CASH DEPOSITS & GOOGLE SHEETS CSV IMPORTER] ===
def render_cash_and_import_tab(df_cash: pd.DataFrame) -> None:
    c_left, c_right = st.columns([1.2, 1.3])

    with c_left:
        st.markdown("#### תיעוד הפקדה או משיכת מזומן (Cash)")
        tx_dt = st.date_input("תאריך תנועה", value=date.today(), key="cash_tx_dt")
        tx_tp = st.selectbox("סוג תנועה", ["Deposit (הפקדה)", "Withdrawal (משיכה)"], key="cash_tx_tp")
        tx_amt = st.number_input("סכום בדולרים ($)", min_value=1.0, value=500.0, step=50.0, key="cash_tx_amt")
        tx_nt = st.text_input("הערה", placeholder="לדוגמה: העברה חודשית לחשבון המסחר", key="cash_tx_nt")

        if st.button("שמור תנועת מזומן", type="primary", use_container_width=True):
            clean_type = "Deposit" if "Deposit" in tx_tp else "Withdrawal"
            insert_cash_tx(tx_dt.isoformat(), clean_type, tx_amt, tx_nt)
            st.success("תנועת המזומן נשמרה!")
            st.rerun()

        if not df_cash.empty:
            st.markdown("**היסטוריית הפקדות ומשיכות:**")
            disp_c = df_cash[["tx_date", "tx_type", "amount_usd", "related_symbol", "notes"]].rename(
                columns={
                    "tx_date": "תאריך",
                    "tx_type": "סוג",
                    "amount_usd": "סכום ($)",
                    "related_symbol": "טיקר מקושר",
                    "notes": "הערה",
                }
            )
            st.dataframe(disp_c, use_container_width=True, hide_index=True)

    with c_right:
        st.markdown("#### ייבוא היסטוריה מגיליון Google Sheets (לשונית Journal)")
        st.info(
            "ייצא את לשונית **Journal** לקובץ CSV והעלה אותו כאן. "
            "המערכת תייבא אוטומטית את כל העסקאות הפתוחות והסגורות, תנקה תאים ריקים, "
            "ותחלץ אוטומטית את כל ההפקדות מעמודת **Cash** לטבלת המזומנים (ללא כפילויות)."
        )
        uploaded_csv = st.file_uploader("בחר קובץ CSV של יומן המסחר", type=["csv"], key="journal_csv_uploader")
        if uploaded_csv is not None:
            df_up = pd.read_csv(uploaded_csv)
            st.caption(f"זוהו {len(df_up)} שורות בקובץ.")
            if st.button("הפעל ייבוא מלא ל-Supabase", type="primary", use_container_width=True):
                with st.spinner("מייבא עסקאות והפקדות מזומן..."):
                    n_trades, n_cash = import_journal_csv(df_up)
                    st.success(f"הייבוא הושלם! נוספו {n_trades} עסקאות ו-{n_cash} תנועות הפקדה.")
                    st.rerun()


# === [SEC-07: MAIN PAGE ORCHESTRATION] ===
def main() -> None:
    df_market = load_market_dataframe()
    price_map: dict[str, float] = {}
    if not df_market.empty:
        for _, r in df_market.iterrows():
            if pd.notna(r.get("display_price")):
                price_map[str(r["symbol"]).upper()] = float(r["display_price"])

    df_trades, df_cash = load_journal_data()
    render_journal_kpis(df_trades, df_cash, price_map)

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "פוזיציות ויומן עסקאות",
            "פתיחת עסקה חדשה (+ Auto-Snapshot)",
            "מדריך MACD / CCI / RSI ושילוב איתותים",
            "הפקדות מזומן וייבוא CSV",
        ]
    )

    with tab1:
        render_trades_tab(df_trades, price_map)

    with tab2:
        render_new_trade_tab(df_market)

    with tab3:
        render_indicator_guide_tab()

    with tab4:
        render_cash_and_import_tab(df_cash)


main()
