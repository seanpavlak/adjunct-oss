"""
Boundary leniency: optimistic one-step bump when the LLM flags borderline scores.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

from rubric.config import RubricGradingConfig
from rubric.types import BOUNDARY_BUMP_FROM, RubricLevel


def apply_boundary_leniency(
    levels: Dict[str, RubricLevel],
    borderline: Mapping[str, bool],
    config: RubricGradingConfig,
) -> Dict[str, RubricLevel]:
    """
    Bump one rubric band up only when the LLM flagged an adjacent-level tie.

    - borderline=true and level 1 (below) → level 2 (needs)
    - borderline=true and level 3 (meets) → level 4 (exceeds)
    - borderline=false → unchanged
    """
    result = dict(levels)
    for name in config.criterion_order:
        if not borderline.get(name):
            continue
        if not config.policy_for(name).lenient:
            continue
        level = result.get(name, "meets")
        bumped = BOUNDARY_BUMP_FROM.get(level)
        if bumped:
            result[name] = bumped
    return result
