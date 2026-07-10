"""Versioned operating-mode, evidence, capability, and ranking contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MINIMAL_SAFE_CI: Final = "minimal-safe-ci"
DEEP_REPOSITORY_UPGRADE: Final = "deep-repository-upgrade"
SUPPORTED_MODES: Final = (MINIMAL_SAFE_CI, DEEP_REPOSITORY_UPGRADE)

EVIDENCE_STATES: Final = (
    "observed",
    "derived",
    "inferred",
    "unavailable",
    "not_applicable",
)
CAPABILITY_STATES: Final = (
    "absent",
    "nominal",
    "partial",
    "operational",
    "operational_but_weak",
    "unknown",
    "not_applicable",
)
RECOMMENDATION_SOURCES: Final = (
    "observed_failure",
    "structural_invariant",
    "baseline_capability",
)
CONFIDENCE_LEVELS: Final = ("low", "medium", "high")
DECISIONS: Final = ("phase_1", "phase_2", "deferred", "rejected")

ORDINAL_DEFINITIONS: Final = {
    "benefit": {
        0: "none",
        1: "limited",
        2: "material",
        3: "high",
    },
    "cost": {
        0: "negligible",
        1: "low",
        2: "moderate",
        3: "high",
    },
}


@dataclass(frozen=True)
class AnalysisPolicy:
    mode: str
    collect_history_structure: bool
    collect_remote_telemetry: bool
    include_baseline_capabilities: bool
    include_testability_gaps: bool
    recommendation_scope: str
    max_phase_1_items: int


POLICIES: Final = {
    MINIMAL_SAFE_CI: AnalysisPolicy(
        mode=MINIMAL_SAFE_CI,
        collect_history_structure=False,
        collect_remote_telemetry=False,
        include_baseline_capabilities=False,
        include_testability_gaps=False,
        recommendation_scope="strongly_justified_gates_only",
        max_phase_1_items=3,
    ),
    DEEP_REPOSITORY_UPGRADE: AnalysisPolicy(
        mode=DEEP_REPOSITORY_UPGRADE,
        collect_history_structure=True,
        collect_remote_telemetry=True,
        include_baseline_capabilities=True,
        include_testability_gaps=True,
        recommendation_scope="repository_code_tests_validators_and_ci",
        max_phase_1_items=5,
    ),
}


class UpgradeContractError(ValueError):
    """Stable contract failure suitable for CLI diagnostics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def get_policy(mode: str) -> AnalysisPolicy:
    try:
        return POLICIES[mode]
    except KeyError as exc:
        allowed = ", ".join(SUPPORTED_MODES)
        raise UpgradeContractError(
            "INVALID_OPERATING_MODE",
            f"Unsupported mode {mode!r}; expected one of: {allowed}.",
        ) from exc


def evidence(
    state: str,
    references: list[str] | tuple[str, ...],
    rationale: str,
    *,
    confidence: str | None = None,
) -> dict[str, object]:
    if state not in EVIDENCE_STATES:
        raise UpgradeContractError(
            "INVALID_EVIDENCE_STATE", f"Unsupported evidence state: {state}."
        )
    if confidence is not None and confidence not in CONFIDENCE_LEVELS:
        raise UpgradeContractError(
            "INVALID_CONFIDENCE", f"Unsupported confidence: {confidence}."
        )
    result: dict[str, object] = {
        "state": state,
        "references": sorted(set(references)),
        "rationale": rationale,
    }
    if confidence is not None:
        result["confidence"] = confidence
    return result


def diagnostic(
    code: str,
    message: str,
    *,
    affected_area: str,
    evidence_references: list[str] | tuple[str, ...] = (),
    repair_hint: str,
    severity: str = "warning",
) -> dict[str, object]:
    if severity not in {"info", "warning", "error"}:
        raise UpgradeContractError(
            "INVALID_DIAGNOSTIC_SEVERITY",
            f"Unsupported diagnostic severity: {severity}.",
        )
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "affected_area": affected_area,
        "evidence_references": sorted(set(evidence_references)),
        "repair_hint": repair_hint,
    }


def ranking_total(factors: dict[str, int]) -> int:
    """Compute a bounded ordinal total; no fractional or probabilistic precision."""
    benefit_keys = (
        "risk_reduction",
        "invariant_criticality",
        "regression_detection",
        "silent_failure_exposure",
        "evidence_strength",
        "maintainability",
        "reversibility",
    )
    cost_keys = (
        "implementation_complexity",
        "execution_time",
        "noise_risk",
        "maintenance_cost",
        "control_overlap",
    )
    required = set(benefit_keys + cost_keys)
    if set(factors) != required:
        missing = sorted(required - set(factors))
        extra = sorted(set(factors) - required)
        raise UpgradeContractError(
            "INVALID_RANKING_FACTORS",
            f"Ranking factors mismatch; missing={missing}, extra={extra}.",
        )
    for name, value in factors.items():
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3:
            raise UpgradeContractError(
                "INVALID_RANKING_VALUE",
                f"{name} must be an integer from 0 through 3.",
            )
    return sum(factors[key] for key in benefit_keys) - sum(
        factors[key] for key in cost_keys
    )


def priority_band(total: int, confidence: str) -> str:
    if confidence == "low":
        return "defer" if total < 9 else "medium"
    if total >= 10:
        return "high"
    if total >= 5:
        return "medium"
    if total >= 1:
        return "low"
    return "defer"
