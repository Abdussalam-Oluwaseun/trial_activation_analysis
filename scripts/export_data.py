"""
scripts/export_data.py
──────────────────────
Pulls all dashboard data from Snowflake and writes it to
data/dashboard/*.json so the API can serve it without a
live Snowflake connection.

Run once (or whenever you want to refresh)::

    env\\Scripts\\python.exe scripts/export_data.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import snowflake.connector

# ─── Config (hard-wired for the export script; no dotenv needed) ──────────────
ACCOUNT   = "LLMQLKG-OS30228"
USER      = "bamzz"
PASSWORD  = "Q9GZRz3QLVGn8wu"
ROLE      = "ACCOUNTADMIN"
WAREHOUSE = "TRIAL_WH"
DATABASE  = "SPLENDOR_ANALYTICS"

MARTS   = f"{DATABASE}.DBT_DEV_MARTS"
STAGING = f"{DATABASE}.DBT_DEV_STAGING"

OUT_DIR = Path(__file__).parent.parent / "data" / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── JSON serialiser (handles Decimal, date, datetime) ───────────────────────
class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def dump(name: str, data: object) -> None:
    path = OUT_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=_Encoder, ensure_ascii=False, indent=2)
    size = path.stat().st_size
    print(f"  [OK]  {path.name}  ({size:,} bytes)")


def rows_to_dicts(cursor) -> list[dict]:
    cols = [d[0].lower() for d in cursor.description]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in cursor.fetchall()]


# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Connecting to Snowflake…")
    conn = snowflake.connector.connect(
        account=ACCOUNT, user=USER, password=PASSWORD,
        role=ROLE, warehouse=WAREHOUSE, database=DATABASE,
        login_timeout=30,
        session_parameters={"QUERY_TAG": "cogent_bi_export"},
    )
    cur = conn.cursor()
    print("Connected.\n")

    # ── 1. fct_trial_activation ───────────────────────────────────────────────
    print("Exporting fct_trial_activation…")
    cur.execute(f"""
        SELECT
            organization_id,
            TO_VARCHAR(trial_start::DATE, 'DD Mon YYYY')  AS trial_start,
            TO_VARCHAR(trial_end::DATE,   'DD Mon YYYY')  AS trial_end,
            converted,
            days_to_convert,
            total_events,
            active_days,
            goals_completed,
            is_activated,
            g1_scheduling_setup,
            g2_schedule_engagement,
            g3_team_communications,
            g4_punch_clock,
            g5_sustained_engagement,
            shifts_created,
            availability_sets,
            schedule_views,
            messages_sent,
            punch_ins,
            punch_outs
        FROM {MARTS}.FCT_TRIAL_ACTIVATION
        ORDER BY goals_completed DESC, active_days DESC
    """)
    activation = rows_to_dicts(cur)
    dump("fct_trial_activation", activation)

    # ── 2. fct_trial_goals ────────────────────────────────────────────────────
    print("Exporting fct_trial_goals…")
    cur.execute(f"""
        SELECT organization_id, goal_id, goal_name, goal_description, is_completed, evidence
        FROM {MARTS}.FCT_TRIAL_GOALS
        ORDER BY organization_id, goal_id
    """)
    goals = rows_to_dicts(cur)
    dump("fct_trial_goals", goals)

    # ── 3. stg_trial_events (heatmap + module usage) ──────────────────────────
    print("Exporting stg_trial_events (heatmap + module aggregates)…")
    # Heatmap: per org per trial_day count
    cur.execute(f"""
        SELECT organization_id, trial_day, COUNT(*) AS event_count
        FROM {STAGING}.STG_TRIAL_EVENTS
        GROUP BY organization_id, trial_day
        ORDER BY organization_id, trial_day
    """)
    heatmap = rows_to_dicts(cur)
    dump("heatmap", heatmap)

    # Module usage: per org per module count
    cur.execute(f"""
        SELECT organization_id, module, COUNT(*) AS event_count
        FROM {STAGING}.STG_TRIAL_EVENTS
        GROUP BY organization_id, module
        ORDER BY organization_id, event_count DESC
    """)
    modules = rows_to_dicts(cur)
    dump("module_usage", modules)

    conn.close()
    print("\nAll exports complete.")
    print(f"Files written to: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
