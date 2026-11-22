import os
import math
from datetime import datetime, timezone
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
LIMIT = int(os.environ.get("STOCK_LIMIT", "0"))


def clean_num(val, decimals=4):
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def clean_int(val):
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(round(f))
    except (ValueError, TypeError):
        return None


def fetch_tradingview_data(symbols: list[str]) -> dict[str, dict]:
    """Fetches EOD snapshot metrics from TradingView Screener API in batches."""
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
    clean_to_orig = {}
    for sym in symbols:
        base = sym.split(":")[-1].strip().upper()
        clean_to_orig.setdefault(base, []).append(sym)

    clean_names = list(clean_to_orig.keys())
    results = {}

    for i in range(0, len(clean_names), 200):
        batch = clean_names[i : i + 200]
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
            data = resp.json().get("data", [])
            for item in data:
                d = item.get("d", [])
                if not d or len(d) < len(tv_columns):
                    continue
                row_dict = dict(zip(tv_columns, d))
                name = str(row_dict.get("name", "")).upper()
                if name in clean_to_orig and name not in results:
                    for orig_sym in clean_to_orig[name]:
                        results[orig_sym] = row_dict
        except Exception as e:
            print(f"[WARN] TradingView batch fetch issue: {e}")

    print(f"TradingView returned data for {len(results)}/{len(symbols)} symbols.")
    return results


def extract_ticker_df(raw_df: pd.DataFrame, yf_sym: str, single_mode: bool) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()
    if single_mode and not isinstance(raw_df.columns, pd.MultiIndex):
        df = raw_df.copy()
    else:
        if yf_sym not in raw_df.columns.get_level_values(0):
            return pd.DataFrame()
        df = raw_df[yf_sym].copy()
    df = df.dropna(subset=["Close"])
    if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return (
        df.resample("W-FRI")
        .agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )
        .dropna(subset=["Close"])
    )


def find_swing_levels(
    df: pd.DataFrame,
    price: float | None,
    left: int = 5,
    right: int = 5,
    min_gap_pct: float = 0.005,
) -> tuple[list[float | None], list[float | None]]:
    """
    Finds up to 5 nearest Swing Lows (supports < price) and 5 nearest Swing Highs (resistances > price),
    matching TradingView's ta.pivotlow(left, right) and ta.pivothigh(left, right).
    Index 0 = closest to current price, Index 4 = furthest.
    """
    if df is None or df.empty or price is None or len(df) < (left + right + 1):
        return [None] * 5, [None] * 5

    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    n = len(df)

    raw_supports = []
    raw_resistances = []

    # Scan backwards from newest confirmed pivot so most recent levels take priority when clustering
    for i in range(n - right - 1, left - 1, -1):
        if not np.isnan(highs[i]):
            window_high = highs[i - left : i + right + 1]
            if highs[i] == np.nanmax(window_high) and highs[i] > price:
                raw_resistances.append(float(highs[i]))

        if not np.isnan(lows[i]):
            window_low = lows[i - left : i + right + 1]
            if lows[i] == np.nanmin(window_low) and lows[i] < price:
                raw_supports.append(float(lows[i]))

    def cluster_levels(levels: list[float]) -> list[float]:
        clustered = []
        for lvl in levels:
            if all(
                abs(lvl - existing) / existing >= min_gap_pct
                for existing in clustered
                if existing > 0
            ):
                clustered.append(lvl)
        return clustered

    supports = sorted(cluster_levels(raw_supports), reverse=True)[:5]
    resistances = sorted(cluster_levels(raw_resistances))[:5]

    supports_padded = [clean_num(x, 2) for x in supports] + [None] * (5 - len(supports))
    resistances_padded = [clean_num(x, 2) for x in resistances] + [None] * (5 - len(resistances))
    return supports_padded, resistances_padded


def compute_wilder_rsi(close: pd.Series, period: int = 14):
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return clean_num(rsi.iloc[-1], 2)


def compute_wilder_atr(df: pd.DataFrame, period: int = 14):
    if len(df) < period + 1:
        return None
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return clean_num(atr.iloc[-1], 4)


def pct_return_bars(close: pd.Series, lookback: int):
    if len(close) <= lookback:
        return None
    prev = float(close.iloc[-1 - lookback])
    curr = float(close.iloc[-1])
    if prev == 0:
        return None
    return clean_num(((curr / prev) - 1.0) * 100.0, 2)


