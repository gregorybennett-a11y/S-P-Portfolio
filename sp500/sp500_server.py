"""
S&P 500 Live Data Server
========================
Run this once — it stays running in the background, serving fresh data
to the portfolio app and re-running the collector on a schedule.

USAGE:
    python sp500_server.py

    Then open portfolio_app_v4.html in Chrome. The app will automatically
    pull live data from this server instead of its embedded snapshot.

    Also open data_monitor.html to watch update progress.

ENDPOINTS (http://localhost:8765):
    GET  /data     — full S&P 500 JSON for the portfolio app
    GET  /status   — server status, last run, next run, log tail
    POST /update   — trigger an immediate update now
    GET  /ping     — health check

SCHEDULE:
    Runs the collector automatically every UPDATE_HOURS hours (default: 24).
    Only re-fetches companies with likely new 10-K filings — typically 5-10 min.
    First run after install fetches everything (~90-120 min, done once).
"""

import json
import os
import sys
import time
import threading
import subprocess
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Configuration ─────────────────────────────────────────────────────────────
PORT           = 8765
UPDATE_HOURS   = 24          # how often to auto-run the collector
DATA_FILE      = os.path.join(os.path.dirname(__file__), "sp500_financials.json")
DESC_FILE      = os.path.join(os.path.dirname(__file__), "descriptions.json")
DIST_DIR       = os.path.join(os.path.dirname(__file__), "dist")
COLLECTOR      = os.path.join(os.path.dirname(__file__), "sp500_financial_data_collector.py")
LOG_FILE       = os.path.join(os.path.dirname(__file__), "server_log.txt")
MAX_LOG_LINES  = 500         # keep last N log lines in memory

# ── Shared state ──────────────────────────────────────────────────────────────
state = {
    "started":        datetime.now().isoformat(),
    "last_update":    None,
    "next_update":    None,
    "update_running": False,
    "update_count":   0,
    "companies":      0,
    "log":            [],        # list of {ts, msg} dicts (last MAX_LOG_LINES)
    "data_loaded":    False,
}
state_lock = threading.Lock()
cached_data          = None   # parsed JSON, rebuilt after each collector run
cached_pipeline_data = None   # parsed active CSV, rebuilt on startup and rotation
data_lock   = threading.RLock()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("sp500_server")

def log_entry(msg):
    log.info(msg)
    entry = {"ts": datetime.now().strftime("%H:%M:%S"), "msg": msg}
    with state_lock:
        state["log"].append(entry)
        if len(state["log"]) > MAX_LOG_LINES:
            state["log"] = state["log"][-MAX_LOG_LINES:]

# ── Data loading ──────────────────────────────────────────────────────────────
HIST_YEARS = [str(y) for y in range(2015, 2026)]

