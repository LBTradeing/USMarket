# === [SEC-01: IMPORTS & HTML RENDER HELPER] ===
import html
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from db import (
    load_market_dataframe,
    save_manual_levels,
    refresh_live_prices_tv,
    sync_setup_pattern,
)
from journal_helpers import SETUP_OPTIONS
from ui_theme import render_logo_html, format_pct_color

# Inline style constants (self-contained Obsidian Deep Dark theme)
S_SECTION = (
    "background-color:#111622; border:1px solid #1E2638; border-radius:16px; "
    "padding:18px 20px; margin-bottom:16px; direction:rtl; text-align:right;"
)
S_SEC_TITLE = (
    "font-size:1.08rem; font-weight:800; color:#F8FAFC; margin-bottom:14px; "
    "display:flex; align-items:center; justify-content:space-between; "
    "border-bottom:1px solid #1E2638; padding-bottom:10px;"
)
S_SUB_LBL = "font-size:0.86rem; font-weight:700; color:#94A3B8; margin:12px 0 8px 0;"
S_GRID_5 = "display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:10px; margin-bottom:10px;"
S_GRID_4 = "display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:12px;"
S_GRID_3 = "display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin-bottom:14px;"
S_GRID_2 = "display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px;"

S_TILE_BASE = (
    "background-color:#0D111A; border:1px solid #1A2233; border-radius:12px; "
    "padding:12px 10px; text-align:center;"
)
S_TILE_GREEN = (
    "background-color:rgba(16, 185, 129, 0.08); border:1px solid rgba(16, 185, 129, 0.35); "
    "border-radius:12px; padding:12px 10px; text-align:center;"
)
S_TILE_RED = (
    "background-color:rgba(239, 68, 68, 0.08); border:1px solid rgba(239, 68, 68, 0.35); "
    "border-radius:12px; padding:12px 10px; text-align:center;"
)
S_TILE_LBL = "font-size:0.84rem; font-weight:600; color:#94A3B8; margin-bottom:6px;"
S_TILE_VAL = (
    "font-size:1.25rem; font-weight:800; direction:ltr; unicode-bidi:isolate; display:inline-block;"
)


def _html(raw: str) -> None:
    """Renders multi-line HTML cleanly without Markdown code-block indentation issues."""
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def _fmt_vol(val) -> str:
    if val is None or pd.isna(val):
        return "--"
    v = float(val)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{int(v):,}"


