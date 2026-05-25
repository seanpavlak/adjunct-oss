"""Map rubric levels to total points (Discussion Rubric 2021 weights)."""

from __future__ import annotations

from typing import Dict, Mapping

from chcp.rubric.criteria_detail import RUBRIC_CRITERIA_DETAIL

LEVEL_MULTIPLIERS = {
    "exceeds": 1.0,
    "meets": 0.85,
    "needs": 0.70,
    "below": 0.0,
}


def grade_points_from_levels(
    levels: Mapping[str, str],
    criterion_points: Dict[str, int] | None = None,
) -> str:
    """Total points from per-criterion levels using rubric max_points."""
    weights = criterion_points or {
        name: int(detail.get("max_points", 0))
        for name, detail in RUBRIC_CRITERIA_DETAIL.items()
    }
    total = 0.0
    for name, max_pts in weights.items():
        level = levels.get(name, "below")
        total += max_pts * LEVEL_MULTIPLIERS.get(level, 0.0)
    return str(int(round(total)))
