"""
api/services/recommendations.py
────────────────────────────────
Rule-based recommendation engine.

Given an organisation's goal-completion state and engagement metrics,
produces 1–3 prioritised, human-readable recommendations.

Rules are ordered by expected impact on conversion likelihood
(derived from the Random Forest / SHAP analysis in notebook 02).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Recommendation:
    priority: Priority
    title: str
    body: str
    suggested_action: str
    expected_impact: str


# ─── Rule definitions ─────────────────────────────────────────────────────────
# Each rule is a function (org_data: dict) → Recommendation | None
# Rules are evaluated in order; only matching rules are included (up to 3).

def _rule_no_scheduling(org: dict) -> Recommendation | None:
    """G1 not completed — highest-leverage action."""
    if org.get("g1_scheduling_setup"):
        return None
    return Recommendation(
        priority=Priority.HIGH,
        title="Start with scheduling setup",
        body=(
            f"This organisation has been in trial for {org.get('active_days', '?')} active days "
            "but has not yet created a shift or set availability. "
            "Scheduling setup (G1) is the single strongest predictor of conversion — "
            "orgs that complete it are 4× more likely to convert."
        ),
        suggested_action="Send scheduling quick-start guide",
        expected_impact="+42% activation likelihood",
    )


def _rule_no_engagement_after_setup(org: dict) -> Recommendation | None:
    """G1 done, G2 not — schedule views are very low."""
    if not org.get("g1_scheduling_setup") or org.get("g2_schedule_engagement"):
        return None
    views = org.get("schedule_views", 0) or 0
    return Recommendation(
        priority=Priority.HIGH,
        title="Drive schedule engagement",
        body=(
            f"The schedule has been set up but viewed only {views} time(s). "
            "Organisations that view the schedule 3+ times (G2) are significantly "
            "more likely to use Punch Clock and Communications features later in the trial."
        ),
        suggested_action="Send mobile app download prompt",
        expected_impact="+28% activation likelihood",
    )


def _rule_no_team_comms(org: dict) -> Recommendation | None:
    """G1+G2 done, G3 not — no messages sent."""
    if not (org.get("g1_scheduling_setup") and org.get("g2_schedule_engagement")):
        return None
    if org.get("g3_team_communications"):
        return None
    return Recommendation(
        priority=Priority.HIGH,
        title="Encourage team communication",
        body=(
            "This organisation is engaging with scheduling but hasn't sent a team message. "
            "Orgs that use in-app messaging (G3) are 2.1× more likely to adopt Punch Clock, "
            "which strongly predicts sustained engagement."
        ),
        suggested_action="Send team messaging feature highlight",
        expected_impact="+21% activation likelihood",
    )


def _rule_no_punch_clock(org: dict) -> Recommendation | None:
    """G1–G3 done, G4 not — Punch Clock unused."""
    if not (org.get("g1_scheduling_setup") and org.get("g3_team_communications")):
        return None
    if org.get("g4_punch_clock"):
        return None
    punch_ins = org.get("punch_ins", 0) or 0
    return Recommendation(
        priority=Priority.MEDIUM,
        title="Activate Punch Clock",
        body=(
            f"Punch Clock has not been used (0 punch-ins recorded). "
            "Clock-in/out activity signals operational go-live and is one of "
            "the clearest indicators of a team genuinely running on the platform."
        ),
        suggested_action="Send Punch Clock walkthrough video",
        expected_impact="+18% activation likelihood",
    )


def _rule_low_active_days(org: dict) -> Recommendation | None:
    """G5 at risk — fewer than 3 active days."""
    if org.get("g5_sustained_engagement"):
        return None
    days = org.get("active_days", 0) or 0
    if days >= 3:
        return None
    return Recommendation(
        priority=Priority.MEDIUM,
        title="Re-engage before trial lapses",
        body=(
            f"This organisation has only been active on {days} day(s) of its trial. "
            "Sustained engagement (5+ active days) is the strongest single predictor "
            "of conversion. A timely nudge now significantly increases return probability."
        ),
        suggested_action="Send re-engagement email with trial day counter",
        expected_impact="+15% activation likelihood",
    )


def _rule_almost_activated(org: dict) -> Recommendation | None:
    """4/5 goals done — one nudge to full activation."""
    goals_done = org.get("goals_completed", 0) or 0
    if goals_done != 4:
        return None
    missing_labels = {
        "g1_scheduling_setup": "Scheduling Setup",
        "g2_schedule_engagement": "Schedule Engagement",
        "g3_team_communications": "Team Communications",
        "g4_punch_clock": "Punch Clock",
        "g5_sustained_engagement": "Sustained Engagement",
    }
    missing = next(
        (label for key, label in missing_labels.items() if not org.get(key)),
        "one remaining goal",
    )
    return Recommendation(
        priority=Priority.MEDIUM,
        title=f"One goal away from full activation",
        body=(
            f"This organisation has completed 4 of 5 goals. "
            f"Only '{missing}' remains. "
            "Fully activated organisations convert at 5.3× the rate of those that don't activate."
        ),
        suggested_action=f"Send targeted '{missing}' completion prompt",
        expected_impact="+35% conversion likelihood",
    )


def _rule_converted_sustain(org: dict) -> Recommendation | None:
    """Already converted — sustain to reduce churn risk."""
    if not org.get("converted") or not org.get("is_activated"):
        return None
    return Recommendation(
        priority=Priority.LOW,
        title="Sustain engagement post-conversion",
        body=(
            "This organisation has converted and fully activated. "
            "Maintaining multi-module usage reduces early-churn risk. "
            "Consider a success check-in to introduce advanced features."
        ),
        suggested_action="Schedule customer success check-in",
        expected_impact="Reduces 90-day churn risk",
    )


_RULES = [
    _rule_no_scheduling,
    _rule_no_engagement_after_setup,
    _rule_no_team_comms,
    _rule_no_punch_clock,
    _rule_low_active_days,
    _rule_almost_activated,
    _rule_converted_sustain,
]


def generate_recommendations(org: dict) -> list[Recommendation]:
    """
    Evaluate all rules against *org* and return up to 3 recommendations,
    ordered by priority (HIGH → MEDIUM → LOW).

    Args:
        org: Dict with keys matching fct_trial_activation columns (lowercase).

    Returns:
        List of up to 3 Recommendation objects.
    """
    results: list[Recommendation] = []
    for rule in _RULES:
        rec = rule(org)
        if rec:
            results.append(rec)
        if len(results) == 3:
            break

    # Stable sort: HIGH first, then MEDIUM, then LOW
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    results.sort(key=lambda r: priority_order[r.priority])
    return results