# === [SEC-02: TOP HEADER CARD (IDENTITY, UNIFORM PRICE/PCT, SIGNAL & SUMMARY)] ===
def render_top_header_card(row: pd.Series) -> None:
    sym = str(row["symbol"])
    comp_name = html.escape(str(row.get("company_name") or sym))
    exch = html.escape(str(row.get("exchange") or "US"))
    sector = html.escape(str(row.get("sector") or ""))
    industry = html.escape(str(row.get("industry") or ""))
    sub_ind = html.escape(str(row.get("sub_industry") or ""))
    curr_setup = str(row.get("setup_pattern") or "").strip() if pd.notna(row.get("setup_pattern")) else ""
    summary = html.escape(str(row.get("short_summary") or "אין תקציר עסקי זמין למניה זו."))
    logo_html = render_logo_html(sym, row.get("logo_url"), size=54)

    price_val = row.get("display_price")
    price_str = f"${price_val:,.2f}" if pd.notna(price_val) else "--"
    pct_val = row.get("change_today_pct") if pd.notna(row.get("change_today_pct")) else None
    pct_str, pct_color = format_pct_color(pct_val)

    is_live = pd.notna(row.get("live_price"))
    mode_badge = (
        '<span class="live-pill"><span class="live-dot"></span>LIVE</span>'
        if is_live
        else '<span class="badge-pill badge-slate">EOD</span>'
    )

    setup_badge = (
        f'<span class="badge-pill" style="background:rgba(139,92,246,0.16); border:1px solid rgba(139,92,246,0.45); color:#C4B5FD; direction:ltr; unicode-bidi:isolate;">'
        f'Setup: {html.escape(curr_setup)}</span>'
        if curr_setup and curr_setup != "ללא Setup"
        else ""
    )

    earnings_badge = ""
    if pd.notna(row.get("next_earnings_date")):
        try:
            ed_date = pd.to_datetime(row["next_earnings_date"]).date()
            days_left = (ed_date - datetime.now(timezone.utc).date()).days
            if days_left >= 0:
                earnings_badge = (
                    f'<span class="badge-pill badge-amber">'
                    f'דוחות קרובים: <span style="direction:ltr; unicode-bidi:isolate;">{ed_date}</span> (בעוד {days_left} ימים)'
                    f'</span>'
                )
        except Exception:
            pass

    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:18px; direction:ltr;">
                <div style="display:flex; align-items:center; gap:14px;">
                    {logo_html}
                    <div>
                        <div style="font-size:1.5rem; font-weight:800; color:#F8FAFC; line-height:1.2;">{comp_name}</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:5px;">
                            <span style="background:#1A2234; border:1px solid #2A354D; color:#F8FAFC; font-weight:800; font-size:0.88rem; padding:2px 10px; border-radius:6px;">{html.escape(sym)}</span>
                            <span style="color:#94A3B8; font-size:0.88rem; font-weight:600;">{exch}</span>
                            {mode_badge}
                        </div>
                    </div>
                </div>

                <div style="display:flex; align-items:center; gap:18px; background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:12px 22px;">
                    <span style="font-size:1.65rem; font-weight:800; color:{pct_color}; direction:ltr; unicode-bidi:isolate;">{pct_str}</span>
                    <span style="width:1px; height:28px; background:#1E2638;"></span>
                    <span style="font-size:1.65rem; font-weight:800; color:#F8FAFC; direction:ltr; unicode-bidi:isolate;">{price_str}</span>
                </div>

                <div style="background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:10px 16px; min-width:210px; direction:rtl; text-align:right;">
                    <div style="font-size:0.78rem; font-weight:700; color:#64748B; margin-bottom:2px;">סטטוס איתות</div>
                    <div style="font-size:0.98rem; font-weight:800; color:#94A3B8; margin-bottom:4px;">ממתין לאיתות</div>
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#64748B;">
                        <span>ציון משוקלל</span>
                        <span style="font-weight:700; direction:ltr; unicode-bidi:isolate;">-- / 100</span>
                    </div>
                </div>
            </div>

            <div style="background:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:14px 16px; margin-top:16px; color:#E2E8F0; font-size:0.98rem; line-height:1.65;">
                {summary}
            </div>

            <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
                {setup_badge}
                {f'<span class="badge-pill badge-slate">סקטור: {sector}</span>' if sector else ''}
                {f'<span class="badge-pill badge-slate">תעשייה: {industry}</span>' if industry else ''}
                {f'<span class="badge-pill badge-blue">תת-תעשייה: {sub_ind}</span>' if sub_ind else ''}
                {earnings_badge}
            </div>
        </div>
        """
    )


# === [SEC-03: PRICE PERFORMANCE (%)] ===
def render_price_performance(row: pd.Series) -> None:
    rows_spec = [
        [
            ("היום (Live)", "change_today_pct"),
            ("אתמול (T-1)", "change_1d"),
            ("לפני יומיים (T-2)", "change_2d"),
            ("לפני 3 ימים (T-3)", "change_3d"),
            ("לפני 4 ימים (T-4)", "change_4d"),
        ],
        [
            ("מתחילת שבוע (WTD)", "start_of_the_week"),
            ("שבוע (5D)", "weekly"),
            ("שבועיים (10D)", "two_weeks"),
            ("3 שבועות (15D)", "three_weeks"),
            ("חודש (1M)", "monthly"),
        ],
        [
            ("3 חודשים (3M)", "three_months"),
            ("6 חודשים (6M)", "six_months"),
            ("9 חודשים (9M)", "nine_months"),
            ("מתחילת השנה (YTD)", "ytd"),
            ("שנה (1Y)", "one_year"),
        ],
    ]

    grids_html = []
    for group in rows_spec:
        tiles = []
        for label, col in group:
            raw_v = row.get(col) if col in row.index and pd.notna(row.get(col)) else None
            pct_str, color = format_pct_color(float(raw_v) if raw_v is not None else None)
            tiles.append(
                f'<div style="{S_TILE_BASE}">'
                f'<div style="{S_TILE_LBL}">{label}</div>'
                f'<div style="{S_TILE_VAL} color:{color};">{pct_str}</div>'
                f'</div>'
            )
        grids_html.append(f'<div style="{S_GRID_5}">{"".join(tiles)}</div>')

    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="{S_SEC_TITLE}">
                <span>ביצועי מחיר ותשואות (%)</span>
                <span style="font-size:0.82rem; color:#64748B; direction:ltr;">PRICE PERFORMANCE</span>
            </div>
            {"".join(grids_html)}
        </div>
        """
    )