SP500_SECTOR = {
  'AAPL':'Information Technology','MSFT':'Information Technology','NVDA':'Information Technology',
  'AVGO':'Information Technology','ADBE':'Information Technology','CRM':'Information Technology',
  'CSCO':'Information Technology','ACN':'Information Technology','ORCL':'Information Technology',
  'INTC':'Information Technology','INTU':'Information Technology','AMD':'Information Technology',
  'TXN':'Information Technology','QCOM':'Information Technology','AMAT':'Information Technology',
  'LRCX':'Information Technology','KLAC':'Information Technology','MU':'Information Technology',
  'NOW':'Information Technology','ADSK':'Information Technology','CDNS':'Information Technology',
  'SNPS':'Information Technology','HPQ':'Information Technology','HPE':'Information Technology',
  'DELL':'Information Technology','PANW':'Information Technology','FTNT':'Information Technology',
  'CRWD':'Information Technology','IBM':'Information Technology','MSI':'Information Technology',
  'GOOGL':'Communication Services','META':'Communication Services','NFLX':'Communication Services',
  'DIS':'Communication Services','CMCSA':'Communication Services','T':'Communication Services',
  'VZ':'Communication Services','CHTR':'Communication Services','TMUS':'Communication Services',
  'EA':'Communication Services','TTWO':'Communication Services','LYV':'Communication Services',
  'AMZN':'Consumer Discretionary','TSLA':'Consumer Discretionary','HD':'Consumer Discretionary',
  'MCD':'Consumer Discretionary','TGT':'Consumer Discretionary','NKE':'Consumer Discretionary',
  'SBUX':'Consumer Discretionary','BKNG':'Consumer Discretionary','MAR':'Consumer Discretionary',
  'HLT':'Consumer Discretionary','GM':'Consumer Discretionary','F':'Consumer Discretionary',
  'AZO':'Consumer Discretionary','ROST':'Consumer Discretionary','TJX':'Consumer Discretionary',
  'DG':'Consumer Discretionary','CMG':'Consumer Discretionary','LOW':'Consumer Discretionary',
  'PG':'Consumer Staples','KO':'Consumer Staples','PEP':'Consumer Staples',
  'COST':'Consumer Staples','WMT':'Consumer Staples','MO':'Consumer Staples',
  'PM':'Consumer Staples','MDLZ':'Consumer Staples','CL':'Consumer Staples',
  'KMB':'Consumer Staples','GIS':'Consumer Staples','KR':'Consumer Staples',
  'XOM':'Energy','CVX':'Energy','COP':'Energy','EOG':'Energy','SLB':'Energy',
  'MPC':'Energy','PSX':'Energy','VLO':'Energy','OXY':'Energy','HAL':'Energy',
  'DVN':'Energy','WMB':'Energy','KMI':'Energy','OKE':'Energy','BKR':'Energy',
  'JPM':'Financials','BAC':'Financials','WFC':'Financials','GS':'Financials',
  'MS':'Financials','C':'Financials','USB':'Financials','PNC':'Financials',
  'TFC':'Financials','COF':'Financials','MET':'Financials','PRU':'Financials',
  'AIG':'Financials','ALL':'Financials','CB':'Financials','AFL':'Financials',
  'AMP':'Financials','SCHW':'Financials','PYPL':'Financials','AXP':'Financials',
  'ICE':'Financials','CME':'Financials','SPGI':'Financials','BLK':'Financials',
  'V':'Financials','MA':'Financials','KKR':'Financials','BX':'Financials',
  'JNJ':'Health Care','UNH':'Health Care','ABT':'Health Care','TMO':'Health Care',
  'MRK':'Health Care','LLY':'Health Care','ABBV':'Health Care','DHR':'Health Care',
  'SYK':'Health Care','ISRG':'Health Care','MDT':'Health Care','BSX':'Health Care',
  'EW':'Health Care','ZTS':'Health Care','GILD':'Health Care','REGN':'Health Care',
  'VRTX':'Health Care','BIIB':'Health Care','CI':'Health Care','CVS':'Health Care',
  'HUM':'Health Care','HCA':'Health Care','MCK':'Health Care','PFE':'Health Care',
  'MRNA':'Health Care','AMGN':'Health Care','ELV':'Health Care',
  'HON':'Industrials','CAT':'Industrials','DE':'Industrials','BA':'Industrials',
  'GE':'Industrials','RTX':'Industrials','LMT':'Industrials','UPS':'Industrials',
  'FDX':'Industrials','CSX':'Industrials','UNP':'Industrials','NSC':'Industrials',
  'EMR':'Industrials','ETN':'Industrials','ITW':'Industrials','PH':'Industrials',
  'ROK':'Industrials','AME':'Industrials','CARR':'Industrials','OTIS':'Industrials',
  'GWW':'Industrials','FAST':'Industrials','IR':'Industrials','ROP':'Industrials',
  'NOC':'Industrials','GD':'Industrials','LHX':'Industrials','WM':'Industrials',
  'NEM':'Materials','FCX':'Materials','DOW':'Materials','APD':'Materials',
  'ECL':'Materials','SHW':'Materials','NUE':'Materials','VMC':'Materials',
  'MLM':'Materials','LIN':'Materials','PPG':'Materials','LYB':'Materials',
  'AMT':'Real Estate','PLD':'Real Estate','EQIX':'Real Estate','CCI':'Real Estate',
  'PSA':'Real Estate','O':'Real Estate','WELL':'Real Estate','VTR':'Real Estate',
  'SPG':'Real Estate','EQR':'Real Estate','AVB':'Real Estate','DLR':'Real Estate',
  'NEE':'Utilities','SO':'Utilities','DUK':'Utilities','SRE':'Utilities',
  'AEP':'Utilities','EXC':'Utilities','D':'Utilities','XEL':'Utilities',
  'PCG':'Utilities','ED':'Utilities','ETR':'Utilities','PPL':'Utilities',
  'WEC':'Utilities','DTE':'Utilities','NRG':'Utilities','VST':'Utilities',
}

