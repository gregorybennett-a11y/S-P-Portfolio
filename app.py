"""
S&P 500 Financial Analytics — Streamlit App
============================================
My Portfolio (browser-saved) · Sector overview · Stock screener
10-year financial history · Bear / Base / Bull projections to 2030
Live prices via yfinance · Data auto-updated via GitHub Actions

Deploy: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from pathlib import Path
import json

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="S&P 500 Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
HIST_YEARS = list(range(2015, 2026))
PROJ_YEARS = list(range(2026, 2031))

YEAR_CONTEXT = {
    2015: "Global growth slowed; China concerns rattled markets. Fed hiked for first time in a decade. S&P 500: -0.7%.",
    2016: "Brexit vote shocked markets. Trump election fueled a year-end rally. Oil recovered. S&P 500: +11.9%.",
    2017: "Synchronized global expansion; historically low volatility. Tax reform passed. S&P 500: +21.8%.",
    2018: "Fed raised rates 4×; trade war with China escalated. Q4 selloff erased gains. S&P 500: -4.4%.",
    2019: "Fed reversed course and cut rates 3×. Trade tensions eased. S&P 500: +31.5%.",
    2020: "COVID-19 caused historic disruption. 34% crash then full recovery. Zero rates + fiscal stimulus. S&P 500: +18.4%.",
    2021: "Vaccine-driven recovery; GDP rebounded sharply. Inflation began emerging. S&P 500: +28.7%.",
    2022: "Fed hiked 0%→4.5% — most aggressive since 1980s. Tech collapsed. Inflation peaked 9.1%. S&P 500: -18.1%.",
    2023: "Inflation fell sharply; soft landing emerged. AI mania — Nvidia +239%. S&P 500: +26.3%.",
    2024: "Fed began cutting rates. AI capex surged. Mag-7 concentration at historic highs. S&P 500: ~+25%.",
    2025: "AI monetization & agents dominated enterprise tech. Tariff uncertainty created volatility.",
}

METRICS = [
    ("revenue_m",             "Revenue ($M)"),
    ("gross_profit_m",        "Gross Profit ($M)"),
    ("operating_income_m",    "Operating Income ($M)"),
    ("net_income_m",          "Net Income ($M)"),
    ("operating_cf_m",        "Operating Cash Flow ($M)"),
    ("free_cash_flow_m",      "Free Cash Flow ($M)"),
    ("capex_m",               "CapEx ($M)"),
    ("total_debt_m",          "Total Debt ($M)"),
    ("eps_diluted",           "EPS Diluted ($)"),
    ("roe_pct",               "ROE (%)"),
    ("pe_ratio",              "P/E Ratio"),
    ("dividend_yield_pct",    "Dividend Yield (%)"),
]

SECTOR_COLORS = {
    "Information Technology": "#3d7fe6",
    "Communication Services": "#9b59b6",
    "Consumer Discretionary": "#e67e22",
    "Consumer Staples":       "#27ae60",
    "Energy":                 "#e74c3c",
    "Financials":             "#f39c12",
    "Health Care":            "#1abc9c",
    "Industrials":            "#3498db",
    "Materials":              "#8e44ad",
    "Real Estate":            "#d35400",
    "Utilities":              "#16a085",
    "Other":                  "#7f8c8d",
}


SCENARIO_MULT = {"Bear": 0.55, "Base": 1.0, "Bull": 1.45}
SCENARIO_COLOR = {"Bear": "#f85149", "Base": "#e3b341", "Bull": "#3fb950"}

MAX_PORTFOLIO_SIZE = 30  # keeps live-price fetches and memory per user bounded

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tighten sidebar */
[data-testid="stSidebar"] { min-width: 220px; }
/* Metric cards */
.metric-card {
    background: #0d1220; border: 1px solid #1c2438;
    border-radius: 6px; padding: 0.85rem 1rem; margin-bottom: 0.5rem;
}
.metric-card .mc-label { font-size: 0.68rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em; color: #4a5568; margin-bottom: 0.25rem; }
.metric-card .mc-val { font-size: 1.3rem; font-weight: 700; color: #e6edf3; }
.metric-card .mc-sub { font-size: 0.72rem; color: #8b949e; margin-top: 0.1rem; }
/* Year context */
.year-card { background: #080c14; border: 1px solid #1c2438; border-radius: 5px;
    padding: 0.6rem 0.75rem; margin-bottom: 0.4rem; border-left: 3px solid #3d7fe6; }
.year-card .yc-year { font-size: 0.8rem; font-weight: 700; color: #e6edf3; }
.year-card .yc-text { font-size: 0.7rem; color: #8b949e; margin-top: 0.2rem; line-height: 1.45; }
/* Sector badge */
.sector-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 3px;
    font-size: 0.7rem; font-weight: 600; }
div[data-testid="stMetric"] { background: #080c14; border: 1px solid #1c2438;
    border-radius: 6px; padding: 0.75rem 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl="12h", show_spinner="Loading financial data…")
def load_data() -> pd.DataFrame:
    """Load the active pipeline CSV. Tries data/ first, then sp500/dist/."""
    candidates = [
        Path("data/sp500_financials.csv"),
        Path("sp500/dist/active_2026-05-30.csv"),
        # Fallback: any active_*.csv in sp500/dist/
        *sorted(Path("sp500/dist").glob("active_*.csv"), reverse=True),
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p)
            if "sector" not in df.columns:
                df["sector"] = "Other"
            return df
    st.error("Could not find financial data CSV. Expected at data/sp500_financials.csv")
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def get_all_tickers(df: pd.DataFrame) -> list[str]:
    return sorted(df["ticker"].unique().tolist())


@st.cache_data(show_spinner=False, max_entries=100)
def get_ticker_df(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    return df[df["ticker"] == ticker].sort_values("year").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False, max_entries=600)
def fetch_live_price(ticker: str) -> dict | None:
    """Fetch live quote via yfinance. Cached 5 min."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        prev  = getattr(info, "previous_close", None)
        if price and price > 0:
            chg = price - prev if prev else 0
            chg_pct = (chg / prev * 100) if prev else 0
            return {
                "price": price,
                "change": chg,
                "change_pct": chg_pct,
                "market_cap": getattr(info, "market_cap", None),
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=300)
def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Fetch OHLCV history via yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        return hist if not hist.empty else None
    except Exception:
        return None


