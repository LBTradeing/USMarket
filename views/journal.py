# === [SEC-01: IMPORTS & STYLING HELPERS] ===
import html
import math
from datetime import date, datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import load_market_dataframe
from journal_helpers import (
    compute_live_entry_indicators,
    load_journal_data,
    insert_trade,
    insert_cash_tx,
)
from views.journal_positions import render_positions_and_log_page

APP_FONT = "'Assistant', 'Rubik', sans-serif"


def _html(raw: str) -> None:
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _fmt_usd(val: float | None, signed: bool = False, decimals: int = 2) -> str:
    if val is None or pd.isna(val):
        return "--"
    v = float(val)
    fmt = f"{{:,.{decimals}f}}"
    if signed:
        sign = "+" if v > 0 else ("-" if v < 0 else "")
        return f"{sign}${fmt.format(abs(v))}"
    return f"${fmt.format(v)}"


def _ltr_num(text: str) -> str:
    return f'<span dir="ltr" style="display:inline-block; font-family:{APP_FONT} !important;">{text}</span>'


@st.cache_data(ttl=1800, show_spinner=False)
def get_live_usd_ils() -> float:
    try:
        import yfinance as yf
        hist = yf.Ticker("ILS=X").history(period="5d")
        if not hist.empty and "Close" in hist.columns:
            val = float(hist["Close"].dropna().iloc[-1])
            if 2.5 <= val <= 5.5:
                return round(val, 3)
    except Exception:
        pass
    return 3.65


