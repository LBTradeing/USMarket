# === [SEC-01: IMPORTS & FILTER RESET CALLBACK] ===
import html
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from db import (
    load_market_dataframe,
    refresh_live_prices_tv,
    find_pending_new_symbols,
    sync_single_new_stock,
)
from ui_theme import render_logo_html, format_pct_color


def _reset_all_filters() -> None:
    """Resets all screener filter widgets in session_state cleanly."""
    st.session_state["flt_search"] = ""
    st.session_state["flt_exch"] = "הכל"
    st.session_state["flt_sector"] = "הכל"
    st.session_state["flt_ind"] = "הכל"
    st.session_state["flt_sub_ind"] = "הכל"
    st.session_state["flt_dir"] = "הכל"
    st.session_state["flt_earn"] = "הכל"
    st.session_state["flt_sort"] = "סימול (A-Z)"
    st.session_state["flt_rvol"] = 0.0
    st.session_state["flt_squeeze"] = 0.0
    st.session_state["flt_atr_pct"] = 0.0
    st.session_state["flt_rsi"] = (0, 100)
    for p in (20, 50, 150, 200):
        st.session_state[f"flt_use_ma_{p}"] = False
        st.session_state[f"flt_dir_ma_{p}"] = "מעל ▲"


# === [SEC-02: TOP CONTROL BAR (LIVE MODE & NEW STOCKS SYNC)] ===
def render_top_controls(all_symbols: list[str]) -> tuple[bool, int]:
    c_live, c_freq, c_btn_now, c_new_box = st.columns([1.4, 1.3, 1.3, 2.2])

    with c_live:
        live_on = st.toggle("מצב מסחר חי (LIVE)", value=False, key="screener_live_toggle")

    with c_freq:
        freq_map = {
            "רענון כל 30 שניות": 30,
            "רענון כל דקה": 60,
            "רענון כל 3 דקות": 180,
            "רענון כל 5 דקות": 300,
        }
        freq_label = st.selectbox(
            "תדירות רענון",
            options=list(freq_map.keys()),
            index=1,
            disabled=not live_on,
            label_visibility="collapsed",
            key="screener_live_freq",
        )
        run_every_sec = freq_map[freq_label]

    with c_btn_now:
        if st.button("רענון מחירים כעת", use_container_width=True):
            with st.spinner("מושך שערים חיים..."):
                updated = refresh_live_prices_tv(all_symbols)
                st.toast(f"עודכנו שערים חיים עבור {updated} מניות")

    with c_new_box:
        with st.popover("הוספה / סנכרון מניות חדשות", use_container_width=True):
            st.markdown("**הוספת טיקר חדש או השלמת מניות שנוספו אחרי 05:00**")
            new_ticker_input = st.text_input(
                "הזן טיקר (לדוגמה: PLTR)",
                placeholder="לדוגמה: PLTR",
                key="new_ticker_field",
            )
            if st.button("הוסף וסנכרן טיקר זה", type="primary", use_container_width=True):
                if new_ticker_input.strip():
                    with st.spinner(f"מבצע סנכרון מלא עבור {new_ticker_input.upper()}..."):
                        ok, msg = sync_single_new_stock(new_ticker_input)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            st.divider()
            pending_syms = find_pending_new_symbols()
            if pending_syms:
                st.info(f"זוהו {len(pending_syms)} מניות חדשות הממתינות להשלמה: {', '.join(pending_syms[:8])}")
                if st.button("השלם נתונים לכל המניות החדשות", use_container_width=True):
                    prog = st.progress(0)
                    for idx, sym in enumerate(pending_syms, start=1):
                        sync_single_new_stock(sym)
                        prog.progress(idx / len(pending_syms))
                    st.success("כל המניות החדשות הושלמו בהצלחה!")
                    st.rerun()
            else:
                st.caption("כל המניות ברשימת המעקב מסונכרנות ומעודכנות.")

    return live_on, run_every_sec


