# === [SEC-01: IMPORTS & PAGE HEADER] ===
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


# === [SEC-02: TOP CONTROL BAR (LIVE MODE & NEW STOCKS SYNC)] ===
def render_top_controls(all_symbols: list[str]) -> tuple[bool, int]:
    st.markdown("## סורק מניות ונתוני שוק")

    c_live, c_freq, c_btn_now, c_new_box = st.columns([1.3, 1.3, 1.2, 2.6])

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
        if st.button("🔄 רענון מחירים כעת", use_container_width=True):
            with st.spinner("מושך שערים חיים..."):
                updated = refresh_live_prices_tv(all_symbols)
                st.toast(f"עודכנו שערים חיים עבור {updated} מניות", icon="✅")

    with c_new_box:
        with st.popover("➕ הוספה / סנכרון מניות חדשות", use_container_width=True):
            st.markdown("**הוספת טיקר חדש או השלמת מניות שנוספו אחרי 05:00**")
            new_ticker_input = st.text_input(
                "הזן טיקר (לדוגמה: PLTR)",
                placeholder="לדוגמה: PLTR",
                key="new_ticker_field",
            )
            if st.button("הוסף וסנכרן טיקר זה", type="primary", use_container_width=True):
                if new_ticker_input.strip():
                    with st.spinner(f"מבצע סנכרון מלא (פרופיל, AI, טכני ורמות) עבור {new_ticker_input.upper()}..."):
                        ok, msg = sync_single_new_stock(new_ticker_input)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            st.divider()
            pending_syms = find_pending_new_symbols()
            if pending_syms:
                st.info(f"זוהו {len(pending_syms)} מניות חדשות ב-Watchlist הממתינות להשלמה: {', '.join(pending_syms[:8])}")
                if st.button("⚡ השלם נתונים לכל המניות החדשות", use_container_width=True):
                    prog = st.progress(0)
                    for idx, sym in enumerate(pending_syms, start=1):
                        sync_single_new_stock(sym)
                        prog.progress(idx / len(pending_syms))
                    st.success("כל המניות החדשות הושלמו בהצלחה!")
                    st.rerun()
            else:
                st.caption("כל המניות ב-Watchlist מסונכרנות ומעודכנות.")

    return live_on, run_every_sec


# === [SEC-03: KPI SUMMARY BAR] ===
def render_kpi_bar(df_filtered: pd.DataFrame, total_count: int) -> None:
    count_shown = len(df_filtered)
    above_200 = (
        round((df_filtered["ma_200_status"] == "Above").mean() * 100, 1)
        if count_shown > 0 and "ma_200_status" in df_filtered.columns
        else 0.0
    )
    green_today = (
        round((df_filtered["change_today_pct"] > 0).mean() * 100, 1)
        if count_shown > 0 and "change_today_pct" in df_filtered.columns
        else 0.0
    )

    upcoming_7d = 0
    if count_shown > 0 and "next_earnings_date" in df_filtered.columns:
        today_dt = datetime.now(timezone.utc).date()
        for dt_val in df_filtered["next_earnings_date"].dropna():
            try:
                d_parsed = pd.to_datetime(dt_val).date()
                if 0 <= (d_parsed - today_dt).days <= 7:
                    upcoming_7d += 1
            except Exception:
                pass

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">מניות מוצגות</div>
                <div class="kpi-value ltr-right">{count_shown} <span style="font-size:0.95rem;color:#64748B;">/ {total_count}</span></div>
                <div class="kpi-sub">מתוך רשימת המעקב הפעילה</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">מעל ממוצע 200 (MA200)</div>
                <div class="kpi-value ltr-right" style="color:#10B981;">{above_200}%</div>
                <div class="kpi-sub">רוחב שוק במגמה ראשית</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">מניות ירוקות היום</div>
                <div class="kpi-value ltr-right" style="color:#60A5FA;">{green_today}%</div>
                <div class="kpi-sub">שינוי יומי חיובי</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">דוחות ב-7 הימים הקרובים</div>
                <div class="kpi-value ltr-right" style="color:#F59E0B;">{upcoming_7d}</div>
                <div class="kpi-sub">התראת תנודתיות דוחות</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# === [SEC-04: FILTER & SORT ENGINE] ===
