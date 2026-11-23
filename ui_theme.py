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


# === [SEC-02: GLOBAL RTL DARK MODE & CARD CSS] ===
def apply_global_theme() -> None:
    """Injects Obsidian Dark Mode, white-text right-side RTL sidebar, and LTR data anchors."""
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

        /* Put Brand Header ABOVE Navigation inside Sidebar */
        [data-testid="stSidebarContent"] {
            display: flex !important;
            flex-direction: column !important;
        }
        [data-testid="stSidebarHeader"] {
            order: 1 !important;
        }
        [data-testid="stSidebarUserContent"] {
            order: 2 !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }
        [data-testid="stSidebarNav"] {
            order: 3 !important;
            padding-top: 6px !important;
        }

        /* Sidebar White Typography & Clean No-Icon Layout */
        [data-testid="stSidebarNav"] span,
        [data-testid="stSidebarNav"] p,
        [data-testid="stSidebarNav"] a,
        [data-testid="stNavSectionHeader"],
        [data-testid="stSidebarNavSeparator"] {
            color: #F8FAFC !important;
            direction: rtl !important;
            text-align: right !important;
        }
        [data-testid="stNavSectionHeader"] {
            font-size: 0.92rem !important;
            font-weight: 800 !important;
            color: #FFFFFF !important;
            letter-spacing: 0.2px;
            margin-top: 10px !important;
        }
        [data-testid="stSidebarNav"] a {
            border-radius: 10px !important;
            margin: 2px 8px !important;
            padding: 6px 12px !important;
            transition: background-color 0.15s ease !important;
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

        /* Header Bar Transparency */
        [data-testid="stHeader"] {
            background-color: rgba(11, 14, 20, 0.85) !important;
        }

        /* Strict LTR Isolation for Tickers, Prices, Percentages & Charts */
        .ltr-box, .ltr-num {
            direction: ltr !important;
            unicode-bidi: isolate !important;
            text-align: left !important;
        }
        .ltr-right {
            direction: ltr !important;
            unicode-bidi: isolate !important;
            text-align: right !important;
        }

        /* KPI Summary Cards */
        .kpi-card {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 10px;
            transition: border-color 0.2s ease;
        }
        .kpi-card:hover {
            border-color: #2563EB;
        }
        .kpi-title {
            color: #94A3B8;
            font-size: 0.85rem;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #F8FAFC;
        }
        .kpi-sub {
            font-size: 0.78rem;
            color: #94A3B8;
            margin-top: 4px;
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

        /* Deep Dive & Placeholder Boxes */
        .profile-box {
            background-color: #111622;
            border: 1px solid #1E2638;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 16px;
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
        [data-baseweb="input"], [data-baseweb="select"] > div {
            background-color: #111622 !important;
            border-color: #1E2638 !important;
            color: #F8FAFC !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# === [SEC-03: REUSABLE HTML COMPONENTS] ===
def render_logo_html(symbol: str, logo_url: str | None = None, size: int = 38) -> str:
    """Renders company logo with automatic fallback to clean monogram badge."""
    clean_sym = html.escape(symbol.split(":")[-1].strip().upper())
    initials = clean_sym[:2] if len(clean_sym) >= 2 else clean_sym
    primary_url = (
        logo_url.strip()
        if logo_url and logo_url.strip()
        else f"https://static2.finnhub.io/file/publicdatany/finnhubimage/stock_logo/{clean_sym}.png"
    )
    safe_url = html.escape(primary_url)

    return (
        f'<div style="width:{size}px;height:{size}px;position:relative;flex-shrink:0;">'
        f'<img src="{safe_url}" class="stock-logo" '
        f'style="width:{size}px;height:{size}px;" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';" />'
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
