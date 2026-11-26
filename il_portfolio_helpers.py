import os
from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import Client, create_client

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
FALLBACK_ANNUAL_INFLATION = 0.03


def get_supabase_client() -> Client:
    """יוצר חיבור ל-Supabase מתוך st.secrets או משתני סביבה."""
    url = ""
    key = ""

    try:
        url = (
            st.secrets.get("SUPABASE_URL", "")
            or st.secrets.get("supabase", {}).get("url", "")
        )
        key = (
            st.secrets.get("SUPABASE_KEY", "")
            or st.secrets.get("SUPABASE_ANON_KEY", "")
            or st.secrets.get("supabase", {}).get("key", "")
        )
    except Exception:
        pass

    url = (url or os.environ.get("SUPABASE_URL", "")).strip()
    key = (
        key
        or os.environ.get("SUPABASE_KEY", "")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        or os.environ.get("SUPABASE_ANON_KEY", "")
    ).strip()

    if not url or not key:
        raise RuntimeError("חסרים מפתחות חיבור ל-Supabase (SUPABASE_URL / SUPABASE_KEY).")

    return create_client(url, key)


def _fetch_all_rows(
    client: Client,
    table_name: str,
    select_cols: str = "*",
    order_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """שולף את כל השורות מטבלה ב-Supabase באמצעות דפדוף (עוקף את מגבלת 1,000 השורות)."""
    all_rows: List[Dict[str, Any]] = []
    batch_size = 1000
    offset = 0

    while True:
        query = client.table(table_name).select(select_cols)
        if order_col:
            query = query.order(order_col, desc=False)
        resp = query.range(offset, offset + batch_size - 1).execute()
        rows = resp.data or []
        all_rows.extend(rows)
        if len(rows) < batch_size:
            break
        offset += batch_size

    return all_rows


@st.cache_data(ttl=600, show_spinner=False)
def load_il_raw_tables() -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """
    טעינה עצלה (Lazy Loading) של טבלאות התיק הישראלי ומדד המחירים לצרכן מ-Supabase.
    הנתונים נשמרים ב-Cache ל-10 דקות או עד ביצוע פעולה / רענון ידני.
    """
    client = get_supabase_client()
    funds = _fetch_all_rows(client, "il_funds", "*", order_col="fund_id")
    transactions = _fetch_all_rows(client, "il_fund_transactions", "*", order_col="tx_date")
    prices = _fetch_all_rows(
        client,
        "il_fund_prices",
        "fund_id,price_date,price_agorot,price_nis,source",
        order_col="price_date",
    )
    try:
        cpi_rows = _fetch_all_rows(
            client,
            "il_cpi_monthly",
            "cpi_month,index_value,monthly_change_pct",
            order_col="cpi_month",
        )
    except Exception:
        cpi_rows = []

    return funds, transactions, prices, cpi_rows


def clear_il_portfolio_cache() -> None:
    """מנקה את זיכרון המטמון לאחר הוספת פעולה או עדכון שערים."""
    load_il_raw_tables.clear()


def compute_il_portfolio_analytics() -> Dict[str, Any]:
    """
    מנוע החישוב המרכזי של התיק הישראלי:
    - מחשב שווי נוכחי, עלות ממוצעת, רווח/הפסד, שינוי יומי ומגמת 10 ימים לכל קרן פעילה.
    - משחזר שווי היסטורי ("מכונת זמן") כולל 7 הקרנות ההיסטוריות שנמכרו בעבר.
    - מחשב תשואות תקופתיות, שנתיות וחודשיות (נומינלי מול ריאלי לפי מדד הלמ"ס).
    - מפיק נתוני פילוח לגרפים מתוך המטא-דאטה של הקרנות.
    """
    funds_rows, tx_rows, price_rows, cpi_rows = load_il_raw_tables()

    funds_map: Dict[str, Dict[str, Any]] = {str(f["fund_id"]): f for f in funds_rows}

    # בניית מפת אינפלציה חודשית אמיתית (YYYY-MM -> שיעור שינוי עשרוני, למשל 0.003 עבור 0.3%)
    cpi_monthly_rate: Dict[str, float] = {}
    for c in cpi_rows:
        m_key = str(c.get("cpi_month") or "").strip()
        if m_key and c.get("monthly_change_pct") is not None:
            cpi_monthly_rate[m_key] = float(c["monthly_change_pct"]) / 100.0

    has_live_cpi = len(cpi_monthly_rate) > 0
    if has_live_cpi:
        sorted_cpi_keys = sorted(cpi_monthly_rate.keys())
        recent_12 = [cpi_monthly_rate[k] for k in sorted_cpi_keys[-12:]]
        default_monthly_infl = sum(recent_12) / len(recent_12)
    else:
        default_monthly_infl = ((1.0 + FALLBACK_ANNUAL_INFLATION) ** (1.0 / 12.0)) - 1.0

    def _get_month_infl_rate(y: int, m: int, is_current_in_progress: bool = False) -> float:
        key = f"{y:04d}-{m:02d}"
        if key in cpi_monthly_rate:
            return cpi_monthly_rate[key]
        # עבור החודש השוטף שעדיין לא פורסם לו מדד רשמי, משתמשים בממוצע 12 חודשים אחרונים
        return default_monthly_infl if not is_current_in_progress else (default_monthly_infl * 0.5)

    # 1. ארגון היסטוריית שערים לפי קרן (ממוין כרונולוגית עולה לחיפוש בינארי מהיר)
    prices_by_fund: Dict[str, List[Tuple[str, float, float]]] = {}
    for p in price_rows:
        fid = str(p["fund_id"])
        p_date = str(p["price_date"])
        p_ag = float(p["price_agorot"])
        p_nis = float(p["price_nis"]) if p.get("price_nis") is not None else (p_ag / 100.0)
        if p_ag > 0:
            prices_by_fund.setdefault(fid, []).append((p_date, p_ag, p_nis))

    price_lookup: Dict[str, Tuple[List[str], List[float], List[float]]] = {}
    for fid, plist in prices_by_fund.items():
        dedup: Dict[str, Tuple[float, float]] = {}
        for d_str, ag, nis in plist:
            dedup[d_str] = (ag, nis)
        sorted_dates = sorted(dedup.keys())
        price_lookup[fid] = (
            sorted_dates,
            [dedup[d][0] for d in sorted_dates],
            [dedup[d][1] for d in sorted_dates],
        )

    # 2. עיבוד יומן התנועות והחזקות
    fund_state: Dict[str, Dict[str, Any]] = {
        fid: {"qty": 0.0, "cost_nis": 0.0, "txs": []}
        for fid in funds_map
    }

    totals = {
        "trading_fees": 0.0,
        "mgmt_fees": 0.0,
        "interest": 0.0,
        "net_mgmt_fees": 0.0,
        "taxes": 0.0,
        "cash_transfers": 0.0,
    }

    annual_raw: Dict[int, Dict[str, float]] = {}
    monthly_raw: Dict[int, Dict[int, Dict[str, float]]] = {}

    def _ensure_period_bucket(y: int, m: int) -> None:
        if y not in annual_raw:
            annual_raw[y] = {"net_flow": 0.0, "trading_fees": 0.0, "mgmt_fees": 0.0, "interest": 0.0, "taxes": 0.0}
        if y not in monthly_raw:
            monthly_raw[y] = {}
        if m not in monthly_raw[y]:
            monthly_raw[y][m] = {"net_flow": 0.0, "trading_fees": 0.0, "mgmt_fees": 0.0, "interest": 0.0, "taxes": 0.0}

    sorted_txs = sorted(tx_rows, key=lambda x: (str(x["tx_date"]), int(x.get("id") or 0)))

    for tx in sorted_txs:
        tx_date_str = str(tx["tx_date"])
        try:
            dt_obj = date.fromisoformat(tx_date_str)
        except ValueError:
            continue

        if dt_obj.year < 2020:
            continue

        y, m = dt_obj.year, dt_obj.month
        _ensure_period_bucket(y, m)

        act = str(tx["action_type"])
        fid = str(tx["fund_id"]) if tx.get("fund_id") is not None else ""
        qty = abs(float(tx.get("quantity") or 0.0))
        exec_ag = abs(float(tx.get("exec_price_agorot") or 0.0))
        fee = abs(float(tx.get("fee_nis") or 0.0))
        amt = float(tx.get("amount_nis") or 0.0)

        if act == "TAX_PAID":
            tax_val = abs(amt)
            annual_raw[y]["taxes"] += tax_val
            monthly_raw[y][m]["taxes"] += tax_val
            totals["taxes"] += tax_val
            continue

        if act == "MGMT_FEE":
            fee_val = abs(amt)
            annual_raw[y]["mgmt_fees"] += fee_val
            monthly_raw[y][m]["mgmt_fees"] += fee_val
            totals["mgmt_fees"] += fee_val
            continue

        if act == "INTEREST":
            int_val = abs(amt)
            annual_raw[y]["interest"] += int_val
            monthly_raw[y][m]["interest"] += int_val
            totals["interest"] += int_val
            continue

        if act == "CASH_TRANSFER":
            totals["cash_transfers"] += amt
            continue

        if act in ("BUY", "SELL"):
            annual_raw[y]["trading_fees"] += fee
            monthly_raw[y][m]["trading_fees"] += fee
            totals["trading_fees"] += fee

            if fid and fid not in fund_state:
                fund_state[fid] = {"qty": 0.0, "cost_nis": 0.0, "txs": []}

            abs_amt = abs(amt)
            if act == "BUY":
                if fid:
                    fund_state[fid]["qty"] += qty
                    fund_state[fid]["cost_nis"] += abs_amt
                    fund_state[fid]["txs"].append((tx_date_str, qty, abs_amt, exec_ag / 100.0))
                annual_raw[y]["net_flow"] += abs_amt
                monthly_raw[y][m]["net_flow"] += abs_amt
            elif act == "SELL":
                if fid:
                    if fund_state[fid]["qty"] > 0:
                        avg_unit_cost = fund_state[fid]["cost_nis"] / fund_state[fid]["qty"]
                        fund_state[fid]["qty"] = max(0.0, fund_state[fid]["qty"] - qty)
                        fund_state[fid]["cost_nis"] = max(0.0, fund_state[fid]["cost_nis"] - (qty * avg_unit_cost))
                    fund_state[fid]["txs"].append((tx_date_str, -qty, -abs_amt, exec_ag / 100.0))
                annual_raw[y]["net_flow"] -= abs_amt
                monthly_raw[y][m]["net_flow"] -= abs_amt

    totals["net_mgmt_fees"] = abs(totals["mgmt_fees"] - totals["interest"])

    def _get_price_nis_at(fid: str, target_date_str: str) -> float:
        if fid in price_lookup:
            dates_arr, _, nis_arr = price_lookup[fid]
            idx = bisect_right(dates_arr, target_date_str) - 1
            if idx >= 0:
                return nis_arr[idx]
        txs = [t for t in fund_state.get(fid, {}).get("txs", []) if t[0] <= target_date_str]
        if txs:
            last_tx = txs[-1]
            if last_tx[3] > 0:
                return last_tx[3]
            if abs(last_tx[1]) > 0:
                return abs(last_tx[2]) / abs(last_tx[1])
        return 0.0

    def _calc_portfolio_value_at(target_date_str: str) -> float:
        total_val = 0.0
        for fid, st_obj in fund_state.items():
            q_at = sum(t[1] for t in st_obj["txs"] if t[0] <= target_date_str)
            if q_at > 0.01:
                p_nis = _get_price_nis_at(fid, target_date_str)
                total_val += q_at * p_nis
        return total_val

    today_dt = datetime.now(ISRAEL_TZ).date()
    today_str = today_dt.isoformat()
    current_year = today_dt.year
    current_month = today_dt.month

    # 3. ניתוח הקרנות הפעילות (החזקות נוכחיות)
    intervals_days = {
        "w": 7,
        "mStart": (today_dt - today_dt.replace(day=1)).days,
        "m": 30,
        "m3": 90,
        "m6": 180,
        "m9": 270,
        "ytd": (today_dt - date(current_year, 1, 1)).days,
        "y1": 365,
    }

    agg_periods: Dict[str, Dict[str, float]] = {k: {"curr": 0.0, "past": 0.0} for k in intervals_days}
    agg_daily_nis = 0.0
    total_value_current = 0.0
    total_cost_active = 0.0

    fund_analysis: List[Dict[str, Any]] = []

    for fid, f_meta in funds_map.items():
        st_obj = fund_state.get(fid, {"qty": 0.0, "cost_nis": 0.0, "txs": []})
        qty = st_obj["qty"]
        is_active = bool(f_meta.get("is_active", True))

        if not is_active and qty <= 0.01:
            continue

        dates_arr, ag_arr, nis_arr = price_lookup.get(fid, ([], [], []))
        cur_p_nis = nis_arr[-1] if nis_arr else _get_price_nis_at(fid, today_str)
        cur_p_ag = ag_arr[-1] if ag_arr else (cur_p_nis * 100.0)
        last_date_fmt = ""
        if dates_arr:
            ld = date.fromisoformat(dates_arr[-1])
            last_date_fmt = ld.strftime("%d/%m/%Y")

        cur_val = qty * cur_p_nis
        cost_nis = st_obj["cost_nis"]
        avg_cost_nis = (cost_nis / qty) if qty > 0 else 0.0
        avg_cost_ag = avg_cost_nis * 100.0
        total_profit = cur_val - cost_nis
        total_yield = ((total_profit / cost_nis) * 100.0) if cost_nis > 0 else 0.0

        if len(nis_arr) >= 2:
            prev_p_nis = nis_arr[-2]
            daily_change_nis = (cur_p_nis - prev_p_nis) * qty
            daily_change_pct = ((cur_p_nis - prev_p_nis) / prev_p_nis * 100.0) if prev_p_nis > 0 else 0.0
        else:
            daily_change_nis = 0.0
            daily_change_pct = 0.0

        sparkline = ag_arr[-10:] if ag_arr else []

        agg_daily_nis += daily_change_nis
        total_value_current += cur_val
        total_cost_active += cost_nis

        periods_dict: Dict[str, Optional[float]] = {}
        for k, delta_days in intervals_days.items():
            target_dt_str = (today_dt - timedelta(days=delta_days)).isoformat()
            p_past_nis = 0.0
            if dates_arr:
                idx = bisect_right(dates_arr, target_dt_str) - 1
                if idx >= 0:
                    p_past_nis = nis_arr[idx]

            if p_past_nis > 0 and cur_p_nis > 0:
                periods_dict[f"{k}Yield"] = ((cur_p_nis - p_past_nis) / p_past_nis) * 100.0
                periods_dict[f"{k}Profit"] = (cur_p_nis - p_past_nis) * qty
            else:
                periods_dict[f"{k}Yield"] = None
                periods_dict[f"{k}Profit"] = None

            agg_periods[k]["curr"] += cur_val
            agg_periods[k]["past"] += (qty * p_past_nis) if p_past_nis > 0 else cost_nis

        years_dict: Dict[int, Dict[str, Optional[float]]] = {}
        for y in range(2020, current_year + 1):
            eoy_prev = f"{y - 1}-12-31"
            eoy_cur = today_str if y == current_year else f"{y}-12-31"

            q_start = sum(t[1] for t in st_obj["txs"] if t[0] <= eoy_prev)
            q_end = sum(t[1] for t in st_obj["txs"] if t[0] <= eoy_cur)
            net_flow_y = sum(t[2] for t in st_obj["txs"] if eoy_prev < t[0] <= eoy_cur)

            if q_start <= 0.01 and q_end <= 0.01 and abs(net_flow_y) < 0.01:
                years_dict[y] = {"yield": None, "profit": None}
                continue

            p_start = _get_price_nis_at(fid, eoy_prev)
            p_end = cur_p_nis if y == current_year else _get_price_nis_at(fid, eoy_cur)

            val_start = q_start * p_start
            val_end = q_end * p_end
            prof_y = val_end - val_start - net_flow_y

            base_p = p_start if p_start > 0 else (nis_arr[0] if nis_arr else 0.0)
            yld_y = ((p_end - base_p) / base_p * 100.0) if (base_p > 0 and p_end > 0) else 0.0
            years_dict[y] = {"yield": yld_y, "profit": prof_y}

        fund_analysis.append({
            "id": fid,
            "isin": f_meta.get("isin") or "",
            "name": f_meta.get("name") or fid,
            "geography": f_meta.get("geography") or "אחר",
            "underlying_asset": f_meta.get("underlying_asset") or "",
            "fund_type": f_meta.get("fund_type") or "קרן נאמנות / אחר",
            "currency_hedged": f_meta.get("currency_hedged"),
            "mgmt_fee_pct": f_meta.get("mgmt_fee_pct"),
            "trustee_fee_pct": f_meta.get("trustee_fee_pct"),
            "qty": qty,
            "avg_cost_nis": avg_cost_nis,
            "avg_cost_agorot": avg_cost_ag,
            "current_price_nis": cur_p_nis,
            "current_price_agorot": cur_p_ag,
            "cur_val": cur_val,
            "cost_nis": cost_nis,
            "total_profit": total_profit,
            "total_yield": total_yield,
            "daily_change_nis": daily_change_nis,
            "daily_change_pct": daily_change_pct,
            "last_date": last_date_fmt,
            "sparkline": sparkline,
            "periods": periods_dict,
            "years": years_dict,
        })

    fund_analysis.sort(key=lambda x: x["cur_val"], reverse=True)
    for f in fund_analysis:
        f["weight_pct"] = (f["cur_val"] / total_value_current * 100.0) if total_value_current > 0 else 0.0

    prev_total_val = total_value_current - agg_daily_nis
    agg_daily_pct = (agg_daily_nis / prev_total_val * 100.0) if prev_total_val > 0 else 0.0

    timeframes_returns: Dict[str, float] = {}
    timeframes_profit: Dict[str, float] = {}
    for k, vals in agg_periods.items():
        diff = vals["curr"] - vals["past"]
        timeframes_profit[k] = diff
        timeframes_returns[k] = (diff / vals["past"] * 100.0) if vals["past"] > 0 else 0.0

    # 4. חישוב שנתי וחודשי היסטורי מלא (כולל אינפלציה חודשית ושנתית אמיתית מהלמ"ס)
    annual_stats: Dict[int, Dict[str, float]] = {}
    monthly_stats: Dict[int, Dict[int, Dict[str, float]]] = {}

    for y in range(2020, current_year + 1):
        monthly_stats[y] = {}
        max_m = current_month if y == current_year else 12
        year_infl_factor = 1.0

        for m in range(1, max_m + 1):
            prev_month_last_day = (date(y, m, 1) - timedelta(days=1)).isoformat()
            last_day_num = monthrange(y, m)[1]
            is_cur_m = (y == current_year and m == current_month)
            cur_month_end = today_str if is_cur_m else date(y, m, last_day_num).isoformat()

            val_start_m = _calc_portfolio_value_at(prev_month_last_day)
            val_end_m = _calc_portfolio_value_at(cur_month_end)
            raw_m = monthly_raw.get(y, {}).get(
                m, {"net_flow": 0.0, "trading_fees": 0.0, "mgmt_fees": 0.0, "interest": 0.0, "taxes": 0.0}
            )

            m_infl = _get_month_infl_rate(y, m, is_current_in_progress=is_cur_m)
            year_infl_factor *= (1.0 + m_infl)

            profit_m = val_end_m - val_start_m - raw_m["net_flow"]
            denom_m = val_start_m + (raw_m["net_flow"] / 2.0)
            yield_m = (profit_m / denom_m * 100.0) if denom_m > 0 else 0.0
            real_yield_m = (((1.0 + yield_m / 100.0) / (1.0 + m_infl)) - 1.0) * 100.0
            erosion_m = max(0.0, denom_m) * m_infl
            real_profit_m = profit_m - erosion_m
            net_mgmt_m = abs(raw_m["mgmt_fees"] - raw_m["interest"])

            monthly_stats[y][m] = {
                "start_balance": val_start_m,
                "end_balance": val_end_m,
                "investment": raw_m["net_flow"],
                "profit": profit_m,
                "yield": yield_m,
                "cpi_pct": m_infl * 100.0,
                "inflation_erosion_nis": erosion_m,
                "real_profit": real_profit_m,
                "real_yield": real_yield_m,
                "trading_fees": raw_m["trading_fees"],
                "mgmt_fees": raw_m["mgmt_fees"],
                "interest": raw_m["interest"],
                "net_mgmt_fees": net_mgmt_m,
                "total_fees": raw_m["trading_fees"] + net_mgmt_m,
                "taxes": raw_m["taxes"],
            }

        t_start_y = f"{y - 1}-12-31"
        t_end_y = today_str if y == current_year else f"{y}-12-31"

        val_start_y = _calc_portfolio_value_at(t_start_y)
        val_end_y = _calc_portfolio_value_at(t_end_y)
        raw_y = annual_raw.get(
            y, {"net_flow": 0.0, "trading_fees": 0.0, "mgmt_fees": 0.0, "interest": 0.0, "taxes": 0.0}
        )

        year_infl_rate = year_infl_factor - 1.0
        profit_y = val_end_y - val_start_y - raw_y["net_flow"]
        denom_y = val_start_y + (raw_y["net_flow"] / 2.0)
        yield_y = (profit_y / denom_y * 100.0) if denom_y > 0 else 0.0
        real_yield_y = (((1.0 + yield_y / 100.0) / (1.0 + year_infl_rate)) - 1.0) * 100.0
        erosion_y = max(0.0, denom_y) * year_infl_rate
        real_profit_y = profit_y - erosion_y
        net_mgmt_y = abs(raw_y["mgmt_fees"] - raw_y["interest"])

        annual_stats[y] = {
            "start_balance": val_start_y,
            "end_balance": val_end_y,
            "investment": raw_y["net_flow"],
            "profit": profit_y,
            "yield": yield_y,
            "cpi_pct": year_infl_rate * 100.0,
            "inflation_erosion_nis": erosion_y,
            "real_profit": real_profit_y,
            "real_yield": real_yield_y,
            "trading_fees": raw_y["trading_fees"],
            "mgmt_fees": raw_y["mgmt_fees"],
            "interest": raw_y["interest"],
            "net_mgmt_fees": net_mgmt_y,
            "total_fees": raw_y["trading_fees"] + net_mgmt_y,
            "taxes": raw_y["taxes"],
        }

    # 5. נתוני פילוח לגרפים מתוך המטא-דאטה של הקרנות
    holdings_pie: Dict[str, float] = {}
    geo_map: Dict[str, float] = {}
    geo_usa_map: Dict[str, float] = {}
    type_map: Dict[str, float] = {}
    hedged_map: Dict[str, float] = {}

    for f in fund_analysis:
        val = f["cur_val"]
        if val <= 0:
            continue
        holdings_pie[f["name"]] = val
        geo = f["geography"] or "אחר"
        geo_usa = 'ארה"ב' if geo == "גלובלי" else geo
        ftype = f["fund_type"] or "קרן נאמנות / אחר"
        hedged_lbl = (
            'מנוטרל מט"ח'
            if f["currency_hedged"] is True
            else ('חשוף למט"ח' if f["currency_hedged"] is False else "לא מוגדר")
        )

        geo_map[geo] = geo_map.get(geo, 0.0) + val
        geo_usa_map[geo_usa] = geo_usa_map.get(geo_usa, 0.0) + val
        type_map[ftype] = type_map.get(ftype, 0.0) + val
        hedged_map[hedged_lbl] = hedged_map.get(hedged_lbl, 0.0) + val

    total_profit_active = total_value_current - total_cost_active
    total_yield_active = (total_profit_active / total_cost_active * 100.0) if total_cost_active > 0 else 0.0

    return {
        "total_value": total_value_current,
        "total_cost": total_cost_active,
        "total_profit": total_profit_active,
        "total_yield": total_yield_active,
        "agg_daily_nis": agg_daily_nis,
        "agg_daily_pct": agg_daily_pct,
        "timeframes_returns": timeframes_returns,
        "timeframes_profit": timeframes_profit,
        "fund_analysis": fund_analysis,
        "annual_stats": annual_stats,
        "monthly_stats": monthly_stats,
        "totals": totals,
        "charts": {
            "holdings_pie": holdings_pie,
            "geo_map": geo_map,
            "geo_usa_map": geo_usa_map,
            "type_map": type_map,
            "hedged_map": hedged_map,
        },
        "all_funds": list(funds_map.values()),
        "has_live_cpi": has_live_cpi,
        "as_of_date": today_str,
    }


def record_il_transaction(
    tx_date: date,
    fund_id: str,
    action_type: str,
    amount_nis: float,
    quantity: float = 0.0,
    exec_price_agorot: float = 0.0,
    fee_nis: float = 0.0,
    notes: str = "",
    new_fund_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    שומר פעולת קנייה/מכירה חדשה ב-Supabase:
    - אם מדובר בקרן חדשה, מוסיף אותה אוטומטית לטבלת il_funds.
    - בקנייה, מוודא שהקרן מסומנת כפעילה (is_active=True) ושומר שער התחלתי אם חסר.
    - במכירה מלאה (כמות נותרת <= 0.01), מעביר אוטומטית את הקרן לסטטוס לא-פעיל.
    """
    client = get_supabase_client()
    clean_fid = str(fund_id).strip()
    if not clean_fid:
        return False, "חובה להזין מספר נייר / סימבול."

    existing_resp = client.table("il_funds").select("*").eq("fund_id", clean_fid).execute()
    existing_fund = existing_resp.data[0] if existing_resp.data else None

    if not existing_fund:
        if not new_fund_meta or not new_fund_meta.get("name"):
            return False, "עבור קרן חדשה חובה להזין לפחות שם קרן."
        fund_payload = {
            "fund_id": clean_fid,
            "name": str(new_fund_meta["name"]).strip(),
            "isin": (str(new_fund_meta.get("isin") or "").strip() or None),
            "geography": (str(new_fund_meta.get("geography") or "").strip() or "אחר"),
            "underlying_asset": (str(new_fund_meta.get("underlying_asset") or "").strip() or None),
            "fund_type": (str(new_fund_meta.get("fund_type") or "").strip() or "מחקה מדד"),
            "currency_hedged": new_fund_meta.get("currency_hedged"),
            "mgmt_fee_pct": new_fund_meta.get("mgmt_fee_pct"),
            "trustee_fee_pct": new_fund_meta.get("trustee_fee_pct"),
            "is_active": True,
        }
        client.table("il_funds").insert(fund_payload).execute()
        fund_name = fund_payload["name"]
    else:
        fund_name = existing_fund["name"]

    tx_date_str = tx_date.isoformat() if isinstance(tx_date, date) else str(tx_date)

    tx_payload = {
        "tx_date": tx_date_str,
        "fund_id": clean_fid,
        "action_type": action_type,
        "description": fund_name,
        "quantity": round(abs(float(quantity)), 4),
        "exec_price_agorot": round(abs(float(exec_price_agorot)), 4),
        "fee_nis": round(abs(float(fee_nis)), 2),
        "amount_nis": round(abs(float(amount_nis)), 2),
        "notes": notes.strip() or None,
    }
    client.table("il_fund_transactions").insert(tx_payload).execute()

    if action_type == "BUY":
        if existing_fund and not existing_fund.get("is_active", True):
            client.table("il_funds").update({"is_active": True}).eq("fund_id", clean_fid).execute()

        if exec_price_agorot > 0:
            p_check = (
                client.table("il_fund_prices")
                .select("id")
                .eq("fund_id", clean_fid)
                .eq("price_date", tx_date_str)
                .execute()
            )
            if not p_check.data:
                client.table("il_fund_prices").insert({
                    "fund_id": clean_fid,
                    "price_date": tx_date_str,
                    "price_agorot": round(abs(float(exec_price_agorot)), 4),
                    "source": "tx_entry",
                }).execute()

    elif action_type == "SELL":
        txs_resp = (
            client.table("il_fund_transactions")
            .select("action_type, quantity")
            .eq("fund_id", clean_fid)
            .in_("action_type", ["BUY", "SELL"])
            .execute()
        )
        net_qty = 0.0
        for r in (txs_resp.data or []):
            q_val = abs(float(r.get("quantity") or 0.0))
            if r["action_type"] == "BUY":
                net_qty += q_val
            elif r["action_type"] == "SELL":
                net_qty -= q_val

        if net_qty <= 0.01:
            client.table("il_funds").update({"is_active": False}).eq("fund_id", clean_fid).execute()

    clear_il_portfolio_cache()
    return True, f"הפעולה עבור '{fund_name}' נשמרה בהצלחה."


def trigger_manual_price_sync() -> Dict[str, Any]:
    """מריץ סנכרון שערים ומדד ידני מתוך הממשק ומנקה את ה-Cache."""
    from il_price_fetcher import sync_all_active_fund_prices

    client = get_supabase_client()
    result = sync_all_active_fund_prices(supabase=client, include_cpi=True)
    clear_il_portfolio_cache()
    return result
