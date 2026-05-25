"""
Build and validate rubric grading configuration from course JSON.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field

from rubric.criteria_detail import CRITERION_ORDER
from rubric.defaults import DEFAULT_CRITERION_GRADING_POLICIES, RUBRIC_GRADING_DEFAULTS
class GradingRequirements(BaseModel):
    """Legacy top-level thresholds; merged into criterion enforcement."""

    min_peer_replies: int = 2
    require_on_time: bool = True
    min_citations: int = 1
    require_citation: bool = True
    min_initial_post_chars: int = 100
    min_peer_reply_chars: int = 40
    min_comprehension_richness_signals: int = 3
    lenient: bool = True


class CriterionGradingPolicy(BaseModel):
    """Per-criterion LLM finetuning and enforcement."""

    llm_guidance: Optional[str] = None
    lenient: bool = True
    enforcement: Optional[Dict[str, Any]] = None


class RubricCriterionConfig(BaseModel):
    """One rubric criterion with optional grading policy."""

    name: str
    max_points: int = 0
    rating: str = ""
    description: Optional[str] = None
    grading_policy: CriterionGradingPolicy = Field(
        default_factory=CriterionGradingPolicy
    )

    @classmethod
    def from_course_dict(cls, data: Mapping[str, Any]) -> RubricCriterionConfig:
        policy_data = data.get("grading_policy") or {}
        return cls(
            name=data["name"],
            max_points=int(data.get("max_points", 0)),
            rating=str(data.get("rating", "")),
            description=data.get("description"),
            grading_policy=CriterionGradingPolicy.model_validate(policy_data),
        )


class RubricGradingDefaults(BaseModel):
    lenient: bool = True
    global_llm_guidance: Optional[str] = None


class RubricGradingConfig(BaseModel):
    """Normalized rubric grading config used by the grader and policy pipeline."""

    criteria: List[RubricCriterionConfig]
    criterion_order: List[str]
    grading_defaults: RubricGradingDefaults
    grading_requirements: GradingRequirements = Field(
        default_factory=GradingRequirements
    )

    def policy_for(self, criterion_name: str) -> CriterionGradingPolicy:
        for criterion in self.criteria:
            if criterion.name == criterion_name:
                return criterion.grading_policy
        return CriterionGradingPolicy.model_validate(
            DEFAULT_CRITERION_GRADING_POLICIES.get(criterion_name, {})
        )

    def enforcement_for(self, criterion_name: str) -> Optional[Dict[str, Any]]:
        return self.policy_for(criterion_name).enforcement

    @property
    def lenient_enabled(self) -> bool:
        return self.grading_defaults.lenient


def _overlay_legacy_requirements(
    criterion_name: str,
    enforcement: Dict[str, Any],
    requirements: GradingRequirements,
) -> Dict[str, Any]:
    result = dict(enforcement)
    rule_type = result.get("type")
    if criterion_name == "Engagement" and rule_type == "min_meaningful_peer_replies":
        result["min_count"] = requirements.min_peer_replies
        result["min_chars_per_reply"] = requirements.min_peer_reply_chars
    elif criterion_name == "Writing" and rule_type == "min_citations":
        result["min_count"] = requirements.min_citations
        result["require_citation"] = requirements.require_citation
    return result


def _merge_policy(
    criterion_name: str,
    user_policy: Optional[Mapping[str, Any]],
    requirements: GradingRequirements,
) -> CriterionGradingPolicy:
    default = deepcopy(DEFAULT_CRITERION_GRADING_POLICIES.get(criterion_name, {}))
    user = dict(user_policy or {})
    merged: Dict[str, Any] = {**default, **user}
    if default.get("enforcement") or user.get("enforcement"):
        enforcement = {**default.get("enforcement", {}), **user.get("enforcement", {})}
        merged["enforcement"] = _overlay_legacy_requirements(
            criterion_name, enforcement, requirements
        )
    return CriterionGradingPolicy.model_validate(merged)


def build_rubric_grading_config(
    criteria: List[Dict[str, Any]],
    grading_requirements: Optional[Mapping[str, Any]] = None,
    grading_defaults: Optional[Mapping[str, Any]] = None,
) -> RubricGradingConfig:
    """Merge course criteria with defaults and legacy requirements."""
    requirements = GradingRequirements.model_validate(
        {**GradingRequirements().model_dump(), **(grading_requirements or {})}
    )
    defaults = RubricGradingDefaults.model_validate(
        {**RUBRIC_GRADING_DEFAULTS, **(grading_defaults or {})}
    )

    merged_criteria: List[RubricCriterionConfig] = []
    for entry in criteria:
        name = entry.get("name", "")
        policy = _merge_policy(name, entry.get("grading_policy"), requirements)
        merged_criteria.append(
            RubricCriterionConfig(
                name=name,
                max_points=int(entry.get("max_points", 0)),
                rating=str(entry.get("rating", "")),
                description=entry.get("description"),
                grading_policy=policy,
            )
        )

    order = [c.name for c in merged_criteria if c.name] or list(CRITERION_ORDER)
    return RubricGradingConfig(
        criteria=merged_criteria,
        criterion_order=order,
        grading_defaults=defaults,
        grading_requirements=requirements,
    )


def config_to_legacy_dict(config: RubricGradingConfig) -> Dict[str, Any]:
    """Serialize for callers that still expect a plain dict."""
    return {
        "criteria": [
            {
                "name": c.name,
                "max_points": c.max_points,
                "rating": c.rating,
                "description": c.description,
                "grading_policy": c.grading_policy.model_dump(exclude_none=True),
            }
            for c in config.criteria
        ],
        "criterion_order": config.criterion_order,
        "grading_defaults": config.grading_defaults.model_dump(exclude_none=True),
        "grading_requirements": config.grading_requirements.model_dump(),
    }


def merge_criterion_grading_policies(
    criteria: List[Dict[str, Any]],
    grading_requirements: Optional[Dict[str, Any]] = None,
    grading_defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = build_rubric_grading_config(
        criteria, grading_requirements, grading_defaults
    )
    return config_to_legacy_dict(config)
