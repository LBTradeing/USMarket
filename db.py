# === [SEC-01: IMPORTS & SUPABASE CLIENT] ===
import os
import math
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import requests
import yfinance as yf
import streamlit as st
from supabase import create_client, Client


def get_secret(key_name: str, default: str = "") -> str:
    if key_name in st.secrets:
        return str(st.secrets[key_name]).strip()
    return os.environ.get(key_name, default).strip()


@st.cache_resource
def get_supabase_client() -> Client:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    return create_client(url, key)


# === [SEC-02: MARKET DATA LOADERS (CACHED)] ===
@st.cache_data(ttl=120)
def load_market_dataframe() -> pd.DataFrame:
    """Loads merged watchlist, company_profiles, and stocks_snapshot."""
    sb = get_supabase_client()

    wl_resp = sb.table("watchlist").select("symbol, source, is_active").eq("is_active", True).execute()
    prof_resp = sb.table("company_profiles").select("*").execute()
    snap_resp = sb.table("stocks_snapshot").select("*").execute()

    df_wl = pd.DataFrame(wl_resp.data or [])
    df_prof = pd.DataFrame(prof_resp.data or [])
    df_snap = pd.DataFrame(snap_resp.data or [])

    if df_wl.empty:
        return pd.DataFrame()

    df = df_wl.copy()
    if not df_prof.empty:
        df = df.merge(df_prof, on="symbol", how="left")
    if not df_snap.empty:
        df = df.merge(df_snap, on="symbol", how="left")

    if "live_price" in df.columns and "price" in df.columns:
        df["display_price"] = df["live_price"].fillna(df["price"])
    elif "price" in df.columns:
        df["display_price"] = df["price"]
    else:
        df["display_price"] = None

    return df.sort_values("symbol").reset_index(drop=True)


def clear_market_cache() -> None:
    load_market_dataframe.clear()


# === [SEC-03: LIVE TRADING PRICE REFRESH (TRADINGVIEW)] ===
def refresh_live_prices_tv(symbols: list[str]) -> int:
    """Fetches real-time price and % change from TradingView and updates stocks_snapshot."""
    if not symbols:
        return 0

    sb = get_supabase_client()
    url = "https://scanner.tradingview.com/america/scan"
    clean_to_orig: dict[str, list[str]] = {}
    for sym in symbols:
        base = sym.split(":")[-1].strip().upper()
        clean_to_orig.setdefault(base, []).append(sym)

    clean_names = list(clean_to_orig.keys())
    now_iso = datetime.now(timezone.utc).isoformat()
    updates: list[dict] = []

    for i in range(0, len(clean_names), 200):
        batch = clean_names[i : i + 200]
        payload = {
            "filter": [{"left": "name", "operation": "in_range", "right": batch}],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "close", "change"],
            "range": [0, len(batch) + 50],
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            for item in resp.json().get("data", []):
                d = item.get("d", [])
                if len(d) < 3 or not d[0] or d[1] is None:
                    continue
                ticker = str(d[0]).strip().upper()
                live_p = round(float(d[1]), 2)
                chg_pct = round(float(d[2]), 2) if d[2] is not None else None
                for orig_sym in clean_to_orig.get(ticker, []):
                    updates.append(
                        {
                            "symbol": orig_sym,
                            "live_price": live_p,
                            "change_today_pct": chg_pct,
                            "live_updated_at": now_iso,
                        }
                    )
        except Exception:
            continue

    if updates:
        for i in range(0, len(updates), 150):
            sb.table("stocks_snapshot").upsert(updates[i : i + 150], on_conflict="symbol").execute()
        clear_market_cache()

    return len(updates)


# === [SEC-04: MANUAL SUPPORT / RESISTANCE LEVELS & BIDIRECTIONAL SETUP SYNC] ===
def save_manual_levels(symbol: str, levels: list[dict]) -> None:
    """Saves user-defined support/resistance levels into company_profiles.manual_levels."""
    sb = get_supabase_client()
    sb.table("company_profiles").update({"manual_levels": levels}).eq("symbol", symbol).execute()
    clear_market_cache()


