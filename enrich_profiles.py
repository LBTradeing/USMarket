# === [SEC-01: IMPORTS & CLIENT INITIALIZATION] ===
import os
import math
import time
import requests
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
ENRICH_LIMIT = int(os.environ.get("ENRICH_LIMIT", "0"))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)


# === [SEC-02: S&P GICS SECTOR NORMALIZATION] ===
SP_SECTOR_MAP = {
    "technology": "Information Technology",
    "information technology": "Information Technology",
    "healthcare": "Health Care",
    "health care": "Health Care",
    "financial services": "Financials",
    "financial": "Financials",
    "financials": "Financials",
    "consumer cyclical": "Consumer Discretionary",
    "consumer discretionary": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "communication services": "Communication Services",
    "industrials": "Industrials",
    "industrial goods": "Industrials",
    "energy": "Energy",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "basic materials": "Materials",
    "materials": "Materials",
}


def normalize_sp_sector(raw_sector: str | None) -> str | None:
    if not raw_sector:
        return None
    cleaned = raw_sector.strip()
    return SP_SECTOR_MAP.get(cleaned.lower(), cleaned)


# === [SEC-03: TRADINGVIEW EXCHANGE BATCH LOOKUP] ===
def normalize_exchange(raw_exch: str | None) -> str | None:
    if not raw_exch:
        return None
    ex = raw_exch.strip().upper()
    if "NASDAQ" in ex:
        return "NASDAQ"
    if "AMEX" in ex or "AMERICAN" in ex:
        return "AMEX"
    if "ARCA" in ex:
        return "NYSE ARCA"
    if "NYSE" in ex:
        return "NYSE"
    return ex


def fetch_exchanges_tv(symbols: list[str], batch_size: int = 150, pause_sec: float = 2.0) -> dict[str, str]:
    """Fetches listing exchange (NASDAQ/NYSE/AMEX) from TradingView Screener in batches."""
    url = "https://scanner.tradingview.com/america/scan"
    clean_to_orig: dict[str, list[str]] = {}
    exchange_map: dict[str, str] = {}

    for sym in symbols:
        if ":" in sym:
            prefix, base = sym.split(":", 1)
            norm_ex = normalize_exchange(prefix)
            if norm_ex:
                exchange_map[sym] = norm_ex
        else:
            base = sym
        clean_to_orig.setdefault(base.strip().upper(), []).append(sym)

    clean_names = list(clean_to_orig.keys())
    total_batches = math.ceil(len(clean_names) / batch_size)

    for idx, i in enumerate(range(0, len(clean_names), batch_size), start=1):
        batch = clean_names[i : i + batch_size]
        payload = {
            "filter": [{"left": "name", "operation": "in_range", "right": batch}],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "exchange"],
            "range": [0, len(batch) + 50],
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            resp.raise_for_status()
            for item in resp.json().get("data", []):
                d = item.get("d", [])
                if len(d) >= 2 and d[0]:
                    ticker = str(d[0]).strip().upper()
                    norm_ex = normalize_exchange(str(d[1]))
                    if ticker in clean_to_orig and norm_ex:
                        for orig_sym in clean_to_orig[ticker]:
                            exchange_map[orig_sym] = norm_ex
        except Exception as e:
            print(f"[WARN] TradingView exchange batch {idx}/{total_batches} issue: {e}")

        if idx < total_batches:
            time.sleep(pause_sec)

    print(f"Resolved exchanges for {len(exchange_map)}/{len(symbols)} symbols.")
    return exchange_map


# === [SEC-04: GEMINI STRUCTURED SCHEMA & BATCH PROMPT] ===
class CompanyEnrichmentItem(BaseModel):
    symbol: str = Field(description="Exact ticker symbol provided in the input.")
    sub_industry: str = Field(
        description=(
            "Concise, standardized sub-industry in English (2-4 words), e.g., "
            "'Photonics & Optical', 'AI Networking & Interconnects', "
            "'Neocloud & AI Infrastructure', 'Construction & Heavy Machinery'. "
            "For straightforward traditional businesses (e.g., regional banks, classic utilities), "
            "keep it clean and aligned with the broad industry."
        )
    )
    short_summary: str = Field(
        description=(
            "Factual business summary in Hebrew without marketing fluff. "
            "If the company is straightforward and traditional (e.g., commercial bank, classic utility, standard retailer), "
            "write ONLY ONE short sentence (10-15 words). "
            "If the company is in technology, biotech, specialized industrials, or a complex niche, "
            "write 2-3 crisp sentences (up to 70 words) covering core products/services, customers, and revenue focus."
        )
    )


class BatchEnrichmentResponse(BaseModel):
    items: list[CompanyEnrichmentItem]