def find_active_csv():
    """Find the most recently modified active_*.csv in the dist/ folder."""
    import glob
    pattern = os.path.join(DIST_DIR, "active_*.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def load_pipeline_csv():
    """
    Read the active CSV from dist/ and convert to portfolio app DATA format.
    CSV columns: ticker, year, revenue_m, net_income_m, eps_diluted, etc.
    Returns a dict in the same shape as build_app_data() output.
    """
    import csv as csvlib
    csv_path = find_active_csv()
    if not csv_path:
        return {}
    try:
        rows = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csvlib.DictReader(f)
            rows = list(reader)

        # Group by ticker
        by_ticker = {}
        for row in rows:
            t = row.get("ticker", "").strip()
            if not t:
                continue
            by_ticker.setdefault(t, []).append(row)

        out = {}
        for ticker, ticker_rows in by_ticker.items():
            years_data = {}
            for row in ticker_rows:
                y = str(row.get("year", "")).strip()
                if not y or not y.isdigit():
                    continue
                def flt(k):
                    v = row.get(k, "")
                    try: return float(v) if v not in ("", "nan", "None") else None
                    except: return None
                mapped = {
                    "revenue":             flt("revenue_m"),
                    "gross_profit":        flt("gross_profit_m"),
                    "gross_margin":        flt("gross_margin_pct"),
                    "operating_income":    flt("operating_income_m"),
                    "net_income":          flt("net_income_m"),
                    "eps_diluted":         flt("eps_diluted"),
                    "operating_cashflow":  flt("operating_cf_m"),
                    "free_cashflow":       flt("free_cash_flow_m"),
                    "capex":               flt("capex_m"),
                    "long_term_debt":      flt("total_debt_m"),
                    "stockholders_equity": flt("stockholders_equity_m"),
                    "de_ratio":            flt("debt_equity"),
                    "roe_pct":             flt("roe_pct"),
                    "market_cap":          flt("market_cap_m"),
                    "pe_ratio":            flt("pe_ratio"),
                    "div_yield":           flt("dividend_yield_pct"),
                }
                if any(v is not None for v in mapped.values()):
                    years_data[y] = mapped
            if years_data:
                out[ticker] = {
                    "name":   ticker,  # CSV doesn't have names; app falls back to ticker
                    "sector": SP500_SECTOR.get(ticker, "Other"),
                    "ticker": ticker,
                    "data":   years_data,
                }
        log_entry(f"Pipeline CSV loaded: {len(out)} tickers from {os.path.basename(csv_path)}")
        return out
    except Exception as e:
        log_entry(f"ERROR loading pipeline CSV: {e}")
        return {}

def build_app_data(raw):
    """Transform raw sp500_financials.json into the portfolio app DATA format."""
    out = {}
    for ticker, info in raw.items():
        years_data = {}
        for y in HIST_YEARS:
            yd = info.get("years", {}).get(y, {})
            mapped = {
                "revenue":            yd.get("revenue"),
                "gross_profit":       yd.get("gross_profit"),
                "gross_margin":       yd.get("gross_margin_pct"),
                "operating_income":   yd.get("operating_income"),
                "net_income":         yd.get("net_income"),
                "eps_diluted":        yd.get("eps_diluted"),
                "operating_cashflow": yd.get("operating_cash_flow"),
                "free_cashflow":      yd.get("free_cash_flow"),
                "capex":              yd.get("capex"),
                "long_term_debt":     yd.get("long_term_debt"),
                "stockholders_equity":yd.get("stockholders_equity"),
                "de_ratio":           yd.get("de_ratio"),
                "roe_pct":            yd.get("roe_pct"),
                "market_cap":         yd.get("market_cap"),
                "pe_ratio":           yd.get("pe_ratio"),
                "div_yield":          yd.get("dividend_yield_pct"),
                "rev_growth_yoy":     yd.get("revenue_growth_yoy_pct"),
            }
            if any(v is not None for v in mapped.values()):
                years_data[y] = mapped
        if years_data:
            out[ticker] = {
                "name":   info.get("name", ticker),
                "sector": SP500_SECTOR.get(ticker, "Other"),
                "ticker": ticker,
                "data":   years_data,
            }
    return out

def load_pipeline_data():
    """Load active CSV → cached_pipeline_data (serves /pipeline-data for portfolio_app_v2.html)."""
    global cached_pipeline_data
    data = load_pipeline_csv()
    if data:
        with data_lock:
            cached_pipeline_data = data
        log_entry(f"Pipeline CSV cached: {len(data)} tickers")

def load_data():
    """Load sp500_financials.json → cached_data (serves /data for portfolio_app_v4.html)."""
    global cached_data
    if not os.path.exists(DATA_FILE):
        log_entry(f"Data file not found: {DATA_FILE}")
        return
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        app_data = build_app_data(raw)
        with data_lock:
            cached_data = app_data
        with state_lock:
            state["companies"] = len(app_data)
            state["data_loaded"] = True
        log_entry(f"Data loaded: {len(app_data)} companies")
    except Exception as e:
        log_entry(f"ERROR loading data: {e}")

# ── Collector runner ──────────────────────────────────────────────────────────
def run_collector():
    with state_lock:
        if state["update_running"]:
            log_entry("Update already running — skipped")
            return
        state["update_running"] = True
        state["update_count"] += 1

    log_entry("── Starting data collector ──────────────────────────")
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, COLLECTOR],
            cwd=os.path.dirname(COLLECTOR),
            capture_output=True,
            text=True,
            timeout=7200,   # 2-hour max
        )
        elapsed = int(time.time() - start)
        if result.returncode == 0:
            log_entry(f"Collector finished in {elapsed}s")
            load_data()
            with state_lock:
                state["last_update"] = datetime.now().isoformat()
        else:
            log_entry(f"Collector exited with code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-10:]:
                    log_entry(f"  ERR: {line}")
    except subprocess.TimeoutExpired:
        log_entry("ERROR: collector timed out after 2 hours")
    except Exception as e:
        log_entry(f"ERROR running collector: {e}")
    finally:
        with state_lock:
            state["update_running"] = False

def schedule_loop():
    """Run collector immediately on start (if needed), then every UPDATE_HOURS."""
    # Load existing data first so the server is useful right away
    load_data()
    load_pipeline_data()

    while True:
        next_dt = datetime.now().replace(microsecond=0)
        with state_lock:
            state["next_update"] = next_dt.isoformat()
        log_entry(f"Scheduled update starting now (next in {UPDATE_HOURS}h)")
        t = threading.Thread(target=run_collector, daemon=True)
        t.start()
        t.join()
        # Schedule next run
        sleep_secs = UPDATE_HOURS * 3600
        next_dt_str = datetime.fromtimestamp(time.time() + sleep_secs).strftime("%Y-%m-%d %H:%M")
        with state_lock:
            state["next_update"] = datetime.fromtimestamp(time.time() + sleep_secs).isoformat()
        log_entry(f"Next scheduled update: {next_dt_str}")
        time.sleep(sleep_secs)

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence default access log

    def send_cors(self, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_cors(204)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/ping":
            self.send_cors()
            self.wfile.write(b'{"ok":true}')

        elif path == "/data":
            with data_lock:
                data = cached_data
            if data is None:
                self.send_cors(503)
                self.wfile.write(json.dumps({"error": "Data not loaded yet"}).encode())
            else:
                self.send_cors()
                self.wfile.write(json.dumps(data, separators=(",", ":")).encode())

        elif path == "/pipeline-data":
            # Serves cached active CSV for portfolio_app_v2.html (data in $M)
            with data_lock:
                pdata = cached_pipeline_data
            if pdata:
                self.send_cors()
                self.wfile.write(json.dumps(pdata, separators=(",", ":")).encode())
            else:
                self.send_cors(503)
                self.wfile.write(b'{"error":"pipeline CSV not loaded yet"}')

        elif path == "/candles":
            # Proxy price history from Yahoo Finance — avoids browser CORS block
            # Usage: GET /candles?symbol=AAPL&range=1Y
            from urllib.parse import urlparse, parse_qs
            import urllib.request
            qs = parse_qs(urlparse(self.path).query)
            symbol = (qs.get("symbol", [""])[0] or "").upper().strip()
            rng    = qs.get("range", ["1Y"])[0]
            YF_MAP = {
                "1D":  ("1d",  "5m"),
                "1W":  ("5d",  "60m"),
                "1M":  ("1mo", "1d"),
                "6M":  ("6mo", "1d"),
                "YTD": ("ytd", "1d"),
                "1Y":  ("1y",  "1d"),
                "5Y":  ("5y",  "1wk"),
                "MAX": ("max", "1mo"),
            }
            yf_range, interval = YF_MAP.get(rng, ("1y", "1d"))
            if not symbol:
                self.send_cors(400)
                self.wfile.write(b'{"error":"symbol required"}')
            else:
                try:
                    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                           f"?range={yf_range}&interval={interval}&includePrePost=false")
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        raw = json.loads(resp.read())
                    result = raw.get("chart", {}).get("result", [None])[0]
                    if result and result.get("timestamp"):
                        q = result.get("indicators", {}).get("quote", [{}])[0]
                        payload = {
                            "t": result["timestamp"],
                            "c": q.get("close", []),
                            "o": q.get("open", []),
                            "h": q.get("high", []),
                            "l": q.get("low", []),
                            "v": q.get("volume", []),
                        }
                        self.send_cors()
                        self.wfile.write(json.dumps(payload, separators=(",", ":")).encode())
                    else:
                        self.send_cors(404)
                        self.wfile.write(b'{"error":"no data"}')
                except Exception as e:
                    self.send_cors(500)
                    self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif path == "/descriptions":
            try:
                with open(DESC_FILE, encoding="utf-8") as f:
                    desc_data = f.read()
                self.send_cors()
                self.wfile.write(desc_data.encode("utf-8"))
            except FileNotFoundError:
                self.send_cors(404)
                self.wfile.write(b'{"error":"descriptions.json not found"}')

        elif path == "/status":
            with state_lock:
                s = dict(state)
                s["log"] = s["log"][-50:]   # last 50 entries for the monitor
            self.send_cors()
            self.wfile.write(json.dumps(s).encode())

        else:
            self.send_cors(404)
            self.wfile.write(b'{"error":"not found"}')

    def do_POST(self):
        if self.path == "/update":
            with state_lock:
                already = state["update_running"]
            if already:
                self.send_cors(409)
                self.wfile.write(b'{"error":"update already running"}')
            else:
                threading.Thread(target=run_collector, daemon=True).start()
                self.send_cors()
                self.wfile.write(b'{"ok":true,"msg":"Update started"}')
        else:
            self.send_cors(404)
            self.wfile.write(b'{"error":"not found"}')

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  S&P 500 Data Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Auto-update every {UPDATE_HOURS} hours")
    print(f"  Data file: {DATA_FILE}")
    print("=" * 60)
    print()
    print("  Open portfolio_app_v4.html in Chrome to use live data.")
    print("  Open data_monitor.html to watch update progress.")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    # Start scheduler in background
    sched = threading.Thread(target=schedule_loop, daemon=True)
    sched.start()

    # Start HTTP server
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
