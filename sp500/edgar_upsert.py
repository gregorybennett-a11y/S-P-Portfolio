"""
edgar_upsert.py
---------------
Checks SEC EDGAR for new 10-K filings every 12 hours.
For any ticker whose filing date is newer than what's in pipeline_state.json,
it fetches the financial data and upserts into the active Parquet file.

SEC EDGAR API is free and requires no API key.
Fair-use rate limit: 10 requests/second (we stay well under this).
"""

import json
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
import pandas as pd

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "pipeline_state.json"
CIK_MAP_FILE = BASE_DIR / "ticker_cik_map.json"
LOG_FILE = BASE_DIR / "edgar_upsert.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

EDGAR_HEADERS = {"User-Agent": "SP500Pipeline contact@example.com"}
CALL_DELAY = 0.15  # 10 req/sec max → stay at ~6/sec to be safe

# ── EDGAR API helpers ──────────────────────────────────────────────────────────

def edgar_get(url: str) -> dict | list | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
            if r.status_code == 429:
                time.sleep(30)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"EDGAR request failed ({attempt+1}/3): {url} — {e}")
            time.sleep(5)
    return None


def get_latest_10k_filing(cik: str) -> dict | None:
    """
    Returns the most recent 10-K filing metadata for a CIK, or None.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = edgar_get(url)
    if not data:
        return None

    filings = data.get("filings", {}).get("recent", {})
    forms       = filings.get("form", [])
    dates       = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    accessions  = filings.get("accessionNumber", [])

    for form, filed_date, report_date, accession in zip(forms, dates, report_dates, accessions):
        if form == "10-K":
            # fiscal_year = year the fiscal period ended, NOT the filing date year
            # e.g. filed 2026-02-20 for period ending 2025-12-31 → FY2025
            fiscal_year = int(report_date[:4]) if report_date else int(filed_date[:4])
            return {"filed_date": filed_date, "report_date": report_date, "fiscal_year": fiscal_year, "accession": accession}
    return None


def get_company_facts(cik: str) -> dict | None:
    """
    Pulls all XBRL facts for a company — this is the structured financial data.
    Returns the us-gaap facts dict or None.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    data = edgar_get(url)
    if not data:
        return None
    return data.get("facts", {}).get("us-gaap", {})


def extract_annual_value(facts: dict, concept: str, year: int) -> float | None:
    """
    From the us-gaap facts dict, find the annual (10-K) value for a given
    concept and fiscal year. Returns the value in dollars (not millions yet).
    """
    concept_data = facts.get(concept, {})
    units = concept_data.get("units", {})

    # Try USD first, then shares for EPS
    for unit_key in ["USD", "USD/shares", "shares"]:
        entries = units.get(unit_key, [])
        for entry in reversed(entries):  # most recent first
            if (
                entry.get("form") == "10-K"
                and entry.get("fp") == "FY"
                and str(entry.get("fy", "")) == str(year)
            ):
                return entry.get("val")
    return None


def to_millions(val: float | None) -> float | None:
    if val is None:
        return None
    return round(val / 1_000_000, 2)


