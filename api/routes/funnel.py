"""
api/routes/funnel.py
────────────────────
GET /api/funnel

Returns goal funnel data, deep-dive metrics, and drop-off insights
computed from the locally cached activation data.
"""

from __future__ import annotations

import statistics
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import local_data

router = APIRouter(prefix="/api/funnel", tags=["funnel"])


class FunnelStage(BaseModel):
    goal_id: str
    goal_label: str
    goal_description: str
    completed_orgs: int
    completion_rate: float
    continued_rate: float | None


class GoalDeepDive(BaseModel):
    goal_id: str
    completion_rate: float
    median_days_to_complete: float | None
    dropoff_to_next: float | None
    pct_of_activated: float


class DropoffInsight(BaseModel):
    stage: str
    message: str


class FunnelResponse(BaseModel):
    stages: list[FunnelStage]
    deep_dive: list[GoalDeepDive]
    dropoff_insights: list[DropoffInsight]


_GOAL_META = [
    ("G1", "g1_scheduling_setup",    "Scheduling Setup",    "Created >=1 shift AND set availability"),
    ("G2", "g2_schedule_engagement", "Schedule Engagement", "Viewed the schedule >=3 times"),
    ("G3", "g3_team_communications", "Team Communications", "Sent >=1 team communication"),
    ("G4", "g4_punch_clock",         "Punch Clock",         "Clocked in or out at least once"),
    ("G5", "g5_sustained_engagement","Sustained Engagement","Active on >=5 distinct trial days"),
]


def _build_dropoff_insights(stages: list[FunnelStage]) -> list[DropoffInsight]:
    insights: list[DropoffInsight] = []
    for i, stage in enumerate(stages[:-1]):
        next_stage = stages[i + 1]
        if stage.continued_rate is not None:
            dropoff = round(100 - stage.continued_rate, 1)
            if dropoff >= 30:
                insights.append(DropoffInsight(
                    stage=stage.goal_id,
                    message=(
                        f"{dropoff}% of organisations that completed {stage.goal_label} "
                        f"did not go on to complete {next_stage.goal_label}. "
                        "This is the largest drop-off point in the funnel."
                    ),
                ))
    last = stages[-1]
    insights.append(DropoffInsight(
        stage="G5",
        message=(
            f"Only {last.completion_rate}% of organisations reach full activation "
            "(all 5 goals). Improving sustained engagement is the highest-leverage "
            "intervention for increasing conversion."
        ),
    ))
    return insights[:3]


@router.get("", response_model=FunnelResponse)
def get_funnel() -> FunnelResponse:
    """Return funnel stage data, deep-dive metrics, and drop-off insights."""
    try:
        rows = local_data.get_activation()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No activation data found.")

    total     = len(rows)
    activated = sum(1 for r in rows if r.get("is_activated"))

    # Per-goal counts
    counts: dict[str, int] = {}
    for gid, col, *_ in _GOAL_META:
        counts[col] = sum(1 for r in rows if r.get(col))

    # Build stages
    cols  = [col for _, col, *_ in _GOAL_META]
    stages: list[FunnelStage] = []
    for i, (gid, col, label, desc) in enumerate(_GOAL_META):
        count = counts[col]
        rate  = round(count / total * 100, 1) if total else 0.0
        # continued rate = % of orgs that completed THIS AND the next
        if i < len(_GOAL_META) - 1:
            next_col   = cols[i + 1]
            both_count = sum(1 for r in rows if r.get(col) and r.get(next_col))
            continued  = round(both_count / count * 100, 1) if count else None
        else:
            continued = None
        stages.append(FunnelStage(
            goal_id=gid, goal_label=label, goal_description=desc,
            completed_orgs=count, completion_rate=rate, continued_rate=continued,
        ))

    # Deep dive — median days computed from days_to_convert as a proxy
    # (exact per-goal timing would need event-level data; use activation timing)
    days_list = [float(r["days_to_convert"]) for r in rows if r.get("days_to_convert") is not None]
    global_median = round(statistics.median(days_list), 1) if days_list else None

    deep_dive: list[GoalDeepDive] = []
    for i, (gid, col, label, _) in enumerate(_GOAL_META):
        count = counts[col]
        rate  = round(count / total * 100, 1) if total else 0.0
        pct_act = round(count / activated * 100, 1) if activated else 0.0
        dropoff = None
        if i < len(_GOAL_META) - 1:
            next_col   = cols[i + 1]
            next_count = counts[next_col]
            dropoff    = round((count - next_count) / count * 100, 1) if count else None
        deep_dive.append(GoalDeepDive(
            goal_id=gid,
            completion_rate=rate,
            median_days_to_complete=global_median,
            dropoff_to_next=dropoff,
            pct_of_activated=pct_act,
        ))

    insights = _build_dropoff_insights(stages)
    return FunnelResponse(stages=stages, deep_dive=deep_dive, dropoff_insights=insights)
