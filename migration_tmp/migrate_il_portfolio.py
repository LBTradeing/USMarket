import os
import sys
import pandas as pd
from supabase import create_client, Client

ACTIVE_FUND_IDS = {
    "5114657", "5118997", "5119854", "5122957", "5128079", "5130976", "5131966",
    "5132154", "5135074", "5137039", "5139878", "5140298", "5140454", "5141718"
}

NON_FUND_IDS = {"900", "9993983", "9992985", "9992983", "9999905", ""}


def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()

    if not url or not key:
        print("שגיאה: חסרים משתני סביבה SUPABASE_URL או SUPABASE_KEY ב-GitHub Secrets.")
        sys.exit(1)

    return create_client(url, key)


def parse_num(val):
    """ממיר ערך מספרי גם אם יש בו פסיקים, רווחים או סימן ₪."""
    if pd.isna(val):
        return None
    s = str(val).replace(",", "").replace("₪", "").strip()
    if not s or s in ("-", "nan", "None", "NaN", "<NA>"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_pct(val):
    if pd.isna(val):
        return None
    s = str(val).replace("%", "").replace(",", "").strip()
    if not s or s in ("-", "nan", "None", "NaN", "<NA>"):
        return None
    try:
        return round(float(s), 4)
    except ValueError:
        return None


def parse_date_iso(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if "." in s:
        parts = s.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3 and len(parts[0]) <= 2:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    dt = pd.to_datetime(s, errors="coerce")
    return dt.strftime("%Y-%m-%d") if pd.notna(dt) else None


def chunked(lst, size=500):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_file = os.path.join(base_dir, "Portfolio_DB_History.csv")
    prices_file = os.path.join(base_dir, "Portfolio_DB_Price_History.csv")

    if not os.path.exists(history_file) or not os.path.exists(prices_file):
        print(f"שגיאה: לא נמצאו קובצי CSV בתיקייה {base_dir}")
        sys.exit(1)

    supabase = get_supabase_client()

    print("1. קורא ומנקה נתונים מקובצי ה-CSV...")
    hist = pd.read_csv(history_file)
    hist["clean_id"] = (
        hist["מס' נייר / סימבול"].astype("string").fillna("").str.replace(".0", "", regex=False).str.strip()
    )
    hist["clean_name"] = hist["שם נייר"].astype("string").fillna("").str.strip()
    hist["clean_action"] = hist["סוג פעולה"].astype("string").fillna("").str.strip()

    # --- קטלוג קרנות (il_funds) ---
    funds_dict = {}
    for _, row in hist.iterrows():
        fid = row["clean_id"]
        if fid in NON_FUND_IDS:
            continue
        if fid not in funds_dict:
            funds_dict[fid] = {
                "fund_id": fid,
                "isin": None,
                "name": row["clean_name"] or fid,
                "is_active": fid in ACTIVE_FUND_IDS,
                "currency_hedged": None,
                "underlying_asset": None,
                "geography": None,
                "fund_type": None,
                "mgmt_fee_pct": None,
                "trustee_fee_pct": None,
            }
        f = funds_dict[fid]
        if row["clean_name"]:
            f["name"] = row["clean_name"]
        if pd.notna(row["מספר ISIN"]) and str(row["מספר ISIN"]).strip() not in ("", "-"):
            f["isin"] = str(row["מספר ISIN"]).strip()
        if pd.notna(row['מנוטרל מט"ח']) and str(row['מנוטרל מט"ח']).strip() in ("כן", "לא"):
            f["currency_hedged"] = str(row['מנוטרל מט"ח']).strip() == "כן"
        if pd.notna(row["נכס בסיס"]) and str(row["נכס בסיס"]).strip() not in ("", "-"):
            f["underlying_asset"] = str(row["נכס בסיס"]).strip()
        if pd.notna(row["גיאוגרפיה"]) and str(row["גיאוגרפיה"]).strip() not in ("", "-"):
            f["geography"] = str(row["גיאוגרפיה"]).strip()
        if pd.notna(row["סוג הקרן"]) and str(row["סוג הקרן"]).strip() not in ("", "-"):
            f["fund_type"] = str(row["סוג הקרן"]).strip()

        mf = parse_pct(row["דמי ניהול קרן"])
        if mf is not None:
            f["mgmt_fee_pct"] = mf
        tf = parse_pct(row["דמי נאמנות קרן"])
        if tf is not None:
            f["trustee_fee_pct"] = tf

    funds_list = list(funds_dict.values())

    # --- יומן תנועות (il_fund_transactions) ---
    tx_records = []
    for idx, row in hist.iterrows():
        tx_date = parse_date_iso(row["תאריך"])
        if not tx_date:
            continue

        fid = row["clean_id"]
        name = row["clean_name"]
        action = row["clean_action"]

        if name in ("מס לשלם", "מס עתידי"):
            continue

        qty_raw = parse_num(row["כמות"])
        price_raw = parse_num(row["שער ביצוע"])
        fee_raw = parse_num(row["עמלת פעולה"])
        raw_nis = parse_num(row["תמורה בשקלים"])

        qty = abs(qty_raw) if qty_raw is not None else 0.0
        exec_price = abs(price_raw) if price_raw is not None else 0.0
        fee = abs(fee_raw) if fee_raw is not None else 0.0
        db_fund_id = fid if fid in funds_dict else None

        if name == "מס ששולם":
            act_type = "TAX_PAID"
            amt = abs(raw_nis) if raw_nis is not None else qty
        elif action == "דמי טפול מזומן":
            act_type = "MGMT_FEE"
            amt = abs(raw_nis) if raw_nis is not None else 0.0
        elif action == "ריבית בניע":
            act_type = "INTEREST"
            amt = abs(raw_nis) if raw_nis is not None else 0.0
        elif action in ("העברה מזומן", "משיכה"):
            act_type = "CASH_TRANSFER"
            amt = raw_nis if raw_nis is not None else 0.0
        elif action == "קניה":
            act_type = "BUY"
            amt = abs(raw_nis) if raw_nis is not None else round((qty * (exec_price / 100.0)) + fee, 2)
        elif action == "מכירה":
            act_type = "SELL"
            amt = abs(raw_nis) if raw_nis is not None else round((qty * (exec_price / 100.0)) - fee, 2)
        else:
            continue

        tx_records.append({
            "tx_date": tx_date,
            "fund_id": db_fund_id,
            "action_type": act_type,
            "description": name or action,
            "quantity": round(qty, 4),
            "exec_price_agorot": round(exec_price, 4),
            "fee_nis": round(fee, 2),
            "amount_nis": round(amt, 2),
            "migration_row_num": int(idx) + 2,
        })

    # --- היסטוריית שערים (il_fund_prices) ---
    prices = pd.read_csv(prices_file)
    price_records = []
    for _, row in prices.iterrows():
        p_val = parse_num(row["מחיר"])
        if p_val is None or p_val <= 0:
            continue
        if pd.isna(row["סימבול"]):
            continue
        fid = str(row["סימבול"]).replace(".0", "").strip()
        if fid not in funds_dict:
            continue
        p_date = parse_date_iso(row["תאריך"])
        if not p_date or p_date >= "2027-01-01":
            continue
        price_records.append({
            "fund_id": fid,
            "price_date": p_date,
            "price_agorot": round(p_val, 4),
            "source": "csv_migration",
        })

    print(f"2. מעלה {len(funds_list)} קרנות לטבלת il_funds...")
    supabase.table("il_funds").upsert(funds_list, on_conflict="fund_id").execute()

    print(f"3. מעלה {len(tx_records)} תנועות לטבלת il_fund_transactions...")
    for batch in chunked(tx_records, 250):
        supabase.table("il_fund_transactions").upsert(batch, on_conflict="migration_row_num").execute()

    print(f"4. מעלה {len(price_records)} שערי סגירה לטבלת il_fund_prices...")
    for i, batch in enumerate(chunked(price_records, 500), start=1):
        supabase.table("il_fund_prices").upsert(batch, on_conflict="fund_id,price_date").execute()
        print(f"   הושלמה אצווה {i} ({min(i * 500, len(price_records))}/{len(price_records)})")

    print("\nהמיגרציה הסתיימה בהצלחה!")


if __name__ == "__main__":
    main()
