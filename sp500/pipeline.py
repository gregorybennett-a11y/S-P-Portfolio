"""
pipeline.py
-----------
Data pipeline for S&P 500 financial data.

File layout (all in the same folder):
  sp500_history.csv            — converted from Excel (by build.py or convert_excel_to_parquet.py)
  active_YYYY-MM-DD.csv        — current 6-month active window (twice-daily updates land here)
  reference_YYYY-MM-DD.csv     — frozen 6-month snapshot (read-only after rotation)
  pipeline_state.json          — tracks active window start date and file paths

The exe uses CSV (zero binary dependencies).
Python scripts can still run DuckDB queries directly against the CSV files.

Run modes (Python only):
  python pipeline.py init       — first-time setup
  python pipeline.py upsert     — merge new API data (every 12 hours)
  python pipeline.py rotate     — promote active → reference (every 6 months)
  python pipeline.py query      — sample DuckDB queries
"""

import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

STATE_FILE    = BASE_DIR / "pipeline_state.json"
HISTORY_CSV   = BASE_DIR / "sp500_history.csv"

log = logging.getLogger(__name__)

# ── State helpers ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def active_path(state: dict) -> Path:
    return BASE_DIR / state["active_file"]

def reference_path(state: dict) -> Path | None:
    ref = state.get("reference_file")
    return BASE_DIR / ref if ref else None

# ── CSV upsert (no binary dependencies) ───────────────────────────────────────

def upsert_into_csv(target: Path, new_df: pd.DataFrame) -> int:
    """
    Merge new_df into target CSV.
    Deduplicates on (ticker, year), keeping the newer row.
    """
    if target.exists():
        existing = pd.read_csv(target)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df.copy()

    combined = combined.drop_duplicates(subset=["ticker", "year"], keep="last")
    combined = combined.sort_values(["ticker", "year"]).reset_index(drop=True)
    combined.to_csv(target, index=False)
    return len(combined)

# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_init():
    """First-time setup: create the active CSV from the history file."""
    log.info(f"cmd_init: BASE_DIR = {BASE_DIR}")
    log.info(f"cmd_init: looking for {HISTORY_CSV}")

    if not HISTORY_CSV.exists():
        log.error(f"sp500_history.csv not found at {HISTORY_CSV}")
        log.error("Run build.py to generate it, or run convert_excel_to_parquet.py then build.py")
        sys.exit(1)

    import shutil
    today = date.today().isoformat()
    active_file = f"active_{today}.csv"
    target = BASE_DIR / active_file

    log.info(f"cmd_init: copying history to {active_file} ...")
    shutil.copy(HISTORY_CSV, target)

    state = {
        "active_file": active_file,
        "active_start": today,
        "reference_file": None,
        "reference_start": None,
        "last_upsert": None,
        "next_rotation": (date.today() + timedelta(days=183)).isoformat(),
    }
    save_state(state)
    log.info(f"cmd_init: done. Next rotation: {state['next_rotation']}")


def cmd_upsert(new_data: pd.DataFrame | None = None):
    """
    Merge new API data into the active CSV file.
    Called automatically every 12 hours by the exe.
    """
    state = load_state()
    if not state:
        log.error("Pipeline not initialized.")
        sys.exit(1)

    if new_data is None:
        log.info("No new data provided — skipping upsert.")
        return

    target = active_path(state)
    total = upsert_into_csv(target, new_data)
    state["last_upsert"] = datetime.now().isoformat()
    save_state(state)
    log.info(f"Upserted {len(new_data)} rows → {target.name} ({total:,} total rows)")

    if date.today().isoformat() >= state["next_rotation"]:
        log.warning("Rotation is due! Run: python pipeline.py rotate")


def cmd_rotate():
    """Promote active → reference, start a fresh active file."""
    state = load_state()
    if not state:
        log.error("Pipeline not initialized.")
        sys.exit(1)

    import shutil
    old_active = active_path(state)
    old_ref = reference_path(state)
    today = date.today().isoformat()

    if old_ref and old_ref.exists():
        old_ref.unlink()
        log.info(f"Removed old reference: {old_ref.name}")

    new_ref_name = f"reference_{state['active_start']}_to_{today}.csv"
    new_ref = BASE_DIR / new_ref_name
    old_active.rename(new_ref)
    log.info(f"Promoted to reference: {new_ref_name}")

    new_active_name = f"active_{today}.csv"
    new_active = BASE_DIR / new_active_name
    shutil.copy(HISTORY_CSV, new_active)

    state.update({
        "active_file": new_active_name,
        "active_start": today,
        "reference_file": new_ref_name,
        "reference_start": state["active_start"],
        "last_upsert": None,
        "next_rotation": (date.today() + timedelta(days=183)).isoformat(),
    })
    save_state(state)
    log.info(f"New active: {new_active_name} | Next rotation: {state['next_rotation']}")


def cmd_query():
    """Sample DuckDB queries against active and reference CSV files."""
    import duckdb  # lazy — only for Python-based analysis, not the exe
    state = load_state()
    if not state:
        print("Not initialized.")
        return

    con = duckdb.connect()
    active = active_path(state)
    ref = reference_path(state)

    print("=== Active file: top 5 by net income (most recent year) ===")
    result = con.execute(f"""
        WITH latest AS (
            SELECT ticker, MAX(year) AS year
            FROM read_csv_auto('{active}')
            GROUP BY ticker
        )
        SELECT a.ticker, a.year, a.net_income_m, a.market_cap_m, a.pe_ratio
        FROM read_csv_auto('{active}') a
        JOIN latest l ON a.ticker = l.ticker AND a.year = l.year
        ORDER BY a.net_income_m DESC NULLS LAST
        LIMIT 5
    """).df()
    print(result.to_string(index=False))

    if ref and ref.exists():
        print(f"\n=== Reference: {ref.name} ===")
        count = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{ref}')").fetchone()[0]
        print(f"  {count:,} rows")

        print("\n=== AAPL revenue history (active + reference) ===")
        result2 = con.execute(f"""
            SELECT ticker, year, revenue_m FROM (
                SELECT * FROM read_csv_auto('{active}')
                UNION ALL
                SELECT * FROM read_csv_auto('{ref}')
            ) WHERE ticker = 'AAPL' ORDER BY year
        """).df()
        print(result2.to_string(index=False))

    con.close()


# ── Entry point ────────────────────────────────────────────────────────────────

COMMANDS = {"init": cmd_init, "upsert": cmd_upsert, "rotate": cmd_rotate, "query": cmd_query}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "query"
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Choose: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[cmd]()