# ── Personal portfolio (browser-saved, zero server storage) ──────────────────
# The portfolio lives in the URL (?pf=AAPL,MSFT,...) and in this browser tab's
# session. Nothing is written server-side, so any number of users can have
# their own portfolio without building up storage or write conflicts.
# Bookmarking the page preserves it across visits.

def get_portfolio(valid_tickers: list[str]) -> list[str]:
    """Load the portfolio from session state, falling back to the URL."""
    if "portfolio" not in st.session_state:
        raw = st.query_params.get("pf", "")
        tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
        valid = set(valid_tickers)
        st.session_state.portfolio = [t for t in tickers if t in valid][:MAX_PORTFOLIO_SIZE]
    return st.session_state.portfolio


def save_portfolio(tickers: list[str]) -> None:
    """Persist to session state + URL so a bookmark restores it."""
    tickers = list(dict.fromkeys(tickers))[:MAX_PORTFOLIO_SIZE]  # dedupe, cap
    st.session_state.portfolio = tickers
    if tickers:
        st.query_params["pf"] = ",".join(tickers)
    else:
        st.query_params.pop("pf", None)


# ── Formatting helpers ─────────────────────────────────────────────────────────
def fmt_m(v, decimals=1) -> str:
    """Format a value in $M → human-readable string."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    a = abs(v)
    if a >= 1_000_000:
        return f"${v/1_000_000:.{decimals}f}T"
    if a >= 1_000:
        return f"${v/1_000:.{decimals}f}B"
    return f"${v:.{decimals}f}M"


def fmt_val(v, col: str) -> str:
    """Format a value based on metric column type."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if col in ("eps_diluted",):
        return f"${v:.2f}"
    if col in ("roe_pct", "pe_ratio", "dividend_yield_pct", "gross_margin_pct", "rev_growth_pct", "debt_equity"):
        return f"{v:.1f}"
    return fmt_m(v)


def pct_change(new, old) -> str:
    if old and new and old != 0:
        p = (new - old) / abs(old) * 100
        return f"{'+' if p >= 0 else ''}{p:.1f}%"
    return "—"