# === [SEC-04: VOLUME MOMENTUM (DAILY VOLUMES & RELATIVE VOLUME)] ===
def render_volume_momentum(row: pd.Series) -> None:
    vol_specs = [
        ("נפח היום", "daily_vol", "change_today_pct"),
        ("אתמול (T-1)", "vol_1d", "change_1d"),
        ("לפני יומיים (T-2)", "vol_2d", "change_2d"),
        ("לפני 3 ימים (T-3)", "vol_3d", "change_3d"),
        ("לפני 4 ימים (T-4)", "vol_4d", "change_4d"),
    ]

    vol_tiles = []
    for label, v_col, chg_col in vol_specs:
        v_raw = row.get(v_col) if v_col in row.index and pd.notna(row.get(v_col)) else None
        chg_raw = row.get(chg_col) if chg_col in row.index and pd.notna(row.get(chg_col)) else None
        v_str = _fmt_vol(v_raw)

        if v_raw is None or chg_raw is None:
            tile_style = S_TILE_BASE
            val_color = "#F8FAFC"
        elif float(chg_raw) >= 0:
            tile_style = S_TILE_GREEN
            val_color = "#10B981"
        else:
            tile_style = S_TILE_RED
            val_color = "#EF4444"

        vol_tiles.append(
            f'<div style="{tile_style}">'
            f'<div style="{S_TILE_LBL}">{label}</div>'
            f'<div style="{S_TILE_VAL} color:{val_color};">{v_str}</div>'
            f'</div>'
        )

    today_chg = (
        float(row["change_today_pct"])
        if "change_today_pct" in row.index and pd.notna(row.get("change_today_pct"))
        else None
    )
    rvol_specs = [
        ("Rel Vol 5D", "rel_vol_5d"),
        ("Rel Vol 10D", "rel_vol_10d"),
        ("Rel Vol 15D", "rel_vol_15d"),
        ("Rel Vol 20D", "rel_vol_20d"),
        ("Rel Vol 30D", "rel_vol_30d"),
    ]

    rvol_tiles = []
    for label, r_col in rvol_specs:
        r_raw = row.get(r_col) if r_col in row.index and pd.notna(row.get(r_col)) else None
        if r_raw is None:
            r_str = "--"
            tile_style = S_TILE_BASE
            val_color = "#94A3B8"
        else:
            rv = float(r_raw)
            r_str = f"{rv:.2f}x"
            if rv >= 1.0 and today_chg is not None:
                if today_chg >= 0:
                    tile_style = S_TILE_GREEN
                    val_color = "#10B981"
                else:
                    tile_style = S_TILE_RED
                    val_color = "#EF4444"
            else:
                tile_style = S_TILE_BASE
                val_color = "#CBD5E1"

        rvol_tiles.append(
            f'<div style="{tile_style}">'
            f'<div style="{S_TILE_LBL} direction:ltr;">{label}</div>'
            f'<div style="{S_TILE_VAL} color:{val_color};">{r_str}</div>'
            f'</div>'
        )

    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="{S_SEC_TITLE}">
                <span>מומנטום ונפחי מסחר</span>
                <span style="font-size:0.82rem; color:#64748B; direction:ltr;">VOLUME MOMENTUM</span>
            </div>
            <div style="{S_SUB_LBL}">נפח מסחר יומי (5 ימי מסחר אחרונים — ירוק ביום עליות / אדום ביום ירידות)</div>
            <div style="{S_GRID_5}">{"".join(vol_tiles)}</div>
            <div style="{S_SUB_LBL}">נפח יחסי לממוצע (Rel Vol — נצבע בירוק או באדום בחריגת נפח מעל 1.00x)</div>
            <div style="{S_GRID_5}">{"".join(rvol_tiles)}</div>
        </div>
        """
    )


# === [SEC-05: MOVING AVERAGES (% AND $ DISTANCE)] ===
def render_moving_averages(row: pd.Series) -> None:
    price = float(row["display_price"]) if pd.notna(row.get("display_price")) else None
    ma_specs = [
        ("MA 20", "ma_20_status", "ma_20_value", "ma_20_dist_pct"),
        ("MA 50", "ma_50_status", "ma_50_value", "ma_50_dist_pct"),
        ("MA 150", "ma_150_status", "ma_150_value", "ma_150_dist_pct"),
        ("MA 200", "ma_200_status", "ma_200_value", "ma_200_dist_pct"),
    ]

    cards = []
    for title, st_col, val_col, pct_col in ma_specs:
        st_val = str(row.get(st_col)) if st_col in row.index and pd.notna(row.get(st_col)) else ""
        ma_val = float(row[val_col]) if val_col in row.index and pd.notna(row.get(val_col)) else None
        dist_pct = float(row[pct_col]) if pct_col in row.index and pd.notna(row.get(pct_col)) else None

        if ma_val is not None and price is not None:
            diff_usd = price - ma_val
            usd_sign = "+" if diff_usd > 0 else ("-" if diff_usd < 0 else "")
            usd_str = f"{usd_sign}${abs(diff_usd):,.2f}"
            pct_sign = "+" if (dist_pct or 0) > 0 else ""
            pct_str = f"{pct_sign}{dist_pct:.2f}%" if dist_pct is not None else "--"
            dist_combo = f"{pct_str}  |  {usd_str}"
            ma_price_str = f"${ma_val:,.2f}"
        else:
            dist_combo = "--"
            ma_price_str = "--"

        if st_val == "Above":
            card_style = (
                "background-color:rgba(16, 185, 129, 0.07); border:1px solid rgba(16, 185, 129, 0.35); "
                "border-radius:12px; padding:14px; text-align:center;"
            )
            status_html = '<span style="color:#10B981;">ABOVE ▲</span>'
            dist_color = "#10B981"
        elif st_val == "Below":
            card_style = (
                "background-color:rgba(239, 68, 68, 0.07); border:1px solid rgba(239, 68, 68, 0.35); "
                "border-radius:12px; padding:14px; text-align:center;"
            )
            status_html = '<span style="color:#EF4444;">BELOW ▼</span>'
            dist_color = "#EF4444"
        else:
            card_style = (
                "background-color:#0D111A; border:1px solid #1E2638; "
                "border-radius:12px; padding:14px; text-align:center;"
            )
            status_html = '<span style="color:#94A3B8;">--</span>'
            dist_color = "#94A3B8"

        cards.append(
            f'<div style="{card_style}">'
            f'<div style="font-size:0.9rem; font-weight:700; color:#CBD5E1; margin-bottom:4px; direction:ltr;">{title}</div>'
            f'<div style="font-size:0.98rem; font-weight:800; margin-bottom:6px; direction:ltr;">{status_html}</div>'
            f'<div style="font-size:1.2rem; font-weight:700; color:#F8FAFC; margin-bottom:8px; direction:ltr; unicode-bidi:isolate;">{ma_price_str}</div>'
            f'<div style="font-size:0.9rem; font-weight:700; padding:5px 10px; border-radius:8px; background-color:#111622; color:{dist_color}; direction:ltr; unicode-bidi:isolate; display:inline-block;">{dist_combo}</div>'
            f'</div>'
        )

    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="{S_SEC_TITLE}">
                <span>ממוצעים נעים (סטטוס, שער ומרחק באחוזים ובדולרים)</span>
                <span style="font-size:0.82rem; color:#64748B; direction:ltr;">MOVING AVERAGES</span>
            </div>
            <div style="{S_GRID_4}">{"".join(cards)}</div>
        </div>
        """
    )


