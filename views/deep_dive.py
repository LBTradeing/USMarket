# === [SEC-01: IMPORTS & HEADER] ===
import html
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import load_market_dataframe, save_manual_levels
from ui_theme import render_logo_html, format_pct_color


# === [SEC-02: PROFILE CARD & AI SUMMARY] ===
def render_profile_header(row: pd.Series) -> None:
    sym = str(row["symbol"])
    comp_name = html.escape(str(row.get("company_name") or sym))
    exch = html.escape(str(row.get("exchange") or "US"))
    sector = html.escape(str(row.get("sector") or ""))
    sub_ind = html.escape(str(row.get("sub_industry") or row.get("industry") or ""))
    summary = html.escape(str(row.get("short_summary") or "אין תקציר זמין למניה זו."))
    logo_html = render_logo_html(sym, row.get("logo_url"), size=52)

    price_val = row.get("display_price")
    price_str = f"${price_val:,.2f}" if pd.notna(price_val) else "--"
    pct_str, pct_color = format_pct_color(row.get("change_today_pct") if pd.notna(row.get("change_today_pct")) else None)

    earnings_badge = ""
    if pd.notna(row.get("next_earnings_date")):
        try:
            ed_date = pd.to_datetime(row["next_earnings_date"]).date()
            days_left = (ed_date - datetime.now(timezone.utc).date()).days
            if days_left >= 0:
                earnings_badge = f'<span class="badge-pill badge-amber">📅 דוחות: {ed_date} (בעוד {days_left} ימים)</span>'
        except Exception:
            pass

    st.markdown(
        f"""
        <div class="profile-box">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px; direction:ltr;">
                <div style="display:flex; align-items:center; gap:14px;">
                    {logo_html}
                    <div>
                        <div style="font-size:1.45rem; font-weight:800; color:#F8FAFC;">{comp_name}</div>
                        <div style="font-size:0.9rem; color:#94A3B8; font-weight:600;">{html.escape(sym)} · {exch}</div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:1.65rem; font-weight:800; color:#F8FAFC;">{price_str}</div>
                    <div style="font-size:1.05rem; font-weight:700; color:{pct_color};">{pct_str}</div>
                </div>
            </div>
            <div style="margin-top:14px; margin-bottom:10px;">
                {f'<span class="badge-pill badge-slate">{sector}</span>' if sector else ''}
                {f'<span class="badge-pill badge-blue">{sub_ind}</span>' if sub_ind else ''}
                {earnings_badge}
            </div>
            <div style="background-color:#0D111A; border:1px solid #1A2233; border-radius:10px; padding:12px 14px; color:#E2E8F0; font-size:0.95rem; line-height:1.6;">
                {summary}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# === [SEC-03: INTERACTIVE LEVELS & MOVING AVERAGES CHART] ===
def render_levels_chart(row: pd.Series, manual_levels: list[dict]) -> None:
    price = float(row["display_price"]) if pd.notna(row.get("display_price")) else None
    if not price:
        st.warning("אין נתוני מחיר להצגת גרף.")
        return

    c_opt1, c_opt2, c_opt3, c_opt4 = st.columns(4)
    with c_opt1:
        show_ma = st.checkbox("ממוצעים נעים (SMA)", value=True, key="dd_show_ma")
    with c_opt2:
        show_daily = st.checkbox("רמות יומיות (D)", value=True, key="dd_show_d")
    with c_opt3:
        show_weekly = st.checkbox("רמות שבועיות (W)", value=True, key="dd_show_w")
    with c_opt4:
        show_manual = st.checkbox("רמות ידניות", value=True, key="dd_show_m")

    fig = go.Figure()

    # Current Price Reference Line
    fig.add_hline(
        y=price,
        line_color="#F8FAFC",
        line_width=2.5,
        annotation_text=f"מחיר נוכחי: ${price:,.2f}",
        annotation_position="top right",
        annotation_font=dict(color="#F8FAFC", size=12),
    )

    y_values = [price]

    if show_ma:
        ma_specs = [
            ("ma_20_value", "SMA 20", "#38BDF8"),
            ("ma_50_value", "SMA 50", "#818CF8"),
            ("ma_150_value", "SMA 150", "#C084FC"),
            ("ma_200_value", "SMA 200", "#F472B6"),
        ]
        for col, label, color in ma_specs:
            val = row.get(col)
            if pd.notna(val):
                v = float(val)
                y_values.append(v)
                fig.add_hline(
                    y=v,
                    line_dash="dot",
                    line_color=color,
                    line_width=1.4,
                    annotation_text=f"{label}: ${v:,.2f}",
                    annotation_position="bottom left",
                    annotation_font=dict(color=color, size=11),
                )

    if show_daily:
        for i in range(1, 6):
            s_val = row.get(f"d_s_{i}")
            if pd.notna(s_val):
                v = float(s_val)
                y_values.append(v)
                fig.add_hline(
                    y=v,
                    line_dash="dash",
                    line_color="rgba(16, 185, 129, 0.55)",
                    line_width=1.2,
                    annotation_text=f"D-S{i}: ${v:,.2f}",
                    annotation_position="top left",
                    annotation_font=dict(color="#10B981", size=10),
                )
            r_val = row.get(f"d_r_{i}")
            if pd.notna(r_val):
                v = float(r_val)
                y_values.append(v)
                fig.add_hline(
                    y=v,
                    line_dash="dash",
                    line_color="rgba(239, 68, 68, 0.55)",
                    line_width=1.2,
                    annotation_text=f"D-R{i}: ${v:,.2f}",
                    annotation_position="top left",
                    annotation_font=dict(color="#EF4444", size=10),
                )

    if show_weekly:
        for i in range(1, 6):
            ws_val = row.get(f"w_s_{i}")
            if pd.notna(ws_val):
                v = float(ws_val)
                y_values.append(v)
                fig.add_hline(
                    y=v,
                    line_color="rgba(16, 185, 129, 0.9)",
                    line_width=1.8,
                    annotation_text=f"W-S{i}: ${v:,.2f}",
                    annotation_position="bottom right",
                    annotation_font=dict(color="#34D399", size=11),
                )
            wr_val = row.get(f"w_r_{i}")
            if pd.notna(wr_val):
                v = float(wr_val)
                y_values.append(v)
                fig.add_hline(
                    y=v,
                    line_color="rgba(239, 68, 68, 0.9)",
                    line_width=1.8,
                    annotation_text=f"W-R{i}: ${v:,.2f}",
                    annotation_position="bottom right",
                    annotation_font=dict(color="#F87171", size=11),
                )

    if show_manual and manual_levels:
        for lvl in manual_levels:
            v = float(lvl.get("price", 0))
            if v > 0:
                y_values.append(v)
                note = lvl.get("note", "רמה ידנית")
                fig.add_hline(
                    y=v,
                    line_dash="longdash",
                    line_color="#3B82F6",
                    line_width=2.0,
                    annotation_text=f"★ {note}: ${v:,.2f}",
                    annotation_position="top right",
                    annotation_font=dict(color="#60A5FA", size=11),
                )

    y_min, y_max = min(y_values) * 0.97, max(y_values) * 1.03
    fig.update_layout(
        paper_bgcolor="#111622",
        plot_bgcolor="#0D111A",
        height=470,
        margin=dict(l=20, r=20, t=25, b=20),
        xaxis=dict(visible=False, range=[0, 10]),
        yaxis=dict(
            range=[y_min, y_max],
            gridcolor="#1E2638",
            tickfont=dict(color="#94A3B8"),
            tickprefix="$",
        ),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


# === [SEC-04: MANUAL LEVELS EDITOR & TECHNICAL BREAKDOWN] ===
def render_manual_levels_editor(symbol: str, manual_levels: list[dict]) -> None:
    with st.expander("✏️ ניהול רמות תמיכה והתנגדות ידניות", expanded=False):
        c1, c2, c3 = st.columns([1.2, 2.0, 1.0])
        with c1:
            new_lvl_price = st.number_input("מחיר רמה ($)", min_value=0.01, value=100.0, step=0.5, key="man_lvl_price")
        with c2:
            new_lvl_note = st.text_input("תווית / הערה", placeholder="לדוגמה: שיא כל הזמנים / תמיכת גאפ", key="man_lvl_note")
        with c3:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("הוסף רמה", use_container_width=True):
                updated = list(manual_levels) + [
                    {"price": round(float(new_lvl_price), 2), "note": new_lvl_note.strip() or "רמה ידנית"}
                ]
                save_manual_levels(symbol, updated)
                st.success("הרמה נשמרה בהצלחה")
                st.rerun()

        if manual_levels:
            st.markdown("**רמות שמורות למניה זו:**")
            for idx, lvl in enumerate(manual_levels):
                rc1, rc2, rc3 = st.columns([1.2, 2.5, 0.8])
                rc1.markdown(f"<span class='ltr-num'>**${lvl.get('price', 0):,.2f}**</span>", unsafe_allow_html=True)
                rc2.write(lvl.get("note", ""))
                if rc3.button("מחק", key=f"del_man_lvl_{symbol}_{idx}"):
                    updated = [x for i, x in enumerate(manual_levels) if i != idx]
                    save_manual_levels(symbol, updated)
                    st.rerun()


def render_technical_details(row: pd.Series) -> None:
    t1, t2 = st.columns(2)

    with t1:
        st.markdown("#### מדדים טכניים ותשואות")
        metrics_rows = [
            ("RSI (14)", f"{row['rsi']:.2f}" if pd.notna(row.get("rsi")) else "--"),
            ("ATR (14) / %", f"${row['atr_14']:.2f} ({row['atr_pct']:.2f}%)" if pd.notna(row.get("atr_14")) else "--"),
            ("Rel Vol 5D / 20D", f"{row['rel_vol_5d']:.2f}x / {row['rel_vol_20d']:.2f}x" if pd.notna(row.get("rel_vol_5d")) else "--"),
            ("תשואה שבועית (5D)", f"{row['weekly']:.2f}%" if pd.notna(row.get("weekly")) else "--"),
            ("תשואה חודשית (1M)", f"{row['monthly']:.2f}%" if pd.notna(row.get("monthly")) else "--"),
            ("תשואה רבעונית (3M)", f"{row['three_months']:.2f}%" if pd.notna(row.get("three_months")) else "--"),
            ("מתחילת השנה (YTD)", f"{row['ytd']:.2f}%" if pd.notna(row.get("ytd")) else "--"),
            ("שנה אחורה (1Y)", f"{row['one_year']:.2f}%" if pd.notna(row.get("one_year")) else "--"),
        ]
        st.dataframe(pd.DataFrame(metrics_rows, columns=["מדד", "ערך"]), use_container_width=True, hide_index=True)

    with t2:
        st.markdown("#### רמות תמיכה והתנגדות (D / W)")
        sr_rows = []
        for i in range(1, 6):
            sr_rows.append(
                {
                    "רמה": f"#{i}",
                    "תמיכה יומית": f"${row[f'd_s_{i}']:,.2f}" if pd.notna(row.get(f"d_s_{i}")) else "--",
                    "התנגדות יומית": f"${row[f'd_r_{i}']:,.2f}" if pd.notna(row.get(f"d_r_{i}")) else "--",
                    "תמיכה שבועית": f"${row[f'w_s_{i}']:,.2f}" if pd.notna(row.get(f"w_s_{i}")) else "--",
                    "התנגדות שבועית": f"${row[f'w_r_{i}']:,.2f}" if pd.notna(row.get(f"w_r_{i}")) else "--",
                }
            )
        st.dataframe(pd.DataFrame(sr_rows), use_container_width=True, hide_index=True)


# === [SEC-05: MAIN PAGE ORCHESTRATION] ===
def main() -> None:
    df = load_market_dataframe()
    if df.empty:
        st.info("אין נתונים להצגה.")
        return

    symbols = df["symbol"].tolist()
    default_sym = st.session_state.get("selected_symbol", symbols[0])
    if default_sym not in symbols:
        default_sym = symbols[0]

    top_c1, top_c2 = st.columns([3.5, 1.2])
    with top_c1:
        selected_sym = st.selectbox(
            "בחר מניה לניתוח עומק",
            options=symbols,
            index=symbols.index(default_sym),
            key="dd_symbol_selector",
        )
        st.session_state["selected_symbol"] = selected_sym

    with top_c2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("⬅️ חזרה לסורק", use_container_width=True):
            st.switch_page("views/screener.py")

    row = df[df["symbol"] == selected_sym].iloc[0]
    raw_manual = row.get("manual_levels")
    manual_levels = raw_manual if isinstance(raw_manual, list) else []

    render_profile_header(row)
    render_levels_chart(row, manual_levels)
    render_manual_levels_editor(selected_sym, manual_levels)
    render_technical_details(row)


main()