def fetch_ticker_financials(ticker: str, cik: str, year: int) -> dict | None:
    """
    Pull all available annual financials from EDGAR for a given ticker + year.
    Returns a dict matching the Parquet schema, or None on failure.
    """
    facts = get_company_facts(cik)
    if not facts:
        return None
    time.sleep(CALL_DELAY)

    # Concept mappings: Parquet column → list of EDGAR concepts to try (in order)
    concept_map = {
        "revenue_m": [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        ],
        "gross_profit_m": ["GrossProfit"],
        "operating_income_m": ["OperatingIncomeLoss"],
        "net_income_m": [
            "NetIncomeLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ],
        "eps_diluted": ["EarningsPerShareDiluted"],
        "operating_cf_m": ["NetCashProvidedByUsedInOperatingActivities"],
        "capex_m": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpendituresIncurredButNotYetPaid",
        ],
        "total_debt_m": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
        "stockholders_equity_m": ["StockholdersEquity"],
    }

    row = {"ticker": ticker, "year": year}
    found_any = False

    for col, concepts in concept_map.items():
        for concept in concepts:
            val = extract_annual_value(facts, concept, year)
            if val is not None:
                # EPS stays as-is; everything else convert to millions
                if col == "eps_diluted":
                    row[col] = round(val, 4)
                else:
                    row[col] = to_millions(val)
                found_any = True
                break

    # Derived metrics (if we have the raw data)
    rev = row.get("revenue_m")
    gp = row.get("gross_profit_m")
    oi = row.get("operating_income_m")
    eq = row.get("stockholders_equity_m")
    ni = row.get("net_income_m")
    debt = row.get("total_debt_m")

    if rev and gp:
        row["gross_margin_pct"] = round(gp / rev * 100, 4)
    if eq and ni:
        row["roe_pct"] = round(ni / eq * 100, 4)
    if eq and debt is not None:
        row["debt_equity"] = round(debt / eq, 4) if eq != 0 else None

    # Free cash flow = operating CF - capex
    ocf = row.get("operating_cf_m")
    capex = row.get("capex_m")
    if ocf is not None and capex is not None:
        row["free_cash_flow_m"] = round(ocf - capex, 2)

    return row if found_any else None


# ── Last-seen filing tracker ───────────────────────────────────────────────────

def load_seen_filings(state: dict) -> dict:
    """Track the last filing date we processed per ticker, stored in pipeline_state."""
    return state.get("seen_filings", {})

def save_seen_filings(state: dict, seen: dict):
    state["seen_filings"] = seen
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Main ───────────────────────────────────────────────────────────────────────

def run_edgar_upsert():
    if not STATE_FILE.exists():
        log.error("pipeline_state.json not found. Run: python pipeline.py init")
        return
    if not CIK_MAP_FILE.exists():
        log.error("ticker_cik_map.json not found.")
        return

    state = json.loads(STATE_FILE.read_text())
    cik_map = json.loads(CIK_MAP_FILE.read_text())
    active_file = BASE_DIR / state["active_file"]

    seen = load_seen_filings(state)
    tickers = list(cik_map.keys())

    log.info(f"Checking {len(tickers)} tickers for new 10-K filings ...")
    new_rows = []
    updated = []
    skipped = 0

    for i, ticker in enumerate(tickers, 1):
        info = cik_map[ticker]
        cik = info["cik"]

        filing = get_latest_10k_filing(cik)
        time.sleep(CALL_DELAY)

        if not filing:
            skipped += 1
            continue

        filed_date = filing["filed_date"]
        last_seen = seen.get(ticker, "2000-01-01")

        if filed_date <= last_seen:
            skipped += 1
            continue

        # New filing found — use fiscal_year (period end year), not filing date year
        year = filing["fiscal_year"]
        log.info(f"  [{i}/{len(tickers)}] {ticker}: new 10-K filed {filed_date} (FY{year})")

        row = fetch_ticker_financials(ticker, cik, year)
        if row:
            new_rows.append(row)
            seen[ticker] = filed_date
            updated.append(ticker)
        else:
            log.warning(f"  {ticker}: filing found but could not extract financials")

        if i % 50 == 0:
            log.info(f"  Progress: {i}/{len(tickers)} | New filings: {len(new_rows)} | Skipped: {skipped}")

    log.info(f"Done scanning. New filings: {len(new_rows)}, Skipped (up to date): {skipped}")

    if not new_rows:
        log.info("No new 10-K data to upsert.")
        save_seen_filings(state, seen)
        return

    # Upsert into active CSV
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from pipeline import upsert_into_csv

    new_df = pd.DataFrame(new_rows)
    total = upsert_into_csv(active_file, new_df)
    save_seen_filings(state, seen)

    log.info(f"Upserted {len(new_df)} rows into {active_file.name} ({total:,} total rows)")
    log.info(f"Updated tickers: {', '.join(updated)}")


if __name__ == "__main__":
    run_edgar_upsert()
