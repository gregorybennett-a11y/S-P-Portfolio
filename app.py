"""
S&P 500 Financial Analytics — Streamlit App
============================================
Admin / Professor / Student accounts · Shared class portfolio
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

# ── Global Plotly theme ───────────────────────────────────────────────────────
import plotly.io as pio
pio.templates["sp_dark"] = go.layout.Template(layout=go.Layout(
    font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#c7d2e0"),
    hoverlabel=dict(bgcolor="#111a30", bordercolor="rgba(99,102,241,.45)",
                    font=dict(family="Inter, sans-serif", size=12, color="#e2e8f0")),
    xaxis=dict(gridcolor="rgba(148,163,184,.08)", zerolinecolor="rgba(148,163,184,.08)"),
    yaxis=dict(gridcolor="rgba(148,163,184,.08)", zerolinecolor="rgba(148,163,184,.08)"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    barcornerradius=5,
    colorway=["#818cf8", "#22d3ee", "#34d399", "#fbbf24", "#fb7185",
              "#a78bfa", "#f472b6", "#38bdf8"],
))
pio.templates.default = "plotly_dark+sp_dark"

# ── Page config + global CSS ──────────────────────────────────────────────────
# Called from main() so it runs on EVERY rerun — including in demo_app.py,
# where app.py is imported once and its top-level code doesn't re-execute.
def setup_page() -> None:
    try:
        st.set_page_config(
            page_title="S&P 500 Analytics",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass  # already configured this run
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="st-"], .stApp { font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; }
/* Restore Streamlit's Material icon font (expander arrows, sidebar collapse, etc.) */
[data-testid="stIconMaterial"], [class*="material-symbols"], .material-symbols-rounded {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal; font-style: normal; letter-spacing: normal;
    text-transform: none; white-space: nowrap; word-wrap: normal; direction: ltr;
}
.stApp {
    background:
      radial-gradient(1100px 520px at 12% -8%, rgba(99,102,241,.15), transparent 60%),
      radial-gradient(900px 480px at 88% -4%, rgba(34,211,238,.09), transparent 55%),
      #05070d;
}
[data-testid="stHeader"] { background: rgba(5,7,13,.72); backdrop-filter: blur(10px); }
h1, h2, h3 { letter-spacing: -.02em; color: #f1f5f9; }

/* Sidebar */
[data-testid="stSidebar"] {
    min-width: 230px;
    background: rgba(7,11,22,.88);
    border-right: 1px solid rgba(148,163,184,.1);
    backdrop-filter: blur(12px);
}
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: .32rem .6rem; border-radius: 10px;
    transition: background .15s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(99,102,241,.12); }

/* Buttons */
.stButton > button {
    border-radius: 10px; border: 1px solid rgba(99,102,241,.35);
    background: linear-gradient(135deg, rgba(99,102,241,.18), rgba(34,211,238,.08));
    color: #e2e8f0; font-weight: 600;
    transition: border-color .15s ease, box-shadow .15s ease;
}
.stButton > button:hover { border-color: #6366f1; box-shadow: 0 0 14px rgba(99,102,241,.30); }

/* Metric cards */
.metric-card {
    background: rgba(15,23,42,.55); border: 1px solid rgba(148,163,184,.14);
    border-radius: 14px; padding: 0.9rem 1.05rem; margin-bottom: 0.55rem;
    backdrop-filter: blur(10px);
    transition: transform .15s ease, border-color .15s ease;
}
.metric-card:hover { transform: translateY(-1px); border-color: rgba(99,102,241,.4); }
.metric-card .mc-label { font-size: 0.66rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: .1em; color: #8494ab; margin-bottom: 0.3rem; }
.metric-card .mc-val { font-family: 'JetBrains Mono', monospace;
    font-size: 1.32rem; font-weight: 700; color: #f1f5f9; }
.metric-card .mc-sub { font-size: 0.72rem; color: #94a3b8; margin-top: 0.12rem; }

/* Year context */
.year-card { background: rgba(10,16,31,.6); border: 1px solid rgba(148,163,184,.13);
    border-radius: 12px; padding: 0.85rem 1rem; margin-bottom: 0.55rem;
    border-left: 3px solid #6366f1; backdrop-filter: blur(8px); }
.year-card .yc-year { font-size: 1rem; font-weight: 700; color: #f1f5f9; }
.year-card .yc-text { font-size: 0.85rem; color: #9aa8bd; margin-top: 0.25rem; line-height: 1.55; }

/* Sector badge */
.sector-badge { display: inline-block; padding: 0.16rem 0.55rem; border-radius: 999px;
    font-size: 0.7rem; font-weight: 600; }

/* Streamlit widgets */
div[data-testid="stMetric"] { background: rgba(15,23,42,.5); border: 1px solid rgba(148,163,184,.13);
    border-radius: 14px; padding: 0.8rem 1rem; backdrop-filter: blur(10px); }
div[data-testid="stMetric"] label { color: #8494ab !important; }
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-weight: 700; }
[data-testid="stDataFrame"] { border: 1px solid rgba(148,163,184,.13); border-radius: 12px; }
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {
    background: rgba(15,23,42,.7) !important;
    border-color: rgba(99,102,241,.25) !important;
    border-radius: 10px !important;
}
div[data-testid="stExpander"] { background: rgba(15,23,42,.45);
    border: 1px solid rgba(148,163,184,.13); border-radius: 14px; overflow: hidden; }
div[data-testid="stAlert"] { border-radius: 12px; backdrop-filter: blur(8px); }
.stTabs [data-baseweb="tab-list"] { gap: .4rem; }
hr { border-color: rgba(148,163,184,.12) !important; }

/* ═══ Motion layer ═══ */
@keyframes fadeUp { from { opacity:0; transform: translateY(10px); } to { opacity:1; transform:none; } }
@keyframes sheen  { to { background-position: 200% center; } }
@keyframes drift  {
  0%,100% { transform: translate(0,0) scale(1); }
  50%     { transform: translate(-50px,35px) scale(1.07); }
}

/* Ambient light drift behind content */
.stApp::before {
  content:''; position: fixed; inset: -15%;
  background:
    radial-gradient(620px 420px at 22% 12%, rgba(99,102,241,.10), transparent 60%),
    radial-gradient(720px 480px at 78% 18%, rgba(34,211,238,.07), transparent 60%);
  animation: drift 26s ease-in-out infinite;
  pointer-events: none; will-change: transform;
}

/* Entrance animation (plays on mount) */
[data-testid="stElementContainer"], .element-container { animation: fadeUp .4s ease-out both; }
[data-testid="stColumn"]:nth-of-type(2) [data-testid="stElementContainer"] { animation-delay: .06s; }
[data-testid="stColumn"]:nth-of-type(3) [data-testid="stElementContainer"] { animation-delay: .12s; }
[data-testid="stColumn"]:nth-of-type(4) [data-testid="stElementContainer"] { animation-delay: .18s; }

/* Charts in glass panels with hover glow */
[data-testid="stPlotlyChart"] {
  background: rgba(15,23,42,.45); border: 1px solid rgba(148,163,184,.12);
  border-radius: 16px; padding: .55rem .35rem .15rem; backdrop-filter: blur(10px);
  transition: border-color .2s ease, box-shadow .2s ease;
}
[data-testid="stPlotlyChart"]:hover {
  border-color: rgba(99,102,241,.35);
  box-shadow: 0 10px 34px rgba(99,102,241,.10);
}

/* Micro-interactions */
.stButton > button { transition: border-color .15s ease, box-shadow .15s ease, transform .1s ease; }
.stButton > button:active { transform: scale(.97); }
div[data-testid="stMetric"] {
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
div[data-testid="stMetric"]:hover {
  transform: translateY(-2px); border-color: rgba(99,102,241,.45);
  box-shadow: 0 12px 30px rgba(2,6,23,.5);
}

/* Scrollbar */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(99,102,241,.35); border-radius: 8px;
  border: 2px solid transparent; background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover { background-color: rgba(99,102,241,.6); }

/* Page title gradient underline */
h1 { position: relative; padding-bottom: .4rem; }
h1::after {
  content:''; position:absolute; left:0; bottom:0; width:64px; height:3px;
  border-radius:3px; background: linear-gradient(90deg,#6366f1,#22d3ee);
}

/* Sidebar brand: animated gradient shimmer */
[data-testid="stSidebar"] h2 {
  background: linear-gradient(120deg,#e2e8f0,#818cf8,#22d3ee,#e2e8f0);
  background-size: 200% auto;
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: sheen 7s linear infinite;
  font-weight: 800; letter-spacing: -.02em;
}

/* Sidebar nav slide-on-hover */
[data-testid="stSidebar"] [role="radiogroup"] label {
  transition: background .15s ease, padding-left .15s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { padding-left: .85rem; }

/* Metric card hover sheen sweep */
.metric-card { position: relative; overflow: hidden; }
.metric-card::after {
  content:''; position:absolute; top:0; left:-70%; width:45%; height:100%;
  background: linear-gradient(105deg, transparent, rgba(255,255,255,.045), transparent);
  transform: skewX(-20deg); transition: left .45s ease;
}
.metric-card:hover::after { left: 130%; }

</style>
""", unsafe_allow_html=True)

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
    "Information Technology": "#6366f1",
    "Communication Services": "#a78bfa",
    "Consumer Discretionary": "#f59e0b",
    "Consumer Staples":       "#34d399",
    "Energy":                 "#fb7185",
    "Financials":             "#22d3ee",
    "Health Care":            "#2dd4bf",
    "Industrials":            "#38bdf8",
    "Materials":              "#c084fc",
    "Real Estate":            "#fb923c",
    "Utilities":              "#4ade80",
    "Other":                  "#64748b",
}


SCENARIO_MULT = {"Bear": 0.55, "Base": 1.0, "Bull": 1.45}
SCENARIO_COLOR = {"Bear": "#fb7185", "Base": "#fbbf24", "Bull": "#34d399"}

