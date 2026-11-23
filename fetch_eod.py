# === [SEC-01: IMPORTS, ENV & SUPABASE CLIENT] ===
import os
import math
import time
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()

raw_limit = os.environ.get("EOD_LIMIT") or os.environ.get("LIMIT") or "0"
EOD_LIMIT = int(raw_limit.strip() or "0")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# === [SEC-02: NUMERIC SANITIZATION & WATCHLIST LOADER] ===
def clean_num(val, decimals: int = 4) -> float | None:
    """Converts numpy/pandas scalars to JSON-safe Python floats, turning NaN/Inf into None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def fetch_active_watchlist(limit: int = 0) -> list[str]:
    """Loads active ticker symbols from Supabase watchlist."""
    resp = (
        supabase.table("watchlist")
        .select("symbol")
        .eq("is_active", True)
        .order("symbol")
        .execute()
    )
    symbols = [r["symbol"].strip() for r in (resp.data or []) if r.get("symbol")]
    if limit > 0:
        symbols = symbols[:limit]
    print(f"Loaded {len(symbols)} active symbols from watchlist.")
    return symbols


# === [SEC-03: TRADINGVIEW SCREENER BATCH FETCH] ===
def fetch_tradingview_data(
    symbols: list[str], batch_size: int = 150, pause_sec: float = 3.0
) -> dict[str, dict]:
    """Fetches EOD snapshot metrics from TradingView Screener API in throttled batches."""
    url = "https://scanner.tradingview.com/america/scan"
    tv_columns = [
        "name",
        "close",
        "change",
        "volume",
        "Perf.W",
        "Perf.1M",
        "Perf.3M",
        "Perf.6M",
        "Perf.YTD",
        "Perf.Y",
        "SMA20",
        "SMA50",
        "SMA200",
        "RSI",
        "ATR",
    ]
    clean_to_orig: dict[str, list[str]] = {}
    for sym in symbols:
        base = sym.split(":")[-1].strip().upper()
        clean_to_orig.setdefault(base, []).append(sym)

    clean_names = list(clean_to_orig.keys())
    results: dict[str, dict] = {}
    total_batches = math.ceil(len(clean_names) / batch_size)

    for idx, i in enumerate(range(0, len(clean_names), batch_size), start=1):
        batch = clean_names[i : i + batch_size]
        payload = {
            "filter": [{"left": "name", "operation": "in_range", "right": batch}],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": tv_columns,
            "range": [0, len(batch) + 50],
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            resp.raise_for_status()
            for item in resp.json().get("data", []):
                d = item.get("d", [])
                if not d or len(d) < len(tv_columns):
                    continue
                row_dict = dict(zip(tv_columns, d))
                name = str(row_dict.get("name", "")).strip().upper()
                if name in clean_to_orig and name not in results:
                    for orig_sym in clean_to_orig[name]:
                        results[orig_sym] = row_dict
        except Exception as e:
            print(f"[WARN] TradingView batch {idx}/{total_batches} issue: {e}")

        if idx < total_batches:
            time.sleep(pause_sec)

    print(f"TradingView returned data for {len(results)}/{len(symbols)} symbols.")
    return results


# === [SEC-04: FINNHUB UPCOMING EARNINGS CALENDAR] ===
def fetch_upcoming_earnings_finnhub() -> dict[str, str]:
    """Fetches upcoming earnings dates (next 120 days) in a single Finnhub API call."""
    if not FINNHUB_API_KEY:
        print("FINNHUB_API_KEY not set; skipping upcoming earnings date lookup.")
        return {}

    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=120)
    url = "https://finnhub.io/api/v1/calendar/earnings"
    params = {
        "from": today.isoformat(),
        "to": end_date.isoformat(),
        "token": FINNHUB_API_KEY,
    }
    earnings_map: dict[str, str] = {}
    try:
        resp = requests.get(url, params=params, timeout=25)
        resp.raise_for_status()
        for item in resp.json().get("earningsCalendar", []):
            sym = str(item.get("symbol", "")).strip().upper()
            dt_str = str(item.get("date", "")).strip()
            if sym and dt_str:
                if sym not in earnings_map or dt_str < earnings_map[sym]:
                    earnings_map[sym] = dt_str
        print(f"Finnhub loaded upcoming earnings dates for {len(earnings_map)} market tickers.")
    except Exception as e:
        print(f"[WARN] Finnhub earnings fetch issue: {e}")

    return earnings_map


# === [SEC-05: HISTORICAL OHLCV BATCH DOWNLOADER] ===
def extract_ticker_df(raw_df: pd.DataFrame, yf_sym: str) -> pd.DataFrame:
    """Safely extracts single-ticker OHLCV DataFrame from yf.download output."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    if isinstance(raw_df.columns, pd.MultiIndex):
        if yf_sym not in raw_df.columns.get_level_values(0):
            return pd.DataFrame()
        df = raw_df[yf_sym].copy()
    else:
        df = raw_df.copy()

    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    df = df[required].dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.sort_index()


