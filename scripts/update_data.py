"""
update_data.py — cloud auto-updater for data/sp500_financials.csv
==================================================================
Runs in GitHub Actions on a schedule (see .github/workflows/update-data.yml).

For each ticker in sp500/ticker_cik_map.json:
  1. Check SEC EDGAR for a 10-K filing newer than the last one we processed
     (tracked in data/update_state.json).
  2. If found, pull the annual financials via the EDGAR XBRL companyfacts API.
  3. Upsert into data/sp500_financials.csv on (ticker, year) — newest row wins.

The CSV schema is LOCKED (see CLAUDE.md) — this script writes the exact same
columns and never renames or drops any.

SEC EDGAR is free, no API key. Fair-use limit 10 req/sec; we stay well under.
"""

import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = REPO_ROOT / "data" / "sp500_financials.csv"
STATE_FILE = REPO_ROOT / "data" / "update_state.json"
CIK_MAP_FILE = REPO_ROOT / "sp500" / "ticker_cik_map.json"

# Locked schema — column order of data/sp500_financials.csv
CSV_COLUMNS = [
    "ticker", "sector", "year", "revenue_m", "rev_growth_pct",
    "gross_profit_m", "gross_margin_pct", "operating_income_m",
    "net_income_m", "eps_diluted", "operating_cf_m", "free_cash_flow_m",
    "capex_m", "total_debt_m", "stockholders_equity_m", "debt_equity",
    "roe_pct", "market_cap_m", "pe_ratio", "dividend_yield_pct",
]

EDGAR_HEADERS = {"User-Agent": "SP500Pipeline robblegregorybennett@gmail.com"}
CALL_DELAY = 0.15  # ~6 req/sec, under EDGAR's 10/sec limit

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── EDGAR helpers (same logic as sp500/edgar_upsert.py) ───────────────────────

def edgar_get(url: str):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=EDGAR_HEADERS, timeout=20)
            if r.status_code == 429:
                time.sleep(30)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"EDGAR request failed ({attempt + 1}/3): {url} — {e}")
            time.sleep(5)
    return None


def get_latest_10k_filing(cik: str) -> dict | None:
    data = edgar_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if not data:
        return None
    filings = data.get("filings", {}).get("recent", {})
    for form, filed_date, report_date in zip(
        filings.get("form", []), filings.get("filingDate", []), filings.get("reportDate", [])
    ):
        if form == "10-K":
            fiscal_year = int(report_date[:4]) if report_date else int(filed_date[:4])
            return {"filed_date": filed_date, "fiscal_year": fiscal_year}
    return None


def extract_annual_value(facts: dict, concept: str, year: int):
    units = facts.get(concept, {}).get("units", {})
    for unit_key in ["USD", "USD/shares", "shares"]:
        for entry in reversed(units.get(unit_key, [])):
            if (
                entry.get("form") == "10-K"
                and entry.get("fp") == "FY"
                and str(entry.get("fy", "")) == str(year)
            ):
                return entry.get("val")
    return None


def to_millions(val):
    return None if val is None else round(val / 1_000_000, 2)


CONCEPT_MAP = {
    "revenue_m": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit_m": ["GrossProfit"],
    "operating_income_m": ["OperatingIncomeLoss"],
    "net_income_m": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cf_m": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex_m": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CapitalExpendituresIncurredButNotYetPaid",
    ],
    "total_debt_m": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
    "stockholders_equity_m": ["StockholdersEquity"],
}


def fetch_ticker_financials(ticker: str, cik: str, year: int) -> dict | None:
    data = edgar_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    if not data:
        return None
    facts = data.get("facts", {}).get("us-gaap", {})
    time.sleep(CALL_DELAY)

    row = {"ticker": ticker, "year": year}
    found_any = False
    for col, concepts in CONCEPT_MAP.items():
        for concept in concepts:
            val = extract_annual_value(facts, concept, year)
            if val is not None:
                row[col] = round(val, 4) if col == "eps_diluted" else to_millions(val)
                found_any = True
                break

    rev, gp = row.get("revenue_m"), row.get("gross_profit_m")
    eq, ni, debt = row.get("stockholders_equity_m"), row.get("net_income_m"), row.get("total_debt_m")
    if rev and gp:
        row["gross_margin_pct"] = round(gp / rev * 100, 4)
    if eq and ni:
        row["roe_pct"] = round(ni / eq * 100, 4)
    if eq and debt is not None and eq != 0:
        row["debt_equity"] = round(debt / eq, 4)
    ocf, capex = row.get("operating_cf_m"), row.get("capex_m")
    if ocf is not None and capex is not None:
        row["free_cash_flow_m"] = round(ocf - capex, 2)

    return row if found_any else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main(limit: int | None = None) -> int:
    """Returns number of rows upserted."""
    cik_map = json.loads(CIK_MAP_FILE.read_text())
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    seen = state.get("seen_filings", {})

    df = pd.read_csv(DATA_CSV)
    sector_map = (
        df[["ticker", "sector"]].dropna().drop_duplicates("ticker")
        .set_index("ticker")["sector"].to_dict()
    )

    tickers = list(cik_map.keys())[:limit] if limit else list(cik_map.keys())
    log.info(f"Checking {len(tickers)} tickers for new 10-K filings ...")

    new_rows, updated = [], []
    for i, ticker in enumerate(tickers, 1):
        cik = cik_map[ticker]["cik"]
        filing = get_latest_10k_filing(cik)
        time.sleep(CALL_DELAY)
        if not filing:
            continue
        if filing["filed_date"] <= seen.get(ticker, "2000-01-01"):
            continue

        year = filing["fiscal_year"]
        log.info(f"  [{i}/{len(tickers)}] {ticker}: new 10-K filed {filing['filed_date']} (FY{year})")
        row = fetch_ticker_financials(ticker, cik, year)
        if row:
            row["sector"] = sector_map.get(ticker, "Other")
            new_rows.append(row)
            seen[ticker] = filing["filed_date"]
            updated.append(ticker)

    if not new_rows:
        log.info("No new 10-K data. CSV unchanged.")
        # Still persist seen-filing state if it grew (first run seeding etc.)
        state["seen_filings"] = seen
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
        return 0

    # Upsert on (ticker, year) — newest wins
    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([df, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["ticker", "year"], keep="last")
    combined = combined.sort_values(["ticker", "year"]).reset_index(drop=True)

    # Recompute rev_growth_pct for updated tickers
    for t in updated:
        mask = combined["ticker"] == t
        tdf = combined.loc[mask].sort_values("year")
        growth = tdf["revenue_m"].pct_change(fill_method=None) * 100
        combined.loc[growth.index, "rev_growth_pct"] = growth.round(4)

    # Enforce locked column order
    combined = combined[[c for c in CSV_COLUMNS if c in combined.columns]]
    combined.to_csv(DATA_CSV, index=False)

    state["seen_filings"] = seen
    state["last_run"] = pd.Timestamp.utcnow().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

    log.info(f"Upserted {len(new_df)} rows ({', '.join(updated)}). Total rows: {len(combined):,}")
    return len(new_df)


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else Non