def inject_journal_home_css() -> None:
    _html(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Rubik:wght@400;500;700;800&display=swap');

        .jh-card, .jh-card *, .jh-bottom-grid, .jh-bottom-grid * {{
            font-family: {APP_FONT} !important;
        }}
        .jh-card {{
            background: linear-gradient(180deg, #111622 0%, #0D111A 100%);
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 10px;
            min-height: 126px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            direction: rtl;
            text-align: right;
            transition: border-color 0.2s ease;
        }}
        .jh-card-r2 {{
            min-height: 142px;
        }}
        .jh-card:hover {{
            border-color: #334155;
        }}
        .jh-title-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}
        .jh-title {{
            font-family: {APP_FONT} !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            color: #CBD5E1 !important;
            text-align: right;
            direction: rtl;
            line-height: 1.3;
        }}
        .jh-fx-badge {{
            font-family: {APP_FONT} !important;
            font-size: 0.74rem;
            font-weight: 700;
            color: #38BDF8;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.28);
            border-radius: 999px;
            padding: 2px 9px;
            direction: ltr;
            white-space: nowrap;
        }}
        .jh-value {{
            font-family: {APP_FONT} !important;
            font-size: 1.54rem;
            font-weight: 800;
            line-height: 1.25;
            text-align: right !important;
            direction: rtl;
            width: 100%;
            margin-bottom: 4px;
        }}
        .jh-ils-inline {{
            font-family: {APP_FONT} !important;
            font-size: 0.96rem;
            font-weight: 700;
            color: #38BDF8;
            margin-right: 10px;
            direction: ltr;
            display: inline-block;
        }}
        .jh-sub {{
            font-family: {APP_FONT} !important;
            font-size: 0.8rem;
            color: #64748B;
            line-height: 1.4;
            text-align: right;
            direction: rtl;
        }}
        /* Split cells inside Avg Trade & Best/Worst cards */
        .jh-split-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            align-items: center;
            margin: 4px 0 6px 0;
        }}
        .jh-split-right {{
            border-left: 1px solid #1E2638;
            padding-left: 10px;
            text-align: right;
        }}
        .jh-split-left {{
            padding-right: 4px;
            text-align: right;
        }}
        .jh-mini-lbl {{
            font-size: 0.75rem;
            color: #64748B;
            margin-bottom: 2px;
        }}
        .jh-split-val {{
            font-size: 1.28rem;
            font-weight: 800;
            line-height: 1.2;
        }}
        .jh-ticker-pill {{
            font-size: 0.74rem;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 7px;
            letter-spacing: 0.4px;
            direction: ltr;
            display: inline-block;
        }}
        .jh-pill-win {{
            color: #10B981;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}
        .jh-pill-loss {{
            color: #EF4444;
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.35);
        }}
        /* Progress bars */
        .jh-bar-track {{
            width: 100%;
            height: 7px;
            background: #1A2234;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 4px;
        }}
        .jh-bar-fill-blue {{
            height: 100%;
            background: linear-gradient(90deg, #2563EB, #38BDF8);
            border-radius: 999px;
        }}
        .jh-split-bar {{
            display: flex;
            width: 100%;
            height: 7px;
            border-radius: 999px;
            overflow: hidden;
            gap: 2px;
            margin-top: 4px;
        }}
        /* Bottom 3-card Equal-Height CSS Grid */
        .jh-bottom-grid {{
            display: grid;
            grid-template-columns: 1.35fr 1fr 1fr;
            gap: 14px;
            align-items: stretch;
            direction: rtl;
            margin-top: 6px;
        }}
        .jh-bottom-grid .jh-card {{
            margin-bottom: 0;
            height: 100%;
        }}
        .jh-sub-box {{
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 12px;
            padding: 11px 14px;
        }}
        .jh-pulse-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: #0A0E17;
            border: 1px solid #1A2234;
            border-radius: 10px;
            margin-bottom: 7px;
            font-size: 0.85rem;
            direction: rtl;
        }}
        .jh-pulse-row:last-child {{
            margin-bottom: 0;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: linear-gradient(180deg, #111622 0%, #0D111A 100%) !important;
            border: 1px solid #1E2638 !important;
            border-radius: 16px !important;
            padding: 14px 16px 8px 16px !important;
        }}
        div[data-testid="stDialog"] input[type="text"] {{
            text-transform: uppercase !important;
            font-weight: 700 !important;
            letter-spacing: 0.8px !important;
        }}
        </style>
        """
    )


# === [SEC-02: MODAL DIALOGS - DEPOSIT & NEW LONG TRADE] ===
@st.dialog("הפקדה לחשבון המסחר", width="small")
def open_deposit_dialog() -> None:
    st.caption("תיעוד הפקדת מזומן חדשה לחשבון המסחר")
    dep_amount = st.number_input(
        "סכום הפקדה בדולרים ($)",
        min_value=1.0,
        value=1000.0,
        step=100.0,
        format="%.2f",
        key="dlg_dep_amount",
    )
    dep_date = st.date_input(
        "תאריך הפקדה",
        value=date.today(),
        key="dlg_dep_date",
    )
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    if st.button("שמור הפקדה", type="primary", use_container_width=True):
        insert_cash_tx(dep_date.isoformat(), "Deposit", dep_amount, "הפקדה דרך יומן מסחר")
        st.success(f"הופקדו ${dep_amount:,.2f} בהצלחה!")
        st.rerun()


@st.dialog("פתיחת עסקה חדשה", width="small")
def open_new_trade_dialog(df_market: pd.DataFrame) -> None:
    raw_ticker = st.text_input(
        "Ticker (סימול מניה)",
        placeholder="לדוגמה: MSFT",
        key="dlg_trade_ticker",
    )
    clean_ticker = "".join(ch for ch in raw_ticker.strip().upper() if ch.isalnum() or ch in (".", "-"))

    snap_row = None
    default_price = 100.0
    comp_name = clean_ticker
    if clean_ticker and not df_market.empty:
        matches = df_market[df_market["symbol"].str.upper().str.endswith(clean_ticker)]
        exact = df_market[df_market["symbol"].str.upper() == clean_ticker]
        chosen_df = exact if not exact.empty else matches
        if not chosen_df.empty:
            snap_row = chosen_df.iloc[0]
            comp_name = str(snap_row.get("company_name") or clean_ticker)
            if pd.notna(snap_row.get("display_price")):
                default_price = float(snap_row["display_price"])

    if clean_ticker:
        _html(
            f"""
            <div style="background:#0D111A; border:1px solid #1E2638; border-radius:10px; padding:8px 12px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#94A3B8; font-size:0.82rem;">{html.escape(comp_name)}</span>
                <span style="color:#38BDF8; font-weight:800; font-size:0.95rem; direction:ltr;">{html.escape(clean_ticker)}</span>
            </div>
            """
        )

    entry_dt = st.date_input("תאריך כניסה", value=date.today(), key="dlg_trade_date")

    c_qty, c_price = st.columns(2)
    with c_qty:
        qty = st.number_input(
            "כמות מניות",
            min_value=0.0001,
            value=1.0,
            step=1.0,
            format="%.4f",
            key="dlg_trade_qty",
        )
    with c_price:
        buy_price = st.number_input(
            "שער קנייה ($)",
            min_value=0.01,
            value=round(default_price, 2),
            step=0.1,
            format="%.2f",
            key="dlg_trade_price",
        )

    invested_total = round(qty * buy_price, 2)
    _html(
        f"""
        <div style="background:linear-gradient(90deg, rgba(16,185,129,0.12) 0%, rgba(13,17,26,0.95) 100%);
                    border:1px solid rgba(16,185,129,0.35); border-radius:12px; padding:12px 14px; margin:10px 0 14px 0;
                    display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#CBD5E1; font-size:0.86rem; font-weight:700;">סכום השקעה מחושב</span>
            <span style="color:#10B981; font-size:1.25rem; font-weight:800; direction:ltr;">${invested_total:,.2f}</span>
        </div>
        """
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

            payload = {
                "entry_date": entry_dt.isoformat(),
                "symbol": clean_ticker,
                "company_name": comp_name,
                "direction": "Long",
                "entry_price": round(float(buy_price), 4),
                "quantity": round(float(qty), 4),
                "purchase_amount": invested_total,
                "status": "Open",
                "volume_trend": live_ind.get("volume_trend"),
                "macd_status": live_ind.get("macd_status"),
                "cci_value": live_ind.get("cci_value"),
                "cci_status": live_ind.get("cci_status"),
                **snap_fields,
            }
            insert_trade(payload)

        st.success(f"עסקת Long ב-{clean_ticker} נפתחה בהצלחה!")
        st.rerun()


# === [SEC-03: METRICS CALCULATION ENGINE] ===
def compute_dashboard_metrics(
    df_trades: pd.DataFrame,
    df_cash: pd.DataFrame,
    price_map: dict[str, float],
    usd_ils: float,
) -> dict:
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
    open_positions_list = []

    for _, r in open_df.iterrows():
        sym = str(r["symbol"]).upper()
        ep = float(r["entry_price"])
        qty = float(r["quantity"])
        cost = ep * qty
        invested_open += cost
        live_p = price_map.get(sym, ep)
        pnl_u = (live_p - ep) * qty
        pnl_pct = ((live_p - ep) / ep * 100.0) if ep > 0 else 0.0
        open_pnl += pnl_u
        sl_val = float(r["stop_loss"]) if pd.notna(r.get("stop_loss")) else None
        open_positions_list.append(
            {
                "symbol": sym,
                "qty": qty,
                "entry_price": ep,
                "stop_loss": sl_val,
                "cost": cost,
                "live_p": live_p,
                "pnl": pnl_u,
                "pnl_pct": pnl_pct,
            }
        )

    realized_pnl = float(closed_df["net_pnl"].fillna(0).sum()) if not closed_df.empty else 0.0
    tax_paid = float(closed_df["tax_paid"].fillna(0).sum()) if not closed_df.empty else 0.0
    fees_paid = float(df_trades["fees"].fillna(0).sum()) if not df_trades.empty else 0.0

    available_cash = total_deposits + realized_pnl - invested_open
    account_value = available_cash + invested_open + open_pnl
    account_value_ils = round(account_value * usd_ils, 0)
    exposure_pct = (invested_open / account_value * 100.0) if account_value > 0 else 0.0

    wins_df = closed_df[closed_df["net_pnl"].fillna(0) > 0] if not closed_df.empty else pd.DataFrame()
    losses_df = closed_df[closed_df["net_pnl"].fillna(0) < 0] if not closed_df.empty else pd.DataFrame()
    n_wins = len(wins_df)
    n_losses = len(losses_df)
    n_closed = len(closed_df)
    n_open = len(open_df)
    n_total = len(df_trades)

    win_rate = (n_wins / n_closed * 100.0) if n_closed > 0 else 0.0
    avg_win = float(wins_df["net_pnl"].mean()) if n_wins > 0 else 0.0
    avg_loss = float(losses_df["net_pnl"].mean()) if n_losses > 0 else 0.0

    best_val = float(closed_df["net_pnl"].max()) if n_closed > 0 else 0.0
    best_sym = str(closed_df.loc[closed_df["net_pnl"].idxmax(), "symbol"]) if n_closed > 0 else "--"
    worst_val = float(closed_df["net_pnl"].min()) if n_closed > 0 else 0.0
    worst_sym = str(closed_df.loc[closed_df["net_pnl"].idxmin(), "symbol"]) if n_closed > 0 else "--"

    plan_valid = df_trades["according_to_plan"].dropna() if not df_trades.empty else pd.Series(dtype=str)
    plan_yes = int((plan_valid == "Yes").sum())
    plan_total = int(len(plan_valid))
    plan_no = max(0, plan_total - plan_yes)
    plan_rate = float(plan_yes / plan_total * 100.0) if plan_total > 0 else 0.0

    if n_closed >= 2:
        std_pnl = float(closed_df["net_pnl"].std())
        mean_abs = float(closed_df["net_pnl"].abs().mean())
        stability = max(0.0, min(100.0, 100.0 - (std_pnl / (mean_abs + 1e-6)) * 25.0))
        consistency_score = round((plan_rate * 0.65) + (stability * 0.35), 1)
    else:
        consistency_score = round(plan_rate, 1)

    streak_count = 0
    streak_dir = 0  # 1 = wins, -1 = losses, 0 = neutral
    if not closed_df.empty and "close_date" in closed_df.columns:
        c_sorted = closed_df.dropna(subset=["close_date", "net_pnl"]).sort_values(["close_date", "id"])
        if not c_sorted.empty:
            vals = c_sorted["net_pnl"].tolist()
            last_sign = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
            if last_sign != 0:
                streak_dir = last_sign
                for v in reversed(vals):
                    if (last_sign > 0 and v > 0) or (last_sign < 0 and v < 0):
                        streak_count += 1
                    else:
                        break

    now_dt = datetime.now()
    now_ym = now_dt.strftime("%Y-%m")
    month_label = now_dt.strftime("%b %Y")
    month_closed_pnl = 0.0
    month_closed_cnt = 0
    month_opened_cnt = 0
    month_deposits = 0.0
    if not closed_df.empty and "close_date" in closed_df.columns:
        m_c = closed_df[closed_df["close_date"].astype(str).str.startswith(now_ym)]
        month_closed_pnl = float(m_c["net_pnl"].fillna(0).sum())
        month_closed_cnt = len(m_c)
    if not df_trades.empty and "entry_date" in df_trades.columns:
        m_o = df_trades[df_trades["entry_date"].astype(str).str.startswith(now_ym)]
        month_opened_cnt = len(m_o)
    if not df_cash.empty and "tx_date" in df_cash.columns:
        m_d = df_cash[(df_cash["tx_date"].astype(str).str.startswith(now_ym)) & (df_cash["tx_type"] == "Deposit")]
        month_deposits = float(m_d["amount_usd"].sum())

    return {
        "account_value": account_value,
        "account_value_ils": account_value_ils,
        "usd_ils": usd_ils,
        "invested_open": invested_open,
        "available_cash": available_cash,
        "realized_pnl": realized_pnl,
        "open_pnl": open_pnl,
        "tax_paid": tax_paid,
        "fees_paid": fees_paid,
        "total_deposits": total_deposits,
        "win_rate": win_rate,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "n_closed": n_closed,
        "n_open": n_open,
        "n_total": n_total,
        "exposure_pct": exposure_pct,
        "consistency_score": consistency_score,
        "plan_rate": plan_rate,
        "plan_yes": plan_yes,
        "plan_no": plan_no,
        "plan_total": plan_total,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "best_val": best_val,
        "best_sym": best_sym,
        "worst_val": worst_val,
        "worst_sym": worst_sym,
        "open_positions_list": sorted(open_positions_list, key=lambda x: abs(x["pnl"]), reverse=True),
        "streak_count": streak_count,
        "streak_dir": streak_dir,
        "month_label": month_label,
        "month_closed_pnl": month_closed_pnl,
        "month_closed_cnt": month_closed_cnt,
        "month_opened_cnt": month_opened_cnt,
        "month_deposits": month_deposits,
    }


# === [SEC-04: EQUITY MILESTONES BUILDER & CHARTS] ===
def _build_equity_milestones(events: list[dict], target_points: int = 24) -> list[dict]:
    if not events:
        return []

    ev_df = pd.DataFrame(events).sort_values("dt")
    atomic: list[dict] = []
    running_eq = 0.0

    for dt_val, grp in ev_df.groupby("dt"):
        dep_d = float(grp[grp["kind"] == "deposit"]["delta"].sum())
        trd_d = float(grp[grp["kind"] == "trade"]["delta"].sum())
        if dep_d != 0:
            running_eq += dep_d
            atomic.append(
                {
                    "dt": dt_val,
                    "kind": "deposit",
                    "delta": round(dep_d, 2),
                    "y": round(running_eq, 2),
                }
            )
        if trd_d != 0 or dep_d == 0:
            running_eq += trd_d
            atomic.append(
                {
                    "dt": dt_val,
                    "kind": "profit" if trd_d >= 0 else "loss",
                    "delta": round(trd_d, 2),
                    "y": round(running_eq, 2),
                }
            )

    if len(atomic) <= target_points:
        return [
            {
                "short_lbl": item["dt"].strftime("%d/%m"),
                "hover_date": item["dt"].strftime("%d/%m/%Y"),
                "kind": item["kind"],
                "delta": item["delta"],
                "y": item["y"],
            }
            for item in atomic
        ]

    segments: list[list[dict]] = []
    curr_trade_run: list[dict] = []
    for item in atomic:
        if item["kind"] == "deposit":
            if curr_trade_run:
                segments.append(curr_trade_run)
                curr_trade_run = []
            segments.append([item])
        else:
            curr_trade_run.append(item)
    if curr_trade_run:
        segments.append(curr_trade_run)

    n_deposits = sum(1 for s in segments if s[0]["kind"] == "deposit")
    total_trades = sum(len(s) for s in segments if s[0]["kind"] != "deposit")
    available_trade_slots = max(8, target_points - n_deposits)
    bucket_size = max(1, math.ceil(total_trades / available_trade_slots))

    milestones: list[dict] = []
    for seg in segments:
        if seg[0]["kind"] == "deposit":
            it = seg[0]
            milestones.append(
                {
                    "short_lbl": it["dt"].strftime("%d/%m"),
                    "hover_date": it["dt"].strftime("%d/%m/%Y"),
                    "kind": "deposit",
                    "delta": it["delta"],
                    "y": it["y"],
                }
            )
        else:
            for idx in range(0, len(seg), bucket_size):
                chunk = seg[idx : idx + bucket_size]
                agg_delta = round(sum(c["delta"] for c in chunk), 2)
                end_eq = chunk[-1]["y"]
                d_start = chunk[0]["dt"].strftime("%d/%m/%Y")
                d_end = chunk[-1]["dt"].strftime("%d/%m/%Y")
                hover_dt = d_end if len(chunk) == 1 else f"{d_start} – {d_end} ({len(chunk)} ימי סגירה)"
                milestones.append(
                    {
                        "short_lbl": chunk[-1]["dt"].strftime("%d/%m"),
                        "hover_date": hover_dt,
                        "kind": "profit" if agg_delta >= 0 else "loss",
                        "delta": agg_delta,
                        "y": end_eq,
                    }
                )
    return milestones


def render_charts_row(df_trades: pd.DataFrame, df_cash: pd.DataFrame) -> None:
    col_right_eq, col_left_daily = st.columns(2)
    closed_df = df_trades[df_trades["status"] == "Closed"].copy() if not df_trades.empty else pd.DataFrame()

    # --- Right Chart: Equity Curve ---
    with col_right_eq:
        with st.container(border=True):
            hdr_c1, hdr_c2 = st.columns([1.15, 1.35])
            with hdr_c1:
                _html(
                    f'<div class="jh-title" style="padding-top:4px;">'
                    f'צמיחת הון - Equity Curve'
                    f'</div>'
                )
            with hdr_c2:
                eq_mode = st.radio(
                    "מצב גרף",
                    ["כולל הפקדות", "רווח/הפסד מסחר בלבד"],
                    horizontal=True,
                    label_visibility="collapsed",
                    key="eq_curve_mode",
                )

            events = []
            if eq_mode == "כולל הפקדות" and not df_cash.empty:
                for _, r in df_cash.iterrows():
                    dt_v = pd.to_datetime(r["tx_date"], errors="coerce")
                    amt = float(r["amount_usd"])
                    if pd.notna(dt_v) and amt > 0:
                        signed_amt = amt if r["tx_type"] == "Deposit" else -amt
                        events.append({"dt": dt_v, "kind": "deposit", "delta": signed_amt})

            if not closed_df.empty:
                for _, r in closed_df.iterrows():
                    dt_v = pd.to_datetime(r["close_date"], errors="coerce")
                    pnl_v = float(r["net_pnl"]) if pd.notna(r.get("net_pnl")) else 0.0
                    if pd.notna(dt_v):
                        events.append({"dt": dt_v, "kind": "trade", "delta": pnl_v})

            view_pts = _build_equity_milestones(events, target_points=24)

            if view_pts:
                fig_eq = go.Figure()
                for i in range(1, len(view_pts)):
                    p0 = view_pts[i - 1]
                    p1 = view_pts[i]
                    if p1["kind"] == "deposit":
                        seg_color = "#38BDF8"
                    elif p1["y"] >= p0["y"]:
                        seg_color = "#10B981"
                    else:
                        seg_color = "#EF4444"

                    fig_eq.add_trace(
                        go.Scatter(
                            x=[i - 1, i],
                            y=[p0["y"], p1["y"]],
                            mode="lines",
                            line=dict(color=seg_color, width=3.2),
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )

                pt_colors = [
                    "#38BDF8" if p["kind"] == "deposit" else ("#10B981" if p["kind"] == "profit" else "#EF4444")
                    for p in view_pts
                ]
                pt_symbols = ["diamond" if p["kind"] == "deposit" else "circle" for p in view_pts]
                pt_texts = [
                    f"<b>{p['hover_date']}</b><br>{'הפקדת הון' if p['kind'] == 'deposit' else 'תוצאת מסחר מצטברת'}: {p['delta']:+,.2f}$<br>שווי חשבון: ${p['y']:,.2f}"
                    for p in view_pts
                ]
                fig_eq.add_trace(
                    go.Scatter(
                        x=list(range(len(view_pts))),
                        y=[p["y"] for p in view_pts],
                        mode="markers",
                        marker=dict(color=pt_colors, size=7.5, symbol=pt_symbols, line=dict(width=1, color="#0B0E14")),
                        text=pt_texts,
                        hovertemplate="%{text}<extra></extra>",
                        showlegend=False,
                    )
                )

                n_pts = len(view_pts)
                step = max(1, (n_pts - 1) // 7)
                tick_idx = sorted(list(set([0] + list(range(step, n_pts - 1, step)) + [n_pts - 1])))
                tick_lbl = [view_pts[idx]["short_lbl"] for idx in tick_idx]

                fig_eq.update_layout(
                    height=265,
                    margin=dict(l=54, r=18, t=12, b=46),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Assistant, Rubik, sans-serif", color="#94A3B8", size=11),
                    xaxis=dict(
                        showgrid=False,
                        tickmode="array",
                        tickvals=tick_idx,
                        ticktext=tick_lbl,
                        tickangle=0,
                        tickfont=dict(size=10.5),
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#1E2638",
                        zeroline=True,
                        zerolinecolor="#334155",
                        tickprefix="$",
                        tickfont=dict(size=10.5),
                    ),
                )
                st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})
                _html(
                    f'<div style="display:flex; gap:16px; justify-content:flex-start; direction:rtl; font-family:{APP_FONT} !important; font-size:0.78rem; color:#94A3B8; padding:0 4px 2px 4px;">'
                    '<span><b style="color:#10B981;">●</b> רווח מעסקה</span>'
                    '<span><b style="color:#EF4444;">●</b> הפסד מעסקה</span>'
                    '<span><b style="color:#38BDF8;">◆</b> הפקדת הון</span>'
                    '</div>'
                )
            else:
                st.info("אין עדיין נתונים להצגת עקומת ההון.")

    # --- Left Chart: Daily P/L Bar Chart ---
    with col_left_daily:
        with st.container(border=True):
            _html(
                f'<div style="display:flex; justify-content:space-between; align-items:center; direction:rtl; padding-top:4px; margin-bottom:2px; font-family:{APP_FONT} !important;">'
                f'<span class="jh-title">רווח / הפסד יומי - Daily P/L</span>'
                f'<span style="font-size:0.76rem; color:#64748B;">14 ימי מסחר אחרונים</span>'
                f'</div>'
            )
            if not closed_df.empty and closed_df["close_date"].notna().any():
                closed_df["dt"] = pd.to_datetime(closed_df["close_date"], errors="coerce")
                daily = (
                    closed_df.dropna(subset=["dt"])
                    .groupby("dt")["net_pnl"]
                    .sum()
                    .sort_index()
                    .tail(14)
                )
                x_short = [d.strftime("%d/%m") for d in daily.index]
                x_full = [d.strftime("%d/%m/%Y") for d in daily.index]
                y_vals = [round(float(v), 2) for v in daily.values]
                bar_colors = ["#10B981" if v >= 0 else "#EF4444" for v in y_vals]

                fig_bar = go.Figure(
                    data=[
                        go.Bar(
                            x=x_short,
                            y=y_vals,
                            customdata=x_full,
                            marker_color=bar_colors,
                            marker_line_width=0,
                            hovertemplate="<b>%{customdata}</b><br>רווח/הפסד: $%{y:,.2f}<extra></extra>",
                        )
                    ]
                )
                fig_bar.update_layout(
                    height=291,
                    margin=dict(l=50, r=16, t=12, b=46),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Assistant, Rubik, sans-serif", color="#94A3B8", size=11),
                    xaxis=dict(
                        showgrid=False,
                        tickangle=-25,
                        tickfont=dict(size=10.5),
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#1E2638",
                        zeroline=True,
                        zerolinecolor="#334155",
                        tickprefix="$",
                        tickfont=dict(size=10.5),
                    ),
                    bargap=0.32,
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("אין עדיין עסקאות סגורות להצגה בגרף היומי.")


# === [SEC-05: MAIN JOURNAL HOME DASHBOARD VIEW] ===
def render_journal_home() -> None:
    inject_journal_home_css()
    df_market = load_market_dataframe()
    price_map: dict[str, float] = {}
    if not df_market.empty:
        for _, r in df_market.iterrows():
            if pd.notna(r.get("display_price")):
                price_map[str(r["symbol"]).upper()] = float(r["display_price"])

    usd_ils = get_live_usd_ils()
    df_trades, df_cash = load_journal_data()
    m = compute_dashboard_metrics(df_trades, df_cash, price_map, usd_ils)

    # Top Action Buttons aligned to the RIGHT
    btn_col1, btn_col2, _spacer = st.columns([1.15, 1.0, 3.1])
    with btn_col1:
        if st.button("＋ פתיחת עסקה חדשה", type="primary", use_container_width=True):
            open_new_trade_dialog(df_market)
    with btn_col2:
        if st.button("＋ הפקדה לחשבון", use_container_width=True):
            open_deposit_dialog()

    # === ROW 1: 8 Capital, P/L, Tax, Fees & Deposits Cards (4 x 2 Grid) ===
    ils_formatted = f"₪{m['account_value_ils']:,.0f}"
    account_val_html = (
        f'{_ltr_num(_fmt_usd(m["account_value"]))}'
        f'<span class="jh-ils-inline">({ils_formatted})</span>'
    )
    account_badge_html = f'<span class="jh-fx-badge">USD/ILS {m["usd_ils"]:.3f} ₪</span>'

    row1_cards = [
        (
            "שווי חשבון - Account Value",
            account_badge_html,
            account_val_html,
            "#F8FAFC",
            "הון פנוי + שווי פוזיציות פתוחות (מומר לש״ח)",
        ),
        (
            "הון מושקע - Invested Capital",
            "",
            _ltr_num(_fmt_usd(m["invested_open"])),
            "#60A5FA",
            f"מושקע כעת ב-{m['n_open']} פוזיציות",
        ),
        (
            "הון פנוי - Available Cash",
            "",
            _ltr_num(_fmt_usd(m["available_cash"])),
            "#38BDF8" if m["available_cash"] >= 0 else "#EF4444",
            "מזומן זמין לפתיחת עסקאות",
        ),
        (
            "רווח / הפסד כולל - Total Net P/L",
            "",
            _ltr_num(_fmt_usd(m["realized_pnl"], signed=True)),
            "#10B981" if m["realized_pnl"] >= 0 else "#EF4444",
            "נטו ממומש לאחר מס ועמלות",
        ),
        (
            "רווח / הפסד פתוח - Open P/L",
            "",
            _ltr_num(_fmt_usd(m["open_pnl"], signed=True)),
            "#10B981" if m["open_pnl"] >= 0 else "#EF4444",
            "שינוי חי בעסקאות הפעילות כרגע",
        ),
        (
            "מס ששולם - Tax Paid",
            "",
            _ltr_num(_fmt_usd(m["tax_paid"])),
            "#F59E0B",
            "סה״כ מס שנוכה מעסקאות סגורות",
        ),
        (
            "עמלות - Commissions",
            "",
            _ltr_num(_fmt_usd(m["fees_paid"])),
            "#CBD5E1",
            "סה״כ עמלות קנייה ומכירה",
        ),
        (
            "סה״כ הפקדות - Total Deposits",
            "",
            _ltr_num(_fmt_usd(m["total_deposits"])),
            "#A78BFA",
            "סך כל ההפקדות לחשבון המסחר",
        ),
    ]

    for batch_start in (0, 4):
        cols = st.columns(4)
        for col, (title, badge_html, val_html, color, sub) in zip(cols, row1_cards[batch_start : batch_start + 4]):
            with col:
                _html(
                    f"""
                    <div class="jh-card">
                        <div class="jh-title-row">
                            <div class="jh-title">{title}</div>
                            {badge_html}
                        </div>
                        <div class="jh-value" style="color:{color};">{val_html}</div>
                        <div class="jh-sub">{sub}</div>
                    </div>
                    """
                )

    # === ROW 2A: Win Rate (with Arc Gauge), Total Trades, Current Exposure (with Ratio & Progress Bar) ===
    r2_c1, r2_c2, r2_c3 = st.columns(3)

    with r2_c1:
        wr_val = max(0.0, min(100.0, float(m["win_rate"])))
        wr_color = "#10B981" if wr_val >= 50 else "#F59E0B"
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">אחוזי הצלחה - Win Rate</div>
                <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
                    <div>
                        <div class="jh-value" style="color:{wr_color}; margin-bottom:6px;">{_ltr_num(f"{wr_val:.1f}%")}</div>
                        <div class="jh-sub">
                            <span style="color:#10B981; font-weight:700;">{m['n_wins']} רווחיות</span> &nbsp;|&nbsp;
                            <span style="color:#EF4444; font-weight:700;">{m['n_losses']} מפסידות</span>
                        </div>
                    </div>
                    <svg viewBox="0 0 100 58" width="96" height="56" style="flex-shrink:0; overflow:visible;">
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="rgba(239,68,68,0.28)" stroke-width="10" stroke-linecap="round" />
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#10B981" stroke-width="10" stroke-linecap="round" pathLength="100" stroke-dasharray="{wr_val:.1f} 100" />
                    </svg>
                </div>
            </div>
            """
        )

    with r2_c2:
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">כמות טריידים - Total Trades</div>
                <div class="jh-value" style="color:#F8FAFC;">{_ltr_num(f"{m['n_total']}")}</div>
                <div class="jh-sub">
                    <span style="color:#60A5FA; font-weight:700;">{m['n_open']} פתוחים</span> &nbsp;|&nbsp;
                    <span style="color:#94A3B8; font-weight:700;">{m['n_closed']} סגורים</span>
                </div>
            </div>
            """
        )

    with r2_c3:
        exp_val = max(0.0, float(m["exposure_pct"]))
        exp_bar_w = min(100.0, exp_val)
        exp_color = "#F8FAFC" if exp_val <= 85 else "#F59E0B"
        ratio_str = f"${m['invested_open']:,.0f} / ${m['account_value']:,.0f}"
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">חשיפה נוכחית - Current Exposure</div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin:2px 0 4px 0;">
                    <span class="jh-value" style="color:{exp_color}; width:auto; margin:0;">{_ltr_num(f"{exp_val:.1f}%")}</span>
                    <span dir="ltr" style="font-size:0.84rem; font-weight:700; color:#94A3B8;">{ratio_str}</span>
                </div>
                <div class="jh-bar-track">
                    <div class="jh-bar-fill-blue" style="width:{exp_bar_w:.1f}%;"></div>
                </div>
            </div>
            """
        )

    # === ROW 2B: Consistency Score, Avg Trade P/L, Best/Worst Trade ===
    r2_c4, r2_c5, r2_c6 = st.columns(3)

    with r2_c4:
        cons_color = "#10B981" if m["consistency_score"] >= 75 else "#38BDF8"
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">ציון עקביות - Consistency Score</div>
                <div class="jh-value" style="color:{cons_color};">{_ltr_num(f"{m['consistency_score']:.1f}%")}</div>
                <div class="jh-sub">
                    עמידה בתוכנית המסחר: <b style="color:#CBD5E1;">{m['plan_yes']} מתוך {m['plan_total']}</b> עסקאות מתועדות
                </div>
            </div>
            """
        )

    with r2_c5:
        aw = float(m["avg_win"])
        al = abs(float(m["avg_loss"]))
        tot_a = aw + al
        win_share = (aw / tot_a * 100.0) if tot_a > 0 else 50.0
        loss_share = 100.0 - win_share
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">ממוצע עסקה - Avg Trade P/L</div>
                <div class="jh-split-grid">
                    <div class="jh-split-right">
                        <div class="jh-mini-lbl">רווח ממוצע</div>
                        <div class="jh-split-val" style="color:#10B981;">{_ltr_num(f"+${aw:,.2f}")}</div>
                    </div>
                    <div class="jh-split-left">
                        <div class="jh-mini-lbl">הפסד ממוצע</div>
                        <div class="jh-split-val" style="color:#EF4444;">{_ltr_num(f"-${al:,.2f}")}</div>
                    </div>
                </div>
                <div class="jh-split-bar">
                    <div style="width:{win_share:.1f}%; background:#10B981;"></div>
                    <div style="width:{loss_share:.1f}%; background:#EF4444;"></div>
                </div>
            </div>
            """
        )

    with r2_c6:
        b_sym = html.escape(str(m["best_sym"]))
        w_sym = html.escape(str(m["worst_sym"]))
        _html(
            f"""
            <div class="jh-card jh-card-r2">
                <div class="jh-title">הטובה / הגרועה - Best / Worst Trade</div>
                <div class="jh-split-grid" style="margin-bottom:2px;">
                    <div class="jh-split-right">
                        <div class="jh-mini-lbl">העסקה הטובה ביותר</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:4px; flex-wrap:wrap;">
                            <span class="jh-split-val" style="color:#10B981;">{_ltr_num(f"+${m['best_val']:,.2f}")}</span>
                            <span class="jh-ticker-pill jh-pill-win">{b_sym}</span>
                        </div>
                    </div>
                    <div class="jh-split-left">
                        <div class="jh-mini-lbl">העסקה הגרועה ביותר</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:4px; flex-wrap:wrap;">
                            <span class="jh-split-val" style="color:#EF4444;">{_ltr_num(f"-${abs(m['worst_val']):,.2f}")}</span>
                            <span class="jh-ticker-pill jh-pill-loss">{w_sym}</span>
                        </div>
                    </div>
                </div>
            </div>
            """
        )

    # === ROW 3: Charts ===
    render_charts_row(df_trades, df_cash)

    # === ROW 4: Equal-Height HTML Grid for Active Positions, Streak & Discipline, Monthly Pulse ===
    # 1. Active Positions Pulse
    top_pos = m["open_positions_list"][:4]
    if top_pos:
        pos_rows_html = ""
        for pos in top_pos:
            c_p = "#10B981" if pos["pnl"] >= 0 else "#EF4444"
            q_val = pos["qty"]
            q_str = f"{int(q_val)} מניה" if q_val == 1 else (f"{int(q_val)} מניות" if float(q_val).is_integer() else f"{q_val:.2f} מניות")
            sl_str = f"SL: ${pos['stop_loss']:,.2f}" if pos["stop_loss"] is not None else f"שער חי: ${pos['live_p']:,.2f}"
            pos_rows_html += (
                f'<div class="jh-pulse-row">'
                f'<div><span style="font-weight:800; color:#F8FAFC; letter-spacing:0.4px;">{pos["symbol"]}</span>'
                f'<span style="color:#64748B; font-size:0.78rem; margin-right:8px;">{q_str}</span></div>'
                f'<span dir="ltr" style="font-weight:800; color:{c_p}; font-size:0.88rem;">{pos["pnl"]:+,.2f}$ ({pos["pnl_pct"]:+.1f}%)</span>'
                f'<span dir="ltr" style="color:#64748B; font-size:0.78rem;">{sl_str}</span>'
                f'</div>'
            )
    else:
        pos_rows_html = '<div class="jh-sub">אין פוזיציות פתוחות כרגע.</div>'

    # 2. Streak & Discipline
    sc = m["streak_count"]
    sdir = m["streak_dir"]
    if sdir == 1:
        st_color = "#10B981"
        st_text = f"{sc} רווח ברצף" if sc == 1 else f"{sc} רווחים ברצף"
        badge_style = "color:#10B981; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.35);"
        badge_txt = "מומנטום חיובי"
    elif sdir == -1:
        st_color = "#EF4444"
        st_text = f"{sc} הפסד ברצף" if sc == 1 else f"{sc} הפסדים ברצף"
        badge_style = "color:#EF4444; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.35);"
        badge_txt = "בקרת סיכון"
    else:
        st_color = "#94A3B8"
        st_text = "אין רצף פעיל"
        badge_style = "color:#94A3B8; background:rgba(148,163,184,0.12); border:1px solid rgba(148,163,184,0.3);"
        badge_txt = "מאוזן"

    pr_val = max(0.0, min(100.0, float(m["plan_rate"])))
    pr_color = "#10B981" if pr_val >= 75 else "#F59E0B"

    # 3. Monthly Pulse
    m_color = "#10B981" if m["month_closed_pnl"] >= 0 else "#EF4444"
    m_dep_str = f"+${m['month_deposits']:,.2f}" if m["month_deposits"] > 0 else "$0.00"

    _html(
        f"""
        <div class="jh-bottom-grid">
            <div class="jh-card">
                <div class="jh-title" style="margin-bottom:10px;">פוזיציות פתוחות מובילות - Active Positions Pulse</div>
                <div>{pos_rows_html}</div>
            </div>

            <div class="jh-card">
                <div class="jh-title" style="margin-bottom:10px;">רצף נוכחי ומשמעת - Streak & Discipline</div>
                <div class="jh-sub-box" style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                    <div>
                        <div class="jh-mini-lbl">רצף סגירות אחרון</div>
                        <div style="font-size:1.3rem; font-weight:800; color:{st_color}; font-family:{APP_FONT} !important;">
                            {st_text}
                        </div>
                    </div>
                    <span style="font-size:0.78rem; font-weight:700; padding:4px 10px; border-radius:8px; white-space:nowrap; {badge_style}">
                        {badge_txt}
                    </span>
                </div>
                <div style="margin-top:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                        <span style="font-size:0.8rem; color:#94A3B8; font-weight:600;">עמידה בכללי התוכנית</span>
                        <span dir="ltr" style="font-size:0.86rem; font-weight:800; color:{pr_color};">{pr_val:.1f}%</span>
                    </div>
                    <div class="jh-bar-track">
                        <div style="width:{pr_val:.1f}%; height:100%; background:{pr_color}; border-radius:999px;"></div>
                    </div>
                    <div class="jh-sub" style="margin-top:6px;">
                        {m['plan_yes']} עסקאות בוצעו לפי התוכנית מול {m['plan_no']} חריגות
                    </div>
                </div>
            </div>

            <div class="jh-card">
                <div class="jh-title-row" style="margin-bottom:10px;">
                    <div class="jh-title">דופק חודשי - Monthly Pulse</div>
                    <span dir="ltr" style="font-size:0.8rem; font-weight:700; color:#64748B;">{m['month_label']}</span>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                    <div class="jh-sub-box">
                        <div class="jh-mini-lbl">הפקדות החודש</div>
                        <div style="font-size:1.26rem; font-weight:800; color:#38BDF8; direction:ltr; text-align:right;">
                            {m_dep_str}
                        </div>
                    </div>
                    <div class="jh-sub-box">
                        <div class="jh-mini-lbl">רווח / הפסד החודש</div>
                        <div style="font-size:1.26rem; font-weight:800; color:{m_color}; direction:ltr; text-align:right;">
                            {_fmt_usd(m['month_closed_pnl'], signed=True)}
                        </div>
                    </div>
                </div>
                <div class="jh-sub-box" style="margin-top:10px; padding:9px 12px; display:flex; justify-content:space-between; align-items:center; font-size:0.8rem;">
                    <span style="color:#64748B;">פעילות בחודש נוכחי</span>
                    <span style="color:#CBD5E1; font-weight:700;">{m['month_opened_cnt']} פוזיציות נפתחו · {m['month_closed_cnt']} נסגרו</span>
                </div>
            </div>
        </div>
        """
    )


def main() -> None:
    active = st.session_state.get("active_page", "יומן מסחר - עמוד הבית")
    if active == "יומן מסחר - פוזיציות ויומן עסקאות":
        render_positions_and_log_page()
    else:
        render_journal_home()


main()