def enrich_batch_with_gemini(
    batch_rows: list[dict], known_sub_industries: set[str]
) -> list[CompanyEnrichmentItem]:
    existing_subs = ", ".join(sorted(known_sub_industries)) if known_sub_industries else "None yet"

    companies_block = "\n".join(
        f"- Ticker: {r['symbol']} | Name: {r.get('company_name') or 'Unknown'} | "
        f"Sector: {r.get('sector') or 'Unknown'} | Industry: {r.get('industry') or 'Unknown'}"
        for r in batch_rows
    )

    prompt = f"""
You are a senior equity research analyst. Classify and summarize each of the following US-listed companies.

Rules:
1. `symbol`: Return the exact ticker symbol as given.
2. `sub_industry`: Provide a sharp, standardized sub-industry label in English (2-4 words) that captures the true operational niche.
   - Reuse an existing label from this list whenever it accurately fits: [{existing_subs}]
   - Create a new concise label only when a distinct niche is needed.
3. `short_summary`: Write a crisp, factual summary in Hebrew (no hype or clichés):
   - For simple, self-explanatory businesses (e.g., regional banks, standard utilities, traditional retail/insurance): write ONLY 1 short sentence (10-15 words).
   - For technology, semiconductors, AI infrastructure, biotech, or specialized industrial niches: write 2-3 focused sentences (max 70 words) explaining what the company builds/delivers, who its customers are, and its main niche.

Companies to process:
{companies_block}
"""

    for attempt in range(1, 4):
        try:
            response = ai_client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchEnrichmentResponse,
                    temperature=0.2,
                ),
            )
            parsed = BatchEnrichmentResponse.model_validate_json(response.text)
            return parsed.items
        except Exception as e:
            wait_sec = 20 * attempt
            print(f"[WARN] Gemini batch attempt {attempt}/3 failed: {e}. Waiting {wait_sec}s...")
            if attempt == 3:
                raise
            time.sleep(wait_sec)

    return []


# === [SEC-05: MAIN EXECUTION & CHECKPOINT SAVER] ===
def main():
    resp = (
        supabase.table("company_profiles")
        .select("symbol, company_name, exchange, sector, industry, sub_industry, short_summary")
        .execute()
    )
    rows = resp.data or []
    if not rows:
        print("No rows found in company_profiles.")
        return

    all_symbols = [r["symbol"] for r in rows]
    exchange_map = fetch_exchanges_tv(all_symbols, batch_size=150, pause_sec=2.0)

    # Step A: Sync normalized S&P sectors & missing exchanges across all profiles
    meta_updates = 0
    for r in rows:
        sym = r["symbol"]
        norm_sec = normalize_sp_sector(r.get("sector"))
        new_exch = r.get("exchange") or exchange_map.get(sym)

        patch = {}
        if norm_sec and norm_sec != r.get("sector"):
            patch["sector"] = norm_sec
            r["sector"] = norm_sec
        if new_exch and new_exch != r.get("exchange"):
            patch["exchange"] = new_exch
            r["exchange"] = new_exch

        if patch:
            supabase.table("company_profiles").update(patch).eq("symbol", sym).execute()
            meta_updates += 1

    print(f"Updated exchange / S&P sector metadata for {meta_updates} profiles.")

    # Step B: Enrich pending sub_industry & short_summary in batches via Gemini
    known_subs = {r["sub_industry"].strip() for r in rows if r.get("sub_industry")}
    pending = [r for r in rows if not r.get("sub_industry") or not r.get("short_summary")]

    if ENRICH_LIMIT > 0:
        pending = pending[:ENRICH_LIMIT]

    if not pending:
        print("All profiles already have sub_industry and short_summary.")
        return

    batch_size = 12
    total_batches = math.ceil(len(pending) / batch_size)
    print(f"Starting Gemini enrichment for {len(pending)} profiles in {total_batches} batches...")

    for idx, i in enumerate(range(0, len(pending), batch_size), start=1):
        batch = pending[i : i + batch_size]
        lookup = {r["symbol"].split(":")[-1].strip().upper(): r["symbol"] for r in batch}
        lookup.update({r["symbol"].strip().upper(): r["symbol"] for r in batch})

        try:
            enriched_items = enrich_batch_with_gemini(batch, known_subs)
            saved_count = 0
            for item in enriched_items:
                key = item.symbol.strip().upper()
                orig_sym = lookup.get(key)
                if not orig_sym:
                    continue
                sub_clean = item.sub_industry.strip()
                sum_clean = item.short_summary.strip()
                known_subs.add(sub_clean)

                supabase.table("company_profiles").update(
                    {
                        "sub_industry": sub_clean,
                        "short_summary": sum_clean,
                    }
                ).eq("symbol", orig_sym).execute()
                saved_count += 1

            print(f"[Batch {idx}/{total_batches}] Saved {saved_count}/{len(batch)} profiles.")
        except Exception as e:
            print(f"[ERROR] Batch {idx}/{total_batches} aborted: {e}")

        if idx < total_batches:
            time.sleep(4.5)

    print("Profile enrichment completed.")


if __name__ == "__main__":
    main()