# === [SEC-03: ADVANCED FILTER & SORT ENGINE (COLLAPSED BY DEFAULT)] ===
def render_filters_and_sort(df: pd.DataFrame) -> pd.DataFrame:
    # Count active filters so the collapsed header reflects active state
    active_count = 0
    if st.session_state.get("flt_search", "").strip():
        active_count += 1
    for k in ("flt_exch", "flt_sector", "flt_ind", "flt_sub_ind", "flt_dir", "flt_earn"):
        if st.session_state.get(k, "הכל") != "הכל":
            active_count += 1
    if st.session_state.get("flt_rvol", 0.0) > 0:
        active_count += 1
    if st.session_state.get("flt_squeeze", 0.0) > 0:
        active_count += 1
    if st.session_state.get("flt_atr_pct", 0.0) > 0:
        active_count += 1
    if st.session_state.get("flt_rsi", (0, 100)) != (0, 100):
        active_count += 1
    for p in (20, 50, 150, 200):
        if st.session_state.get(f"flt_use_ma_{p}", False):
            active_count += 1

    expander_label = (
        f"סינון ומיון מתקדם (פעילים: {active_count} מסננים)"
        if active_count > 0
        else "סינון ומיון מתקדם"
    )

    with st.expander(expander_label, expanded=False):
        # --- Row 1: Free Search, Exchange, Sector, Industry ---
        r1_c1, r1_c2, r1_c3, r1_c4 = st.columns([1.6, 1.0, 1.2, 1.3])

        with r1_c1:
            search_q = st.text_input(
                "חיפוש חופשי",
                placeholder="טיקר, שם חברה או מילת מפתח בתיאור...",
                key="flt_search",
            ).strip().lower()

        with r1_c2:
            exchanges = (
                ["הכל"] + sorted(df["exchange"].dropna().unique().tolist())
                if "exchange" in df.columns
                else ["הכל"]
            )
            if st.session_state.get("flt_exch") not in exchanges:
                st.session_state["flt_exch"] = "הכל"
            sel_exch = st.selectbox("בורסה", exchanges, key="flt_exch")

        with r1_c3:
            sectors = (
                ["הכל"] + sorted(df["sector"].dropna().unique().tolist())
                if "sector" in df.columns
                else ["הכל"]
            )
            if st.session_state.get("flt_sector") not in sectors:
                st.session_state["flt_sector"] = "הכל"
            sel_sector = st.selectbox("סקטור", sectors, key="flt_sector")

        with r1_c4:
            df_sec = df if sel_sector == "הכל" else df[df["sector"] == sel_sector]
            industries = (
                ["הכל"] + sorted(df_sec["industry"].dropna().unique().tolist())
                if "industry" in df_sec.columns
                else ["הכל"]
            )
            if st.session_state.get("flt_ind") not in industries:
                st.session_state["flt_ind"] = "הכל"
            sel_ind = st.selectbox("תעשייה", industries, key="flt_ind")

        # --- Row 2: Sub-Industry, Daily Direction, Earnings Shield, Sort ---
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.4, 1.1, 1.3, 1.3])

        with r2_c1:
            df_ind = df_sec if sel_ind == "הכל" else df_sec[df_sec["industry"] == sel_ind]
            sub_inds = (
                ["הכל"] + sorted(df_ind["sub_industry"].dropna().unique().tolist())
                if "sub_industry" in df_ind.columns
                else ["הכל"]
            )
            if st.session_state.get("flt_sub_ind") not in sub_inds:
                st.session_state["flt_sub_ind"] = "הכל"
            sel_sub = st.selectbox("תת-תעשייה", sub_inds, key="flt_sub_ind")

        with r2_c2:
            sel_dir = st.selectbox(
                "כיוון היום",
                ["הכל", "ירוקות היום בלבד", "אדומות היום בלבד"],
                key="flt_dir",
            )

        with r2_c3:
            sel_earn = st.selectbox(
                "דוחות כספיים",
                [
                    "הכל",
                    "ללא דוחות ב-7 ימים קרובים",
                    "ללא דוחות ב-14 ימים קרובים",
                    "רק דוחות ב-7 ימים קרובים",
                ],
                key="flt_earn",
            )

        with r2_c4:
            sort_choice = st.selectbox(
                "מיון לפי",
                [
                    "סימול (A-Z)",
                    "% שינוי יומי (גבוה לנמוך)",
                    "% שינוי יומי (נמוך לגבוה)",
                    "Rel Vol 5D (גבוה לנמוך)",
                    "ATR Squeeze % (גבוה לנמוך)",
                    "ATR % (גבוה לנמוך)",
                    "RSI 14 (נמוך לגבוה)",
                    "RSI 14 (גבוה לנמוך)",
                    "קרבה לדוחות כספיים",
                ],
                key="flt_sort",
            )

        # --- Row 3: Numeric Technical Thresholds ---
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns([1.1, 1.1, 1.1, 1.8])

        with r3_c1:
            min_rvol = st.number_input(
                "מינימום Rel Vol 5D",
                min_value=0.0,
                value=0.0,
                step=0.2,
                key="flt_rvol",
            )

        with r3_c2:
            min_squeeze = st.number_input(
                "מינימום ATR Squeeze %",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=5.0,
                key="flt_squeeze",
            )

        with r3_c3:
            min_atr_pct = st.number_input(
                "מינימום ATR %",
                min_value=0.0,
                value=0.0,
                step=0.5,
                key="flt_atr_pct",
            )

        with r3_c4:
            rsi_range = st.slider(
                "טווח RSI (14)",
                min_value=0,
                max_value=100,
                value=(0, 100),
                key="flt_rsi",
            )

        st.markdown("---")
        st.markdown(
            "**סינון ממוצעים נעים** "
            "<span style='color:#94A3B8; font-size:0.84rem;'>"
            "(סמן כל ממוצע שברצונך לכלול ובחר מעל / מתחת — מתאים לשילובי פולבק ומגמה)"
            "</span>",
            unsafe_allow_html=True,
        )

        # --- Row 4: Modular Moving Averages Checkboxes + Above/Below ---
        ma_cols = st.columns(4)
        ma_conditions: list[tuple[int, str]] = []
        for idx, period in enumerate((20, 50, 150, 200)):
            with ma_cols[idx]:
                use_ma = st.checkbox(f"סנן MA {period}", key=f"flt_use_ma_{period}")
                ma_side = st.radio(
                    f"כיוון MA {period}",
                    options=["מעל ▲", "מתחת ▼"],
                    horizontal=True,
                    disabled=not use_ma,
                    label_visibility="collapsed",
                    key=f"flt_dir_ma_{period}",
                )
                if use_ma:
                    ma_conditions.append((period, "Above" if "מעל" in ma_side else "Below"))

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        _, btn_reset_col = st.columns([4.2, 1.2])
        with btn_reset_col:
            st.button(
                "איפוס כל המסננים",
                on_click=_reset_all_filters,
                use_container_width=True,
            )

    # === APPLY FILTERS ===
    out = df.copy()

    if search_q:
        mask = (
            out["symbol"].fillna("").str.lower().str.contains(search_q, regex=False)
            | out.get("company_name", pd.Series("", index=out.index)).fillna("").str.lower().str.contains(search_q, regex=False)
            | out.get("short_summary", pd.Series("", index=out.index)).fillna("").str.lower().str.contains(search_q, regex=False)
        )
        out = out[mask]

    if sel_exch != "הכל" and "exchange" in out.columns:
        out = out[out["exchange"] == sel_exch]

    if sel_sector != "הכל" and "sector" in out.columns:
        out = out[out["sector"] == sel_sector]

    if sel_ind != "הכל" and "industry" in out.columns:
        out = out[out["industry"] == sel_ind]

    if sel_sub != "הכל" and "sub_industry" in out.columns:
        out = out[out["sub_industry"] == sel_sub]

    if sel_dir == "ירוקות היום בלבד" and "change_today_pct" in out.columns:
        out = out[out["change_today_pct"].fillna(0) > 0]
    elif sel_dir == "אדומות היום בלבד" and "change_today_pct" in out.columns:
        out = out[out["change_today_pct"].fillna(0) < 0]

    if sel_earn != "הכל" and "next_earnings_date" in out.columns:
        today_dt = datetime.now(timezone.utc).date()
        parsed_dates = pd.to_datetime(out["next_earnings_date"], errors="coerce").dt.date
        days_diff = parsed_dates.apply(lambda d: (d - today_dt).days if pd.notna(d) else None)
        if sel_earn == "ללא דוחות ב-7 ימים קרובים":
            out = out[days_diff.isna() | (days_diff < 0) | (days_diff > 7)]
        elif sel_earn == "ללא דוחות ב-14 ימים קרובים":
            out = out[days_diff.isna() | (days_diff < 0) | (days_diff > 14)]
        elif sel_earn == "רק דוחות ב-7 ימים קרובים":
            out = out[days_diff.notna() & (days_diff >= 0) & (days_diff <= 7)]

    if min_rvol > 0 and "rel_vol_5d" in out.columns:
        out = out[out["rel_vol_5d"].fillna(0) >= min_rvol]

    if min_squeeze > 0 and "atr_squeeze_pct" in out.columns:
        out = out[out["atr_squeeze_pct"].fillna(0) >= min_squeeze]

    if min_atr_pct > 0 and "atr_pct" in out.columns:
        out = out[out["atr_pct"].fillna(0) >= min_atr_pct]

    if rsi_range != (0, 100) and "rsi" in out.columns:
        low_rsi, high_rsi = rsi_range
        out = out[out["rsi"].notna() & (out["rsi"] >= low_rsi) & (out["rsi"] <= high_rsi)]

    for period, expected_status in ma_conditions:
        col_name = f"ma_{period}_status"
        if col_name in out.columns:
            out = out[out[col_name] == expected_status]

    # === APPLY SORTING ===
    if sort_choice == "% שינוי יומי (גבוה לנמוך)":
        out = out.sort_values("change_today_pct", ascending=False, na_position="last")
    elif sort_choice == "% שינוי יומי (נמוך לגבוה)":
        out = out.sort_values("change_today_pct", ascending=True, na_position="last")
    elif sort_choice == "Rel Vol 5D (גבוה לנמוך)" and "rel_vol_5d" in out.columns:
        out = out.sort_values("rel_vol_5d", ascending=False, na_position="last")
    elif sort_choice == "ATR Squeeze % (גבוה לנמוך)" and "atr_squeeze_pct" in out.columns:
        out = out.sort_values("atr_squeeze_pct", ascending=False, na_position="last")
    elif sort_choice == "ATR % (גבוה לנמוך)" and "atr_pct" in out.columns:
        out = out.sort_values("atr_pct", ascending=False, na_position="last")
    elif sort_choice == "RSI 14 (נמוך לגבוה)" and "rsi" in out.columns:
        out = out.sort_values("rsi", ascending=True, na_position="last")
    elif sort_choice == "RSI 14 (גבוה לנמוך)" and "rsi" in out.columns:
        out = out.sort_values("rsi", ascending=False, na_position="last")
    elif sort_choice == "קרבה לדוחות כספיים" and "next_earnings_date" in out.columns:
        out = out.sort_values("next_earnings_date", ascending=True, na_position="last")
    else:
        out = out.sort_values("symbol", ascending=True)

    return out.reset_index(drop=True)


