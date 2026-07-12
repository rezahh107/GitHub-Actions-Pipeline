"""Versioned, evidence-derived ordinal ranking without fake precision."""
from __future__ import annotations
import json
from pathlib import Path
from tools.ci_upgrade_models import RANKING_KEYS, UpgradeContractError, priority_band, ranking_total

DEFAULT_PATH=Path(__file__).resolve().parents[1]/"profiles"/"ranking-policy.v1.json"


def load_ranking_policy(path:Path|None=None)->dict[str,object]:
    source=path or DEFAULT_PATH
    try:data=json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:raise UpgradeContractError("RANKING_POLICY_UNAVAILABLE",f"Could not read ranking policy {source}: {exc}") from exc
    except json.JSONDecodeError as exc:raise UpgradeContractError("RANKING_POLICY_INVALID_JSON",f"Ranking policy {source} is invalid JSON: {exc}") from exc
    if not isinstance(data,dict) or data.get("ranking_policy_version")!="1.0.0":raise UpgradeContractError("RANKING_POLICY_INVALID_SHAPE","Ranking policy must use version 1.0.0.")
    return data


def _bounded(value:object,name:str)->int:
    if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=3:raise UpgradeContractError("RANKING_POLICY_INVALID_VALUE",f"{name} must be an integer from 0 through 3.")
    return value


def derive_ranking(*,source:str,capability_id:str|None,capability_state:str,confidence:str,evidence_references:list[str],implementation_steps:list[str],policy:dict[str,object]|None=None,complexity_hint:int|None=None,reversibility_hint:int|None=None,maintainability_hint:int|None=None)->dict[str,object]:
    p=policy or load_ranking_policy();default=p.get("default",{});caps=p.get("capabilities",{});cap_policy=caps.get(capability_id,{}) if isinstance(caps,dict) and capability_id else {}
    def setting(name:str)->int:return _bounded(cap_policy.get(name,default.get(name)),name)
    source_map=p.get("source_risk_reduction",{});confidence_map=p.get("confidence_evidence_strength",{});overlap_map=p.get("capability_overlap",{})
    risk=_bounded(source_map.get(source),"source_risk_reduction")
    # Direct references and stronger confidence can raise baseline risk reduction by one, but never above 3.
    if source=="baseline_capability" and evidence_references and confidence in {"medium","high"}:risk=min(2,risk+1)
    evidence_strength=_bounded(confidence_map.get(confidence),"confidence_evidence_strength")
    overlap=_bounded(overlap_map.get(capability_state,0),"capability_overlap")
    complexity=complexity_hint if complexity_hint is not None else min(3,max(1,(len(implementation_steps)+1)//2))
    reversibility=reversibility_hint if reversibility_hint is not None else (3 if complexity<=1 else 2)
    maintainability=maintainability_hint if maintainability_hint is not None else (3 if capability_id in {"schema_validation","tests_run_on_pull_requests","negative_parser_validator_tests"} else 2)
    factors={
      "risk_reduction":risk,
      "invariant_criticality":setting("invariant_criticality"),
      "regression_detection":setting("regression_detection"),
      "silent_failure_exposure":setting("silent_failure_exposure"),
      "evidence_strength":evidence_strength,
      "maintainability":_bounded(maintainability,"maintainability"),
      "reversibility":_bounded(reversibility,"reversibility"),
      "implementation_complexity":_bounded(complexity,"implementation_complexity"),
      "execution_time":setting("execution_time"),
      "noise_risk":setting("noise_risk"),
      "maintenance_cost":setting("maintenance_cost"),
      "control_overlap":overlap,
    }
    if set(factors)!=set(RANKING_KEYS):raise AssertionError("ranking factor contract drift")
    total=ranking_total(factors)
    rationale={
      "risk_reduction":f"Source channel {source} maps to {risk} under ranking-policy.v1.",
      "invariant_criticality":f"Capability policy for {capability_id or 'repository'} sets criticality {factors['invariant_criticality']}.",
      "regression_detection":f"Capability policy sets regression-detection value {factors['regression_detection']}.",
      "silent_failure_exposure":f"Capability policy sets silent-failure exposure {factors['silent_failure_exposure']}.",
      "evidence_strength":f"Confidence {confidence} maps to evidence strength {evidence_strength}; {len(evidence_references)} references are preserved.",
      "maintainability":f"Implementation shape maps to maintainability value {factors['maintainability']}.",
      "reversibility":f"Estimated mutation reversibility is {factors['reversibility']}.",
      "implementation_complexity":f"{len(implementation_steps)} bounded implementation steps map to complexity {factors['implementation_complexity']}.",
      "execution_time":f"Capability policy sets runtime cost {factors['execution_time']}.",
      "noise_risk":f"Capability policy sets false-positive/noise risk {factors['noise_risk']}.",
      "maintenance_cost":f"Capability policy sets ongoing maintenance cost {factors['maintenance_cost']}.",
      "control_overlap":f"Current capability state {capability_state} maps to overlap {overlap}.",
    }
    return {"model_version":"1.1.0","policy_version":str(p["ranking_policy_version"]),"inputs":{"source":source,"capability_id":capability_id,"capability_state":capability_state,"confidence":confidence,"evidence_reference_count":len(set(evidence_references)),"implementation_step_count":len(implementation_steps)},"factors":factors,"factor_rationale":rationale,"ordinal_total":total,"priority_band":priority_band(total,confidence)}