# === [SEC-06: SIGNAL ANALYSIS PLACEHOLDER (PHASE 5)] ===
def render_signal_analysis() -> None:
    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="{S_SEC_TITLE}">
                <span>ניתוח איתות ופירוט ניקוד</span>
                <span style="font-size:0.82rem; color:#64748B; direction:ltr;">SIGNAL ANALYSIS</span>
            </div>
            <div style="background:#0D111A; border:1px dashed #263147; border-radius:12px; padding:20px; text-align:center; color:#94A3B8; font-size:0.95rem;">
                אין כרגע איתות פעיל לניתוח — תשתית זו תתמלא אוטומטית עם חיבור מנוע האיתותים בשלב 5.
            </div>
        </div>
        """
    )


# === [SEC-07: TECH LEVELS (3 ATR METRICS + DAILY / WEEKLY / MANUAL S/R)] ===
def render_tech_levels(row: pd.Series, manual_levels: list[dict]) -> None:
    atr_14 = float(row["atr_14"]) if "atr_14" in row.index and pd.notna(row.get("atr_14")) else None
    atr_pct = float(row["atr_pct"]) if "atr_pct" in row.index and pd.notna(row.get("atr_pct")) else None
    atr_sq = float(row["atr_squeeze_pct"]) if "atr_squeeze_pct" in row.index and pd.notna(row.get("atr_squeeze_pct")) else None

    atr_14_str = f"${atr_14:,.2f}" if atr_14 is not None else "--"
    atr_pct_str = f"{atr_pct:.2f}%" if atr_pct is not None else "--"
    atr_sq_str = f"{atr_sq:.1f}%" if atr_sq is not None else "--"
    sq_width = max(0.0, min(100.0, atr_sq)) if atr_sq is not None else 0.0

    pill_res_style = (
        "background-color:rgba(239, 68, 68, 0.12); border:1px solid rgba(239, 68, 68, 0.45); "
        "color:#FCA5A5; font-size:0.98rem; font-weight:800; padding:6px 14px; border-radius:8px; "
        "direction:ltr; unicode-bidi:isolate;"
    )
    pill_sup_style = (
        "background-color:rgba(16, 185, 129, 0.12); border:1px solid rgba(16, 185, 129, 0.45); "
        "color:#6EE7B7; font-size:0.98rem; font-weight:800; padding:6px 14px; border-radius:8px; "
        "direction:ltr; unicode-bidi:isolate;"
    )
    pill_man_style = (
        "background-color:rgba(37, 99, 235, 0.15); border:1px solid rgba(37, 99, 235, 0.45); "
        "color:#93C5FD; font-size:0.94rem; font-weight:700; padding:6px 14px; border-radius:8px;"
    )

    def collect_pills(prefix: str, style_str: str) -> str:
        pills = []
        for i in range(1, 6):
            col = f"{prefix}_{i}"
            if col in row.index and pd.notna(row.get(col)):
                pills.append(f'<span style="{style_str}">${float(row[col]):,.2f}</span>')
        return "".join(pills) if pills else '<span style="color:#64748B; font-size:0.86rem;">לא זוהו רמות בטווח</span>'

    d_res_html = collect_pills("d_r", pill_res_style)
    d_sup_html = collect_pills("d_s", pill_sup_style)
    w_res_html = collect_pills("w_r", pill_res_style)
    w_sup_html = collect_pills("w_s", pill_sup_style)

    lvl_box_style = "background-color:#0D111A; border:1px solid #1A2233; border-radius:12px; padding:16px; text-align:center;"
    pills_wrap_style = "display:flex; flex-wrap:wrap; justify-content:center; gap:8px; direction:ltr;"

    manual_block = ""
    if manual_levels:
        m_pills = "".join(
            f'<span style="{pill_man_style}">★ {html.escape(str(lvl.get("note", "רמה ידנית")))}: '
            f'<span style="direction:ltr; unicode-bidi:isolate;">${float(lvl.get("price", 0)):,.2f}</span></span>'
            for lvl in manual_levels
            if float(lvl.get("price", 0)) > 0
        )
        if m_pills:
            manual_block = f"""
            <div style="{lvl_box_style} margin-top:14px;">
                <div style="font-size:0.98rem; font-weight:800; color:#F8FAFC; margin-bottom:10px;">רמות ידניות שמורות</div>
                <div style="display:flex; flex-wrap:wrap; justify-content:center; gap:8px; direction:rtl;">{m_pills}</div>
            </div>
            """

    _html(
        f"""
        <div style="{S_SECTION}">
            <div style="{S_SEC_TITLE}">
                <span>רמות טכניות ומדדי תנודתיות (ATR)</span>
                <span style="font-size:0.82rem; color:#64748B; direction:ltr;">TECH LEVELS & VOLATILITY</span>
            </div>

            <div style="{S_GRID_3}">
                <div style="{S_TILE_BASE}">
                    <div style="{S_TILE_LBL}">טווח תנועה יומי (ATR 14)</div>
                    <div style="{S_TILE_VAL} color:#F8FAFC;">{atr_14_str}</div>
                </div>
                <div style="{S_TILE_BASE}">
                    <div style="{S_TILE_LBL}">תנודתיות באחוזים (ATR %)</div>
                    <div style="{S_TILE_VAL} color:#60A5FA;">{atr_pct_str}</div>
                </div>
                <div style="{S_TILE_BASE}">
                    <div style="{S_TILE_LBL}">התכווצות תנודתיות (ATR Squeeze %)</div>
                    <div style="{S_TILE_VAL} color:#F59E0B;">{atr_sq_str}</div>
                    <div style="width:80%; height:5px; background:#1E293B; border-radius:999px; margin:8px auto 0 auto; overflow:hidden;">
                        <div style="width:{sq_width}%; height:100%; background:#F59E0B;"></div>
                    </div>
                </div>
            </div>

            <div style="{S_GRID_2}">
                <div style="{lvl_box_style}">
                    <div style="font-size:0.98rem; font-weight:800; color:#F8FAFC; margin-bottom:12px;">רמות יומיות (Daily Levels)</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#EF4444; margin:8px 0 6px 0;">התנגדות (Resistance — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap_style}">{d_res_html}</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#10B981; margin:14px 0 6px 0;">תמיכה (Support — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap_style}">{d_sup_html}</div>
                </div>

                <div style="{lvl_box_style}">
                    <div style="font-size:0.98rem; font-weight:800; color:#F8FAFC; margin-bottom:12px;">רמות שבועיות (Weekly Levels)</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#EF4444; margin:8px 0 6px 0;">התנגדות (Resistance — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap_style}">{w_res_html}</div>
                    <div style="font-size:0.82rem; font-weight:700; color:#10B981; margin:14px 0 6px 0;">תמיכה (Support — מהקרובה לרחוקה)</div>
                    <div style="{pills_wrap_style}">{w_sup_html}</div>
                </div>
            </div>
            {manual_block}
        </div>
        """
    )


def render_manual_levels_editor(symbol: str, manual_levels: list[dict]) -> None:
    with st.expander("הוספה או עריכה של רמות תמיכה והתנגדות ידניות", expanded=False):
        c1, c2, c3 = st.columns([1.2, 2.2, 1.0])
        with c1:
            new_lvl_price = st.number_input("מחיר רמה ($)", min_value=0.01, value=100.0, step=0.5, key="man_lvl_price")
        with c2:
            new_lvl_note = st.text_input("תווית / הערה", placeholder="לדוגמה: שיא כל הזמנים / תמיכת גאפ", key="man_lvl_note")
        with c3:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("שמור רמה", use_container_width=True):
                updated = list(manual_levels) + [
                    {"price": round(float(new_lvl_price), 2), "note": new_lvl_note.strip() or "רמה ידנית"}
                ]
                save_manual_levels(symbol, updated)
                st.success("הרמה נשמרה בהצלחה")
                st.rerun()

        if manual_levels:
            st.markdown("**רמות ידניות קיימות:**")
            for idx, lvl in enumerate(manual_levels):
                rc1, rc2, rc3 = st.columns([1.2, 2.5, 0.8])
                rc1.markdown(
                    f"<span style='direction:ltr; unicode-bidi:isolate;'>**${float(lvl.get('price', 0)):,.2f}**</span>",
                    unsafe_allow_html=True,
                )
                rc2.write(lvl.get("note", ""))
                if rc3.button("מחק", key=f"del_man_lvl_{symbol}_{idx}"):
                    updated = [x for i, x in enumerate(manual_levels) if i != idx]
                    save_manual_levels(symbol, updated)
                    st.rerun()


# === [SEC-08: MAIN PAGE ORCHESTRATION] ===
def main() -> None:
    df = load_market_dataframe()
    if df.empty:
        st.info("אין נתונים להצגה.")
        return

    symbols = df["symbol"].tolist()
    default_sym = st.session_state.get("selected_symbol", symbols[0])
    if default_sym not in symbols:
        default_sym = symbols[0]

    top_c1, top_c2, top_c3, top_c4 = st.columns([2.1, 1.8, 1.0, 1.2])
    with top_c1:
        selected_sym = st.selectbox(
            "בחר מניה לניתוח עומק",
            options=symbols,
            index=symbols.index(default_sym),
            label_visibility="collapsed",
            key="dd_symbol_selector",
        )
        st.session_state["selected_symbol"] = selected_sym

    row = df[df["symbol"] == selected_sym].iloc[0]

    with top_c2:
        saved_setup = (
            str(row.get("setup_pattern")).strip()
            if "setup_pattern" in row.index and pd.notna(row.get("setup_pattern")) and str(row.get("setup_pattern")).strip()
            else "ללא Setup"
        )
        if saved_setup not in SETUP_OPTIONS:
            saved_setup = "ללא Setup"

        chosen_setup = st.selectbox(
            "תבנית טכנית (Setup)",
            options=SETUP_OPTIONS,
            index=SETUP_OPTIONS.index(saved_setup),
            label_visibility="collapsed",
            key=f"dd_setup_combo_{selected_sym}",
        )
        if chosen_setup != saved_setup:
            sync_setup_pattern(selected_sym, chosen_setup)
            st.toast(f"תבנית Setup עבור {selected_sym} עודכנה וסונכרנה ליומן המסחר: {chosen_setup}")
            st.rerun()

    with top_c3:
        if st.button("רענן מחיר חי", use_container_width=True):
            with st.spinner("מושך מחיר חי..."):
                refresh_live_prices_tv([selected_sym])
                st.rerun()

    with top_c4:
        if st.button("חזרה למעקב ואנליטיקה", use_container_width=True):
            st.switch_page("views/screener.py")

    raw_manual = row.get("manual_levels")
    manual_levels = raw_manual if isinstance(raw_manual, list) else []

    render_top_header_card(row)
    render_price_performance(row)
    render_volume_momentum(row)
    render_moving_averages(row)
    render_signal_analysis()
    render_tech_levels(row, manual_levels)
    render_manual_levels_editor(selected_sym, manual_levels)


main()
