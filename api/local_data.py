"""
api/local_data.py
─────────────────
Loads the exported Snowflake JSON files into memory at startup
and exposes simple query helpers that the route modules call
instead of live Snowflake queries.

Data is loaded once and cached; call reload() to refresh after
running scripts/export_data.py again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data" / "dashboard"

# ─── In-memory store ──────────────────────────────────────────────────────────
_store: dict[str, list[dict]] = {}


def _load_file(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Data file '{path}' not found. "
            "Run: env\\Scripts\\python.exe scripts\\export_data.py"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def reload() -> None:
    """(Re)load all data files into the in-memory store."""
    global _store
    _store = {
        "activation":   _load_file("fct_trial_activation"),
        "goals":        _load_file("fct_trial_goals"),
        "heatmap":      _load_file("heatmap"),
        "module_usage": _load_file("module_usage"),
    }


def _ensure_loaded() -> None:
    if not _store:
        reload()


# ─── Public query helpers ─────────────────────────────────────────────────────

def get_activation() -> list[dict]:
    _ensure_loaded()
    return _store["activation"]


def get_activation_for_org(org_id: str) -> dict | None:
    _ensure_loaded()
    org_id_lower = org_id.lower()
    for row in _store["activation"]:
        if str(row.get("organization_id", "")).lower() == org_id_lower:
            return row
    return None


def get_goals_for_org(org_id: str) -> list[dict]:
    _ensure_loaded()
    org_id_lower = org_id.lower()
    return [
        r for r in _store["goals"]
        if str(r.get("organization_id", "")).lower() == org_id_lower
    ]


def get_heatmap_for_org(org_id: str) -> list[dict]:
    _ensure_loaded()
    org_id_lower = org_id.lower()
    return [
        r for r in _store["heatmap"]
        if str(r.get("organization_id", "")).lower() == org_id_lower
    ]


def get_module_usage_for_org(org_id: str) -> list[dict]:
    _ensure_loaded()
    org_id_lower = org_id.lower()
    rows = [
        r for r in _store["module_usage"]
        if str(r.get("organization_id", "")).lower() == org_id_lower
    ]
    return sorted(rows, key=lambda r: r.get("event_count", 0), reverse=True)


def filter_activation(
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Filter the activation table by status and/or org ID substring."""
    _ensure_loaded()
    rows = _store["activation"]

    if status == "Converted":
        rows = [r for r in rows if r.get("converted")]
    elif status == "Activated":
        rows = [r for r in rows if r.get("is_activated") and not r.get("converted")]
    elif status == "At Risk":
        rows = [r for r in rows if not r.get("is_activated") and not r.get("converted") and (r.get("active_days") or 0) <= 2]
    elif status == "Trial":
        rows = [r for r in rows if not r.get("is_activated") and not r.get("converted") and (r.get("active_days") or 0) > 2]

    if search:
        search_lower = search.lower()
        rows = [r for r in rows if search_lower in str(r.get("organization_id", "")).lower()]

    return rows