MAX_PORTFOLIO_SIZE = 503  # whole S&P 500 — prices are batch-fetched so size is not a problem

# Public demo mode (set True by demo_app.py): no login, manage pages hidden,
# portfolio edits live only in the visitor's session — nothing is saved.
DEMO_MODE = False
DEMO_PORTFOLIO = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM",
    "V", "JNJ", "XOM", "WMT", "PG", "KO", "DIS", "NFLX", "AMD", "CRM", "COST",
]

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


@st.cache_data(show_spinner=False)
def latest_per_ticker(df: pd.DataFrame) -> pd.DataFrame:
    """Each ticker's most recent year that has revenue data (10-Ks are annual,
    so 'latest' differs per company depending on fiscal year end)."""
    have = df[df["revenue_m"].notna()]
    if have.empty:
        return have
    idx = have.groupby("ticker")["year"].idxmax()
    return have.loc[idx]


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


@st.cache_data(ttl=300, show_spinner=False, max_entries=50)
def fetch_live_prices_bulk(tickers: tuple) -> dict:
    """Quotes for many tickers in ONE yfinance download — fast for big portfolios."""
    if not tickers:
        return {}
    try:
        data = yf.download(list(tickers), period="2d", interval="1d",
                           group_by="ticker", progress=False, threads=True)
        out = {}
        for t in tickers:
            try:
                closes = (data[t]["Close"] if len(tickers) > 1 else data["Close"]).dropna()
                if len(closes):
                    price = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
                    chg = price - prev if prev else 0.0
                    out[t] = {
                        "price": price, "change": chg,
                        "change_pct": (chg / prev * 100) if prev else 0.0,
                        "market_cap": None,
                    }
            except Exception:
                continue
        return out
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False, max_entries=300)
def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Fetch OHLCV history via yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        return hist if not hist.empty else None
    except Exception:
        return None


# ── GitHub-backed storage (accounts + shared class portfolio) ────────────────
# Accounts and the class portfolio are stored as JSON on a separate branch
# ("appdata") of the GitHub repo, written via the GitHub API using a token in
# Streamlit secrets. A non-default branch is used so saves do NOT trigger a
# Streamlit redeploy. Survives restarts; tiny write volume for a class.

import base64
import hashlib
import secrets as _pysecrets
from datetime import datetime, timezone

import requests as _rq

ACCOUNTS_PATH = "data/accounts.json"


def _gh_cfg():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["repo"], gh.get("branch", "appdata")
    except Exception:
        return None, None, None


def _gh_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _gh_ensure_branch(token: str, repo: str, branch: str) -> bool:
    r = _rq.get(f"https://api.github.com/repos/{repo}/branches/{branch}",
                headers=_gh_headers(token), timeout=15)
    if r.status_code == 200:
        return True
    rd = _rq.get(f"https://api.github.com/repos/{repo}", headers=_gh_headers(token), timeout=15)
    default = rd.json().get("default_branch", "main")
    rs = _rq.get(f"https://api.github.com/repos/{repo}/git/ref/heads/{default}",
                 headers=_gh_headers(token), timeout=15)
    sha = rs.json().get("object", {}).get("sha")
    if not sha:
        return False
    rc = _rq.post(f"https://api.github.com/repos/{repo}/git/refs", headers=_gh_headers(token),
                  json={"ref": f"refs/heads/{branch}", "sha": sha}, timeout=15)
    return rc.status_code in (200, 201)


@st.cache_data(ttl=30, show_spinner=False)
def _gh_read_json(path: str, _v: int = 0):
    """Read a JSON file from the appdata branch. _v busts the cache after writes."""
    token, repo, branch = _gh_cfg()
    if not token:
        return None
    r = _rq.get(f"https://api.github.com/repos/{repo}/contents/{path}",
                params={"ref": branch}, headers=_gh_headers(token), timeout=15)
    if r.status_code != 200:
        return None
    return json.loads(base64.b64decode(r.json()["content"]))


def gh_read(path: str):
    return _gh_read_json(path, st.session_state.get("gh_v", 0))