def render_filters_and_sort(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    with st.expander("🔎 סינון ומיון מתקדם", expanded=True):
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

        s1, s2, s3, s4 = st.columns([1.2, 1.2, 1.3, 1.6])

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

        with s4:
            view_mode = st.radio(
                "תצוגה",
                ["כרטיסיות", "טבלה מלאה"],
                horizontal=True,
                key="screener_view_mode",
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

    # Sorting
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

    return out.reset_index(drop=True), view_mode


# === [SEC-05: CARD GRID & FULL TABLE RENDERERS] ===
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
            pct_str, pct_color = format_pct_color(r.get("change_today_pct") if pd.notna(r.get("change_today_pct")) else None)

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
                if st.button("🔍 ניתוח עומק", key=f"open_dd_{sym}", use_container_width=True):
                    st.session_state["selected_symbol"] = sym
                    st.switch_page("views/deep_dive.py")


def render_full_table(df_filtered: pd.DataFrame) -> None:
    if df_filtered.empty:
        st.warning("לא נמצאו מניות התואמות לסינון שנבחר.")
        return

    col_group = st.radio(
        "קבוצת עמודות",
        ["מבט על", "תשואות תקופתיות", "נפחים ונפח יחסי", "רמות תמיכה והתנגדות"],
        horizontal=True,
        key="tbl_col_group",
    )

    base_cols = ["symbol", "company_name", "exchange", "sector", "sub_industry", "display_price", "change_today_pct"]
    if col_group == "מבט על":
        extra = ["ma_20_status", "ma_50_status", "ma_150_status", "ma_200_status", "rsi", "atr_pct", "rel_vol_5d", "next_earnings_date"]
    elif col_group == "תשואות תקופתיות":
        extra = ["change_1d", "change_2d", "start_of_the_week", "weekly", "two_weeks", "monthly", "three_months", "six_months", "ytd", "one_year"]
    elif col_group == "נפחים ונפח יחסי":
        extra = ["daily_vol", "vol_1d", "rel_vol_5d", "rel_vol_10d", "rel_vol_15d", "rel_vol_20d", "rel_vol_30d"]
    else:
        extra = ["d_s_2", "d_s_1", "d_r_1", "d_r_2", "w_s_1", "w_r_1"]

    chosen_cols = [c for c in (base_cols + extra) if c in df_filtered.columns]
    view_df = df_filtered[chosen_cols].copy()

    st.dataframe(view_df, use_container_width=True, hide_index=True, height=620)


# === [SEC-06: MAIN PAGE ORCHESTRATION WITH LIVE FRAGMENT] ===
def render_live_workspace(all_symbols: list[str], auto_refresh_live: bool) -> None:
    if auto_refresh_live:
        refresh_live_prices_tv(all_symbols)

    df = load_market_dataframe()
    if df.empty:
        st.info("אין עדיין נתונים להצגה. לחץ על 'הוספה / סנכרון מניות חדשות' למעלה.")
        return

    # Status strip (Live indicator + last timestamp)
    last_live = df["live_updated_at"].dropna().max() if "live_updated_at" in df.columns else None
    last_eod = df["updated_at"].dropna().max() if "updated_at" in df.columns else None

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
            <div>
                {('<span class="live-pill"><span class="live-dot"></span>LIVE</span>' if auto_refresh_live else '<span class="badge-pill badge-slate">נתוני סגירה (EOD)</span>')}
            </div>
            <div style="color:#94A3B8; font-size:0.8rem;">
                עדכון אחרון: <span class="ltr-num">{str(last_live or last_eod or '')[:19].replace('T', ' ')} UTC</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_filtered, view_mode = render_filters_and_sort(df)
    render_kpi_bar(df_filtered, total_count=len(df))

    if view_mode == "כרטיסיות":
        render_cards_grid(df_filtered)
    else:
        render_full_table(df_filtered)


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