def sync_setup_pattern(
    symbol: str,
    setup_pattern: str | None,
    trade_id: int | None = None,
) -> None:
    """Bidirectionally syncs Setup pattern between company_profiles (Analytics) and trade_journal (Journal)."""
    sb = get_supabase_client()
    clean_sym = symbol.split(":")[-1].strip().upper()
    clean_setup = setup_pattern.strip() if setup_pattern and setup_pattern.strip() and setup_pattern != "ללא Setup" else None
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Update company_profiles (Analytics Deep Dive)
    try:
        sb.table("company_profiles").update({"setup_pattern": clean_setup}).eq("symbol", clean_sym).execute()
    except Exception:
        pass

    # 2. Update trade_journal (Journal)
    try:
        if trade_id is not None:
            sb.table("trade_journal").update(
                {"setup_pattern": clean_setup, "updated_at": now_iso}
            ).eq("id", trade_id).execute()

        # Also keep any open positions for this symbol synchronized
        open_rows = (
            sb.table("trade_journal")
            .select("id")
            .eq("symbol", clean_sym)
            .eq("status", "Open")
            .execute()
            .data
            or []
        )
        if open_rows:
            sb.table("trade_journal").update(
                {"setup_pattern": clean_setup, "updated_at": now_iso}
            ).eq("symbol", clean_sym).eq("status", "Open").execute()
        elif trade_id is None:
            # If no open trade exists, sync the most recent trade for this symbol if any
            latest = (
                sb.table("trade_journal")
                .select("id")
                .eq("symbol", clean_sym)
                .order("entry_date", desc=True)
                .order("id", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if latest:
                sb.table("trade_journal").update(
                    {"setup_pattern": clean_setup, "updated_at": now_iso}
                ).eq("id", latest[0]["id"]).execute()
    except Exception:
        pass

    clear_market_cache()
    try:
        from journal_helpers import clear_journal_cache
        clear_journal_cache()
    except Exception:
        pass


# === [SEC-05: NEW STOCKS DETECTION & FULL ON-DEMAND SYNC] ===
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


def find_pending_new_symbols() -> list[str]:
    """Finds active watchlist symbols missing snapshot data or AI profile enrichment."""
    sb = get_supabase_client()
    wl = sb.table("watchlist").select("symbol").eq("is_active", True).execute().data or []
    snaps = sb.table("stocks_snapshot").select("symbol, price").execute().data or []
    profs = sb.table("company_profiles").select("symbol, short_summary").execute().data or []

    valid_snaps = {r["symbol"] for r in snaps if r.get("price") is not None}
    valid_profs = {r["symbol"] for r in profs if r.get("short_summary")}

    pending = [
        r["symbol"].strip().upper()
        for r in wl
        if r.get("symbol") and (r["symbol"] not in valid_snaps or r["symbol"] not in valid_profs)
    ]
    return sorted(set(pending))


def _clean_num(val, decimals: int = 4) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def _extract_swing_sr(df: pd.DataFrame, current_price: float, left: int, right: int):
    if df is None or len(df) < (left + right + 1) or current_price <= 0:
        return [None] * 5, [None] * 5
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    raw_pivots: list[float] = []
    for idx in range(left, len(df) - right):
        if highs[idx] == np.max(highs[idx - left : idx + right + 1]):
            raw_pivots.append(float(highs[idx]))
        if lows[idx] == np.min(lows[idx - left : idx + right + 1]):
            raw_pivots.append(float(lows[idx]))

    sorted_lvls = sorted(raw_pivots)
    clustered = []
    for lvl in sorted_lvls:
        if not clustered or abs(lvl - clustered[-1]) / clustered[-1] > 0.004:
            clustered.append(lvl)
        else:
            clustered[-1] = (clustered[-1] + lvl) / 2.0

    supports = sorted([p for p in clustered if p < current_price * 0.999], reverse=True)[:5]
    resistances = sorted([p for p in clustered if p > current_price * 1.001])[:5]
    s_out = [_clean_num(supports[i], 2) if i < len(supports) else None for i in range(5)]
    r_out = [_clean_num(resistances[i], 2) if i < len(resistances) else None for i in range(5)]
    return s_out, r_out


def sync_single_new_stock(raw_symbol: str) -> tuple[bool, str]:
    """Runs complete end-to-end profile, AI, technical, S/R, and earnings sync for one ticker."""
    sym = raw_symbol.split(":")[-1].strip().upper()
    if not sym:
        return False, "טיקר לא תקין"

    sb = get_supabase_client()
    finnhub_key = get_secret("FINNHUB_API_KEY")
    gemini_key = get_secret("GEMINI_API_KEY")
    now_iso = datetime.now(timezone.utc).isoformat()

    sb.table("watchlist").upsert(
        {"symbol": sym, "source": "manual", "is_active": True},
        on_conflict="symbol",
    ).execute()

    tv_row = {}
    tv_cols = [
        "name", "description", "exchange", "sector", "industry",
        "close", "change", "volume", "Perf.W", "Perf.1M", "Perf.3M",
        "Perf.6M", "Perf.YTD", "Perf.Y", "SMA20", "SMA50", "SMA200", "RSI", "ATR",
    ]
    try:
        r_tv = requests.post(
            "https://scanner.tradingview.com/america/scan",
            json={
                "filter": [{"left": "name", "operation": "equal", "right": sym}],
                "options": {"lang": "en"},
                "symbols": {"query": {"types": []}, "tickers": []},
                "columns": tv_cols,
                "range": [0, 5],
            },
            timeout=15,
        )
        for item in r_tv.json().get("data", []):
            d = item.get("d", [])
            if len(d) >= len(tv_cols) and str(d[0]).upper() == sym:
                tv_row = dict(zip(tv_cols, d))
                break
    except Exception:
        pass

    fh_prof = {}
    next_earnings = None
    if finnhub_key:
        try:
            rp = requests.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": sym, "token": finnhub_key},
                timeout=12,
            )
            fh_prof = rp.json() or {}
        except Exception:
            pass
        try:
            today = datetime.now(timezone.utc).date()
            re = requests.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={
                    "symbol": sym,
                    "from": today.isoformat(),
                    "to": (today + timedelta(days=120)).isoformat(),
                    "token": finnhub_key,
                },
                timeout=12,
            )
            cals = re.json().get("earningsCalendar", [])
            if cals:
                next_earnings = sorted(c["date"] for c in cals if c.get("date"))[0]
        except Exception:
            pass

    yf_sym = sym.replace(".", "-")
    df = yf.download(yf_sym, period="3y", interval="1d", auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(yf_sym, axis=1, level=0) if yf_sym in df.columns.get_level_values(0) else pd.DataFrame()

    if df is None or df.empty:
        return False, f"לא נמצאו נתוני מסחר עבור {sym}"

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    closes = df["Close"]
    vols = df["Volume"]

    price = _clean_num(tv_row.get("close"), 2) or _clean_num(closes.iloc[-1], 2)
    if not price or price <= 0:
        return False, f"מחיר לא תקין עבור {sym}"

    existing_prof_resp = sb.table("company_profiles").select("*").eq("symbol", sym).execute()
    existing_prof = existing_prof_resp.data[0] if existing_prof_resp.data else {}

    company_name = (
        existing_prof.get("company_name")
        or fh_prof.get("name")
        or tv_row.get("description")
        or sym
    )
    raw_exch = (existing_prof.get("exchange") or tv_row.get("exchange") or fh_prof.get("exchange") or "").upper()
    exchange = (
        "NASDAQ" if "NASDAQ" in raw_exch
        else ("AMEX" if "AMEX" in raw_exch else ("NYSE" if "NYSE" in raw_exch else (raw_exch or None)))
    )
    raw_sec = existing_prof.get("sector") or tv_row.get("sector") or ""
    sector = SP_SECTOR_MAP.get(raw_sec.strip().lower(), raw_sec.strip() or None)
    industry = existing_prof.get("industry") or tv_row.get("industry") or fh_prof.get("finnhubIndustry") or None
    logo_url = existing_prof.get("logo_url") or fh_prof.get("logo") or None
    sub_industry = existing_prof.get("sub_industry")
    short_summary = existing_prof.get("short_summary")

    if gemini_key and (not sub_industry or not short_summary):
        try:
            from pydantic import BaseModel, Field
            from google import genai
            from google.genai import types

            class SingleEnrichment(BaseModel):
                sub_industry: str = Field(description="Standardized 2-4 word sub-industry in English.")
                short_summary: str = Field(
                    description=(
                        "Factual business summary in Hebrew without marketing fluff. "
                        "1 short sentence (10-15 words) for simple traditional businesses, "
                        "or 2-3 focused sentences (up to 70 words) for tech/complex niches."
                    )
                )

            ai_client = genai.Client(api_key=gemini_key)
            prompt = (
                f"Classify and summarize this US-listed company:\n"
                f"Ticker: {sym} | Name: {company_name} | Sector: {sector} | Industry: {industry}\n"
                f"Return standardized English `sub_industry` (2-4 words) and crisp Hebrew `short_summary` "
                f"(1 short sentence for simple traditional businesses, or 2-3 focused sentences up to 70 words for complex/tech niches)."
            )
            ai_resp = ai_client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SingleEnrichment,
                    temperature=0.2,
                ),
            )
            parsed = SingleEnrichment.model_validate_json(ai_resp.text)
            sub_industry = parsed.sub_industry.strip()
            short_summary = parsed.short_summary.strip()
        except Exception:
            pass

    sb.table("company_profiles").upsert(
        {
            "symbol": sym,
            "company_name": company_name,
            "exchange": exchange,
            "sector": sector,
            "industry": industry,
            "sub_industry": sub_industry,
            "short_summary": short_summary,
            "logo_url": logo_url,
        },
        on_conflict="symbol",
    ).execute()

    def pct_ret(lb: int):
        if len(closes) <= lb or float(closes.iloc[-(lb + 1)]) == 0:
            return None
        return _clean_num(((float(closes.iloc[-1]) - float(closes.iloc[-(lb + 1)])) / float(closes.iloc[-(lb + 1)])) * 100.0, 2)

    def day_step(ago: int):
        if len(closes) < ago + 2 or float(closes.iloc[-(ago + 2)]) == 0:
            return None
        return _clean_num(((float(closes.iloc[-(ago + 1)]) - float(closes.iloc[-(ago + 2)])) / float(closes.iloc[-(ago + 2)])) * 100.0, 2)

    daily_vol = int(tv_row["volume"]) if tv_row.get("volume") is not None else int(vols.iloc[-1])

    def rel_vol(win: int):
        if len(vols) < win + 1:
            return None
        avg_v = float(vols.iloc[-(win + 1) : -1].mean())
        return _clean_num(daily_vol / avg_v, 2) if avg_v > 0 else None

    def ma_blk(period: int, tv_k: str | None):
        mv = _clean_num(tv_row.get(tv_k), 2) if tv_k else None
        if mv is None and len(closes) >= period:
            mv = _clean_num(closes.iloc[-period:].mean(), 2)
        if not mv or mv <= 0:
            return None, None, None
        return ("Above" if price >= mv else "Below"), mv, _clean_num(((price - mv) / mv) * 100.0, 2)

    ma20_s, ma20_v, ma20_d = ma_blk(20, "SMA20")
    ma50_s, ma50_v, ma50_d = ma_blk(50, "SMA50")
    ma150_s, ma150_v, ma150_d = ma_blk(150, None)
    ma200_s, ma200_v, ma200_d = ma_blk(200, "SMA200")

    rsi = _clean_num(tv_row.get("RSI"), 2)
    if rsi is None and len(closes) >= 15:
        delta = closes.diff()
        ag = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        al = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rsi = 100.0 if al.iloc[-1] == 0 else _clean_num(100.0 - (100.0 / (1.0 + ag.iloc[-1] / al.iloc[-1])), 2)

    atr_series = pd.Series(dtype=float)
    if len(df) >= 15:
        pc = closes.shift(1)
        tr = pd.concat([(df["High"] - df["Low"]), (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    atr_14 = _clean_num(tv_row.get("ATR"), 2) or (_clean_num(atr_series.iloc[-1], 2) if not atr_series.empty else None)
    atr_pct = _clean_num((atr_14 / price) * 100.0, 2) if atr_14 else None

    atr_squeeze_pct = None
    if not atr_series.empty and len(atr_series) >= 20:
        peak_atr = float(atr_series.iloc[-50:].max())
        if peak_atr > 0:
            atr_squeeze_pct = _clean_num(max(0.0, min(100.0, (1.0 - (float(atr_series.iloc[-1]) / peak_atr)) * 100.0)), 1)

    d_sup, d_res = _extract_swing_sr(df, price, left=5, right=5)
    if len(df) >= 35:
        w_df = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna(subset=["Close"])
        w_sup, w_res = _extract_swing_sr(w_df, price, left=3, right=3)
    else:
        w_sup, w_res = [None] * 5, [None] * 5

    snap_payload = {
        "atr_squeeze_pct": atr_squeeze_pct,
        "symbol": sym,
        "price": price,
        "change_today_pct": _clean_num(tv_row.get("change"), 2) or pct_ret(1),
        "live_price": price,
        "live_updated_at": now_iso,
        "change_1d": day_step(1),
        "change_2d": day_step(2),
        "change_3d": day_step(3),
        "change_4d": day_step(4),
        "weekly": _clean_num(tv_row.get("Perf.W"), 2) or pct_ret(5),
        "two_weeks": pct_ret(10),
        "three_weeks": pct_ret(15),
        "monthly": _clean_num(tv_row.get("Perf.1M"), 2) or pct_ret(21),
        "three_months": _clean_num(tv_row.get("Perf.3M"), 2) or pct_ret(63),
        "six_months": _clean_num(tv_row.get("Perf.6M"), 2) or pct_ret(126),
        "nine_months": pct_ret(189),
        "ytd": _clean_num(tv_row.get("Perf.YTD"), 2),
        "one_year": _clean_num(tv_row.get("Perf.Y"), 2) or pct_ret(252),
        "daily_vol": daily_vol,
        "vol_1d": int(vols.iloc[-2]) if len(vols) >= 2 else None,
        "vol_2d": int(vols.iloc[-3]) if len(vols) >= 3 else None,
        "vol_3d": int(vols.iloc[-4]) if len(vols) >= 4 else None,
        "vol_4d": int(vols.iloc[-5]) if len(vols) >= 5 else None,
        "rel_vol_5d": rel_vol(5),
        "rel_vol_10d": rel_vol(10),
        "rel_vol_15d": rel_vol(15),
        "rel_vol_20d": rel_vol(20),
        "rel_vol_30d": rel_vol(30),
        "ma_20_status": ma20_s, "ma_20_value": ma20_v, "ma_20_dist_pct": ma20_d,
        "ma_50_status": ma50_s, "ma_50_value": ma50_v, "ma_50_dist_pct": ma50_d,
        "ma_150_status": ma150_s, "ma_150_value": ma150_v, "ma_150_dist_pct": ma150_d,
        "ma_200_status": ma200_s, "ma_200_value": ma200_v, "ma_200_dist_pct": ma200_d,
        "rsi": rsi,
        "atr_14": atr_14,
        "atr_pct": atr_pct,
        "d_s_1": d_sup[0], "d_s_2": d_sup[1], "d_s_3": d_sup[2], "d_s_4": d_sup[3], "d_s_5": d_sup[4],
        "d_r_1": d_res[0], "d_r_2": d_res[1], "d_r_3": d_res[2], "d_r_4": d_res[3], "d_r_5": d_res[4],
        "w_s_1": w_sup[0], "w_s_2": w_sup[1], "w_s_3": w_sup[2], "w_s_4": w_sup[3], "w_s_5": w_sup[4],
        "w_r_1": w_res[0], "w_r_2": w_res[1], "w_r_3": w_res[2], "w_r_4": w_res[3], "w_r_5": w_res[4],
        "next_earnings_date": next_earnings,
        "updated_at": now_iso,
    }

    sb.table("stocks_snapshot").upsert(snap_payload, on_conflict="symbol").execute()
    clear_market_cache()
    return True, f"המניה {sym} סונכרנה בהצלחה"
