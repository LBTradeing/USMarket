# === [SEC-01: IMPORTS & PALETTE CONSTANTS] ===
import html
import streamlit as st

PALETTE = {
    "bg_main": "#0B0E14",
    "bg_card": "#111622",
    "bg_card_hover": "#161D2C",
    "bg_inner": "#0D111A",
    "border": "#1E2638",
    "accent_blue": "#2563EB",
    "green": "#10B981",
    "red": "#EF4444",
    "amber": "#F59E0B",
    "text_primary": "#F8FAFC",
    "text_muted": "#94A3B8",
}


# === [SEC-02: GLOBAL RTL DARK MODE & SIDEBAR CSS] ===
def apply_global_theme() -> None:
    """Injects Obsidian Dark Mode, uniform white RTL right sidebar, and LTR data anchors."""
    st.markdown(
        """
        <style>
        /* Main App Background & RTL Root */
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #0B0E14 !important;
            color: #F8FAFC !important;
            direction: rtl !important;
            text-align: right !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        /* Place Sidebar on the Right Side for Hebrew RTL */
        [data-testid="stAppViewContainer"] {
            flex-direction: row !important;
        }
        [data-testid="stSidebar"] {
            background-color: #0F141F !important;
            border-left: 1px solid #1E2638 !important;
            border-right: none !important;
            direction: rtl !important;
            text-align: right !important;
        }

        /* Desktop Sidebar Width & Clean Collapse */
        @media (min-width: 769px) {
            section[data-testid="stSidebar"][aria-expanded="true"] {
                width: 195px !important;
                min-width: 195px !important;
                max-width: 195px !important;
                transform: none !important;
                margin: 0 !important;
            }
            section[data-testid="stSidebar"][aria-expanded="false"] {
                display: none !important;
            }
        }

        /* Uniform Clean White Typography for Sidebar Items (No Icons) */
        [data-testid="stSidebarNav"] {
            padding-top: 8px !important;
        }
        [data-testid="stSidebarNav"] a {
            border-radius: 10px !important;
            margin: 4px 6px !important;
            padding: 9px 12px !important;
            direction: rtl !important;
            text-align: right !important;
            transition: background-color 0.15s ease !important;
        }
        [data-testid="stSidebarNav"] a span,
        [data-testid="stSidebarNav"] a p {
            color: #FFFFFF !important;
            font-size: 0.96rem !important;
            font-weight: 500 !important;
            direction: rtl !important;
            text-align: right !important;
        }
        [data-testid="stSidebarNav"] a:hover {
            background-color: #1A2234 !important;
        }
        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background-color: #2563EB !important;
        }
        [data-testid="stSidebarNav"] a[aria-current="page"] span {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        /* Hide Deep Dive from Sidebar Nav (opened by clicking a stock card) */
        [data-testid="stSidebarNav"] a[href*="deep_dive"] {
            display: none !important;
        }

        /* Header Bar & Sidebar Toggle Controls Visibility */
        header[data-testid="stHeader"] {
            background: transparent !important;
            pointer-events: none !important;
        }
        header[data-testid="stHeader"] button,
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"] {
            pointer-events: auto !important;
            visibility: visible !important;
            opacity: 1 !important;
            color: #F8FAFC !important;
        }

        /* Mobile Drawer Behavior (<= 768px) */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 2.9rem !important;
            }

            /* Subtle Floating Open Button in Top-Right Corner */
            [data-testid="collapsedControl"],
            [data-testid="stSidebarCollapsedControl"],
            [data-testid="stExpandSidebarButton"] {
                position: fixed !important;
                top: 10px !important;
                right: 12px !important;
                left: auto !important;
                z-index: 999999 !important;
                background: rgba(17, 22, 34, 0.94) !important;
                border: 1px solid #334155 !important;
                border-radius: 10px !important;
                padding: 4px 8px !important;
                box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5) !important;
                backdrop-filter: blur(8px) !important;
            }

            /* Completely Hide Sidebar When Collapsed on Mobile */
            section[data-testid="stSidebar"][aria-expanded="false"] {
                display: none !important;
            }

            /* Clean Right-Side Overlay Drawer When Expanded on Mobile */
            section[data-testid="stSidebar"][aria-expanded="true"] {
                display: flex !important;
                position: fixed !important;
                top: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                left: auto !important;
                width: 220px !important;
                min-width: 220px !important;
                max-width: 80vw !important;
                height: 100dvh !important;
                transform: none !important;
                margin: 0 !important;
                z-index: 999998 !important;
                box-shadow: -10px 0 30px rgba(0, 0, 0, 0.75) !important;
            }

            /* Clear Close Button Inside Open Mobile Drawer */
            [data-testid="stSidebarHeader"] {
                display: flex !important;
                justify-content: flex-end !important;
                padding: 8px 10px 0 10px !important;
            }
            [data-testid="stSidebarCollapseButton"] button {
                background: rgba(30, 41, 59, 0.85) !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
                color: #F8FAFC !important;
            }
        }

        /* Fix Expander RTL Arrow Spacing */
        [data-testid="stExpander"] summary {
            direction: rtl !important;
            text-align: right !important;
            gap: 8px !important;
        }

        /* Strict LTR Isolation for Tickers, Prices, Percentages & Charts */
        .ltr-box, .ltr-num {
            direction: ltr !important;
            unicode-bidi: isolate !important;
            display: inline-block;
        }

        /* KPI Summary Cards (Strictly RTL Right-Aligned) */
        .kpi-card {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 15px 18px;
            margin-bottom: 12px;
            direction: rtl !important;
            text-align: right !important;
            transition: border-color 0.2s ease;
        }
        .kpi-card:hover {
            border-color: #2563EB;
        }
        .kpi-title {
            color: #94A3B8;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 6px;
            direction: rtl !important;
            text-align: right !important;
        }
        .kpi-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #F8FAFC;
            direction: rtl !important;
            text-align: right !important;
        }
        .kpi-sub {
            font-size: 0.78rem;
            color: #64748B;
            margin-top: 4px;
            direction: rtl !important;
            text-align: right !important;
        }

        /* Stock Card (Screener Grid) */
        .stock-card {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-bottom: none;
            border-radius: 14px 14px 0 0;
            padding: 16px 18px 12px 18px;
            transition: all 0.2s ease;
        }
        .stock-card:hover {
            background-color: #151C2B;
            border-color: #2563EB;
        }
        .stock-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            direction: ltr !important;
            margin-bottom: 12px;
        }
        .stock-identity {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
            direction: ltr !important;
        }
        .stock-logo {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            object-fit: contain;
            background-color: #1A2234;
            border: 1px solid #263147;
            padding: 4px;
            flex-shrink: 0;
        }
        .stock-monogram {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border: 1px solid #2B3954;
            color: #60A5FA;
            font-weight: 700;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .stock-name {
            color: #F8FAFC;
            font-weight: 700;
            font-size: 0.96rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 175px;
        }
        .stock-ticker {
            color: #94A3B8;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.4px;
        }
        .stock-price-block {
            text-align: right;
            direction: ltr !important;
            flex-shrink: 0;
        }
        .stock-pct {
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .stock-price {
            color: #E2E8F0;
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 2px;
        }

        /* Inner Signal Placeholder Box inside Card */
        .signal-inner-box {
            background-color: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 10px;
            padding: 10px 12px;
            direction: rtl !important;
            text-align: right !important;
        }
        .signal-inner-label {
            color: #64748B;
            font-size: 0.72rem;
            font-weight: 600;
            margin-bottom: 3px;
        }
        .signal-inner-status {
            color: #94A3B8;
            font-size: 0.84rem;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .signal-score-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.72rem;
            color: #64748B;
            margin-bottom: 4px;
        }
        .signal-bar-bg {
            width: 100%;
            height: 4px;
            background-color: #1E293B;
            border-radius: 999px;
            overflow: hidden;
        }

        /* Live Indicator Pill */
        .live-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10B981;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            direction: ltr !important;
        }
        .live-dot {
            width: 7px;
            height: 7px;
            background-color: #10B981;
            border-radius: 50%;
            display: inline-block;
        }

        /* Deep Dive & Section Boxes */
        .profile-box {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 16px;
            direction: rtl !important;
            text-align: right !important;
        }
        .badge-pill {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            margin-left: 6px;
            margin-bottom: 4px;
        }
        .badge-blue {
            background-color: rgba(37, 99, 235, 0.16);
            border: 1px solid rgba(37, 99, 235, 0.4);
            color: #60A5FA;
        }
        .badge-slate {
            background-color: #1A2234;
            border: 1px solid #2A354D;
            color: #CBD5E1;
        }
        .badge-amber {
            background-color: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.4);
            color: #FBBF24;
        }

        /* Streamlit Buttons & Inputs Polish */
        .stButton > button {
            border-radius: 10px !important;
            border: 1px solid #1E2638 !important;
            background-color: #151C2B !important;
            color: #F8FAFC !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }
        .stButton > button:hover {
            border-color: #2563EB !important;
            background-color: #1E293B !important;
            color: #FFFFFF !important;
        }

        /* === DEEP DIVE COMPONENT STYLES (OBSIDIAN DEEP DARK) === */
        .dd-section {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-radius: 16px;
            padding: 18px 20px;
            margin-bottom: 16px;
            direction: rtl !important;
            text-align: right !important;
        }
        .dd-section-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #F8FAFC;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #1E2638;
            padding-bottom: 10px;
        }
        .dd-sub-label {
            font-size: 0.85rem;
            font-weight: 700;
            color: #94A3B8;
            margin: 12px 0 8px 0;
        }
        .dd-grid-5 {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 10px;
        }
        .dd-grid-4 {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }
        .dd-grid-3 {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .dd-grid-2 {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
        }
        @media (max-width: 900px) {
            .dd-grid-5, .dd-grid-4, .dd-grid-3, .dd-grid-2 {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        .dd-tile {
            background-color: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 12px 10px;
            text-align: center;
            transition: border-color 0.15s ease;
        }
        .dd-tile:hover {
            border-color: #2B3954;
        }
        .dd-tile-green {
            background-color: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.32);
        }
        .dd-tile-red {
            background-color: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.32);
        }
        .dd-tile-lbl {
            font-size: 0.82rem;
            font-weight: 600;
            color: #94A3B8;
            margin-bottom: 6px;
        }
        .dd-tile-val {
            font-size: 1.22rem;
            font-weight: 800;
            direction: ltr !important;
            unicode-bidi: isolate !important;
            display: inline-block;
        }
        .dd-ma-card {
            background-color: #0D111A;
            border: 1px solid #1E2638;
            border-radius: 12px;
            padding: 14px;
            text-align: center;
        }
        .dd-ma-green {
            background-color: rgba(16, 185, 129, 0.07);
            border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .dd-ma-red {
            background-color: rgba(239, 68, 68, 0.07);
            border: 1px solid rgba(239, 68, 68, 0.35);
        }
        .dd-ma-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #CBD5E1;
            margin-bottom: 4px;
            direction: ltr !important;
        }
        .dd-ma-status {
            font-size: 0.95rem;
            font-weight: 800;
            margin-bottom: 6px;
            direction: ltr !important;
        }
        .dd-ma-price {
            font-size: 1.15rem;
            font-weight: 700;
            color: #F8FAFC;
            margin-bottom: 6px;
            direction: ltr !important;
        }
        .dd-ma-dist {
            font-size: 0.88rem;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 8px;
            background-color: #111622;
            direction: ltr !important;
            display: inline-block;
        }
        .dd-lvl-box {
            background-color: #0D111A;
            border: 1px solid #1A2233;
            border-radius: 12px;
            padding: 14px 16px;
            text-align: center;
        }
        .dd-lvl-group-title {
            font-size: 0.95rem;
            font-weight: 800;
            color: #F8FAFC;
            margin-bottom: 12px;
        }
        .dd-lvl-sub {
            font-size: 0.8rem;
            font-weight: 700;
            margin: 8px 0 6px 0;
        }
        .dd-pills-wrap {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            direction: ltr !important;
        }
        .dd-pill-res {
            background-color: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.45);
            color: #FCA5A5;
            font-size: 0.95rem;
            font-weight: 800;
            padding: 6px 12px;
            border-radius: 8px;
        }
        .dd-pill-sup {
            background-color: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.45);
            color: #6EE7B7;
            font-size: 0.95rem;
            font-weight: 800;
            padding: 6px 12px;
            border-radius: 8px;
        }
        .dd-pill-man {
            background-color: rgba(37, 99, 235, 0.15);
            border: 1px solid rgba(37, 99, 235, 0.45);
            color: #93C5FD;
            font-size: 0.92rem;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# === [SEC-03: REUSABLE HTML COMPONENTS] ===
def render_logo_html(symbol: str, logo_url: str | None = None, size: int = 38) -> str:
    """Renders company logo with multi-source fallback before monogram badge."""
    clean_sym = html.escape(symbol.split(":")[-1].strip().upper())
    clean_fmp = clean_sym.replace(".", "-")
    initials = clean_sym[:2] if len(clean_sym) >= 2 else clean_sym

    candidates: list[str] = []
    if logo_url and logo_url.strip() and logo_url.strip().lower() not in ("none", "null"):
        candidates.append(logo_url.strip())
    candidates.extend(
        [
            f"https://financialmodelingprep.com/image-stock/{clean_fmp}.png",
            f"https://static2.finnhub.io/file/publicdatany/finnhubimage/stock_logo/{clean_sym}.png",
        ]
    )

    unique_urls: list[str] = []
    for u in candidates:
        if u not in unique_urls:
            unique_urls.append(u)

    first_url = html.escape(unique_urls[0])
    fallback_chain = html.escape("|".join(unique_urls[1:]))

    return (
        f'<div style="width:{size}px;height:{size}px;position:relative;flex-shrink:0;">'
        f'<img src="{first_url}" data-fallbacks="{fallback_chain}" class="stock-logo" '
        f'style="width:{size}px;height:{size}px;" '
        f'onerror="var fb=this.getAttribute(\'data-fallbacks\');'
        f'if(fb){{var arr=fb.split(\'|\');this.src=arr.shift();this.setAttribute(\'data-fallbacks\',arr.join(\'|\'));}}'
        f'else{{this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';}}" />'
        f'<div class="stock-monogram" style="display:none;width:{size}px;height:{size}px;">{initials}</div>'
        f"</div>"
    )


def format_pct_color(val: float | None) -> tuple[str, str]:
    """Returns formatted percentage string and hex color."""
    if val is None:
        return "--", "#94A3B8"
    sign = "+" if val > 0 else ""
    color = "#10B981" if val > 0 else ("#EF4444" if val < 0 else "#94A3B8")
    return f"{sign}{val:.2f}%", color
