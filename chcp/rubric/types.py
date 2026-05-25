"""
Shared rubric types and constants.
"""

from typing import Literal, Tuple

RubricLevel = Literal["below", "needs", "meets", "exceeds"]

RUBRIC_LEVEL_ORDER: Tuple[RubricLevel, ...] = ("below", "needs", "meets", "exceeds")

# Numeric bands (1–4) for leniency documentation and prompts
LEVEL_NUMBER: dict[RubricLevel, int] = {
    "below": 1,
    "needs": 2,
    "meets": 3,
    "exceeds": 4,
}

# Adjacent pairs where borderline leniency may bump one step (1↔2, 3↔4)
BOUNDARY_BUMP_FROM: dict[RubricLevel, RubricLevel] = {
    "below": "needs",
    "meets": "exceeds",
}

EnforcementRuleType = Literal[
    "timeliness",
    "min_meaningful_peer_replies",
    "min_citations",
    "comprehension_effort",
]
