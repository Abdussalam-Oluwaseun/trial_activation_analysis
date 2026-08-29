"""
api/routes/organisations.py
────────────────────────────
GET /api/organisations         — paginated org list with key metrics
GET /api/organisations/{org_id} — full org journey: goals, heatmap, recommendations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api import local_data
from api.services.recommendations import generate_recommendations, Recommendation

router = APIRouter(prefix="/api/organisations", tags=["organisations"])


# ─── Pydantic models ──────────────────────────────────────────────────────────

class OrgSummary(BaseModel):
    organization_id: str
    goals_completed: int
    is_activated: bool
    converted: bool
    active_days: int
    trial_start: str | None
    trial_end: str | None
    status: str


class OrgListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    organisations: list[OrgSummary]


class GoalDetail(BaseModel):
    goal_id: str
    goal_label: str
    is_completed: bool
    evidence: str


class HeatmapDay(BaseModel):
    day: int
    event_count: int


class ModuleUsage(BaseModel):
    module: str
    event_count: int


class RecommendationOut(BaseModel):
    priority: str
    title: str
    body: str
    suggested_action: str
    expected_impact: str


class OrgDetailResponse(BaseModel):
    organization_id: str
    trial_start: str | None
    trial_end: str | None
    status: str
    converted: bool
    is_activated: bool
    goals_completed: int
    days_to_convert: float | None
    active_days: int
    total_events: int
    goals: list[GoalDetail]
    heatmap: list[HeatmapDay]
    module_usage: list[ModuleUsage]
    recommendations: list[RecommendationOut]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _derive_status(row: dict) -> str:
    if row.get("converted"):
        return "Converted"
    if row.get("is_activated"):
        return "Activated"
    if (row.get("active_days") or 0) <= 2:
        return "At Risk"
    return "Trial"


def _to_org_summary(row: dict) -> OrgSummary:
    return OrgSummary(
        organization_id=str(row["organization_id"]),
        goals_completed=int(row.get("goals_completed") or 0),
        is_activated=bool(row.get("is_activated")),
        converted=bool(row.get("converted")),
        active_days=int(row.get("active_days") or 0),
        trial_start=row.get("trial_start"),
        trial_end=row.get("trial_end"),
        status=_derive_status(row),
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("", response_model=OrgListResponse)
def list_organisations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> OrgListResponse:
    """Return a paginated list of organisations with key metrics."""
    try:
        rows = local_data.filter_activation(status=status, search=search)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    total  = len(rows)
    start  = (page - 1) * page_size
    paged  = rows[start: start + page_size]

    return OrgListResponse(
        total=total,
        page=page,
        page_size=page_size,
        organisations=[_to_org_summary(r) for r in paged],
    )


@router.get("/{org_id}", response_model=OrgDetailResponse)
def get_organisation(org_id: str) -> OrgDetailResponse:
    """Return full journey detail for a single organisation."""
    try:
        row = local_data.get_activation_for_org(org_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not row:
        raise HTTPException(status_code=404, detail=f"Organisation '{org_id}' not found.")

    # Goals
    goal_rows = local_data.get_goals_for_org(org_id)
    _goal_labels = {
        "G1": "Scheduling Setup",
        "G2": "Schedule Engagement",
        "G3": "Team Communications",
        "G4": "Punch Clock",
        "G5": "Sustained Engagement",
    }
    if goal_rows:
        goals = [
            GoalDetail(
                goal_id=str(gr["goal_id"]),
                goal_label=str(gr.get("goal_name") or _goal_labels.get(str(gr["goal_id"]), "")),
                is_completed=bool(gr.get("is_completed")),
                evidence=str(gr.get("evidence") or ""),
            )
            for gr in goal_rows
        ]
    else:
        # Fallback from activation flags
        flag_map = [
            ("G1", "g1_scheduling_setup",    "Scheduling Setup"),
            ("G2", "g2_schedule_engagement", "Schedule Engagement"),
            ("G3", "g3_team_communications", "Team Communications"),
            ("G4", "g4_punch_clock",         "Punch Clock"),
            ("G5", "g5_sustained_engagement","Sustained Engagement"),
        ]
        goals = [
            GoalDetail(goal_id=gid, goal_label=label, is_completed=bool(row.get(col)), evidence="")
            for gid, col, label in flag_map
        ]

    # Heatmap — ensure all 30 days present
    heat_rows = local_data.get_heatmap_for_org(org_id)
    heat_map  = {int(r["trial_day"]): int(r["event_count"]) for r in heat_rows}
    heatmap   = [HeatmapDay(day=d, event_count=heat_map.get(d, 0)) for d in range(30)]

    # Module usage
    module_rows = local_data.get_module_usage_for_org(org_id)
    module_usage = [
        ModuleUsage(module=str(r["module"]), event_count=int(r["event_count"]))
        for r in module_rows
    ]

    # Recommendations
    recs: list[Recommendation] = generate_recommendations({
        **{k: v for k, v in row.items()},
        "g1_scheduling_setup":    bool(row.get("g1_scheduling_setup")),
        "g2_schedule_engagement": bool(row.get("g2_schedule_engagement")),
        "g3_team_communications": bool(row.get("g3_team_communications")),
        "g4_punch_clock":         bool(row.get("g4_punch_clock")),
        "g5_sustained_engagement":bool(row.get("g5_sustained_engagement")),
    })

    recs_out = [
        RecommendationOut(
            priority=rec.priority.value,
            title=rec.title,
            body=rec.body,
            suggested_action=rec.suggested_action,
            expected_impact=rec.expected_impact,
        )
        for rec in recs
    ]

    return OrgDetailResponse(
        organization_id=str(row["organization_id"]),
        trial_start=row.get("trial_start"),
        trial_end=row.get("trial_end"),
        status=_derive_status(row),
        converted=bool(row.get("converted")),
        is_activated=bool(row.get("is_activated")),
        goals_completed=int(row.get("goals_completed") or 0),
        days_to_convert=float(row["days_to_convert"]) if row.get("days_to_convert") is not None else None,
        active_days=int(row.get("active_days") or 0),
        total_events=int(row.get("total_events") or 0),
        goals=goals,
        heatmap=heatmap,
        module_usage=module_usage,
        recommendations=recs_out,
    )
