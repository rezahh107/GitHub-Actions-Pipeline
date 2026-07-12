"""Validated deterministic aggregation of repository outcomes into review-only proposals."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft7Validator

from tools.ci_models import canonical_json_bytes
from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

OUTCOME_VERSION = "1.0.0"
EVOLUTION_VERSION = "1.0.0"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "repository_outcomes.v1.schema.json"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _schema_error_message(error: object) -> str:
    path = "/".join(str(part) for part in getattr(error, "absolute_path", [])) or "<root>"
    return f"{path}: {getattr(error, 'message', str(error))}"


def validate_outcome_registry(registry: object, *, schema_path: Path | None = None) -> dict[str, object]:
    """Validate shape, exact identities, and duplicate/conflict semantics."""
    source = schema_path or DEFAULT_SCHEMA
    try:
        schema = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpgradeContractError("OUTCOME_SCHEMA_UNAVAILABLE", f"Could not read outcome schema {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpgradeContractError("OUTCOME_SCHEMA_INVALID_JSON", f"Outcome schema {source} is invalid JSON: {exc}") from exc
    Draft7Validator.check_schema(schema)
    errors = sorted(Draft7Validator(schema).iter_errors(registry), key=lambda item: list(item.absolute_path))
    if errors:
        details = "; ".join(_schema_error_message(error) for error in errors[:5])
        raise UpgradeContractError("OUTCOME_REGISTRY_SCHEMA_INVALID", f"Outcome registry failed canonical schema validation: {details}")
    assert isinstance(registry, dict)

    by_id: dict[str, bytes] = {}
    by_evidence_identity: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    for item in registry["outcomes"]:
        outcome_id = str(item["outcome_id"])
        canonical = canonical_json_bytes(item)
        if outcome_id in by_id:
            code = "OUTCOME_ID_DUPLICATE" if by_id[outcome_id] == canonical else "OUTCOME_ID_CONFLICT"
            raise UpgradeContractError(code, f"Outcome identity {outcome_id!r} appears more than once; duplicate and conflicting records are rejected before aggregation.")
        by_id[outcome_id] = canonical
        validation = item["validation"]
        exact_head = validation["exact_head_sha"]
        workflow_head = validation["workflow_head_sha"]
        if not GIT_SHA.fullmatch(exact_head) or not GIT_SHA.fullmatch(workflow_head):
            raise UpgradeContractError("OUTCOME_EXACT_HEAD_INVALID", f"Outcome {outcome_id!r} must use lowercase 40-character hexadecimal exact and workflow head SHAs.")
        identity = (str(item["repository_fingerprint"]), str(item["capability_id"]), str(item["recommendation_id"]), exact_head)
        outcome_signature = (workflow_head, str(validation["workflow_conclusion"]))
        previous = by_evidence_identity.get(identity)
        if previous is not None:
            code = "OUTCOME_EVIDENCE_DUPLICATE" if previous == outcome_signature else "OUTCOME_EVIDENCE_CONFLICT"
            raise UpgradeContractError(code, f"Outcome evidence identity {identity!r} is repeated or conflicts across records; each exact-head capability outcome must be unique.")
        by_evidence_identity[identity] = outcome_signature
    return registry


def load_outcomes(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpgradeContractError("OUTCOME_REGISTRY_UNAVAILABLE", f"Could not read outcome registry {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpgradeContractError("OUTCOME_REGISTRY_INVALID_JSON", f"Outcome registry {path} is invalid JSON: {exc}") from exc
    return validate_outcome_registry(data)


def _qualification(item: dict[str, object]) -> tuple[bool, str]:
    validation = item["validation"]
    if validation["exact_head_sha"] != validation["workflow_head_sha"]:
        return False, "workflow_head_does_not_match_exact_head"
    if validation["workflow_conclusion"] != "success":
        return False, "workflow_not_successful"
    if item["implementation_status"] != "applied":
        return False, "implementation_not_applied"
    if item["post_capability_state"] not in {"operational", "operational_but_weak"}:
        return False, "post_capability_not_operational"
    return True, "exact_head_verified_success"


def build_profile_evolution_proposals(registry: dict[str, object], *, minimum_distinct_repositories: int = 3) -> dict[str, object]:
    registry = validate_outcome_registry(registry)
    if minimum_distinct_repositories < 2:
        raise UpgradeContractError("EVOLUTION_THRESHOLD_TOO_LOW", "minimum_distinct_repositories must be at least 2.")
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    rejected: list[dict[str, object]] = []
    for item in registry["outcomes"]:
        qualified, reason = _qualification(item)
        if not qualified:
            rejected.append({"outcome_id": item["outcome_id"], "reason": reason})
            continue
        for profile in item["profile_ids"]:
            key = (str(profile), str(item["capability_id"]), str(item["recommendation_id"]))
            groups.setdefault(key, []).append(item)

    proposals: list[dict[str, object]] = []
    for key, items in sorted(groups.items()):
        profile, capability, recommendation = key
        repositories = sorted({str(item["repository_fingerprint"]) for item in items})
        if len(repositories) < minimum_distinct_repositories:
            continue
        pre_states = sorted({str(item["pre_capability_state"]) for item in items})
        post_states = sorted({str(item["post_capability_state"]) for item in items})
        references = sorted(str(item["outcome_id"]) for item in items)
        proposal_id = "EVOLVE-" + hashlib.sha256(canonical_json_bytes({"key": key, "repos": repositories, "refs": references})).hexdigest()[:16].upper()
        proposals.append({
            "proposal_id": proposal_id,
            "profile_id": profile,
            "capability_id": capability,
            "recommendation_id": recommendation,
            "proposal_type": "review_baseline_or_recipe_promotion",
            "status": "proposed_for_human_review",
            "distinct_repository_count": len(repositories),
            "pre_capability_states": pre_states,
            "post_capability_states": post_states,
            "evidence": evidence("derived", references, "Multiple distinct repositories have schema-valid, exact-head-tied successful outcomes for the same profile, capability, and recommendation. This supports review, not automatic registry mutation.", confidence="high"),
            "required_review": [
                "Verify repositories are genuinely independent and representative.",
                "Inspect false-positive, runtime, and maintenance outcomes.",
                "Update the versioned profile or recipe registry in a separate reviewed change.",
                "Add fixtures and migration notes before activation.",
            ],
        })
    diagnostics: list[dict[str, object]] = []
    if rejected:
        diagnostics.append(diagnostic("OUTCOMES_EXCLUDED_FROM_EVOLUTION", f"Excluded {len(rejected)} schema-valid outcomes that were not exact-head-tied successful applications.", affected_area="profile_evolution", evidence_references=[str(item["outcome_id"]) for item in rejected], repair_hint="Require matching exact_head_sha and workflow_head_sha, successful conclusion, applied implementation, and operational post-state.", severity="info"))
    return {"profile_evolution_contract_version": EVOLUTION_VERSION, "minimum_distinct_repositories": minimum_distinct_repositories, "automatic_registry_mutation": False, "proposals": proposals, "excluded_outcomes": rejected, "diagnostics": diagnostics}