def fetch_historical_bars(
    yf_tickers: list[str], batch_size: int = 20, pause_sec: float = 5.0
) -> dict[str, pd.DataFrame]:
    """Downloads 3y daily OHLCV bars in small, spaced chunks with cooldown retry."""
    hist_map: dict[str, pd.DataFrame] = {}
    total_batches = math.ceil(len(yf_tickers) / batch_size)

    for idx, i in enumerate(range(0, len(yf_tickers), batch_size), start=1):
        batch = yf_tickers[i : i + batch_size]
        print(f"Fetching historical batch {idx}/{total_batches} ({len(batch)} symbols)...")

        for attempt in (1, 2):
            try:
                raw_df = yf.download(
                    tickers=batch,
                    period="3y",
                    interval="1d",
                    auto_adjust=False,
                    group_by="ticker",
                    progress=False,
                    threads=False,
                )
                batch_hits = 0
                for yf_sym in batch:
                    df = extract_ticker_df(raw_df, yf_sym)
                    if not df.empty:
                        hist_map[yf_sym] = df
                        batch_hits += 1

                if batch_hits > 0 or attempt == 2:
                    break
                print(f"[RETRY] Batch {idx} returned empty, cooling down 15s...")
                time.sleep(15.0)
            except Exception as e:
                print(f"[WARN] Historical batch {idx}/{total_batches} attempt {attempt} issue: {e}")
                if attempt == 1:
                    time.sleep(15.0)

        if idx < total_batches:
            time.sleep(pause_sec)

    print(f"Historical bars retrieved for {len(hist_map)}/{len(yf_tickers)} tickers.")
    return hist_map


# === [SEC-06: TECHNICAL INDICATORS & SWING S/R LEVELS] ===
def compute_wilder_rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = avg_gain.iloc[-1] / last_loss
    return clean_num(100.0 - (100.0 / (1.0 + rs)), 2)


def compute_wilder_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    if len(df) < period + 1:
        return None
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return clean_num(atr.iloc[-1], 4)


def cluster_levels(levels: list[float], tolerance_pct: float = 0.004) -> list[float]:
    """Merges swing levels within 0.4% of each other to avoid stacked duplicate lines."""
    if not levels:
        return []
    sorted_lvls = sorted(levels)
    clustered = [sorted_lvls[0]]
    for lvl in sorted_lvls[1:]:
        if abs(lvl - clustered[-1]) / clustered[-1] <= tolerance_pct:
            clustered[-1] = (clustered[-1] + lvl) / 2.0
        else:
            clustered.append(lvl)
    return clustered


