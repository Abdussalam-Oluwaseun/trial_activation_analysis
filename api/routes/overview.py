"""
api/routes/overview.py
──────────────────────
GET /api/overview

Returns executive KPIs and per-goal completion rates
computed from the locally cached fct_trial_activation data.
"""

from __future__ import annotations

import statistics
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import local_data

router = APIRouter(prefix="/api/overview", tags=["overview"])


class KpiResponse(BaseModel):
    total_orgs: int
    converted_orgs: int
    conversion_rate: float
    activated_orgs: int
    activation_rate: float
    avg_days_to_convert: float | None
    median_days_to_convert: float | None


class GoalCompletionItem(BaseModel):
    goal_id: str
    goal_label: str
    completed_orgs: int
    completion_rate: float


class OverviewResponse(BaseModel):
    kpis: KpiResponse
    goal_completion: list[GoalCompletionItem]


_GOAL_META = [
    ("G1", "g1_scheduling_setup",    "Scheduling Setup"),
    ("G2", "g2_schedule_engagement", "Schedule Engagement"),
    ("G3", "g3_team_communications", "Team Communications"),
    ("G4", "g4_punch_clock",         "Punch Clock"),
    ("G5", "g5_sustained_engagement","Sustained Engagement"),
]


@router.get("", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    """Return KPIs and per-goal completion rates."""
    try:
        rows = local_data.get_activation()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No activation data found.")

    total          = len(rows)
    converted      = sum(1 for r in rows if r.get("converted"))
    activated      = sum(1 for r in rows if r.get("is_activated"))
    days_list      = [float(r["days_to_convert"]) for r in rows if r.get("days_to_convert") is not None]

    avg_days    = round(statistics.mean(days_list), 1)    if days_list else None
    median_days = round(statistics.median(days_list), 1)  if days_list else None

    goal_completion = [
        GoalCompletionItem(
            goal_id=gid,
            goal_label=label,
            completed_orgs=(count := sum(1 for r in rows if r.get(col))),
            completion_rate=round(count / total * 100, 1) if total else 0.0,
        )
        for gid, col, label in _GOAL_META
    ]

    return OverviewResponse(
        kpis=KpiResponse(
            total_orgs=total,
            converted_orgs=converted,
            conversion_rate=round(converted / total * 100, 1) if total else 0.0,
            activated_orgs=activated,
            activation_rate=round(activated / total * 100, 1) if total else 0.0,
            avg_days_to_convert=avg_days,
            median_days_to_convert=median_days,
        ),
        goal_completion=goal_completion,
    )
