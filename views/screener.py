# === [SEC-01: IMPORTS] ===
import html
import pandas as pd
import streamlit as st
from db import (
    load_market_dataframe,
    refresh_live_prices_tv,
    find_pending_new_symbols,
    sync_single_new_stock,
)
from ui_theme import render_logo_html, format_pct_color


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


# === [SEC-03: FILTER & SORT ENGINE] ===
def render_filters_and_sort(df: pd.DataFrame) -> pd.DataFrame:
    with st.expander("סינון ומיון מתקדם", expanded=True):
        f1, f2, f3, f4 = st.columns([1.6, 1.1, 1.3, 1.3])

        with f1:
            search_q = st.text_input(
                "חיפוש חופשי",
                placeholder="טיקר, שם חברה או מילת מפתח בתיאור...",
                key="flt_search",
            ).strip().lower()

        with f2:
            exchanges = ["הכל"] + sorted(df["exchange"].dropna().unique().tolist()) if "exchange" in df.columns else ["הכל"]
            sel_exch = st.selectbox("בורסה", exchanges, key="flt_exch")

        with f3:
            sectors = ["הכל"] + sorted(df["sector"].dropna().unique().tolist()) if "sector" in df.columns else ["הכל"]
            sel_sector = st.selectbox("סקטור (S&P)", sectors, key="flt_sector")

        with f4:
            sub_df = df if sel_sector == "הכל" else df[df["sector"] == sel_sector]
            sub_inds = ["הכל"] + sorted(sub_df["sub_industry"].dropna().unique().tolist()) if "sub_industry" in sub_df.columns else ["הכל"]
            sel_sub = st.selectbox("תת-תעשייה", sub_inds, key="flt_sub_ind")

        s1, s2, s3 = st.columns([1.4, 1.2, 1.4])

        with s1:
            ma_filter = st.selectbox(
                "ממוצעים נעים",
                ["הכל", "מעל MA 200", "מעל MA 50 ו-MA 200", "מעל כל הממוצעים (20/50/150/200)"],
                key="flt_ma",
            )

        with s2:
            min_rvol = st.number_input("מינימום Rel Vol 5D", min_value=0.0, value=0.0, step=0.2, key="flt_rvol")

        with s3:
            sort_choice = st.selectbox(
                "מיון לפי",
                [
                    "סימול (A-Z)",
                    "% שינוי יומי (גבוה לנמוך)",
                    "% שינוי יומי (נמוך לגבוה)",
                    "Rel Vol 5D (גבוה לנמוך)",
                    "ATR % (גבוה לנמוך)",
                    "קרבה לדוחות כספיים",
                ],
                key="flt_sort",
            )

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

    if sel_sub != "הכל" and "sub_industry" in out.columns:
        out = out[out["sub_industry"] == sel_sub]

    if ma_filter == "מעל MA 200":
        out = out[out["ma_200_status"] == "Above"]
    elif ma_filter == "מעל MA 50 ו-MA 200":
        out = out[(out["ma_50_status"] == "Above") & (out["ma_200_status"] == "Above")]
    elif ma_filter == "מעל כל הממוצעים (20/50/150/200)":
        out = out[
            (out["ma_20_status"] == "Above")
            & (out["ma_50_status"] == "Above")
            & (out["ma_150_status"] == "Above")
            & (out["ma_200_status"] == "Above")
        ]

    if min_rvol > 0 and "rel_vol_5d" in out.columns:
        out = out[out["rel_vol_5d"].fillna(0) >= min_rvol]

    if sort_choice == "% שינוי יומי (גבוה לנמוך)":
        out = out.sort_values("change_today_pct", ascending=False, na_position="last")
    elif sort_choice == "% שינוי יומי (נמוך לגבוה)":
        out = out.sort_values("change_today_pct", ascending=True, na_position="last")
    elif sort_choice == "Rel Vol 5D (גבוה לנמוך)":
        out = out.sort_values("rel_vol_5d", ascending=False, na_position="last")
    elif sort_choice == "ATR % (גבוה לנמוך)":
        out = out.sort_values("atr_pct", ascending=False, na_position="last")
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

    live_series = df["live_updated_at"].dropna() if "live_updated_at" in df.columns else pd.Series(dtype=str)
    eod_series = df["updated_at"].dropna() if "updated_at" in df.columns else pd.Series(dtype=str)
    last_ts = live_series.max() if not live_series.empty else (eod_series.max() if not eod_series.empty else "")
    ts_display = str(last_ts)[:19].replace("T", " ") if pd.notna(last_ts) and str(last_ts) else "--"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
            <div>
                {('<span class="live-pill"><span class="live-dot"></span>LIVE</span>' if auto_refresh_live else '<span class="badge-pill badge-slate">נתוני סגירה (EOD)</span>')}
            </div>
            <div style="color:#94A3B8; font-size:0.8rem;">
                עדכון אחרון: <span class="ltr-num">{ts_display} UTC</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_filtered = render_filters_and_sort(df)
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