def gh_write(path: str, obj: dict, message: str) -> bool:
    token, repo, branch = _gh_cfg()
    if not token:
        st.error("Storage isn't configured — the site owner must add the [github] section to Streamlit secrets.")
        return False
    _gh_ensure_branch(token, repo, branch)
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = _rq.get(url, params={"ref": branch}, headers=_gh_headers(token), timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {
        "message": message, "branch": branch,
        "content": base64.b64encode(json.dumps(obj, indent=2).encode()).decode(),
    }
    if sha:
        payload["sha"] = sha
    r = _rq.put(url, headers=_gh_headers(token), json=payload, timeout=20)
    ok = r.status_code in (200, 201)
    if ok:
        st.session_state["gh_v"] = st.session_state.get("gh_v", 0) + 1
    else:
        st.error(f"Save failed (HTTP {r.status_code}). Check the GitHub token's Contents permission.")
    return ok


# ── Accounts & authentication ─────────────────────────────────────────────────

def _hash_pw(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode()).hexdigest()


def load_accounts() -> dict:
    return gh_read(ACCOUNTS_PATH) or {"professors": {}, "students": {}}


def add_account(role_key: str, username: str, pw: str, created_by: str,
                professor: str | None = None) -> bool:
    acc = load_accounts()
    salt = _pysecrets.token_hex(8)
    entry = {
        "salt": salt, "hash": _hash_pw(pw, salt),
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if role_key == "students" and professor:
        entry["professor"] = professor
    acc.setdefault(role_key, {})[username] = entry
    return gh_write(ACCOUNTS_PATH, acc, f"Add {role_key[:-1]} account: {username}")


def delete_account(role_key: str, username: str) -> bool:
    acc = load_accounts()
    if username in acc.get(role_key, {}):
        del acc[role_key][username]
        if role_key == "professors":
            # Cascade: remove that professor's students too
            acc["students"] = {u: i for u, i in acc.get("students", {}).items()
                               if i.get("professor") != username}
        return gh_write(ACCOUNTS_PATH, acc, f"Delete {role_key[:-1]} account: {username}")
    return False


def check_login(username: str, pw: str) -> str | None:
    """Returns 'admin' / 'professor' / 'student' or None."""
    try:
        a = st.secrets["auth"]
        if username == a["admin_username"] and pw == a["admin_password"]:
            return "admin"
    except Exception:
        pass
    # Two attempts: if the first misses, force a fresh read from GitHub in
    # case the cached accounts file predates a just-created account.
    for _ in range(2):
        acc = load_accounts()
        for role_key, role in (("professors", "professor"), ("students", "student")):
            u = acc.get(role_key, {}).get(username)
            if u and _hash_pw(pw, u["salt"]) == u["hash"]:
                return role
        st.session_state["gh_v"] = st.session_state.get("gh_v", 0) + 1
    return None


def current_role() -> str:
    if DEMO_MODE:
        return "professor"  # full edit UI, but nothing persists
    return st.session_state.get("auth", {}).get("role", "student")


# ── Class portfolios (one per professor; students see their professor's) ─────

def _pf_path(owner: str) -> str:
    return f"data/portfolios/{owner}.json"


def portfolio_owner() -> str | None:
    """Whose class portfolio the current user works with."""
    auth = st.session_state.get("auth")
    if not auth:
        return None
    if auth["role"] == "professor":
        return auth["username"]
    if auth["role"] == "student":
        return auth.get("professor")
    return st.session_state.get("admin_view_owner", auth["username"])  # admin


def get_portfolio(valid_tickers: list[str]) -> list[str]:
    if DEMO_MODE:
        valid = set(valid_tickers)
        return [t for t in st.session_state.get("demo_portfolio", DEMO_PORTFOLIO) if t in valid]
    owner = portfolio_owner()
    if not owner:
        return []
    data = gh_read(_pf_path(owner)) or {}
    valid = set(valid_tickers)
    return [t for t in data.get("tickers", []) if t in valid][:MAX_PORTFOLIO_SIZE]


def save_portfolio(tickers: list[str]) -> bool:
    if DEMO_MODE:
        st.session_state["demo_portfolio"] = list(dict.fromkeys(tickers))[:MAX_PORTFOLIO_SIZE]
        return True
    owner = portfolio_owner()
    if not owner:
        return False
    tickers = list(dict.fromkeys(tickers))[:MAX_PORTFOLIO_SIZE]
    user = st.session_state.get("auth", {}).get("username", "?")
    return gh_write(_pf_path(owner), {
        "tickers": tickers, "updated_by": user,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, f"Update class portfolio of {owner} ({user})")


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

    # Historical line (numeric years — string years break on plotly >= 6)
    hist_x = list(HIST_YEARS)
    hist_y = [v for v in hist]
    fig.add_trace(go.Scatter(
        x=hist_x, y=hist_y, name="Historical",
        line=dict(color=color, width=3),
        fill="tozeroy", fillcolor=rgba(color, 0.09),
        connectgaps=False, mode="lines+markers",
        marker=dict(size=6), hovertemplate="%{x}: %{y:,.1f}<extra></extra>",
    ))

    # Projection scenarios
    for sce in ["Bear", "Base", "Bull"]:
        proj = project_scenario(hist, sce, cagr_override)
        if not proj:
            continue
        # Bridge from last historical point
        last_hist_yr = next((y for y in reversed(HIST_YEARS) if hist[HIST_YEARS.index(y)] is not None), None)
        bridge_x = [last_hist_yr] if last_hist_yr else []
        bridge_y = [hist[HIST_YEARS.index(last_hist_yr)]] if last_hist_yr else []
        proj_x = bridge_x + list(PROJ_YEARS)
        proj_y = bridge_y + [proj.get(y) for y in PROJ_YEARS]
        dash = "solid" if sce == "Base" else "dot"
        fig.add_trace(go.Scatter(
            x=proj_x, y=proj_y, name=sce,
            line=dict(color=SCENARIO_COLOR[sce], width=1.8, dash=dash),
            mode="lines", connectgaps=True,
            hovertemplate=f"{sce} %{{x}}: %{{y:,.1f}}<extra></extra>",
        ))

    # Vertical divider at 2025/2026 boundary
    fig.add_vline(x=2025.5, line_dash="dash", line_color="rgba(148,163,184,.3)", line_width=1)
    fig.add_annotation(x=2025.5, y=1, yref="paper", text="Projection →",
                       showarrow=False, font=dict(size=10, color="#94a3b8"), xshift=40)

    fig.update_layout(
        title=dict(text=label, font=dict(size=15, color="#e2e8f0"), x=0.01, xanchor="left"),
        height=400,
        margin=dict(l=10, r=10, t=58, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,20,38,0.45)",
        font=dict(color="#9aa8bd", size=12),
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right", font=dict(size=11)),
        xaxis=dict(gridcolor="#26314e", tickfont=dict(size=12), showgrid=False,
                   tickformat="d", dtick=2),
        yaxis=dict(gridcolor="#26314e", tickfont=dict(size=12)),
        hovermode="x unified",
    )
    return fig


def make_price_chart(hist_df: pd.DataFrame, ticker: str, color: str) -> go.Figure:
    """Candlestick / close price chart."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df.index, y=hist_df["Close"],
        name="Close", line=dict(color=color, width=2.5),
        fill="tozeroy", fillcolor=rgba(color, 0.10),
        hovertemplate="%{x|%b %d, %Y}: $%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,20,38,0.45)",
        font=dict(color="#8b949e", size=12),
        xaxis=dict(gridcolor="#26314e", showgrid=False),
        yaxis=dict(gridcolor="#26314e", tickprefix="$"),
        hovermode="x unified",
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
        marker_color="rgba(52,211,153,0.85)", offsetgroup=1,
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
        title=dict(text="Revenue & Net Income Forecast 2026–2030", font=dict(size=14, color="#e2e8f0"), x=0.01, xanchor="left"),
        height=340,
        margin=dict(l=10, r=10, t=35, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,20,38,0.45)",
        font=dict(color="#8b949e", size=10),
        legend=dict(orientation="h", y=-0.22, font=dict(size=10)),
        xaxis=dict(gridcolor="#26314e", showgrid=False),
        yaxis=dict(gridcolor="#26314e"),
    )
    return fig


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_overview(df: pd.DataFrame) -> None:
    """Sector-level overview with summary stats."""
    st.title("S&P 500 Financial Analytics")
    st.caption("10-year historical financials · Bear / Base / Bull projections to 2030 · Live prices via Yahoo Finance")

    # Top-level stats
    latest = latest_per_ticker(df)
    latest_year = int(latest["year"].max()) if len(latest) else int(df["year"].max())
    total_tickers = df["ticker"].nunique()
    total_rev = latest["revenue_m"].sum() / 1_000  # → $B
    total_ni  = latest["net_income_m"].sum() / 1_000

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies", f"{total_tickers}")
    c2.metric("Latest Data Year", str(latest_year))
    c3.metric("Total Revenue (latest filings)", f"${total_rev:,.0f}B")
    c4.metric("Total Net Income (latest filings)", f"${total_ni:,.0f}B")

    st.divider()
    st.subheader("Sectors")

    sectors = sorted(df["sector"].unique())
    cols = st.columns(3)
    for idx, sector in enumerate(sectors):
        color = SECTOR_COLORS.get(sector, "#7f8c8d")
        sec_df = df[df["sector"] == sector]
        tickers = sorted(sec_df["ticker"].unique())
        sec_latest = latest[latest["sector"] == sector]
        rev_sum = sec_latest["revenue_m"].sum()
        ni_sum  = sec_latest["net_income_m"].sum()
        with cols[idx % 3]:
            st.markdown(f"""
            <div style="background:#0a101f;border:1px solid #26314e;border-left:4px solid {color};
                        border-radius:8px;padding:1.1rem 1.25rem;margin-bottom:0.75rem">
              <div style="font-size:1.1rem;font-weight:700;color:#e6edf3">{sector}</div>
              <div style="font-size:0.92rem;color:#aeb7c2;margin-top:0.3rem">
                {len(tickers)} companies &nbsp;·&nbsp;
                Rev: {fmt_m(rev_sum)} &nbsp;·&nbsp;
                NI: {fmt_m(ni_sum)}
              </div>
              <div style="margin-top:0.6rem;font-size:0.8rem;color:#6b7687">
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
    st.title("Stock Screener")

    latest = latest_per_ticker(df).copy()

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

    st.caption(f"Showing {len(filtered)} companies · each company's latest 10-K filing")

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

    sel_col, _ = st.columns([2, 3])
    with sel_col:
        ticker = st.selectbox(
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
        if current_role() in ("professor", "admin"):
            portfolio = get_portfolio(all_tickers)
            if ticker in portfolio:
                if st.button(f"In class portfolio — remove {ticker}", key="pf_remove"):
                    save_portfolio([t for t in portfolio if t != ticker])
                    st.rerun()
            elif len(portfolio) < MAX_PORTFOLIO_SIZE:
                if st.button(f"Add {ticker} to Class Portfolio", key="pf_add"):
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
            bg = rgba(color, 0.08) if has_data else "#0a101f"
            st.markdown(f"""
            <div style="background:{bg};border:1px solid #26314e;border-radius:4px;
                        padding:0.4rem 0.35rem;text-align:center;border-top:2px solid {color if has_data else '#26314e'}">
              <div style="font-size:0.72rem;font-weight:700;color:#e6edf3">{yr}</div>
              <div style="font-size:0.62rem;color:#8b949e;margin-top:0.15rem">R:{rev_val}</div>
              <div style="font-size:0.62rem;color:#8b949e">NI:{ni_val}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Financial metric charts ──
    st.markdown(f"**Financial Metrics 2015–{latest_year} + Projections 2026–2030**")
    st.caption("Bear (0.55× CAGR) · Base (1.0× CAGR) · Bull (1.45× CAGR)")

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

    latest = latest_per_ticker(df)
    if sel_sector != "All Sectors":
        choices = sorted(latest[latest["sector"] == sel_sector]["ticker"].unique())
    else:
        choices = sorted(latest["ticker"].unique())
    # Keep already-picked tickers selectable even when filtered out
    options = sorted(set(choices) | set(existing))

    picked = st.multiselect(
        "Choose your stocks",
        options,
        default=[t for t in existing if t in options],
        placeholder="Type a ticker, e.g. AAPL",
        key="pf_picker",
    )

    c1, c2 = st.columns([1, 1])
    if c1.button("Save Portfolio", type="primary", use_container_width=True):
        save_portfolio(picked)
        st.rerun()
    if existing and c2.button("Clear Portfolio", use_container_width=True):
        save_portfolio([])
        st.rerun()


def page_portfolio(df: pd.DataFrame) -> None:
    """Shared class portfolio: professor edits, students view."""
    all_tickers = get_all_tickers(df)
    portfolio = get_portfolio(all_tickers)
    can_edit = current_role() in ("professor", "admin")

    # ── No portfolio yet ──
    if not portfolio:
        if can_edit:
            st.title("Build Your Portfolio" if DEMO_MODE else "Build the Class Portfolio")
            st.markdown(
                "Pick the S&P 500 stocks for your class — as many as you like. "
                "Students will see exactly this portfolio when they log in."
            )
            _portfolio_builder(df, [])
        else:
            st.title("Portfolio" if DEMO_MODE else "Class Portfolio")
            st.info("Your professor hasn't added stocks yet — check back soon!")
        return

    # ── Dashboard ──
    st.title("Portfolio" if DEMO_MODE else "Class Portfolio")
    if DEMO_MODE:
        st.caption(f"{len(portfolio)} holdings · demo portfolio — add or remove stocks freely, nothing is saved")
    else:
        st.caption(
            f"{len(portfolio)} holdings · " +
            ("students see this portfolio when they log in" if can_edit else "managed by your professor")
        )

    pf_latest = latest_per_ticker(df[df["ticker"].isin(portfolio)])

    # Live prices — one batched request for the whole portfolio (cached 5 min)
    with st.spinner("Fetching live prices…"):
        quotes = fetch_live_prices_bulk(tuple(portfolio))
        if not quotes:  # bulk endpoint throttled — fall back to per-ticker quotes
            quotes = {t: fetch_live_price(t) for t in portfolio[:50]}

    # Summary metrics
    n_up = sum(1 for q in quotes.values() if q and q["change_pct"] >= 0)
    n_dn = sum(1 for q in quotes.values() if q and q["change_pct"] < 0)
    total_rev = pf_latest["revenue_m"].sum()
    total_ni = pf_latest["net_income_m"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Holdings", f"{len(portfolio)}")
    c2.metric("Up / Down Today", f"{n_up} / {n_dn}")
    c3.metric("Combined Revenue (latest filings)", fmt_m(total_rev))
    c4.metric("Combined Net Income (latest filings)", fmt_m(total_ni))

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
        st.caption("Open any holding in **Stock Detail** for 10-yr history & projections.")

    with pie_col:
        st.markdown("**Sector Mix**")
        if len(pf_latest):
            mix = pf_latest.groupby("sector")["ticker"].count().reset_index()
            mix.columns = ["sector", "count"]
            fig = px.pie(
                mix, names="sector", values="count",
                color="sector", color_discrete_map=SECTOR_COLORS, hole=0.62,
            )
            fig.update_traces(
                marker=dict(line=dict(color="#05070d", width=2)),
                textfont=dict(size=12, color="#f1f5f9"),
            )
            fig.add_annotation(
                text=(f"<b>{int(mix['count'].sum())}</b><br>"
                      "<span style='font-size:10px;color:#94a3b8'>holdings</span>"),
                showarrow=False, font=dict(size=22, color="#f1f5f9"),
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#9aa8bd", size=11),
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(font=dict(size=10)),
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
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
            font=dict(color="#8b949e", size=10),
            xaxis=dict(gridcolor="#26314e", showgrid=False),
            yaxis=dict(gridcolor="#26314e", tickprefix="$", ticksuffix="M"),
        )
        st.plotly_chart(fig, use_container_width=True)

    if can_edit:
        st.divider()
        with st.expander("Edit Class Portfolio", expanded=False):
            _portfolio_builder(df, portfolio)


def page_risk_analysis(df: pd.DataFrame) -> None:
    """Cross-sector risk and performance comparison."""
    st.title("Risk & Comparative Analysis")

    latest = latest_per_ticker(df).copy()
    latest_year = int(latest["year"].max()) if len(latest) else int(df["year"].max())

    tab1, tab2, tab3 = st.tabs(["Revenue by Sector", "Margin Analysis", "Debt & Coverage"])

    with tab1:
        sec_rev = latest.groupby("sector")["revenue_m"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(
            sec_rev, x="sector", y="revenue_m",
            color="sector", color_discrete_map=SECTOR_COLORS,
            title="Total Revenue by Sector (latest filings)",
            labels={"revenue_m": "Revenue ($M)", "sector": ""},
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
            font=dict(color="#8b949e"), showlegend=False,
            height=400, margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(tickangle=-30),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Revenue CAGR 2020→latest per sector
        st.subheader("Revenue Growth (2020 → latest)")
        yr_2020 = df[df["year"] == 2020].groupby("sector")["revenue_m"].sum()
        yr_latest = latest.groupby("sector")["revenue_m"].sum()
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
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
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
            title="Gross Margin % Distribution by Sector (latest filings)",
            labels={"gross_margin_pct": "Gross Margin %", "sector": ""},
        )
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
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
            title="D/E Ratio vs ROE % (latest filings)",
            labels={"debt_equity": "Debt / Equity", "roe_pct": "ROE %"},
        )
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
            font=dict(color="#8b949e"),
            height=450, margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig4, use_container_width=True)


# ── Login & account pages ─────────────────────────────────────────────────────

def page_login() -> None:
    # Center the sign-in at 40% width on desktop (full width on phones/tablets)
    st.markdown("""
    <style>
    @media (min-width: 992px) {
      [data-testid="stMainBlockContainer"], section.main > div.block-container {
        max-width: 50vw; margin-left: auto; margin-right: auto;
      }
    }
    </style>
    """, unsafe_allow_html=True)
    st.title("S&P 500 Analytics — Sign In")
    token, _, _ = _gh_cfg()
    if not token:
        st.warning(
            "Account storage isn't configured yet. The site owner must add "
            "the `[auth]` and `[github]` sections to Streamlit secrets "
            "(app menu → Settings → Secrets)."
        )

    tab_in, tab_reg = st.tabs(["Sign in", "Register as professor"])

    with tab_in:
        with st.form("login"):
            u = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                u = u.strip()
                role = check_login(u, pw)
                if role:
                    auth = {"username": u, "role": role}
                    if role == "student":
                        rec = load_accounts().get("students", {}).get(u, {})
                        auth["professor"] = rec.get("professor")
                    st.session_state["auth"] = auth
                    # Fresh data on login: re-read portfolio/accounts and live prices
                    st.session_state["gh_v"] = st.session_state.get("gh_v", 0) + 1
                    fetch_live_price.clear()
                    fetch_price_history.clear()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        st.caption("Students: ask your professor for your login.")

    with tab_reg:
        try:
            reg_code = st.secrets["auth"].get("professor_code")
        except Exception:
            reg_code = None
        if not reg_code:
            st.info("Professor self-registration is disabled — ask the site admin for an account.")
        else:
            st.markdown("Create your professor account. You'll need the **sign-up code** from the site admin.")
            try:
                hint = st.secrets["auth"].get("professor_code_hint")
            except Exception:
                hint = None
            if hint:
                st.info(hint)
            with st.form("register"):
                code = st.text_input("Sign-up code")
                u = st.text_input("Choose a username")
                pw = st.text_input("Choose a password", type="password")
                pw2 = st.text_input("Repeat password", type="password")
                if st.form_submit_button("Create my professor account", type="primary", use_container_width=True):
                    u = u.strip()
                    acc = load_accounts()
                    taken = set(acc.get("students", {})) | set(acc.get("professors", {}))
                    if code != reg_code:
                        st.error("Wrong sign-up code.")
                    elif not u or not pw:
                        st.warning("Enter a username and a password.")
                    elif pw != pw2:
                        st.warning("Passwords don't match.")
                    elif u in taken:
                        st.warning(f"'{u}' is already taken.")
                    elif add_account("professors", u, pw, "self-registered"):
                        st.success("Account created! Switch to the Sign in tab to log in.")


def _account_manager(role_key: str, role_label: str) -> None:
    """Shared add/delete UI for student or professor accounts."""
    me = st.session_state["auth"]["username"]
    role = current_role()
    acc = load_accounts()
    users = acc.get(role_key, {})
    professors = sorted(acc.get("professors", {}))

    # Professors only ever see their own students
    if role_key == "students" and role == "professor":
        users = {u: i for u, i in users.items() if i.get("professor") == me}

    st.subheader(f"Add a {role_label}")
    with st.form(f"add_{role_key}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        u = c1.text_input("Username")
        pw = c2.text_input("Password", type="password")
        owner = me
        if role_key == "students" and role == "admin" and professors:
            owner = st.selectbox("Assign to professor's class", professors + [me])
        if st.form_submit_button(f"Create {role_label} account", type="primary"):
            u = u.strip()
            taken = set(acc.get("students", {})) | set(acc.get("professors", {}))
            if not u or not pw:
                st.warning("Enter both a username and a password.")
            elif u in taken:
                st.warning(f"'{u}' already exists.")
            elif add_account(role_key, u, pw, me,
                             professor=owner if role_key == "students" else None):
                st.success(f"{role_label.title()} '{u}' created — share the username and password with them.")
                st.rerun()

    st.divider()
    st.subheader(f"Current {role_label}s ({len(users)})")
    if not users:
        st.caption(f"No {role_label} accounts yet.")
    for u, info in sorted(users.items()):
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.markdown(f"**{u}**")
        extra = f" · class of {info['professor']}" if info.get("professor") and role == "admin" else ""
        c2.caption(f"added by {info.get('created_by', '?')} · {str(info.get('created_at', ''))[:10]}{extra}")
        if c3.button("Delete", key=f"del_{role_key}_{u}"):
            st.session_state["pending_delete"] = (role_key, u)
            st.rerun()

    # ── Typed confirmation before any delete ──
    pending = st.session_state.get("pending_delete")
    if pending and pending[0] == role_key:
        _, name = pending
        st.divider()
        if role_key == "professors":
            st.warning(f"Deleting professor **{name}** also deletes ALL of their student accounts and their class portfolio access. This cannot be undone.")
        else:
            st.warning(f"You are about to permanently delete the {role_label} account **{name}**.")
        typed = st.text_input(f"Type the username ({name}) to confirm:", key="confirm_del_text")
        c1, c2 = st.columns(2)
        if c1.button("Yes, delete this account", type="primary", use_container_width=True):
            if typed.strip() == name:
                delete_account(role_key, name)
                st.session_state.pop("pending_delete", None)
                st.rerun()
            else:
                st.error("Username doesn't match — account was NOT deleted.")
        if c2.button("Cancel", use_container_width=True):
            st.session_state.pop("pending_delete", None)
            st.rerun()


def page_manage_students() -> None:
    st.title("Manage Student Accounts")
    st.caption("Students can sign in and view the class portfolio — they cannot edit it.")
    _account_manager("students", "student")


def page_manage_professors() -> None:
    st.title("Manage Professor Accounts")
    st.caption("Professors can edit the class portfolio and manage student accounts.")
    _account_manager("professors", "professor")


# ── Role-specific how-to ──────────────────────────────────────────────────────

def page_howto(role: str) -> None:
    st.title("How to Use This App")

    if DEMO_MODE:
        st.markdown("""
### Welcome to the public demo
This is a fully working copy of a classroom app where professors build a stock
portfolio and their students study it. Here, **you** play the professor: edit
the portfolio on **Portfolio** (or from any stock's detail page), and
every other page filters to your picks. Changes last for your browser session
only — refresh and it resets.

The production version adds logins: an admin creates professors, professors
manage their own class portfolio and student accounts, and students get
view-only access. Financial data is pulled automatically from SEC EDGAR 10-K
filings every 4 hours via a GitHub Actions pipeline; prices are live from
Yahoo Finance.
""")
        return

    common_view = """
**Class Portfolio** — the home page. Shows every stock in the portfolio with
live prices (refreshed every 5 minutes from Yahoo Finance), today's gainers and
losers, a sector mix chart, and the portfolio's combined 10-year revenue.

**Overview** — sector-by-sector summary of the portfolio companies, plus a
year-by-year recap of what happened in the market since 2015.

**Stock Screener** — a sortable table of the portfolio companies. Filter by
sector, search by ticker, and sort by revenue, net income, EPS, or P/E.

**Stock Detail** — pick any company to see its live price chart, 10 years of
financials, and Bear / Base / Bull projections to 2030. The growth-rate slider
lets you test "what if" scenarios — it only changes the charts on your screen.

**Risk Analysis** — compares the portfolio companies: revenue by sector,
margins, and debt-vs-return scatter.

Financial data comes from official SEC 10-K filings and updates automatically
twice a day — nobody needs to upload anything.
"""

    if role == "student":
        st.markdown(f"""
### Signing in
Your professor creates your username and password and gives them to you. If you
forget your password, ask your professor — they can delete your account and make
a new one.

### What you'll see
Everything in this app is filtered to **your class portfolio** — the set of
stocks your professor picked. You can look at every chart, table, and projection,
but only your professor can add or remove stocks.

### The pages
{common_view}
""")
    elif role == "professor":
        st.markdown(f"""
### Your role
You manage **your own class portfolio** and **your own student accounts** —
every professor has a separate class. Your students see exactly the portfolio
you build — view-only. Other professors can't see or change your class.

### Building the portfolio
On **Class Portfolio**, use the picker to choose any number of S&P 500
stocks, then hit **Save**. To change it later, open **Edit Class
Portfolio** at the bottom of that page. You can also add or remove a single
stock from its **Stock Detail** page.

### Exploring beyond the portfolio
The sidebar toggle **"Portfolio companies only"** is on by default. Turn it
off to browse all S&P 500 companies — useful when deciding what to add.

### Managing students
On **Manage Students**, create an account by typing a username and password,
then share those with the student. Students you create belong to your class
only. To delete an account you'll be asked to
re-type the username as confirmation — deletions are permanent.

### The pages
{common_view}
""")
    else:  # admin
        st.markdown(f"""
### Your role
You have full control: everything a professor can do, **plus** creating and
deleting professor accounts on **Manage Professors** (same typed-confirmation
rule as student deletions).

### Typical setup flow
1. Add `professor_code = "YOUR-CODE"` to the `[auth]` section of Streamlit
   secrets and share that code with professors — they register themselves on
   the login page. (You can also create them on **Manage Professors**.)
2. Each professor builds their own class portfolio and creates their student logins.
3. Students sign in and see their professor's portfolio, view-only.
4. The sidebar "Viewing class of" picker lets you inspect any professor's class.
5. Deleting a professor also deletes their students (typed confirmation required).

### How it all works under the hood
- **Accounts & portfolio** are stored as JSON on the `appdata` branch of your
  GitHub repo, written via the API token in Streamlit secrets. Saves there do
  **not** trigger a redeploy. Passwords are stored salted + hashed.
- **Financial data** (`data/sp500_financials.csv` on `main`) is refreshed by a
  GitHub Action every 12 hours from SEC EDGAR. You can run it manually from the
  repo's **Actions** tab → "Auto-update S&P 500 data" → Run workflow.
- **Admin login** comes from the `[auth]` section in Streamlit secrets — change
  it there anytime (app menu → Settings → Secrets).

### The pages
{common_view}
""")


# ── Company Report page ───────────────────────────────────────────────────────
# Text-first research note per company: profile, market snapshot, key metrics,
# strengths/weaknesses, risk (qualitative + quantitative), valuation, industry
# position, and recent news sentiment. Fundamentals come from the pipeline CSV;
# profile / market / news data come from Yahoo Finance (yfinance), cached.

@st.cache_data(ttl=86400, show_spinner=False)
def load_descriptions() -> dict:
    """Company description text keyed by ticker (repo JSON)."""
    for p in [Path("data/company_descriptions.json"), Path("sp500/descriptions.json")]:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


@st.cache_data(ttl=86400, show_spinner=False)
def load_company_names() -> dict:
    """Ticker → company name, from the SEC CIK map (works offline)."""
    p = Path("sp500/ticker_cik_map.json")
    if p.exists():
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            return {t: v.get("company", t) for t, v in m.items()}
        except Exception:
            pass
    return {}


@st.cache_data(ttl=3600, show_spinner=False, max_entries=300)
def fetch_company_profile(ticker: str) -> dict:
    """Slim slice of yfinance .info — profile, market and valuation fields."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    keys = [
        "longName", "shortName", "longBusinessSummary", "sector", "industry",
        "website", "fullTimeEmployees", "city", "state", "country",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "averageVolume", "beta",
        "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
        "pegRatio", "enterpriseToEbitda", "dividendYield", "marketCap",
        "ebitda", "totalDebt", "totalCash", "currentPrice", "debtToEquity",
        "returnOnEquity", "profitMargins", "revenueGrowth",
    ]
    prof = {k: info.get(k) for k in keys}
    # .info is often rate-limited on cloud hosts; fast_info usually still works
    try:
        fi = yf.Ticker(ticker).fast_info
        for pk, fk in (("fiftyTwoWeekHigh", "year_high"), ("fiftyTwoWeekLow", "year_low"),
                       ("averageVolume", "three_month_average_volume"),
                       ("marketCap", "market_cap"), ("currentPrice", "last_price")):
            if prof.get(pk) is None:
                v = getattr(fi, fk, None)
                if v:
                    prof[pk] = v
    except Exception:
        pass
    return prof


@st.cache_data(ttl=3600, show_spinner=False, max_entries=300)
def fetch_interest_coverage(ticker: str) -> pd.DataFrame | None:
    """Interest coverage (EBITDA / interest expense) per fiscal year.

    Pulled from the yfinance annual income statement (~4 years). Falls back to
    operating income when EBITDA is unavailable.
    """
    try:
        inc = yf.Ticker(ticker).income_stmt
        if inc is None or inc.empty:
            return None
        rows = {lbl: inc.loc[lbl] for lbl in
                ("EBITDA", "Interest Expense", "Operating Income") if lbl in inc.index}
        if "Interest Expense" not in rows:
            return None
        out = []
        for col in inc.columns:
            ie = rows["Interest Expense"].get(col)
            eb = rows.get("EBITDA", pd.Series(dtype=float)).get(col)
            oi = rows.get("Operating Income", pd.Series(dtype=float)).get(col)
            num = eb if (eb is not None and not pd.isna(eb)) else oi
            if ie is not None and not pd.isna(ie) and ie != 0 \
                    and num is not None and not pd.isna(num):
                out.append({
                    "year": int(getattr(col, "year", 0)) or int(str(col)[:4]),
                    "coverage": float(abs(num) / abs(ie)),
                    "basis": "EBITDA" if (eb is not None and not pd.isna(eb)) else "Op. income",
                })
        return pd.DataFrame(out).sort_values("year") if out else None
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False, max_entries=300)
def fetch_company_news(ticker: str) -> list[dict]:
    """Recent headlines via yfinance. Handles both old and new payload shapes."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items = []
    for n in raw[:10]:
        c = n.get("content", n) if isinstance(n, dict) else {}
        title = c.get("title")
        if not title:
            continue
        url = ""
        for k in ("canonicalUrl", "clickThroughUrl"):
            v = c.get(k)
            if isinstance(v, dict) and v.get("url"):
                url = v["url"]
                break
        url = url or n.get("link", "")
        prov = c.get("provider")
        source = prov.get("displayName", "") if isinstance(prov, dict) else n.get("publisher", "")
        pub = str(c.get("pubDate") or c.get("providerPublishTime") or "")[:10]
        items.append({"title": title, "url": url, "source": source,
                      "published": pub, "summary": (c.get("summary") or "")[:280]})
    return items


# Small lexicon for headline sentiment — deliberately simple and transparent.
_POS_WORDS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "record", "growth",
    "strong", "upgrade", "upgraded", "raise", "raises", "raised", "buy",
    "outperform", "profit", "gain", "gains", "rally", "rallies", "jump",
    "jumps", "boost", "boosts", "wins", "win", "expands", "expansion",
    "breakthrough", "dividend", "buyback", "tops", "exceed", "exceeds",
}
_NEG_WORDS = {
    "miss", "misses", "fall", "falls", "drop", "drops", "plunge", "plunges",
    "weak", "downgrade", "downgraded", "cut", "cuts", "sell", "underperform",
    "loss", "losses", "lawsuit", "probe", "investigation", "recall", "layoff",
    "layoffs", "warning", "warns", "decline", "declines", "slump", "slumps",
    "fine", "fined", "risk", "concern", "concerns", "tumble", "tumbles",
}


def score_headline(title: str) -> int:
    """Return +1 / 0 / -1 sentiment for a headline via lexicon match."""
    words = {w.strip(".,!?:;()'\"").lower() for w in title.split()}
    score = len(words & _POS_WORDS) - len(words & _NEG_WORDS)
    return 1 if score > 0 else (-1 if score < 0 else 0)


_SECTOR_RISK_NOTES = {
    "Information Technology": "Technology companies face rapid product cycles, intense competition for talent, and the constant risk of disruption — but tend to carry high margins and light balance sheets.",
    "Health Care": "Health care carries regulatory and patent-cliff risk (drug approvals, pricing reform), partially offset by demand that holds up in recessions.",
    "Financials": "Financials are sensitive to interest rates, credit cycles and regulation; leverage is inherent to the business model, so headline debt ratios read differently here.",
    "Consumer Discretionary": "Discretionary names are cyclical — revenue tracks consumer confidence and disposable income, so downturns hit harder than for staples.",
    "Consumer Staples": "Staples are defensive with steady demand, but face thin margins, private-label pressure and input-cost inflation.",
    "Energy": "Energy earnings swing with commodity prices largely outside management control; capital discipline and break-even costs are the key variables.",
    "Industrials": "Industrials are tied to capex cycles and global trade; backlog quality and margin execution matter more than headline growth.",
    "Materials": "Materials are price-takers on global commodities; costs, capacity discipline and currency drive results.",
    "Utilities": "Utilities offer regulated, stable cash flows but carry heavy debt loads by design and are sensitive to interest rates and rate-case outcomes.",
    "Real Estate": "REITs and real-estate names depend on occupancy, rates and refinancing conditions; distributions limit retained capital.",
    "Communication Services": "Communication services mixes high-growth platforms with mature telecoms; advertising cyclicality and content costs are the swing factors.",
}


def _sector_medians(df: pd.DataFrame, sector: str) -> dict:
    """Median latest-year metrics for a sector — the comparison baseline."""
    latest = latest_per_ticker(df)
    sec = latest[latest["sector"] == sector]
    if sec.empty:
        return {}
    out = {}
    for c in ("gross_margin_pct", "rev_growth_pct", "roe_pct", "debt_equity",
              "pe_ratio", "dividend_yield_pct"):
        if c in sec.columns:
            vals = sec[c]
            if c == "pe_ratio":       # negative P/E (loss-makers) breaks the median
                vals = vals[(vals > 0) & (vals < 200)]
            v = vals.median()
            out[c] = float(v) if not pd.isna(v) else None
    out["n"] = len(sec)
    return out


def _num(v):
    """None-safe float: returns None for NaN/None."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def analyze_strengths_weaknesses(tdf: pd.DataFrame, med: dict) -> tuple[list, list]:
    """Rule-based strengths / weaknesses from the company's own 10-K history
    compared against its sector's medians."""
    strengths, weaknesses = [], []
    rows = tdf[tdf["revenue_m"].notna()].sort_values("year")
    if rows.empty:
        return strengths, weaknesses
    last = rows.iloc[-1]

    gm = _num(last.get("gross_margin_pct"))
    med_gm = med.get("gross_margin_pct")
    if gm is not None and med_gm:
        if gm >= med_gm * 1.15:
            strengths.append(f"**High-margin business** — gross margin of {gm:.0f}% sits well above the sector median of {med_gm:.0f}%, giving pricing power and room to absorb cost shocks.")
        elif gm <= med_gm * 0.75:
            weaknesses.append(f"**Below-average margins** — gross margin of {gm:.0f}% trails the sector median of {med_gm:.0f}%, leaving less cushion when costs rise.")

    rg_rows = rows[rows["rev_growth_pct"].notna()].tail(3)
    if len(rg_rows):
        avg_g = float(rg_rows["rev_growth_pct"].mean())
        if avg_g >= 10:
            strengths.append(f"**Strong top-line growth** — revenue has grown ~{avg_g:.0f}% a year on average over the last {len(rg_rows)} reported years.")
        elif avg_g < -0.5:
            weaknesses.append(f"**Shrinking revenue** — sales have declined ~{abs(avg_g):.1f}% a year on average over the last {len(rg_rows)} reported years.")
        elif avg_g < 1.5:
            weaknesses.append(f"**Stagnant revenue** — sales have been roughly flat ({avg_g:+.1f}% a year on average) over the last {len(rg_rows)} reported years.")

    fcf = _num(last.get("free_cash_flow_m"))
    rev = _num(last.get("revenue_m"))
    if fcf is not None and rev:
        conv = fcf / rev * 100
        if conv >= 15:
            strengths.append(f"**Cash generative** — free cash flow is ~{conv:.0f}% of revenue ({fmt_m(fcf)}), funding dividends, buybacks or reinvestment without borrowing.")
        elif fcf < 0:
            weaknesses.append(f"**Burning cash** — free cash flow was negative ({fmt_m(fcf)}) in the latest year, so operations plus capex consume more than they produce.")

    roe = _num(last.get("roe_pct"))
    if roe is not None:
        if roe >= 60:
            strengths.append(f"**High returns on equity** — ROE of {roe:.0f}% is exceptional, though partly a product of buybacks shrinking the equity base (see weaknesses).")
        elif roe >= 20:
            strengths.append(f"**High returns on equity** — ROE of {roe:.0f}% means shareholder capital is being put to work efficiently.")
        elif roe < 5:
            weaknesses.append(f"**Weak returns on equity** — ROE of {roe:.0f}% suggests capital is earning little for shareholders.")

    de = _num(last.get("debt_equity"))
    med_de = med.get("debt_equity")
    if de is not None:
        if de <= 0.5:
            strengths.append(f"**Conservative balance sheet** — debt/equity of {de:.2f} is low, leaving borrowing capacity for downturns or acquisitions.")
        elif med_de and de >= max(2.0, med_de * 1.75):
            weaknesses.append(f"**Heavy leverage** — debt/equity of {de:.2f} is well above the sector median of {med_de:.2f}; refinancing and interest costs are a real exposure.")

    ni_rows = rows[rows["net_income_m"].notna()]
    if len(ni_rows) >= 3 and (ni_rows["net_income_m"] < 0).any():
        n_loss = int((ni_rows["net_income_m"] < 0).sum())
        weaknesses.append(f"**Inconsistent profitability** — {n_loss} loss-making year(s) in the reported history.")
    elif len(ni_rows) >= 5 and (ni_rows["net_income_m"] > 0).all():
        strengths.append(f"**Consistent profitability** — positive net income in every one of the last {len(ni_rows)} reported years.")

    dy = _num(last.get("dividend_yield_pct"))
    if dy is not None and dy >= 2.5:
        strengths.append(f"**Meaningful dividend** — a {dy:.1f}% yield returns cash to shareholders while they wait.")

    # ── Soft "watch items" — every company has something worth monitoring ──
    if len(weaknesses) < 2:
        watch = []
        if roe is not None and roe >= 60:
            watch.append("**Thin equity base** — years of buybacks have shrunk stockholders' equity, which flatters ROE but leaves less book-value cushion in a downturn.")
        else:
            eq_rows = rows[rows["stockholders_equity_m"].notna()] if "stockholders_equity_m" in rows.columns else rows.iloc[0:0]
            if len(eq_rows) >= 4:
                eq_then, eq_now = float(eq_rows.iloc[-4]["stockholders_equity_m"]), float(eq_rows.iloc[-1]["stockholders_equity_m"])
                if eq_then > 0 and eq_now < eq_then * 0.7:
                    watch.append(f"**Shrinking equity base** — stockholders' equity has fallen from {fmt_m(eq_then)} to {fmt_m(eq_now)} over three years, reducing the balance-sheet cushion.")
        rg_all = rows[rows["rev_growth_pct"].notna()]
        if len(rg_all) >= 4:
            recent = float(rg_all.iloc[-1]["rev_growth_pct"])
            prior = float(rg_all.iloc[-4:-1]["rev_growth_pct"].mean())
            if recent < prior - 3:
                watch.append(f"**Slowing growth** — revenue grew {recent:.1f}% last year vs. a {prior:.1f}% average over the prior three years, so momentum is fading.")
        gm_all = rows[rows["gross_margin_pct"].notna()]
        if len(gm_all) >= 4:
            gm_now, gm_then = float(gm_all.iloc[-1]["gross_margin_pct"]), float(gm_all.iloc[-4]["gross_margin_pct"])
            if gm_now < gm_then - 2:
                watch.append(f"**Margin compression** — gross margin has slipped from {gm_then:.0f}% to {gm_now:.0f}% over three years.")
        if "total_debt_m" in rows.columns:
            db_rows = rows[rows["total_debt_m"].notna()]
            if len(db_rows) >= 4:
                d_then, d_now = float(db_rows.iloc[-4]["total_debt_m"]), float(db_rows.iloc[-1]["total_debt_m"])
                if d_then > 0 and d_now > d_then * 1.4:
                    watch.append(f"**Rising debt load** — total debt has grown from {fmt_m(d_then)} to {fmt_m(d_now)} in three years.")
        if rev is not None and rev >= 150_000:
            watch.append(f"**Law of large numbers** — at {fmt_m(rev)} of revenue, each new % of growth is enormous in absolute terms; sustaining historical growth rates only gets harder from here.")
        med_g = med.get("rev_growth_pct")
        rg_last = _num(last.get("rev_growth_pct"))
        if not watch and rg_last is not None and med_g is not None and rg_last < med_g:
            watch.append(f"**Growth trails the sector** — {rg_last:.1f}% revenue growth vs. a {med_g:.1f}% sector median.")
        weaknesses.extend(watch[:max(0, 3 - len(weaknesses))])
    if not weaknesses:
        weaknesses.append("**Expectations risk** — nothing in the reported numbers stands out as weak, which is itself a risk: strong execution is already priced in, so any stumble tends to be punished hard by the market.")

    return strengths, weaknesses


def page_company_report(df: pd.DataFrame) -> None:
    """Text-first company research note — meant to be read, not just scanned."""
    all_tickers = get_all_tickers(df)
    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = "AAPL"

    sel_col, _ = st.columns([2, 3])
    with sel_col:
        ticker = st.selectbox(
            "Select Company", all_tickers,
            index=all_tickers.index(st.session_state.selected_ticker)
            if st.session_state.selected_ticker in all_tickers else 0,
            key="report_ticker_selector",
        )
    st.session_state.selected_ticker = ticker

    tdf = get_ticker_df(df, ticker)
    if tdf.empty:
        st.warning(f"No data found for {ticker}.")
        return

    sector = tdf["sector"].iloc[0] if "sector" in tdf.columns else "Other"
    color = SECTOR_COLORS.get(sector, "#3d7fe6")
    rows = tdf[tdf["revenue_m"].notna()].sort_values("year")
    last = rows.iloc[-1] if len(rows) else tdf.iloc[-1]
    latest_year = int(last["year"])

    with st.spinner("Loading company profile…"):
        prof = fetch_company_profile(ticker)
        quote = fetch_live_price(ticker)
    name = (prof.get("longName") or prof.get("shortName")
            or load_company_names().get(ticker) or ticker)
    med = _sector_medians(df, sector)

    # ── Header ──
    hdr, pxc = st.columns([3, 1])
    with hdr:
        st.markdown(f"""
        <div style="border-left:4px solid {color};padding-left:0.75rem;margin-bottom:0.5rem">
          <div style="font-size:1.6rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em">{name}{f' <span style="color:#8b949e;font-weight:500">({ticker})</span>' if name != ticker else ''}</div>
          <div style="font-size:0.8rem;color:#8b949e;margin-top:0.15rem">{sector}{' · ' + prof['industry'] if prof.get('industry') else ''}</div>
        </div>""", unsafe_allow_html=True)
    with pxc:
        if quote:
            cc = "green" if quote["change_pct"] >= 0 else "red"
            sg = "+" if quote["change_pct"] >= 0 else ""
            st.markdown(f"""
            <div style="text-align:right">
              <div style="font-size:1.8rem;font-weight:700;color:#e6edf3">${quote['price']:.2f}</div>
              <div style="font-size:0.85rem;color:{cc}">{sg}{quote['change']:.2f} ({sg}{quote['change_pct']:.2f}%)</div>
              <div style="font-size:0.68rem;color:#4a5568;margin-top:0.2rem">Live · Yahoo Finance</div>
            </div>""", unsafe_allow_html=True)

    # ── What the company does ──
    st.subheader("What the company does")
    desc = load_descriptions().get(ticker, "")
    if desc:
        st.markdown(desc)
    yf_desc = prof.get("longBusinessSummary")
    if yf_desc:
        with st.expander("Full business description (from the company profile)"):
            st.markdown(yf_desc)
            meta = []
            if prof.get("fullTimeEmployees"):
                meta.append(f"~{prof['fullTimeEmployees']:,} employees")
            loc = ", ".join(x for x in (prof.get("city"), prof.get("state"), prof.get("country")) if x)
            if loc:
                meta.append(f"HQ: {loc}")
            if prof.get("website"):
                meta.append(f"[{prof['website']}]({prof['website']})")
            if meta:
                st.caption(" · ".join(meta))
    if not desc and not yf_desc:
        st.info("No description available for this company yet.")

    # ── Market snapshot ──
    st.subheader("Market snapshot")
    lo, hi = _num(prof.get("fiftyTwoWeekLow")), _num(prof.get("fiftyTwoWeekHigh"))
    price = _num(prof.get("currentPrice")) or (quote["price"] if quote else None)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("52-week high", f"${hi:,.2f}" if hi else "—")
    c2.metric("52-week low", f"${lo:,.2f}" if lo else "—")
    av = prof.get("averageVolume")
    c3.metric("Avg volume (3mo)", f"{av/1e6:.1f}M" if av else "—")
    mc = prof.get("marketCap")
    c4.metric("Market cap", fmt_m(mc / 1e6) if mc else "—")
    beta = _num(prof.get("beta"))
    c5.metric("Beta", f"{beta:.2f}" if beta is not None else "—")
    if price and lo and hi and hi > lo:
        pos = max(0.0, min(1.0, (price - lo) / (hi - lo)))
        st.markdown(f"""
        <div style="margin:0.3rem 0 0.6rem">
          <div style="height:8px;border-radius:999px;background:linear-gradient(90deg,#fb7185,#fbbf24,#34d399);position:relative">
            <div style="position:absolute;left:{pos*100:.1f}%;top:-4px;width:3px;height:16px;background:#e6edf3;border-radius:2px"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#8b949e;margin-top:0.25rem">
            <span>${lo:,.2f}</span>
            <span>Currently {pos*100:.0f}% of the way up its 52-week range</span>
            <span>${hi:,.2f}</span>
          </div>
        </div>""", unsafe_allow_html=True)
        if beta is not None:
            vol_txt = ("more volatile than" if beta > 1.15 else
                       "about as volatile as" if beta >= 0.85 else "less volatile than")
            st.caption(f"A beta of {beta:.2f} means the stock has historically been {vol_txt} the overall market.")

    # ── Key financial metrics ──
    st.subheader(f"Key financial metrics (FY {latest_year})")
    rev, ni = _num(last.get("revenue_m")), _num(last.get("net_income_m"))
    eps, gm = _num(last.get("eps_diluted")), _num(last.get("gross_margin_pct"))
    fcf, roe = _num(last.get("free_cash_flow_m")), _num(last.get("roe_pct"))
    rg = _num(last.get("rev_growth_pct"))
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Revenue", fmt_m(rev), f"{rg:+.1f}% YoY" if rg is not None else None)
    k2.metric("Net income", fmt_m(ni))
    k3.metric("EPS (diluted)", f"${eps:.2f}" if eps is not None else "—")
    k4.metric("Gross margin", f"{gm:.1f}%" if gm is not None else "—")
    k5.metric("Free cash flow", fmt_m(fcf))
    k6.metric("ROE", f"{roe:.1f}%" if roe is not None else "—")
    if len(rows) >= 2:
        first = rows.iloc[0]
        span = latest_year - int(first["year"])
        bits = []
        if _num(first.get("revenue_m")) and rev:
            bits.append(f"revenue has gone from {fmt_m(float(first['revenue_m']))} to {fmt_m(rev)} ({pct_change(rev, float(first['revenue_m']))})")
        if _num(first.get("net_income_m")) is not None and ni is not None:
            bits.append(f"net income from {fmt_m(float(first['net_income_m']))} to {fmt_m(ni)}")
        if bits:
            st.markdown(f"Over the {span} years of reported history, {' and '.join(bits)}.")

    # ── Strengths & weaknesses ──
    st.subheader("Strengths & weaknesses")
    strengths, weaknesses = analyze_strengths_weaknesses(tdf, med)
    sc, wc = st.columns(2)
    with sc:
        st.markdown("##### Strengths")
        if strengths:
            for s in strengths:
                st.markdown(f"- {s}")
        else:
            st.caption("No standout strengths versus sector peers in the reported data.")
    with wc:
        st.markdown("##### Weaknesses")
        if weaknesses:
            for w in weaknesses:
                st.markdown(f"- {w}")
        else:
            st.caption("No major red flags versus sector peers in the reported data.")
    st.caption(f"Generated automatically from {ticker}'s 10-K history vs. {med.get('n', 0)} {sector} peers. Not investment advice.")

    # ── Risk analysis ──
    st.subheader("Risk analysis")
    de = _num(last.get("debt_equity"))
    med_de = med.get("debt_equity")
    risk_lines = []
    if de is not None:
        lvl = ("low" if de < 0.5 else "moderate" if de < 1.5 else "high")
        cmp_txt = ""
        if med_de:
            cmp_txt = f" (sector median: {med_de:.2f})"
        risk_lines.append(f"**Leverage** is {lvl}: debt/equity stands at {de:.2f}{cmp_txt}. " +
                          ("Low leverage means the company can ride out downturns and borrow opportunistically."
                           if de < 0.5 else
                           "This is manageable in normal conditions but worth watching if rates rise or earnings dip."
                           if de < 1.5 else
                           "High leverage magnifies both good and bad years — interest costs and refinancing terms matter a lot here."))
    cov_df = fetch_interest_coverage(ticker)
    if cov_df is not None and len(cov_df):
        cov = float(cov_df.iloc[-1]["coverage"])
        basis = cov_df.iloc[-1]["basis"]
        cov_lvl = ("very comfortable" if cov >= 10 else "adequate" if cov >= 4 else "thin")
        risk_lines.append(f"**Interest coverage** ({basis} ÷ interest expense) is {cov:.1f}× — {cov_lvl}. This measures how many times over annual earnings could pay the interest bill; below ~3× is where credit analysts start to worry.")
    if _num(last.get("free_cash_flow_m")) is not None and float(last["free_cash_flow_m"]) < 0:
        risk_lines.append("**Cash burn**: free cash flow was negative in the latest fiscal year, so the company must fund itself from reserves or new capital.")
    sec_note = _SECTOR_RISK_NOTES.get(sector)
    if sec_note:
        risk_lines.append(f"**Sector backdrop**: {sec_note}")
    for line in risk_lines:
        st.markdown(line)

    r1, r2 = st.columns(2)
    with r1:
        de_rows = tdf[tdf["debt_equity"].notna()].sort_values("year")
        if len(de_rows) >= 2:
            fig = go.Figure(go.Scatter(
                x=de_rows["year"].astype(int).tolist(), y=de_rows["debt_equity"].tolist(),
                mode="lines+markers", line=dict(color="#fb7185", width=3),
                fill="tozeroy", fillcolor=rgba("#fb7185", 0.09),
                hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
            fig.update_layout(title=dict(text="Debt / Equity over time", font=dict(size=14), x=0.01, xanchor="left"),
                              height=300, margin=dict(l=10, r=10, t=44, b=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
                              xaxis=dict(tickformat="d", dtick=2), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Not enough debt/equity history to chart.")
    with r2:
        if cov_df is not None and len(cov_df):
            colors = ["#34d399" if c >= 4 else "#fbbf24" if c >= 2 else "#fb7185"
                      for c in cov_df["coverage"]]
            fig = go.Figure(go.Bar(
                x=cov_df["year"].astype(int).tolist(), y=cov_df["coverage"].tolist(),
                marker_color=colors, hovertemplate="%{x}: %{y:.1f}×<extra></extra>"))
            fig.add_hline(y=3, line_dash="dot", line_color="rgba(148,163,184,.5)",
                          annotation_text="3× caution line", annotation_font_size=10)
            fig.update_layout(title=dict(text="Interest coverage (×)", font=dict(size=14), x=0.01, xanchor="left"),
                              height=300, margin=dict(l=10, r=10, t=44, b=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,20,38,0.45)",
                              xaxis=dict(tickformat="d", dtick=1), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Interest coverage unavailable (no interest expense reported — common for cash-rich companies).")

    # ── Valuation ──
    st.subheader("Valuation")
    tpe, fpe = _num(prof.get("trailingPE")), _num(prof.get("forwardPE"))
    pb = _num(prof.get("priceToBook"))
    ps = _num(prof.get("priceToSalesTrailing12Months"))
    ev_eb = _num(prof.get("enterpriseToEbitda"))
    dyv = _num(prof.get("dividendYield"))
    if dyv is not None and dyv < 1:      # yfinance sometimes returns 0.0065 vs 0.65
        dyv *= 100
    # Yahoo .info is often unavailable on cloud hosts — compute what we can
    # from latest 10-K fundamentals + live price / market cap instead
    mc_m = (mc / 1e6) if mc else None
    used_fallback = False
    if tpe is None and price and eps and eps > 0:
        tpe, used_fallback = price / eps, True
    if ps is None and mc_m and rev and rev > 0:
        ps, used_fallback = mc_m / rev, True
    eq_v = _num(last.get("stockholders_equity_m"))
    if pb is None and mc_m and eq_v and eq_v > 0:
        pb, used_fallback = mc_m / eq_v, True
    if dyv is None:
        dyv = _num(last.get("dividend_yield_pct"))
        used_fallback = used_fallback or dyv is not None
    v1, v2, v3, v4, v5, v6 = st.columns(6)
    v1.metric("P/E (trailing)", f"{tpe:.1f}×" if tpe else "—")
    v2.metric("P/E (forward)", f"{fpe:.1f}×" if fpe else "—")
    v3.metric("Price / Sales", f"{ps:.1f}×" if ps else "—")
    v4.metric("Price / Book", f"{pb:.1f}×" if pb else "—")
    v5.metric("EV / EBITDA", f"{ev_eb:.1f}×" if ev_eb else "—")
    v6.metric("Dividend yield", f"{dyv:.2f}%" if dyv is not None else "—")
    if used_fallback:
        st.caption("Some multiples computed from the latest 10-K fundamentals and live price.")
    med_pe = med.get("pe_ratio")
    if tpe and med_pe:
        rel = tpe / med_pe
        verdict = ("at a clear premium to" if rel >= 1.3 else
                   "roughly in line with" if rel >= 0.8 else "at a discount to")
        st.markdown(
            f"At {tpe:.1f}× trailing earnings, {ticker} trades {verdict} its sector "
            f"(median P/E: {med_pe:.1f}× across {med.get('n', 0)} {sector} companies). "
            + ("A premium multiple means the market expects above-average growth — the risk is disappointment. "
               if rel >= 1.3 else
               "A discount can signal a bargain or a business the market has doubts about — the rest of this report helps judge which. "
               if rel < 0.8 else
               "The market is pricing it much like a typical peer. ")
            + (f"The forward P/E of {fpe:.1f}× implies analysts expect earnings to "
               f"{'grow' if fpe < tpe else 'shrink'} next year." if fpe else ""))
    elif tpe:
        band = ("a premium multiple — the market is paying up for expected growth"
                if tpe >= 28 else
                "a moderate multiple, broadly in line with long-run market averages"
                if tpe >= 14 else
                "a low multiple — the market is pricing in slow growth or elevated risk")
        st.markdown(
            f"At {tpe:.1f}× trailing earnings, {ticker} trades at {band} "
            f"(the S&P 500 has historically averaged roughly 15–20×). "
            + (f"The forward P/E of {fpe:.1f}× implies analysts expect earnings to "
               f"{'grow' if fpe < tpe else 'shrink'} next year." if fpe else ""))

    # ── Industry & competitive position ──
    st.subheader("Industry & competitive position")
    latest_all = latest_per_ticker(df)
    sec_latest = latest_all[latest_all["sector"] == sector].copy()
    pos_lines = []
    if len(sec_latest) > 1 and rev:
        sec_rank = sec_latest.sort_values("revenue_m", ascending=False).reset_index(drop=True)
        rank_idx = sec_rank.index[sec_rank["ticker"] == ticker]
        if len(rank_idx):
            rank = int(rank_idx[0]) + 1
            n = len(sec_rank)
            share = rev / float(sec_rank["revenue_m"].sum()) * 100
            tier = ("one of the giants of" if rank <= max(3, n // 10) else
                    "a mid-sized player in" if rank <= n // 2 else
                    "a smaller player in")
            pos_lines.append(
                f"By revenue, {name} ranks **#{rank} of {n}** S&P 500 companies in {sector}, "
                f"making it {tier} its sector with roughly {share:.1f}% of the group's combined revenue.")
    gm_med = med.get("gross_margin_pct")
    if gm is not None and gm_med:
        if gm > gm_med * 1.1:
            pos_lines.append(f"Its gross margin ({gm:.0f}% vs. a {gm_med:.0f}% sector median) suggests real pricing power — a sign of differentiation, brand strength or scale advantages competitors can't easily copy.")
        elif gm < gm_med * 0.9:
            pos_lines.append(f"Its gross margin ({gm:.0f}% vs. a {gm_med:.0f}% sector median) points to a more commoditized position, competing more on price than differentiation.")
        else:
            pos_lines.append(f"Its gross margin ({gm:.0f}%) is close to the sector median ({gm_med:.0f}%), suggesting a competitive position typical of its peers.")
    if prof.get("industry"):
        pos_lines.append(f"Within {sector}, Yahoo Finance classifies it under **{prof['industry']}**.")
    for line in pos_lines:
        st.markdown(line)
    if not pos_lines:
        st.caption("Not enough sector data to assess competitive position.")

    # ── Recent news & sentiment ──
    st.subheader("Recent news & sentiment")
    news = fetch_company_news(ticker)
    if news:
        scores = [score_headline(n["title"]) for n in news]
        pos_n, neg_n = sum(1 for s in scores if s > 0), sum(1 for s in scores if s < 0)
        neu_n = len(scores) - pos_n - neg_n
        overall = ("leaning positive" if pos_n > neg_n else
                   "leaning negative" if neg_n > pos_n else "mixed / neutral")
        st.markdown(
            f"Across the {len(news)} most recent headlines, coverage is **{overall}** "
            f"({pos_n} positive · {neu_n} neutral · {neg_n} negative, scored by keyword analysis of titles).")
        badge = {1: ("Positive", "#34d399"), 0: ("Neutral", "#94a3b8"), -1: ("Negative", "#fb7185")}
        for n, s in zip(news[:8], scores):
            lbl, bc = badge[s]
            title_html = (f"<a href='{n['url']}' target='_blank' style='color:#c7d2e0;text-decoration:none'>{n['title']}</a>"
                          if n["url"] else n["title"])
            meta = " · ".join(x for x in (n["source"], n["published"]) if x)
            st.markdown(f"""
            <div style="padding:0.45rem 0;border-bottom:1px solid rgba(148,163,184,.1)">
              <span style="display:inline-block;min-width:64px;text-align:center;font-size:0.66rem;font-weight:700;
                     color:{bc};border:1px solid {rgba(bc, 0.4)};border-radius:999px;padding:0.1rem 0.5rem;margin-right:0.5rem">{lbl}</span>
              <span style="font-size:0.9rem">{title_html}</span>
              <div style="font-size:0.7rem;color:#64748b;margin-left:72px">{meta}</div>
            </div>""", unsafe_allow_html=True)
        st.caption("Headline sentiment is a simple keyword score — read the articles before drawing conclusions.")
    else:
        st.caption("No recent news available from Yahoo Finance for this ticker.")


# ── Sidebar navigation ────────────────────────────────────────────────────────
def main() -> None:
    setup_page()
    df = load_data()
    if df.empty:
        return

    # ── Login gate (skipped entirely in the public demo) ──
    if DEMO_MODE:
        st.session_state.setdefault("auth", {"username": "demo", "role": "professor"})
    auth = st.session_state.get("auth")
    if not auth:
        page_login()
        return
    role = auth["role"]

    st.sidebar.markdown("## S&P 500 Analytics")
    if DEMO_MODE:
        st.sidebar.caption("Public demo — explore freely! Portfolio edits last for your session only.")
        if st.sidebar.button("Refresh prices", use_container_width=True):
            fetch_live_price.clear()
            fetch_live_prices_bulk.clear()
            fetch_price_history.clear()
            st.rerun()
    else:
        st.sidebar.caption(f"Signed in as **{auth['username']}** · {role}")
        c1, c2 = st.sidebar.columns(2)
        if c1.button("Refresh", use_container_width=True, help="Re-fetch live prices and the latest portfolio"):
            st.session_state["gh_v"] = st.session_state.get("gh_v", 0) + 1
            fetch_live_price.clear()
            fetch_price_history.clear()
            st.rerun()
        if c2.button("Log out", use_container_width=True):
            st.session_state.pop("auth", None)
            st.rerun()
    st.sidebar.markdown("---")

    if role == "admin":
        profs = sorted(load_accounts().get("professors", {}))
        if profs:
            st.sidebar.selectbox(
                "Viewing class of",
                [auth["username"]] + profs,
                key="admin_view_owner",
                help="Choose which professor's class portfolio to view or edit.",
            )

    pages = {
        ("Portfolio" if DEMO_MODE else "Class Portfolio"):  "portfolio",
        "Overview":         "overview",
        "Stock Screener":   "screener",
        "Stock Detail":     "stock",
        "Company Report":   "report",
        "Risk Analysis":    "risk",
    }
    if role in ("professor", "admin") and not DEMO_MODE:
        pages["Manage Students"] = "students"
    if role == "admin" and not DEMO_MODE:
        pages["Manage Professors"] = "professors"
    pages["How to Use"] = "howto"

    page_label = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")
    page = pages[page_label]

    # ── Portfolio-wide filtering by role ──
    portfolio = get_portfolio(get_all_tickers(df))
    df_view = df
    if role == "student":
        # Students only ever see the class portfolio
        if portfolio:
            df_view = df[df["ticker"].isin(portfolio)]
        elif page not in ("howto", "portfolio"):
            st.title("Class Portfolio")
            st.info("Your professor hasn't added stocks yet — check back soon!")
            return
    elif portfolio:
        st.sidebar.markdown("---")
        pf_only = st.sidebar.toggle(
            "Portfolio companies only",
            value=True,
            key="pf_only_toggle",
            help="Filter pages to the class portfolio. Turn off to explore all companies and add new ones.",
        )
        if pf_only:
            df_view = df[df["ticker"].isin(portfolio)]
            st.sidebar.caption(f"Filtered to the {len(portfolio)} portfolio companies")
        else:
            st.sidebar.caption(f"Exploring all {df['ticker'].nunique()} companies")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Data: {df['ticker'].nunique()} tickers  {int(df['year'].max())} latest year")
    st.sidebar.caption("Prices via Yahoo Finance (yfinance)")
    st.sidebar.caption("Fundamentals: SEC EDGAR 10-K pipeline")

    if page == "portfolio":
        page_portfolio(df)          # builder needs the full universe
    elif page == "overview":
        page_overview(df_view)
    elif page == "screener":
        page_screener(df_view)
    elif page == "stock":
        page_stock_detail(df_view)
    elif page == "report":
        page_company_report(df_view)
    elif page == "risk":
        page_risk_analysis(df_view)
    elif page == "students":
        page_manage_students()
    elif page == "professors":
        page_manage_professors()
    elif page == "howto":
        page_howto(role)


if __name__ == "__main__":
    main()
