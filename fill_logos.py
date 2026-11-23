# === [SEC-01: IMPORTS & SUPABASE CLIENT] ===
import os
import time
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# === [SEC-02: IMAGE URL VALIDATOR & MULTI-SOURCE RESOLVER] ===
def is_valid_image_url(url: str) -> bool:
    """Checks that a logo URL responds with HTTP 200 and an image content-type."""
    if not url or not url.startswith("http"):
        return False
    try:
        resp = requests.get(
            url,
            timeout=8,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        ctype = resp.headers.get("Content-Type", "").lower()
        resp.close()
        return resp.status_code == 200 and ("image" in ctype or "svg" in ctype)
    except Exception:
        return False


def fetch_finnhub_profile(ticker: str) -> dict:
    """Queries Finnhub profile2 with automatic 429 rate-limit cooldown."""
    if not FINNHUB_API_KEY:
        return {}
    url = "https://finnhub.io/api/v1/stock/profile2"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}

    for attempt in (1, 2):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                print(f"[RATE LIMIT] Finnhub 429 on {ticker}, sleeping 20s...")
                time.sleep(20.0)
                continue
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as e:
            print(f"[WARN] Finnhub lookup failed for {ticker} (attempt {attempt}): {e}")
            if attempt == 1:
                time.sleep(3.0)
    return {}


def resolve_best_logo(base_ticker: str) -> tuple[str | None, dict]:
    """Finds a verified logo URL across Finnhub profile2 and secondary ticker repositories."""
    profile = fetch_finnhub_profile(base_ticker)
    candidates: list[str] = []

    fh_logo = str(profile.get("logo") or "").strip()
    if fh_logo:
        candidates.append(fh_logo)

    clean_fmp = base_ticker.replace(".", "-")
    candidates.extend(
        [
            f"https://financialmodelingprep.com/image-stock/{clean_fmp}.png",
            f"https://static2.finnhub.io/file/publicdatany/finnhubimage/stock_logo/{base_ticker}.png",
        ]
    )

    seen: set[str] = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        if is_valid_image_url(url):
            return url, profile

    return None, profile


# === [SEC-03: MAIN BACKFILL EXECUTION] ===
def main() -> None:
    wl_resp = (
        supabase.table("watchlist")
        .select("symbol")
        .eq("is_active", True)
        .order("symbol")
        .execute()
    )
    active_symbols = [r["symbol"].strip() for r in (wl_resp.data or []) if r.get("symbol")]

    prof_resp = supabase.table("company_profiles").select("symbol, logo_url").execute()
    existing_map = {
        r["symbol"].strip(): (r.get("logo_url") or "").strip()
        for r in (prof_resp.data or [])
        if r.get("symbol")
    }

    missing_symbols = [
        sym
        for sym in active_symbols
        if not existing_map.get(sym) or existing_map.get(sym).lower() in ("none", "null")
    ]

    print(
        f"Active watchlist: {len(active_symbols)} | "
        f"Already have logo: {len(active_symbols) - len(missing_symbols)} | "
        f"Missing logos to resolve: {len(missing_symbols)}"
    )

    if not missing_symbols:
        print("All active symbols already have valid logos!")
        return

    updated_count = 0
    for idx, sym in enumerate(missing_symbols, start=1):
        base_ticker = sym.split(":")[-1].strip().upper()
        logo_url, profile = resolve_best_logo(base_ticker)

        if logo_url:
            payload: dict = {"symbol": sym, "logo_url": logo_url}
            if sym not in existing_map:
                comp_name = str(profile.get("name") or base_ticker).strip()
                payload["company_name"] = comp_name
            supabase.table("company_profiles").upsert(payload, on_conflict="symbol").execute()
            updated_count += 1
            print(f"[{idx}/{len(missing_symbols)}] OK: {sym} -> {logo_url}")
        else:
            print(f"[{idx}/{len(missing_symbols)}] NO LOGO FOUND: {sym}")

        # ~44 calls/min pace to stay safely below Finnhub's 60 req/min limit
        time.sleep(1.35)

    print(f"Logo backfill finished: resolved {updated_count}/{len(missing_symbols)} missing logos.")


if __name__ == "__main__":
    main()