# === [SEC-04: STOCK RECTANGLE CARDS GRID] ===
def render_cards_grid(df_filtered: pd.DataFrame) -> None:
    if df_filtered.empty:
        st.warning("לא נמצאו מניות התואמות לסינון שנבחר.")
        return

    page_size = 30
    total_pages = max(1, (len(df_filtered) + page_size - 1) // page_size)
    if total_pages > 1:
        pg_num = st.number_input(
            f"עמוד (מתוך {total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key="cards_page_num",
        )
    else:
        pg_num = 1

    start_idx = (pg_num - 1) * page_size
    page_df = df_filtered.iloc[start_idx : start_idx + page_size]

    cols_per_row = 3
    rows_list = [page_df.iloc[i : i + cols_per_row] for i in range(0, len(page_df), cols_per_row)]

    for row_chunk in rows_list:
        cols = st.columns(cols_per_row)
        for col_idx, (_, r) in enumerate(row_chunk.iterrows()):
            sym = str(r["symbol"])
            comp_name = html.escape(str(r.get("company_name") or sym))
            logo_html = render_logo_html(sym, r.get("logo_url"), size=38)

            price_val = r.get("display_price")
            price_str = f"${price_val:,.2f}" if pd.notna(price_val) else "--"
            pct_str, pct_color = format_pct_color(
                r.get("change_today_pct") if pd.notna(r.get("change_today_pct")) else None
            )

            with cols[col_idx]:
                st.markdown(
                    f"""
                    <div class="stock-card">
                        <div class="stock-card-top">
                            <div class="stock-identity">
                                {logo_html}
                                <div style="min-width:0;">
                                    <div class="stock-name" title="{comp_name}">{comp_name}</div>
                                    <div class="stock-ticker">{html.escape(sym)}</div>
                                </div>
                            </div>
                            <div class="stock-price-block">
                                <div class="stock-pct" style="color:{pct_color};">{pct_str}</div>
                                <div class="stock-price">{price_str}</div>
                            </div>
                        </div>
                        <div class="signal-inner-box">
                            <div class="signal-inner-label">סטטוס איתות</div>
                            <div class="signal-inner-status">ממתין לאיתות</div>
                            <div class="signal-score-row">
                                <span>ציון</span>
                                <span class="ltr-num">--</span>
                            </div>
                            <div class="signal-bar-bg"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("ניתוח עומק", key=f"open_dd_{sym}", use_container_width=True):
                    st.session_state["selected_symbol"] = sym
                    st.switch_page("views/deep_dive.py")


# === [SEC-05: MAIN PAGE ORCHESTRATION WITH LIVE FRAGMENT] ===
def render_live_workspace(all_symbols: list[str], auto_refresh_live: bool) -> None:
    if auto_refresh_live:
        refresh_live_prices_tv(all_symbols)

    df = load_market_dataframe()
    if df.empty:
        st.info("אין עדיין נתונים להצגה. לחץ על 'הוספה / סנכרון מניות חדשות' למעלה.")
        return

    df_filtered = render_filters_and_sort(df)

    live_series = df["live_updated_at"].dropna() if "live_updated_at" in df.columns else pd.Series(dtype=str)
    eod_series = df["updated_at"].dropna() if "updated_at" in df.columns else pd.Series(dtype=str)
    last_ts = live_series.max() if not live_series.empty else (eod_series.max() if not eod_series.empty else "")
    ts_display = str(last_ts)[:19].replace("T", " ") if pd.notna(last_ts) and str(last_ts) else "--"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                {('<span class="live-pill"><span class="live-dot"></span>LIVE</span>' if auto_refresh_live else '<span class="badge-pill badge-slate">נתוני סגירה (EOD)</span>')}
                <span class="badge-pill badge-blue">מציג {len(df_filtered)} מתוך {len(df)} מניות</span>
            </div>
            <div style="color:#94A3B8; font-size:0.8rem;">
                עדכון אחרון: <span class="ltr-num">{ts_display} UTC</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_cards_grid(df_filtered)


def main() -> None:
    df_init = load_market_dataframe()
    all_symbols = df_init["symbol"].tolist() if not df_init.empty else []

    live_on, run_every_sec = render_top_controls(all_symbols)

    if live_on:
        @st.fragment(run_every=run_every_sec)
        def _live_fragment():
            render_live_workspace(all_symbols, auto_refresh_live=True)

        _live_fragment()
    else:
        render_live_workspace(all_symbols, auto_refresh_live=False)


main()