def extract_swing_sr(
    df: pd.DataFrame, current_price: float, left: int, right: int
) -> tuple[list[float | None], list[float | None]]:
    """Finds 5 closest supports below price and 5 closest resistances above price."""
    if df is None or len(df) < (left + right + 1) or current_price <= 0:
        return [None] * 5, [None] * 5

    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    n = len(df)

    raw_pivots: list[float] = []
    for idx in range(left, n - right):
        win_high = highs[idx - left : idx + right + 1]
        if highs[idx] == np.max(win_high):
            raw_pivots.append(float(highs[idx]))

        win_low = lows[idx - left : idx + right + 1]
        if lows[idx] == np.min(win_low):
            raw_pivots.append(float(lows[idx]))

    unique_pivots = cluster_levels(raw_pivots, tolerance_pct=0.004)

    supports = sorted([p for p in unique_pivots if p < current_price * 0.999], reverse=True)[:5]
    resistances = sorted([p for p in unique_pivots if p > current_price * 1.001])[:5]

    s_out = [clean_num(supports[i], 2) if i < len(supports) else None for i in range(5)]
    r_out = [clean_num(resistances[i], 2) if i < len(resistances) else None for i in range(5)]
    return s_out, r_out


def pct_return_bars(closes: pd.Series, lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    base = float(closes.iloc[-(lookback + 1)])
    curr = float(closes.iloc[-1])
    if base == 0:
        return None
    return clean_num(((curr - base) / base) * 100.0, 2)


def daily_step_return(closes: pd.Series, days_ago: int) -> float | None:
    """Returns single-day % change `days_ago` sessions back (1 = yesterday's session)."""
    idx_curr = -(days_ago + 1)
    idx_prev = -(days_ago + 2)
    if len(closes) < abs(idx_prev):
        return None
    prev_val = float(closes.iloc[idx_prev])
    curr_val = float(closes.iloc[idx_curr])
    if prev_val == 0:
        return None
    return clean_num(((curr_val - prev_val) / prev_val) * 100.0, 2)


# === [SEC-07: SNAPSHOT BUILDER FOR SINGLE SYMBOL] ===
def build_snapshot_row(
    symbol: str,
    tv: dict,
    df: pd.DataFrame,
    next_earnings: str | None,
    now_iso: str,
) -> dict | None:
    has_df = df is not None and not df.empty
    closes = df["Close"] if has_df else pd.Series(dtype=float)
    vols = df["Volume"] if has_df else pd.Series(dtype=float)

    # Price & Today % Change
    price = clean_num(tv.get("close"), 2)
    if price is None and has_df:
        price = clean_num(closes.iloc[-1], 2)
    if price is None or price <= 0:
        return None

    change_today = clean_num(tv.get("change"), 2)
    if change_today is None and len(closes) >= 2:
        change_today = pct_return_bars(closes, 1)

    # Daily historical returns (1d..4d ago)
    c_1d = daily_step_return(closes, 1) if has_df else None
    c_2d = daily_step_return(closes, 2) if has_df else None
    c_3d = daily_step_return(closes, 3) if has_df else None
    c_4d = daily_step_return(closes, 4) if has_df else None

    # Start of the week (WTD)
    wtd = None
    if has_df and len(df) >= 2:
        last_dt = df.index[-1]
        last_iso = last_dt.isocalendar()
        prior_weeks = df[
            [
                (d.isocalendar().year, d.isocalendar().week)
                < (last_iso.year, last_iso.week)
                for d in df.index
            ]
        ]
        if not prior_weeks.empty:
            prev_wk_close = float(prior_weeks["Close"].iloc[-1])
            if prev_wk_close > 0:
                wtd = clean_num(((price - prev_wk_close) / prev_wk_close) * 100.0, 2)

    # Multi-period returns
    weekly = clean_num(tv.get("Perf.W"), 2)
    if weekly is None and has_df:
        weekly = pct_return_bars(closes, 5)

    two_weeks = pct_return_bars(closes, 10) if has_df else None
    three_weeks = pct_return_bars(closes, 15) if has_df else None

    monthly = clean_num(tv.get("Perf.1M"), 2)
    if monthly is None and has_df:
        monthly = pct_return_bars(closes, 21)

    three_months = clean_num(tv.get("Perf.3M"), 2)
    if three_months is None and has_df:
        three_months = pct_return_bars(closes, 63)

    six_months = clean_num(tv.get("Perf.6M"), 2)
    if six_months is None and has_df:
        six_months = pct_return_bars(closes, 126)

    nine_months = pct_return_bars(closes, 189) if has_df else None

    ytd = clean_num(tv.get("Perf.YTD"), 2)
    if ytd is None and has_df:
        curr_year = df.index[-1].year
        prev_year_bars = df[df.index.year < curr_year]
        if not prev_year_bars.empty:
            yr_base = float(prev_year_bars["Close"].iloc[-1])
            if yr_base > 0:
                ytd = clean_num(((price - yr_base) / yr_base) * 100.0, 2)

    one_year = clean_num(tv.get("Perf.Y"), 2)
    if one_year is None and has_df:
        one_year = pct_return_bars(closes, 252)

    # Volumes & Relative Volume (baseline excludes today's bar)
    daily_vol = int(tv["volume"]) if tv.get("volume") is not None else (
        int(vols.iloc[-1]) if has_df else None
    )
    vol_1d = int(vols.iloc[-2]) if has_df and len(vols) >= 2 else None
    vol_2d = int(vols.iloc[-3]) if has_df and len(vols) >= 3 else None
    vol_3d = int(vols.iloc[-4]) if has_df and len(vols) >= 4 else None
    vol_4d = int(vols.iloc[-5]) if has_df and len(vols) >= 5 else None

    def calc_rel_vol(window: int) -> float | None:
        if not has_df or daily_vol is None or len(vols) < window + 1:
            return None
        avg_v = float(vols.iloc[-(window + 1) : -1].mean())
        if avg_v <= 0:
            return None
        return clean_num(daily_vol / avg_v, 2)

    # Moving Averages (20, 50, 150, 200)
    def calc_ma_block(period: int, tv_key: str | None) -> tuple[str | None, float | None, float | None]:
        ma_val = clean_num(tv.get(tv_key), 2) if tv_key else None
        if ma_val is None and has_df and len(closes) >= period:
            ma_val = clean_num(closes.iloc[-period:].mean(), 2)
        if ma_val is None or ma_val <= 0:
            return None, None, None
        status = "Above" if price >= ma_val else "Below"
        dist_pct = clean_num(((price - ma_val) / ma_val) * 100.0, 2)
        return status, ma_val, dist_pct

    ma20_st, ma20_v, ma20_d = calc_ma_block(20, "SMA20")
    ma50_st, ma50_v, ma50_d = calc_ma_block(50, "SMA50")
    ma150_st, ma150_v, ma150_d = calc_ma_block(150, None)
    ma200_st, ma200_v, ma200_d = calc_ma_block(200, "SMA200")

    # RSI & ATR
    rsi = clean_num(tv.get("RSI"), 2)
    if rsi is None and has_df:
        rsi = compute_wilder_rsi(closes, 14)

    atr_14 = clean_num(tv.get("ATR"), 2)
    if atr_14 is None and has_df:
        atr_14 = compute_wilder_atr(df, 14)
    atr_pct = clean_num((atr_14 / price) * 100.0, 2) if (atr_14 is not None and price > 0) else None

    # Daily & Weekly Support / Resistance Levels
    d_sup, d_res = extract_swing_sr(df, price, left=5, right=5) if has_df else ([None] * 5, [None] * 5)
    if has_df and len(df) >= 35:
        weekly_df = (
            df.resample("W-FRI")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna(subset=["Close"])
        )
        w_sup, w_res = extract_swing_sr(weekly_df, price, left=3, right=3)
    else:
        w_sup, w_res = [None] * 5, [None] * 5

    return {
        "symbol": symbol,
        "price": price,
        "change_today_pct": change_today,
        "live_price": None,
        "live_updated_at": None,
        "change_1d": c_1d,
        "change_2d": c_2d,
        "change_3d": c_3d,
        "change_4d": c_4d,
        "start_of_the_week": wtd,
        "weekly": weekly,
        "two_weeks": two_weeks,
        "three_weeks": three_weeks,
        "monthly": monthly,
        "three_months": three_months,
        "six_months": six_months,
        "nine_months": nine_months,
        "ytd": ytd,
        "one_year": one_year,
        "daily_vol": daily_vol,
        "vol_1d": vol_1d,
        "vol_2d": vol_2d,
        "vol_3d": vol_3d,
        "vol_4d": vol_4d,
        "rel_vol_5d": calc_rel_vol(5),
        "rel_vol_10d": calc_rel_vol(10),
        "rel_vol_15d": calc_rel_vol(15),
        "rel_vol_20d": calc_rel_vol(20),
        "rel_vol_30d": calc_rel_vol(30),
        "ma_20_status": ma20_st,
        "ma_20_value": ma20_v,
        "ma_20_dist_pct": ma20_d,
        "ma_50_status": ma50_st,
        "ma_50_value": ma50_v,
        "ma_50_dist_pct": ma50_d,
        "ma_150_status": ma150_st,
        "ma_150_value": ma150_v,
        "ma_150_dist_pct": ma150_d,
        "ma_200_status": ma200_st,
        "ma_200_value": ma200_v,
        "ma_200_dist_pct": ma200_d,
        "rsi": rsi,
        "atr_14": atr_14,
        "atr_pct": atr_pct,
        "d_s_1": d_sup[0],
        "d_s_2": d_sup[1],
        "d_s_3": d_sup[2],
        "d_s_4": d_sup[3],
        "d_s_5": d_sup[4],
        "d_r_1": d_res[0],
        "d_r_2": d_res[1],
        "d_r_3": d_res[2],
        "d_r_4": d_res[3],
        "d_r_5": d_res[4],
        "w_s_1": w_sup[0],
        "w_s_2": w_sup[1],
        "w_s_3": w_sup[2],
        "w_s_4": w_sup[3],
        "w_s_5": w_sup[4],
        "w_r_1": w_res[0],
        "w_r_2": w_res[1],
        "w_r_3": w_res[2],
        "w_r_4": w_res[3],
        "w_r_5": w_res[4],
        "next_earnings_date": next_earnings,
        "updated_at": now_iso,
    }


# === [SEC-08: MAIN PIPELINE EXECUTION & SUPABASE UPSERT] ===
def main():
    symbols = fetch_active_watchlist(limit=EOD_LIMIT)
    if not symbols:
        print("No active symbols found in watchlist.")
        return

    tv_data = fetch_tradingview_data(symbols, batch_size=150, pause_sec=3.0)
    earnings_map = fetch_upcoming_earnings_finnhub()

    yf_map = {
        sym: sym.split(":")[-1].strip().upper().replace(".", "-")
        for sym in symbols
    }
    unique_yf_tickers = sorted(set(yf_map.values()))
    hist_map = fetch_historical_bars(unique_yf_tickers, batch_size=20, pause_sec=5.0)

    now_iso = datetime.now(timezone.utc).isoformat()
    snapshot_rows: list[dict] = []

    for sym in symbols:
        base_ticker = sym.split(":")[-1].strip().upper()
        yf_sym = yf_map[sym]
        row = build_snapshot_row(
            symbol=sym,
            tv=tv_data.get(sym, {}),
            df=hist_map.get(yf_sym, pd.DataFrame()),
            next_earnings=earnings_map.get(base_ticker),
            now_iso=now_iso,
        )
        if row:
            snapshot_rows.append(row)
        else:
            print(f"[SKIP] Insufficient price data for {sym}")

    print(f"Built {len(snapshot_rows)}/{len(symbols)} snapshot rows. Upserting to Supabase...")

    upsert_batch_size = 100
    for i in range(0, len(snapshot_rows), upsert_batch_size):
        chunk = snapshot_rows[i : i + upsert_batch_size]
        supabase.table("stocks_snapshot").upsert(chunk, on_conflict="symbol").execute()

    print(f"EOD sync completed successfully: {len(snapshot_rows)} stocks updated.")


if __name__ == "__main__":
    main()