def daily_change_at_offset(close: pd.Series, offset: int):
    if len(close) <= offset + 1:
        return None
    curr = float(close.iloc[-1 - offset])
    prev = float(close.iloc[-2 - offset])
    if prev == 0:
        return None
    return clean_num(((curr / prev) - 1.0) * 100.0, 2)


def rel_volume(vol: pd.Series, period: int):
    if len(vol) <= period:
        return None
    today_vol = float(vol.iloc[-1])
    avg_prev = float(vol.iloc[-1 - period : -1].mean())
    if avg_prev <= 0:
        return None
    return clean_num(today_vol / avg_prev, 2)


def main():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    query = supabase.table("watchlist").select("symbol").eq("is_active", True)
    if LIMIT > 0:
        query = query.limit(LIMIT)
    resp = query.execute()
    symbols = [row["symbol"] for row in (resp.data or [])]

    if not symbols:
        print("No active symbols found in watchlist.")
        return

    print(f"Starting EOD sync for {len(symbols)} symbols (LIMIT={LIMIT})...")

    # 1. Fetch primary EOD snapshot from TradingView
    tv_data = fetch_tradingview_data(symbols)

    # 2. Fetch 3 years of daily OHLCV bars (supports multi-period returns + Daily & Weekly S/R pivots)
    yf_map = {
        sym: sym.split(":")[-1].strip().replace(".", "-")
        for sym in symbols
    }
    unique_yf_tickers = list(set(yf_map.values()))
    raw_hist = yf.download(
        tickers=unique_yf_tickers,
        period="3y",
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    single_mode = len(unique_yf_tickers) == 1

    now_iso = datetime.now(timezone.utc).isoformat()
    snapshot_rows = []

    for sym in symbols:
        tv = tv_data.get(sym, {})
        df = extract_ticker_df(raw_hist, yf_map[sym], single_mode)

        if df.empty and not tv:
            print(f"[SKIP] No market data found for {sym}")
            continue

        close = df["Close"] if not df.empty else pd.Series(dtype=float)
        vol = df["Volume"] if not df.empty else pd.Series(dtype=float)

        # Price & Today %
        price = clean_num(tv.get("close"), 4)
        if price is None and not close.empty:
            price = clean_num(close.iloc[-1], 4)

        change_today_pct = clean_num(tv.get("change"), 2)
        if change_today_pct is None and not close.empty:
            change_today_pct = daily_change_at_offset(close, 0)

        # Start of the week (WTD) & YTD from closed daily bars
        start_of_week_pct = None
        ytd_pct = clean_num(tv.get("Perf.YTD"), 2)
        if not df.empty and price is not None:
            latest_dt = df.index[-1]
            latest_iso = latest_dt.isocalendar()
            prev_week_bars = df[
                df.index.map(
                    lambda d: (d.isocalendar()[0], d.isocalendar()[1])
                    < (latest_iso[0], latest_iso[1])
                )
            ]
            if not prev_week_bars.empty:
                pw_close = float(prev_week_bars["Close"].iloc[-1])
                if pw_close > 0:
                    start_of_week_pct = clean_num(((price / pw_close) - 1.0) * 100.0, 2)

            if ytd_pct is None:
                prev_year_bars = df[df.index.year < latest_dt.year]
                if not prev_year_bars.empty:
                    py_close = float(prev_year_bars["Close"].iloc[-1])
                    if py_close > 0:
                        ytd_pct = clean_num(((price / py_close) - 1.0) * 100.0, 2)

        # Multi-period returns
        weekly = clean_num(tv.get("Perf.W"), 2) or pct_return_bars(close, 5)
        two_weeks = pct_return_bars(close, 10)
        three_weeks = pct_return_bars(close, 15)
        monthly = clean_num(tv.get("Perf.1M"), 2) or pct_return_bars(close, 21)
        three_months = clean_num(tv.get("Perf.3M"), 2) or pct_return_bars(close, 63)
        six_months = clean_num(tv.get("Perf.6M"), 2) or pct_return_bars(close, 126)
        nine_months = pct_return_bars(close, 189)
        one_year = clean_num(tv.get("Perf.Y"), 2) or pct_return_bars(close, 252)

        # Daily volumes (last 5 closed sessions)
        daily_vol = clean_int(tv.get("volume"))
        if daily_vol is None and not vol.empty:
            daily_vol = clean_int(vol.iloc[-1])
        vol_1d = clean_int(vol.iloc[-2]) if len(vol) >= 2 else None
        vol_2d = clean_int(vol.iloc[-3]) if len(vol) >= 3 else None
        vol_3d = clean_int(vol.iloc[-4]) if len(vol) >= 4 else None
        vol_4d = clean_int(vol.iloc[-5]) if len(vol) >= 5 else None

        # Moving averages
        def get_sma(period: int, tv_key: str | None):
            val = clean_num(tv.get(tv_key), 4) if tv_key else None
            if val is None and len(close) >= period:
                val = clean_num(close.iloc[-period:].mean(), 4)
            if val is None or price is None or val == 0:
                return None, None, None
            status = "Above" if price > val else "Below"
            dist = clean_num(((price - val) / val) * 100.0, 2)
            return status, val, dist

        ma_20, ma_20_val, ma_20_dist = get_sma(20, "SMA20")
        ma_50, ma_50_val, ma_50_dist = get_sma(50, "SMA50")
        ma_150, ma_150_val, ma_150_dist = get_sma(150, None)
        ma_200, ma_200_val, ma_200_dist = get_sma(200, "SMA200")

        # RSI & ATR
        rsi_val = clean_num(tv.get("RSI"), 2)
        if rsi_val is None and not close.empty:
            rsi_val = compute_wilder_rsi(close, 14)

        atr_val = clean_num(tv.get("ATR"), 4)
        if atr_val is None and not df.empty:
            atr_val = compute_wilder_atr(df, 14)

        atr_pct = (
            clean_num((atr_val / price) * 100.0, 2)
            if (atr_val is not None and price is not None and price > 0)
            else None
        )

        # Daily (D) & Weekly (W) Support and Resistance levels (5 each)
        d_sup, d_res = find_swing_levels(df, price, left=5, right=5, min_gap_pct=0.005)
        weekly_df = resample_weekly(df)
        w_sup, w_res = find_swing_levels(weekly_df, price, left=3, right=3, min_gap_pct=0.01)

        snapshot_rows.append(
            {
                "symbol": sym,
                "price": price,
                "change_today_pct": change_today_pct,
                "change_1d": daily_change_at_offset(close, 1),
                "change_2d": daily_change_at_offset(close, 2),
                "change_3d": daily_change_at_offset(close, 3),
                "change_4d": daily_change_at_offset(close, 4),
                "start_of_the_week": start_of_week_pct,
                "weekly": weekly,
                "two_weeks": two_weeks,
                "three_weeks": three_weeks,
                "monthly": monthly,
                "three_months": three_months,
                "six_months": six_months,
                "nine_months": nine_months,
                "ytd": ytd_pct,
                "one_year": one_year,
                "daily_vol": daily_vol,
                "vol_1d": vol_1d,
                "vol_2d": vol_2d,
                "vol_3d": vol_3d,
                "vol_4d": vol_4d,
                "rel_vol_5d": rel_volume(vol, 5),
                "rel_vol_10d": rel_volume(vol, 10),
                "rel_vol_15d": rel_volume(vol, 15),
                "rel_vol_20d": rel_volume(vol, 20),
                "rel_vol_30d": rel_volume(vol, 30),
                "ma_20": ma_20,
                "ma_50": ma_50,
                "ma_150": ma_150,
                "ma_200": ma_200,
                "ma_20_value": ma_20_val,
                "ma_50_value": ma_50_val,
                "ma_150_value": ma_150_val,
                "ma_200_value": ma_200_val,
                "ma_20_dist_pct": ma_20_dist,
                "ma_50_dist_pct": ma_50_dist,
                "ma_150_dist_pct": ma_150_dist,
                "ma_200_dist_pct": ma_200_dist,
                "rsi": rsi_val,
                "atr_14": atr_val,
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
                "updated_at": now_iso,
            }
        )

    for i in range(0, len(snapshot_rows), 200):
        batch = snapshot_rows[i : i + 200]
        supabase.table("stocks_snapshot").upsert(batch, on_conflict="symbol").execute()

    print(f"Successfully upserted {len(snapshot_rows)} rows into stocks_snapshot.")


if __name__ == "__main__":
    main()
