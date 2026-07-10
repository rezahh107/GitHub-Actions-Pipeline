"""Deterministic aggregation of validated repository outcomes into review-only profile proposals."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from tools.ci_models import canonical_json_bytes
from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

OUTCOME_VERSION="1.0.0";EVOLUTION_VERSION="1.0.0"


def load_outcomes(path:Path)->dict[str,object]:
    try:data=json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:raise UpgradeContractError("OUTCOME_REGISTRY_UNAVAILABLE",f"Could not read outcome registry {path}: {exc}") from exc
    except json.JSONDecodeError as exc:raise UpgradeContractError("OUTCOME_REGISTRY_INVALID_JSON",f"Outcome registry {path} is invalid JSON: {exc}") from exc
    if not isinstance(data,dict) or data.get("outcome_contract_version")!=OUTCOME_VERSION or not isinstance(data.get("outcomes"),list):raise UpgradeContractError("OUTCOME_REGISTRY_INVALID_SHAPE",f"Outcome registry must use version {OUTCOME_VERSION} and contain outcomes.")
    return data


def _verified(item:dict[str,object])->bool:
    validation=item.get("validation",{})
    return isinstance(validation,dict) and validation.get("exact_head_sha") and validation.get("workflow_conclusion")=="success" and item.get("implementation_status")=="applied" and item.get("post_capability_state") in {"operational","operational_but_weak"}


def build_profile_evolution_proposals(registry:dict[str,object],*,minimum_distinct_repositories:int=3)->dict[str,object]:
    if minimum_distinct_repositories<2:raise UpgradeContractError("EVOLUTION_THRESHOLD_TOO_LOW","minimum_distinct_repositories must be at least 2.")
    groups={};rejected=[]
    for item in registry.get("outcomes",[]):
        if not isinstance(item,dict):continue
        if not _verified(item):
            rejected.append({"outcome_id":item.get("outcome_id"),"reason":"not_exact_head_verified_success"});continue
        profiles=item.get("profile_ids",[])
        if not isinstance(profiles,list):continue
        for profile in profiles:
            key=(str(profile),str(item.get("capability_id")),str(item.get("recommendation_id")))
            groups.setdefault(key,[]).append(item)
    proposals=[]
    for key,items in sorted(groups.items()):
        profile,capability,recommendation=key;repos=sorted({str(x.get("repository_fingerprint")) for x in items if x.get("repository_fingerprint")})
        if len(repos)<minimum_distinct_repositories:continue
        pre_states=sorted({str(x.get("pre_capability_state")) for x in items});post_states=sorted({str(x.get("post_capability_state")) for x in items});refs=sorted(str(x.get("outcome_id")) for x in items)
        proposal_id="EVOLVE-"+hashlib.sha256(canonical_json_bytes({"key":key,"repos":repos,"refs":refs})).hexdigest()[:16].upper()
        proposals.append({"proposal_id":proposal_id,"profile_id":profile,"capability_id":capability,"recommendation_id":recommendation,"proposal_type":"review_baseline_or_recipe_promotion","status":"proposed_for_human_review","distinct_repository_count":len(repos),"pre_capability_states":pre_states,"post_capability_states":post_states,"evidence":evidence("derived",refs,"Multiple distinct repositories have exact-head successful outcomes for the same profile, capability, and recommendation. This supports review, not automatic registry mutation.",confidence="high"),"required_review":["Verify repositories are genuinely independent and representative.","Inspect false-positive, runtime, and maintenance outcomes.","Update the versioned profile or recipe registry in a separate reviewed change.","Add fixtures and migration notes before activation."]})
    diagnostics=[]
    if rejected:diagnostics.append(diagnostic("OUTCOMES_EXCLUDED_FROM_EVOLUTION",f"Excluded {len(rejected)} outcomes lacking exact-head successful validation.",affected_area="profile_evolution",evidence_references=[str(x.get("outcome_id")) for x in rejected],repair_hint="Provide exact head SHA, successful workflow conclusion, applied implementation status, and operational post-state.",severity="info"))
    return {"profile_evolution_contract_version":EVOLUTION_VERSION,"minimum_distinct_repositories":minimum_distinct_repositories,"automatic_registry_mutation":False,"proposals":proposals,"excluded_outcomes":rejected,"diagnostics":diagnostics}
