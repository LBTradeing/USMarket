import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from supabase import Client, create_client

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_supabase_client() -> Client:
    """יוצר חיבור ל-Supabase מתוך משתני סביבה או Streamlit secrets."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )

    if not url or not key:
        try:
            import streamlit as st
            url = url or st.secrets.get("SUPABASE_URL", "") or st.secrets.get("supabase", {}).get("url", "")
            key = key or st.secrets.get("SUPABASE_KEY", "") or st.secrets.get("supabase", {}).get("key", "")
        except Exception:
            pass

    if not url or not key:
        raise RuntimeError("חסרים מפתחות חיבור ל-Supabase (SUPABASE_URL / SUPABASE_KEY).")

    return create_client(url, key)


def _is_valid_price(
    price_agorot: Optional[float],
    fund_id: str,
    last_known_price: Optional[float],
    max_daily_jump_pct: float = 0.25,
) -> bool:
    """בדיקת שפיות: מוודא שהשער חיובי, לא שווה למספר הנייר, וללא קפיצה חריגה."""
    if price_agorot is None or price_agorot <= 5 or price_agorot > 50000:
        return False

    try:
        if int(round(price_agorot)) == int(fund_id):
            return False
    except ValueError:
        pass

    if last_known_price and last_known_price > 0:
        ratio = abs(price_agorot - last_known_price) / last_known_price
        if ratio > max_daily_jump_pct:
            return False

    return True


def _fetch_from_maya(fund_id: str, session: requests.Session) -> Optional[Tuple[float, str]]:
    """מקור 1: API של מאיה (הבורסה לניירות ערך בתל אביב)."""
    url = f"https://mayaapi.tase.co.il/api/fund/details?fundId={fund_id}"
    headers = {
        **BROWSER_HEADERS,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://maya.tase.co.il",
        "Referer": f"https://maya.tase.co.il/fund/{fund_id}",
        "X-Maya-With": "allow",
    }
    resp = session.get(url, headers=headers, timeout=12)
    if resp.status_code != 200:
        return None

    data = resp.json()
    if not isinstance(data, dict):
        return None

    payload = data.get("FundDetails") or data.get("Data") or data
    raw_price = (
        payload.get("PurchasePrice")
        or payload.get("RedemptionPrice")
        or payload.get("UnitValue")
        or payload.get("LastPrice")
    )
    if raw_price is None:
        return None

    price_val = float(str(raw_price).replace(",", "").strip())
    return price_val, "maya_api"


def _fetch_from_funder(fund_id: str, session: requests.Session) -> Optional[Tuple[float, str]]:
    """מקור 2: דף הקרן באתר Funder."""
    url = f"https://www.funder.co.il/fund/{fund_id}"
    resp = session.get(url, headers=BROWSER_HEADERS, timeout=12)
    if resp.status_code != 200:
        return None

    html = resp.text
    patterns = [
        r'"(?:buyPrice|PurchasePrice|redemptionPrice|RedemptionPrice)"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'מחיר\s*(?:קנייה|פדיון)[^0-9]{0,60}(?<!\d)([0-9]{2,4}(?:\.[0-9]{1,4})?)(?!\d)',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return float(m.group(1)), "funder"

    return None


def _fetch_from_bizportal(fund_id: str, session: requests.Session) -> Optional[Tuple[float, str]]:
    """מקור 3: דף הקרן באתר ביזפורטל."""
    section = "tradedfunds" if fund_id.startswith("11") else "mutualfunds"
    url = f"https://www.bizportal.co.il/{section}/quote/generalview/{fund_id}"
    resp = session.get(url, headers=BROWSER_HEADERS, timeout=12)
    if resp.status_code != 200:
        return None

    html = resp.text
    patterns = [
        r'class=["\']num["\'][^>]*>\s*([0-9]{2,4}(?:,[0-9]{3})*(?:\.[0-9]{1,4})?)\s*<',
        r'(?:מחיר\s*קנייה|שער\s*בסיס|שער\s*אחרון)[^0-9]{0,60}(?<!\d)([0-9]{2,4}(?:\.[0-9]{1,4})?)(?!\d)',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return float(m.group(1).replace(",", "")), "bizportal"

    return None


def _fetch_from_yahoo(fund_id: str, session: requests.Session) -> Optional[Tuple[float, str]]:
    """מקור 4: Yahoo Finance (רלוונטי בעיקר לקרנות סל סחירות עם סיומת .TA)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{fund_id}.TA?range=5d&interval=1d"
    resp = session.get(url, headers=BROWSER_HEADERS, timeout=10)
    if resp.status_code != 200:
        return None

    data = resp.json()
    result = (data.get("chart") or {}).get("result")
    if not result:
        return None

    meta = result[0].get("meta") or {}
    closes = ((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

    for close_val in reversed(closes):
        if close_val is not None and close_val > 0:
            price_val = float(close_val)
            if meta.get("currency") == "ILS" and price_val < 50:
                price_val *= 100.0
            return price_val, "yahoo_finance"

    return None


def fetch_single_fund_quote(
    fund_id: str,
    target_date: str,
    last_known_price: Optional[float] = None,
    session: Optional[requests.Session] = None,
) -> Optional[Dict[str, Any]]:
    """מנסה למשוך את השער העדכני לקרן בודדת לפי סדר עדיפויות ושומר תחת target_date."""
    own_session = session is None
    sess = session or requests.Session()

    sources = [_fetch_from_maya, _fetch_from_funder, _fetch_from_bizportal, _fetch_from_yahoo]
    try:
        for fetcher in sources:
            try:
                res = fetcher(fund_id, sess)
                if res:
                    price_val, src_name = res
                    if _is_valid_price(price_val, fund_id, last_known_price):
                        return {
                            "fund_id": fund_id,
                            "price_date": target_date,
                            "price_agorot": round(price_val, 4),
                            "source": src_name,
                        }
            except Exception:
                continue
        return None
    finally:
        if own_session:
            sess.close()


def delete_prices_for_date(target_date: str, supabase: Optional[Client] = None) -> None:
    """מוחק שערים של תאריך מסוים (שימושי לבדיקות)."""
    client = supabase or get_supabase_client()
    client.table("il_fund_prices").delete().eq("price_date", target_date).execute()
    print(f"נמחקו רשומות שערים עבור תאריך {target_date}.")


def sync_all_active_fund_prices(
    supabase: Optional[Client] = None,
    target_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    מושך שער עדכני לכל הקרנות הפעילות (is_active = True)
    ושומר תחת התאריך של היום (או target_date) ב-il_fund_prices.
    """
    client = supabase or get_supabase_client()
    run_date = target_date or datetime.now(ISRAEL_TZ).date().isoformat()

    # 1. שליפת הקרנות הפעילות בלבד
    funds_resp = client.table("il_funds").select("fund_id, name").eq("is_active", True).execute()
    active_funds = funds_resp.data or []
    if not active_funds:
        return {"updated_count": 0, "total_active": 0, "failed_funds": [], "details": []}

    # 2. שליפת השער האחרון שלפני run_date לצורך בדיקת שפיות
    last_prices: Dict[str, float] = {}
    for f in active_funds:
        fid = f["fund_id"]
        p_resp = (
            client.table("il_fund_prices")
            .select("price_agorot")
            .eq("fund_id", fid)
            .lt("price_date", run_date)
            .order("price_date", desc=True)
            .limit(1)
            .execute()
        )
        if p_resp.data:
            last_prices[fid] = float(p_resp.data[0]["price_agorot"])

    # 3. שליפת שערים לכל קרן
    records_to_upsert: List[Dict[str, Any]] = []
    failed_funds: List[Dict[str, str]] = []
    details: List[Dict[str, Any]] = []

    with requests.Session() as sess:
        for f in active_funds:
            fid = f["fund_id"]
            fname = f["name"]
            quote = fetch_single_fund_quote(
                fid,
                target_date=run_date,
                last_known_price=last_prices.get(fid),
                session=sess,
            )
            if quote:
                records_to_upsert.append(quote)
                details.append({**quote, "name": fname, "status": "ok"})
            else:
                failed_funds.append({"fund_id": fid, "name": fname})
                details.append({"fund_id": fid, "name": fname, "status": "failed"})
            time.sleep(0.35)

    # 4. שמירה למסד הנתונים
    if records_to_upsert:
        client.table("il_fund_prices").upsert(records_to_upsert, on_conflict="fund_id,price_date").execute()

    return {
        "updated_count": len(records_to_upsert),
        "total_active": len(active_funds),
        "failed_funds": failed_funds,
        "details": details,
        "target_date": run_date,
        "timestamp": datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
    }


if __name__ == "__main__":
    client = get_supabase_client()

    # תמיכה במחיקה יזומה לבדיקה מתוך משתנה סביבה (למשל ב-GitHub Actions)
    delete_date = os.environ.get("DELETE_TEST_DATE", "").strip()
    if delete_date:
        delete_prices_for_date(delete_date, supabase=client)

    print("מתחיל סנכרון שערי קרנות ישראליות...")
    summary = sync_all_active_fund_prices(supabase=client)
    print(f"עודכנו {summary['updated_count']} מתוך {summary['total_active']} קרנות עבור תאריך {summary['target_date']} ({summary['timestamp']}).")
    for item in summary["details"]:
        if item["status"] == "ok":
            print(f"  [OK] {item['fund_id']} ({item['name']}): {item['price_agorot']} אג' | מקור: {item['source']}")
        else:
            print(f"  [FAIL] {item['fund_id']} ({item['name']}): לא נמצא שער תקין באף מקור")