# ── Color helper ─────────────────────────────────────────────────────────────
def rgba(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb + alpha float → rgba() string for Plotly."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Projection math ───────────────────────────────────────────────────────────
def compute_cagr(values: list, years: list | None = None, n_years: int = 5) -> float:
    """
    CAGR using the actual year span between data points (not sequential count).
    Falls back to index-based if years not provided.
    Result is capped to [-0.30, +0.50] to avoid absurd projections from sparse data.
    """
    if years is None:
        years = list(range(len(values)))
    pairs = [(y, v) for y, v in zip(years, values)
             if v is not None and not (isinstance(v, float) and np.isnan(v)) and v != 0]
    if len(pairs) < 2:
        return 0.05
    # Use last n_years+1 data points at most
    pairs = pairs[max(0, len(pairs) - n_years - 1):]
    first_yr, first_val = pairs[0]
    last_yr, last_val = pairs[-1]
    n = last_yr - first_yr
    if n <= 0 or first_val <= 0 or last_val <= 0:
        return 0.05
    raw = float(np.power(last_val / first_val, 1 / n) - 1)
    return max(-0.30, min(0.50, raw))


def lin_reg(xs: list, ys: list) -> tuple[float, float]:
    """Returns (slope, intercept) via OLS."""
    if len(ys) < 2:
        return 0.0, ys[0] if ys else 0.0
    xs_a, ys_a = np.array(xs, dtype=float), np.array(ys, dtype=float)
    n = len(xs_a)
    sx, sy = xs_a.sum(), ys_a.sum()
    sx2 = (xs_a ** 2).sum()
    sxy = (xs_a * ys_a).sum()
    denom = n * sx2 - sx ** 2
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    inter = (sy - slope * sx) / n
    return float(slope), float(inter)


def project_scenario(hist_values: list, scenario: str, cagr_override: float | None = None) -> dict[int, float]:
    """
    Project PROJ_YEARS values for a given scenario.
    hist_values: list aligned to HIST_YEARS (None = missing).
    Returns {year: projected_value}.
    """
    pairs = [(i, v) for i, v in enumerate(hist_values) if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if len(pairs) < 2:
        return {}
    xs, ys = zip(*pairs)
    slope, inter = lin_reg(list(xs), list(ys))
    cagr = cagr_override if cagr_override is not None else compute_cagr(hist_values, years=HIST_YEARS)
    sm = SCENARIO_MULT[scenario]
    adj = max(-0.30, min(0.50, cagr * sm))
    last_val = ys[-1]
    result = {}
    for i, yr in enumerate(PROJ_YEARS, start=1):
        base_proj = inter + slope * (len(HIST_YEARS) + (i - 1))
        growth_proj = last_val * ((1 + adj) ** i)
        projected = (base_proj + growth_proj) / 2
        result[yr] = float(projected)
    return result


# ── Chart builders ────────────────────────────────────────────────────────────
def make_metric_chart(
    ticker_df: pd.DataFrame,
    col: str,
    label: str,
    color: str,
    cagr_override: float | None = None,
) -> go.Figure:
    """Time-series chart with historical data + bear/base/bull projections."""
    hist = []
    for yr in HIST_YEARS:
        row = ticker_df[ticker_df["year"] == yr]
        val = row[col].values[0] if len(row) and col in row.columns and not pd.isna(row[col].values[0]) else None
        hist.append(val)

    all_labels = [str(y) for y in HIST_YEARS + PROJ_YEARS]
    fig = go.Figure()

    # Historical line
    hist_x = [str(y) for y in HIST_YEARS]
    hist_y = [v for v in hist]
    fig.add_trace(go.Scatter(
        x=hist_x, y=hist_y, name="Historical",
        line=dict(color=color, width=2.5),
        fill="tozeroy", fillcolor=rgba(color, 0.09),
        connectgaps=False, mode="lines+markers",
        marker=dict(size=4), hovertemplate="%{x}: %{y:,.1f}<extra></extra>",
    ))

    # Projection scenarios
    for sce in ["Bear", "Base", "Bull"]:
        proj = project_scenario(hist, sce, cagr_override)
        if not proj:
            continue
        # Bridge from last historical point
        last_hist_yr = next((y for y in reversed(HIST_YEARS) if hist[HIST_YEARS.index(y)] is not None), None)
        bridge_x = [str(last_hist_yr)] if last_hist_yr else []
        bridge_y = [hist[HIST_YEARS.index(last_hist_yr)]] if last_hist_yr else []
        proj_x = bridge_x + [str(y) for y in PROJ_YEARS]
        proj_y = bridge_y + [proj.get(y) for y in PROJ_YEARS]
        dash = "solid" if sce == "Base" else "dot"
        fig.add_trace(go.Scatter(
            x=proj_x, y=proj_y, name=sce,
            line=dict(color=SCENARIO_COLOR[sce], width=1.8, dash=dash),
            mode="lines", connectgaps=True,
            hovertemplate=f"{sce} %{{x}}: %{{y:,.1f}}<extra></extra>",
        ))

    # Vertical divider at 2025/2026 boundary
    fig.add_vline(x="2025", line_dash="dash", line_color="#4a5568", line_width=1)
    fig.add_annotation(x="2025", y=1, yref="paper", text="Proj →",
                       showarrow=False, font=dict(size=9, color="#4a5568"), xshift=22)

    fig.update_layout(
        title=dict(text=label, font=dict(size=12, color="#8b949e")),
        height=260,
        margin=dict(l=10, r=10, t=35, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#080c14",
        font=dict(color="#8b949e", size=10),
        legend=dict(orientation="h", y=-0.2, font=dict(size=9)),
        xaxis=dict(gridcolor="#1c2438", tickfont=dict(size=9), showgrid=False),
        yaxis=dict(gridcolor="#1c2438", tickfont=dict(size=9)),
        hovermode="x unified",
    )
    return fig


def make_price_chart(hist_df: pd.DataFrame, ticker: str, color: str) -> go.Figure:
    """Candlestick / close price chart."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df.index, y=hist_df["Close"],
        name="Close", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=rgba(color, 0.08),
        hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#080c14",
        font=dict(color="#8b949e", size=10),
        xaxis=dict(gridcolor="#1c2438", showgrid=False),
        yaxis=dict(gridcolor="#1c2438", tickprefix="$"),
        showlegend=False,
    )
    return fig


def make_projection_summary_chart(
    ticker_df: pd.DataFrame,
    col_rev: str, col_ni: str,
    color: str,
) -> go.Figure:
    """Bar chart: revenue vs net income projections (base case) 2026-2030."""
    hist_rev = [
        (ticker_df[ticker_df["year"] == yr][col_rev].values[0]
         if len(ticker_df[ticker_df["year"] == yr]) and not pd.isna(
            ticker_df[ticker_df["year"] == yr][col_rev].values[0]) else None)
        for yr in HIST_YEARS
    ]
    hist_ni = [
        (ticker_df[ticker_df["year"] == yr][col_ni].values[0]
         if len(ticker_df[ticker_df["year"] == yr]) and not pd.isna(
            ticker_df[ticker_df["year"] == yr][col_ni].values[0]) else None)
        for yr in HIST_YEARS
    ]
    rev_base = project_scenario(hist_rev, "Base")
    ni_base  = project_scenario(hist_ni,  "Base")
    rev_bear = project_scenario(hist_rev, "Bear")
    ni_bear  = project_scenario(hist_ni,  "Bear")
    rev_bull = project_scenario(hist_rev, "Bull")
    ni_bull  = project_scenario(hist_ni,  "Bull")

    years_str = [str(y) for y in PROJ_YEARS]
    fig = go.Figure()

    def safe_list(d):
        return [d.get(y) for y in PROJ_YEARS]

    fig.add_trace(go.Bar(
        x=years_str, y=safe_list(rev_base), name="Revenue (Base)",
        marker_color=rgba(color, 0.80), offsetgroup=0,
    ))
    fig.add_trace(go.Bar(
        x=years_str, y=safe_list(ni_base), name="Net Income (Base)",
        marker_color="rgba(63,185,80,0.80)", offsetgroup=1,
    ))
    fig.add_trace(go.Scatter(
        x=years_str, y=safe_list(rev_bear), name="Rev Bear",
        line=dict(color=SCENARIO_COLOR["Bear"], width=1.5, dash="dot"), mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=years_str, y=safe_list(rev_bull), name="Rev Bull",
        line=dict(color=SCENARIO_COLOR["Bull"], width=1.5, dash="dot"), mode="lines",
    ))

    fig.update_layout(
        barmode="group",
        title=dict(text="Revenue & Net Income Forecast 2026–2030", font=dict(size=11, color="#8b949e")),
        height=270,
        margin=dict(l=10, r=10, t=35, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#080c14",
        font=dict(color="#8b949e", size=10),
        legend=dict(orientation="h", y=-0.25, font=dict(size=9)),
        xaxis=dict(gridcolor="#1c2438", showgrid=False),
        yaxis=dict(gridcolor="#1c2438"),
    )
    return fig


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_overview(df: pd.DataFrame) -> None:
    """Sector-level overview with summary stats."""
    st.title("📈 S&P 500 Financial Analytics")
    st.caption("10-year historical financials · Bear / Base / Bull projections to 2030 · Live prices via Yahoo Finance")

    # Top-level stats
    latest_year = df[df["revenue_m"].notna()]["year"].max()
    total_tickers = df["ticker"].nunique()
    total_rev = df[df["year"] == latest_year]["revenue_m"].sum() / 1_000  # → $B
    total_ni  = df[df["year"] == latest_year]["net_income_m"].sum() / 1_000

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies", f"{total_tickers}")
    c2.metric("Latest Data Year", str(int(latest_year)))
    c3.metric(f"Total Revenue ({int(latest_year)})", f"${total_rev:,.0f}B")
    c4.metric(f"Total Net Income ({int(latest_year)})", f"${total_ni:,.0f}B")

    st.divider()
    st.subheader("Sectors")

    sectors = sorted(df["sector"].unique())
    cols = st.columns(3)
    for idx, sector in enumerate(sectors):
        color = SECTOR_COLORS.get(sector, "#7f8c8d")
        sec_df = df[df["sector"] == sector]
        tickers = sorted(sec_df["ticker"].unique())
        latest = sec_df[sec_df["year"] == latest_year]
        rev_sum = latest["revenue_m"].sum()
        ni_sum  = latest["net_income_m"].sum()
        with cols[idx % 3]:
            st.markdown(f"""
            <div style="background:#080c14;border:1px solid #1c2438;border-left:3px solid {color};
                        border-radius:6px;padding:0.85rem 1rem;margin-bottom:0.6rem">
              <div style="font-size:0.85rem;font-weight:700;color:#e6edf3">{sector}</div>
              <div style="font-size:0.72rem;color:#8b949e;margin-top:0.2rem">
                {len(tickers)} companies &nbsp;·&nbsp;
                Rev: {fmt_m(rev_sum)} &nbsp;·&nbsp;
                NI: {fmt_m(ni_sum)}
              </div>
              <div style="margin-top:0.5rem;font-size:0.67rem;color:#4a5568">
                {" &nbsp;".join(tickers[:12])}{"…" if len(tickers)>12 else ""}
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("Year-over-Year Context")
    yr_cols = st.columns(3)
    for idx, (yr, ctx) in enumerate(YEAR_CONTEXT.items()):
        with yr_cols[idx % 3]:
            st.markdown(f"""
            <div class="year-card">
              <div class="yc-year">{yr}</div>
              <div class="yc-text">{ctx}</div>
            </div>
            """, unsafe_allow_html=True)


def page_screener(df: pd.DataFrame) -> None:
    """Stock screener with filters."""
    st.title("🔍 Stock Screener")

    latest_year = int(df[df["revenue_m"].notna()]["year"].max())
    latest = df[df["year"] == latest_year].copy()

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sector_opts = ["All Sectors"] + sorted(df["sector"].unique())
        sel_sector = st.selectbox("Sector", sector_opts)
    with col2:
        search = st.text_input("Search ticker / name", placeholder="e.g. AAPL")
    with col3:
        sort_col = st.selectbox("Sort by", ["revenue_m", "net_income_m", "eps_diluted", "pe_ratio"])

    filtered = latest.copy()
    if sel_sector != "All Sectors":
        filtered = filtered[filtered["sector"] == sel_sector]
    if search.strip():
        q = search.strip().upper()
        filtered = filtered[filtered["ticker"].str.contains(q, case=False, na=False)]
    filtered = filtered.sort_values(sort_col, ascending=False, na_position="last")

    st.caption(f"Showing {len(filtered)} companies · {latest_year} data")

    # Display as a table
    display_cols = {
        "ticker": "Ticker",
        "sector": "Sector",
        "revenue_m": "Revenue ($M)",
        "net_income_m": "Net Income ($M)",
        "eps_diluted": "EPS",
        "pe_ratio": "P/E",
        "gross_margin_pct": "Gross Margin %",
        "dividend_yield_pct": "Div Yield %",
        "debt_equity": "D/E",
    }
    display = filtered[[c for c in display_cols if c in filtered.columns]].copy()
    display.columns = [display_cols.get(c, c) for c in display.columns]
    st.dataframe(
        display,
        use_container_width=True,
        height=550,
        hide_index=True,
        column_config={
            "Revenue ($M)": st.column_config.NumberColumn(format="$%.0f M"),
            "Net Income ($M)": st.column_config.NumberColumn(format="$%.0f M"),
            "EPS": st.column_config.NumberColumn(format="$%.2f"),
            "P/E": st.column_config.NumberColumn(format="%.1f×"),
            "Gross Margin %": st.column_config.NumberColumn(format="%.1f%%"),
            "Div Yield %": st.column_config.NumberColumn(format="%.2f%%"),
            "D/E": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def page_stock_detail(df: pd.DataFrame) -> None:
    """Full stock detail: live price, 10-yr history, projections."""
    all_tickers = get_all_tickers(df)

    # Sidebar ticker selector (also allow override from session state)
    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = "AAPL"

    ticker = st.sidebar.selectbox(
        "Select Ticker",
        all_tickers,
        index=all_tickers.index(st.session_state.selected_ticker)
        if st.session_state.selected_ticker in all_tickers else 0,
        key="ticker_selector",
    )
    st.session_state.selected_ticker = ticker

    tdf = get_ticker_df(df, ticker)
    if tdf.empty:
        st.warning(f"No data found for {ticker}.")
        return

    sector = tdf["sector"].iloc[0] if "sector" in tdf.columns else "Other"
    color = SECTOR_COLORS.get(sector, "#3d7fe6")

    # ── Header ──
    latest_yr_row = tdf[tdf["revenue_m"].notna()].sort_values("year").iloc[-1] if len(tdf[tdf["revenue_m"].notna()]) else tdf.iloc[-1]
    latest_year = int(latest_yr_row["year"])

    col_hdr, col_price = st.columns([3, 1])
    with col_hdr:
        st.markdown(f"""
        <div style="border-left:4px solid {color};padding-left:0.75rem;margin-bottom:0.5rem">
          <div style="font-size:1.6rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em">{ticker}</div>
          <div style="font-size:0.8rem;color:#8b949e;margin-top:0.15rem">{sector}</div>
        </div>
        """, unsafe_allow_html=True)
        portfolio = get_portfolio(all_tickers)
        if ticker in portfolio:
            if st.button(f"✓ In portfolio — remove {ticker}", key="pf_remove"):
                save_portfolio([t for t in portfolio if t != ticker])
                st.rerun()
        elif len(portfolio) < MAX_PORTFOLIO_SIZE:
            if st.button(f"➕ Add {ticker} to My Portfolio", key="pf_add"):
                save_portfolio(portfolio + [ticker])
                st.rerun()
    with col_price:
        with st.spinner("Fetching price…"):
            px_data = fetch_live_price(ticker)
        if px_data:
            chg_color = "green" if px_data["change_pct"] >= 0 else "red"
            sign = "+" if px_data["change_pct"] >= 0 else ""
            st.markdown(f"""
            <div style="text-align:right">
              <div style="font-size:1.8rem;font-weight:700;color:#e6edf3">${px_data['price']:.2f}</div>
              <div style="font-size:0.85rem;color:{chg_color}">{sign}{px_data['change']:.2f} ({sign}{px_data['change_pct']:.2f}%)</div>
              <div style="font-size:0.68rem;color:#4a5568;margin-top:0.2rem">Live · Yahoo Finance</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Key metrics row ──
    rev = latest_yr_row.get("revenue_m")
    ni  = latest_yr_row.get("net_income_m")
    eps = latest_yr_row.get("eps_diluted")
    pe  = latest_yr_row.get("pe_ratio")
    gm  = latest_yr_row.get("gross_margin_pct")
    dy  = latest_yr_row.get("dividend_yield_pct")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(f"Revenue ({latest_year})", fmt_m(rev))
    m2.metric(f"Net Income ({latest_year})", fmt_m(ni))
    m3.metric("EPS (Diluted)", f"${eps:.2f}" if eps and not np.isnan(eps) else "—")
    m4.metric("P/E Ratio", f"{pe:.1f}×" if pe and not np.isnan(pe) else "—")
    m5.metric("Gross Margin", f"{gm:.1f}%" if gm and not np.isnan(gm) else "—")
    m6.metric("Div Yield", f"{dy:.2f}%" if dy and not np.isnan(dy) else "—")

    st.divider()

    # ── Price chart + controls side by side ──
    price_col, ctrl_col = st.columns([3, 1])

    with ctrl_col:
        st.markdown("**Projection Settings**")
        cagr_rows = tdf[tdf["revenue_m"].notna()][["year", "revenue_m"]]
        default_cagr = (
            compute_cagr(cagr_rows["revenue_m"].tolist(), years=cagr_rows["year"].tolist()) * 100
            if len(cagr_rows) >= 2 else 5.0
        )
        growth_override = st.slider(
            "Annual Growth Rate Override",
            min_value=-20.0, max_value=40.0,
            value=round(default_cagr, 1), step=0.5,
            format="%.1f%%",
            help=f"Historical 3-yr CAGR: {default_cagr:.1f}%",
        )
        cagr_override = growth_override / 100

        price_period = st.selectbox("Price Chart Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)

    with price_col:
        with st.spinner("Loading price history…"):
            hist_price = fetch_price_history(ticker, period=price_period)
        if hist_price is not None:
            st.plotly_chart(make_price_chart(hist_price, ticker, color), use_container_width=True)
        else:
            st.info("Price history unavailable.")

    # ── Year context strip ──
    st.markdown("**Year Context (2015–2025)**")
    yr_cols = st.columns(len(HIST_YEARS))
    for i, yr in enumerate(HIST_YEARS):
        yr_row = tdf[tdf["year"] == yr]
        has_data = len(yr_row) > 0 and not pd.isna(yr_row["revenue_m"].values[0]) if len(yr_row) else False
        rev_val = fmt_m(yr_row["revenue_m"].values[0]) if has_data else "—"
        ni_val  = fmt_m(yr_row["net_income_m"].values[0]) if has_data else "—"
        with yr_cols[i]:
            bg = rgba(color, 0.08) if has_data else "#080c14"
            st.markdown(f"""
            <div style="background:{bg};border:1px solid #1c2438;border-radius:4px;
                        padding:0.4rem 0.35rem;text-align:center;border-top:2px solid {color if has_data else '#1c2438'}">
              <div style="font-size:0.72rem;font-weight:700;color:#e6edf3">{yr}</div>
              <div style="font-size:0.62rem;color:#8b949e;margin-top:0.15rem">R:{rev_val}</div>
              <div style="font-size:0.62rem;color:#8b949e">NI:{ni_val}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Financial metric charts ──
    st.markdown(f"**Financial Metrics 2015–{latest_year} + Projections 2026–2030**")
    st.caption("🔴 Bear (0.55× CAGR) · 🟡 Base (1.0× CAGR) · 🟢 Bull (1.45× CAGR)")

    available_metrics = [(col, lbl) for col, lbl in METRICS if col in tdf.columns and tdf[col].notna().any()]

    # 2 charts per row
    for i in range(0, len(available_metrics), 2):
        chunk = available_metrics[i:i+2]
        cols = st.columns(len(chunk))
        for j, (col, lbl) in enumerate(chunk):
            is_small = col in ("eps_diluted", "roe_pct", "pe_ratio", "dividend_yield_pct")
            with cols[j]:
                fig = make_metric_chart(
                    tdf, col, lbl, color,
                    cagr_override=None if is_small else cagr_override,
                )
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Projection summary ──
    st.markdown("**Projections Summary 2026–2030**")
    proj_chart_col, proj_tbl_col = st.columns([3, 2])

    with proj_chart_col:
        if "revenue_m" in tdf.columns and "net_income_m" in tdf.columns:
            fig_proj = make_projection_summary_chart(tdf, "revenue_m", "net_income_m", color)
            st.plotly_chart(fig_proj, use_container_width=True)

    with proj_tbl_col:
        st.markdown("**Key Metrics — Bear / Base / Bull**")
        proj_metrics = [
            ("revenue_m", "Revenue ($M)"),
            ("net_income_m", "Net Income ($M)"),
            ("eps_diluted", "EPS ($)"),
            ("free_cash_flow_m", "Free Cash Flow ($M)"),
        ]
        tbl_rows = []
        tbl_years = [latest_year, 2026, 2028, 2030]
        header = ["Metric"] + [str(y) for y in tbl_years[:-2]] + ["2026 Bear", "2026 Base", "2026 Bull", "2030 Base"]
        for col, lbl in proj_metrics:
            if col not in tdf.columns:
                continue
            hist_vals = [
                (tdf[tdf["year"] == yr][col].values[0]
                 if len(tdf[tdf["year"] == yr]) and not pd.isna(tdf[tdf["year"] == yr][col].values[0]) else None)
                for yr in HIST_YEARS
            ]
            bear = project_scenario(hist_vals, "Bear", cagr_override if col == "revenue_m" else None)
            base = project_scenario(hist_vals, "Base", cagr_override if col == "revenue_m" else None)
            bull = project_scenario(hist_vals, "Bull", cagr_override if col == "revenue_m" else None)

            latest_val = next(
                (tdf[tdf["year"] == yr][col].values[0]
                 for yr in reversed(HIST_YEARS)
                 if len(tdf[tdf["year"] == yr]) and not pd.isna(tdf[tdf["year"] == yr][col].values[0])),
                None
            )

            def fv(v):
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return "—"
                if col == "eps_diluted":
                    return f"${v:.2f}"
                return fmt_m(v)

            tbl_rows.append({
                "Metric": lbl,
                str(latest_year): fv(latest_val),
                "2026 Bear": fv(bear.get(2026)),
                "2026 Base": fv(base.get(2026)),
                "2026 Bull": fv(bull.get(2026)),
                "2030 Base": fv(base.get(2030)),
            })

        if tbl_rows:
            st.dataframe(
                pd.DataFrame(tbl_rows),
                hide_index=True,
                use_container_width=True,
            )

    st.divider()

    # ── Full historical data table ──
    with st.expander("Full Historical Data Table", expanded=False):
        disp_cols = {
            "year": "Year",
            "revenue_m": "Revenue ($M)",
            "rev_growth_pct": "Rev Growth %",
            "gross_profit_m": "Gross Profit ($M)",
            "gross_margin_pct": "Gross Margin %",
            "operating_income_m": "Op. Income ($M)",
            "net_income_m": "Net Income ($M)",
            "eps_diluted": "EPS",
            "operating_cf_m": "Op. CF ($M)",
            "free_cash_flow_m": "FCF ($M)",
            "capex_m": "CapEx ($M)",
            "total_debt_m": "Total Debt ($M)",
            "stockholders_equity_m": "Equity ($M)",
            "debt_equity": "D/E",
            "roe_pct": "ROE %",
            "market_cap_m": "Mkt Cap ($M)",
            "pe_ratio": "P/E",
            "dividend_yield_pct": "Div Yield %",
        }
        show_df = tdf[[c for c in disp_cols if c in tdf.columns]].sort_values("year", ascending=False)
        show_df.columns = [disp_cols.get(c, c) for c in show_df.columns]
        st.dataframe(show_df, hide_index=True, use_container_width=True)


def _portfolio_builder(df: pd.DataFrame, existing: list[str]) -> None:
    """Shared builder/editor UI: sector filter + multiselect + save."""
    sectors = ["All Sectors"] + sorted(df["sector"].unique())
    sel_sector = st.selectbox("Filter by sector", sectors, key="pf_sector_filter")

    latest_year = int(df[df["revenue_m"].notna()]["year"].max())
    latest = df[df["year"] == latest_year]
    if sel_sector != "All Sectors":
        choices = sorted(latest[latest["sector"] == sel_sector]["ticker"].unique())
    else:
        choices = sorted(latest["ticker"].unique())
    # Keep already-picked tickers selectable even when filtered out
    options = sorted(set(choices) | set(existing))

    picked = st.multiselect(
        f"Choose your stocks (max {MAX_PORTFOLIO_SIZE})",
        options,
        default=[t for t in existing if t in options],
        max_selections=MAX_PORTFOLIO_SIZE,
        placeholder="Type a ticker, e.g. AAPL",
        key="pf_picker",
    )

    c1, c2 = st.columns([1, 1])
    if c1.button("💾 Save Portfolio", type="primary", use_container_width=True):
        save_portfolio(picked)
        st.rerun()
    if existing and c2.button("🗑️ Clear Portfolio", use_container_width=True):
        save_portfolio([])
        st.rerun()


def page_portfolio(df: pd.DataFrame) -> None:
    """Personal portfolio: first-visit builder, then a live dashboard."""
    all_tickers = get_all_tickers(df)
    portfolio = get_portfolio(all_tickers)

    # ── First visit: onboarding builder ──
    if not portfolio:
        st.title("💼 Build Your Portfolio")
        st.markdown(
            "Welcome! Pick the S&P 500 stocks you want to follow and create your "
            "own personalized portfolio. It's saved **in your browser's URL** — "
            "no account needed. After saving, **bookmark the page** to keep it."
        )
        _portfolio_builder(df, [])
        return

    # ── Returning user: dashboard ──
    st.title("💼 My Portfolio")
    st.caption(
        f"{len(portfolio)} holdings · saved in your URL — bookmark this page to keep it"
    )

    latest_year = int(df[df["revenue_m"].notna()]["year"].max())
    pf_latest = df[(df["ticker"].isin(portfolio)) & (df["year"] == latest_year)]

    # Live prices (cached 5 min per ticker)
    quotes = {}
    with st.spinner("Fetching live prices…"):
        for t in portfolio:
            quotes[t] = fetch_live_price(t)

    # Summary metrics
    n_up = sum(1 for q in quotes.values() if q and q["change_pct"] >= 0)
    n_dn = sum(1 for q in quotes.values() if q and q["change_pct"] < 0)
    total_rev = pf_latest["revenue_m"].sum()
    total_ni = pf_latest["net_income_m"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Holdings", f"{len(portfolio)}")
    c2.metric("Up / Down Today", f"🟢 {n_up} / 🔴 {n_dn}")
    c3.metric(f"Combined Revenue ({latest_year})", fmt_m(total_rev))
    c4.metric(f"Combined Net Income ({latest_year})", fmt_m(total_ni))

    st.divider()

    tbl_col, pie_col = st.columns([3, 2])

    with tbl_col:
        st.markdown("**Holdings**")
        rows = []
        for t in portfolio:
            r = pf_latest[pf_latest["ticker"] == t]
            r = r.iloc[0] if len(r) else None
            q = quotes.get(t)
            rows.append({
                "Ticker": t,
                "Sector": r["sector"] if r is not None else "—",
                "Price": q["price"] if q else None,
                "Today %": q["change_pct"] if q else None,
                "Revenue ($M)": r["revenue_m"] if r is not None else None,
                "Net Income ($M)": r["net_income_m"] if r is not None else None,
                "EPS": r["eps_diluted"] if r is not None else None,
                "P/E": r["pe_ratio"] if r is not None else None,
            })
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            height=min(420, 38 + 35 * len(rows)),
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Today %": st.column_config.NumberColumn(format="%.2f%%"),
                "Revenue ($M)": st.column_config.NumberColumn(format="$%.0f M"),
                "Net Income ($M)": st.column_config.NumberColumn(format="$%.0f M"),
                "EPS": st.column_config.NumberColumn(format="$%.2f"),
                "P/E": st.column_config.NumberColumn(format="%.1f×"),
            },
        )
        st.caption("Open any holding in **📊 Stock Detail** for 10-yr history & projections.")

    with pie_col:
        st.markdown("**Sector Mix**")
        if len(pf_latest):
            mix = pf_latest.groupby("sector")["ticker"].count().reset_index()
            mix.columns = ["sector", "count"]
            fig = px.pie(
                mix, names="sector", values="count",
                color="sector", color_discrete_map=SECTOR_COLORS, hole=0.45,
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#8b949e", size=10),
                height=300, margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(font=dict(size=9)),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Combined revenue history of the portfolio
    st.markdown("**Portfolio Combined Revenue (10-Year)**")
    pf_hist = (
        df[df["ticker"].isin(portfolio) & df["year"].isin(HIST_YEARS)]
        .groupby("year")["revenue_m"].sum().reset_index()
    )
    if len(pf_hist):
        fig = go.Figure(go.Scatter(
            x=pf_hist["year"].astype(str), y=pf_hist["revenue_m"],
            line=dict(color="#3d7fe6", width=2.5), fill="tozeroy",
            fillcolor=rgba("#3d7fe6", 0.09), mode="lines+markers", marker=dict(size=4),
            hovertemplate="%{x}: $%{y:,.0f}M<extra></extra>",
        ))
        fig.update_layout(
            height=260, margin=dict(l=10, r=10, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080c14",
            font=dict(color="#8b949e", size=10),
            xaxis=dict(gridcolor="#1c2438", showgrid=False),
            yaxis=dict(gridcolor="#1c2438", tickprefix="$", ticksuffix="M"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    with st.expander("✏️ Edit Portfolio", expanded=False):
        _portfolio_builder(df, portfolio)


def page_risk_analysis(df: pd.DataFrame) -> None:
    """Cross-sector risk and performance comparison."""
    st.title("⚠️ Risk & Comparative Analysis")

    latest_year = int(df[df["revenue_m"].notna()]["year"].max())
    latest = df[df["year"] == latest_year].copy()

    tab1, tab2, tab3 = st.tabs(["Revenue by Sector", "Margin Analysis", "Debt & Coverage"])

    with tab1:
        sec_rev = latest.groupby("sector")["revenue_m"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(
            sec_rev, x="sector", y="revenue_m",
            color="sector", color_discrete_map=SECTOR_COLORS,
            title=f"Total Revenue by Sector ({latest_year})",
            labels={"revenue_m": "Revenue ($M)", "sector": ""},
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080c14",
            font=dict(color="#8b949e"), showlegend=False,
            height=400, margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(tickangle=-30),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Revenue CAGR 2020→latest per sector
        st.subheader("Revenue Growth (2020 → latest)")
        yr_2020 = df[df["year"] == 2020].groupby("sector")["revenue_m"].sum()
        yr_latest = df[df["year"] == latest_year].groupby("sector")["revenue_m"].sum()
        n_yrs = latest_year - 2020
        cagr_data = []
        for s in yr_2020.index:
            r0, r1 = yr_2020.get(s), yr_latest.get(s)
            if r0 and r1 and r0 > 0 and r1 > 0 and n_yrs > 0:
                cagr = (r1 / r0) ** (1 / n_yrs) - 1
                cagr_data.append({"Sector": s, "Revenue CAGR %": round(cagr * 100, 1)})
        if cagr_data:
            cagr_df = pd.DataFrame(cagr_data).sort_values("Revenue CAGR %", ascending=False)
            fig2 = px.bar(
                cagr_df, x="Sector", y="Revenue CAGR %", color="Sector",
                color_discrete_map=SECTOR_COLORS,
                title=f"Revenue CAGR {2020}→{latest_year} by Sector",
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080c14",
                font=dict(color="#8b949e"), showlegend=False,
                height=350, margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(tickangle=-30),
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        margin = latest[latest["gross_margin_pct"].notna()].copy()
        fig3 = px.box(
            margin, x="sector", y="gross_margin_pct",
            color="sector", color_discrete_map=SECTOR_COLORS,
            title=f"Gross Margin % Distribution by Sector ({latest_year})",
            labels={"gross_margin_pct": "Gross Margin %", "sector": ""},
        )
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080c14",
            font=dict(color="#8b949e"), showlegend=False,
            height=400, margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(tickangle=-30),
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Top 20 by net margin
        st.subheader("Top 20 by Net Income Margin")
        margin2 = latest[latest["revenue_m"].notna() & latest["net_income_m"].notna()].copy()
        margin2["net_margin_pct"] = margin2["net_income_m"] / margin2["revenue_m"] * 100
        top20 = margin2.nlargest(20, "net_margin_pct")[["ticker", "sector", "net_margin_pct", "revenue_m", "net_income_m"]].copy()
        top20.columns = ["Ticker", "Sector", "Net Margin %", "Revenue ($M)", "Net Income ($M)"]
        top20["Net Margin %"] = top20["Net Margin %"].round(1)
        st.dataframe(top20, hide_index=True, use_container_width=True)

    with tab3:
        debt = latest[latest["debt_equity"].notna() & (latest["debt_equity"] > 0) & (latest["debt_equity"] < 20)].copy()
        fig4 = px.scatter(
            debt, x="debt_equity", y="roe_pct",
            color="sector", color_discrete_map=SECTOR_COLORS,
            hover_data=["ticker"],
            title=f"D/E Ratio vs ROE % ({latest_year})",
            labels={"debt_equity": "Debt / Equity", "roe_pct": "ROE %"},
        )
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#080c14",
            font=dict(color="#8b949e"),
            height=450, margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig4, use_container_width=True)


# ── Sidebar navigation ────────────────────────────────────────────────────────
def main() -> None:
    df = load_data()
    if df.empty:
        return

    st.sidebar.markdown("## 📈 S&P 500 Analytics")
    st.sidebar.markdown("---")

    pages = {
        "💼 My Portfolio":     "portfolio",
        "🏠 Overview":         "overview",
        "🔍 Stock Screener":   "screener",
        "📊 Stock Detail":     "stock",
        "Risk Analysis":    "risk",
    }
    page_label = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")
    page = pages[page_label]

    # ── Portfolio-wide filter ─────────────────────────────────────────────────
    # When the user has a portfolio, every page can be filtered to just their
    # holdings. Toggle off to explore all companies (and add new ones).
    portfolio = get_portfolio(get_all_tickers(df))

    # New users see nothing until they build a portfolio
    if not portfolio and page != "portfolio":
        st.title("💼 Welcome — build your portfolio first")
        st.markdown(
            "This app is personalized to **your** portfolio. Head to "
            "**💼 My Portfolio** in the sidebar and pick the S&P 500 stocks "
            "you want to follow — then every page (Overview, Screener, "
            "Stock Detail, Risk Analysis) will show your companies."
        )
        st.info("Once saved, use the sidebar toggle to explore all 487 companies and add more anytime.")
        return

    df_view = df
    if portfolio:
        st.sidebar.markdown("---")
        pf_only = st.sidebar.toggle(
            "💼 My portfolio only",
            value=True,
            key="pf_only_toggle",
            help="Filter every page to just your holdings. Turn off to explore all companies and add new ones.",
        )
        if pf_only:
            df_view = df[df["ticker"].isin(portfolio)]
            st.sidebar.caption(f"Filtered to your {len(portfolio)} holdings")
        else:
            st.sidebar.caption(f"Exploring all {df['ticker'].nunique()} companies")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Data: {df['ticker'].nunique()} tickers  {int(df['year'].max())} latest year")
    st.sidebar.caption("Prices via Yahoo Finance (yfinance)")
    st.sidebar.caption("Fundamentals: SEC EDGAR 10-K pipeline")

    if page == "portfolio":
        page_portfolio(df)          # builder always needs the full universe
    elif page == "overview":
        page_overview(df_view)
    elif page == "screener":
        page_screener(df_view)
    elif page == "stock":
        page_stock_detail(df_view)
    elif page == "risk":
        page_risk_analysis(df_view)


if __name__ == "__main__":
    main()
