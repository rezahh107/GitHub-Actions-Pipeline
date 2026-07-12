"""Versioned operating-mode, evidence, capability, and ranking contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final

MINIMAL_SAFE_CI: Final = "minimal-safe-ci"
DEEP_REPOSITORY_UPGRADE: Final = "deep-repository-upgrade"
SUPPORTED_MODES: Final = (MINIMAL_SAFE_CI, DEEP_REPOSITORY_UPGRADE)
EVIDENCE_STATES: Final = ("observed","derived","inferred","unavailable","not_applicable")
CAPABILITY_STATES: Final = ("absent","nominal","partial","operational","operational_but_weak","unknown","not_applicable")
RECOMMENDATION_SOURCES: Final = ("observed_failure","structural_invariant","baseline_capability")
CONFIDENCE_LEVELS: Final = ("low","medium","high")
DECISIONS: Final = ("phase_1","phase_2","deferred","rejected")
IMPLEMENTATION_STATES: Final = ("applicable","blocked","unsupported","applied","failed","skipped")

@dataclass(frozen=True)
class AnalysisPolicy:
    mode:str
    collect_history_structure:bool
    collect_remote_telemetry:bool
    include_baseline_capabilities:bool
    include_testability_gaps:bool
    include_implementation_package:bool
    recommendation_scope:str
    max_phase_1_items:int

POLICIES: Final = {
    MINIMAL_SAFE_CI: AnalysisPolicy(MINIMAL_SAFE_CI,False,False,False,False,False,"strongly_justified_gates_only",3),
    DEEP_REPOSITORY_UPGRADE: AnalysisPolicy(DEEP_REPOSITORY_UPGRADE,True,True,True,True,True,"repository_code_tests_validators_and_ci",5),
}

class UpgradeContractError(ValueError):
    def __init__(self,code:str,message:str)->None:
        super().__init__(message); self.code=code; self.message=message

def get_policy(mode:str)->AnalysisPolicy:
    try:return POLICIES[mode]
    except KeyError as exc: raise UpgradeContractError("INVALID_OPERATING_MODE",f"Unsupported mode {mode!r}; expected one of: {', '.join(SUPPORTED_MODES)}.") from exc

def evidence(state:str,references:list[str]|tuple[str,...],rationale:str,*,confidence:str|None=None)->dict[str,object]:
    if state not in EVIDENCE_STATES: raise UpgradeContractError("INVALID_EVIDENCE_STATE",f"Unsupported evidence state: {state}.")
    if confidence is not None and confidence not in CONFIDENCE_LEVELS: raise UpgradeContractError("INVALID_CONFIDENCE",f"Unsupported confidence: {confidence}.")
    out:dict[str,object]={"state":state,"references":sorted(set(references)),"rationale":rationale}
    if confidence is not None: out["confidence"]=confidence
    return out

def diagnostic(code:str,message:str,*,affected_area:str,evidence_references:list[str]|tuple[str,...]=(),repair_hint:str,severity:str="warning")->dict[str,object]:
    if severity not in {"info","warning","error"}: raise UpgradeContractError("INVALID_DIAGNOSTIC_SEVERITY",f"Unsupported diagnostic severity: {severity}.")
    return {"code":code,"severity":severity,"message":message,"affected_area":affected_area,"evidence_references":sorted(set(evidence_references)),"repair_hint":repair_hint}

BENEFIT_KEYS: Final=("risk_reduction","invariant_criticality","regression_detection","silent_failure_exposure","evidence_strength","maintainability","reversibility")
COST_KEYS: Final=("implementation_complexity","execution_time","noise_risk","maintenance_cost","control_overlap")
RANKING_KEYS: Final=BENEFIT_KEYS+COST_KEYS

def ranking_total(factors:dict[str,int])->int:
    required=set(RANKING_KEYS)
    if set(factors)!=required:
        raise UpgradeContractError("INVALID_RANKING_FACTORS",f"Ranking factors mismatch; missing={sorted(required-set(factors))}, extra={sorted(set(factors)-required)}.")
    for name,value in factors.items():
        if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=3: raise UpgradeContractError("INVALID_RANKING_VALUE",f"{name} must be an integer from 0 through 3.")
    return sum(factors[k] for k in BENEFIT_KEYS)-sum(factors[k] for k in COST_KEYS)

def priority_band(total:int,confidence:str)->str:
    if confidence=="low": return "defer" if total<9 else "medium"
    if total>=10:return "high"
    if total>=5:return "medium"
    if total>=1:return "low"
    return "defer"
