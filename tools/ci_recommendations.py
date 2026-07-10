"""Independent recommendation channels and bounded ordinal ranking."""
from __future__ import annotations
from typing import Iterable
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI, diagnostic, priority_band, ranking_total

FACTORS={"risk_reduction":2,"invariant_criticality":2,"regression_detection":2,"silent_failure_exposure":2,"evidence_strength":2,"maintainability":2,"reversibility":2,"implementation_complexity":1,"execution_time":1,"noise_risk":1,"maintenance_cost":1,"control_overlap":0}

def _caps(model):return {str(x["capability_id"]):x for x in model.get("capabilities",[]) if isinstance(x,dict) and "capability_id" in x}
def _refs(model,key):return [str(x) for x in model.get(key,[]) if isinstance(x,str)]

def _rec(rid,source,title,*,cap,invariant,refs:Iterable[str],basis,confidence="medium",factors=None,steps=None,code="CAPABILITY_GAP",message="Repository capability gap detected.",hint="Inspect the cited evidence and implement the smallest operational control."):
    values=dict(FACTORS); values.update(factors or {}); total=ranking_total(values)
    return {"recommendation_id":rid,"source":source,"title":title,"affected_capability":cap,"protected_invariant":invariant,"evidence":{"references":sorted(set(refs)),"basis":basis,"confidence":confidence},"ranking":{"model_version":"1.0.0","factors":values,"ordinal_total":total,"priority_band":priority_band(total,confidence)},"implementation":steps or [],"decision":"deferred","diagnostic":diagnostic(code,message,affected_area=cap or "repository",evidence_references=sorted(set(refs)),repair_hint=hint)}

def observed_failure_recommendations(history,telemetry):
    out=[]; reverts=history.get("revert_chains",[])
    if isinstance(reverts,list) and reverts:
        refs=[str(x.get("commit_sha")) for x in reverts if isinstance(x,dict) and x.get("commit_sha")]
        out.append(_rec("OBS-REVERT-REGRESSION-ORACLE","observed_failure","Protect reverted behavior with a deterministic regression oracle",cap="tests_run_on_pull_requests",invariant="Previously reversed behavior must not regress silently.",refs=refs,basis="Explicit revert commits were observed in bounded local history.",confidence="high",factors={"risk_reduction":3,"regression_detection":3,"silent_failure_exposure":3,"evidence_strength":3},steps=["Identify the reverted behavior from cited commits.","Add one deterministic regression fixture or assertion.","Run it on pull requests with a repair-oriented failure message."],code="OBSERVED_REVERT_WITHOUT_ORACLE",message="Explicit revert evidence exists; verify that the reversed behavior has a machine-checkable oracle.",hint="Trace the revert to its subsystem and add one deterministic regression test."))
    repeated=history.get("repeated_fix_subsystems",[])
    if isinstance(repeated,list):
        for x in repeated[:3]:
            if not isinstance(x,dict):continue
            sub=str(x.get("subsystem") or "unknown"); count=int(x.get("fix_commit_count") or 0); token=sub.replace("/","-").replace(".","root").upper()
            out.append(_rec(f"OBS-REPEATED-FIX-{token}","observed_failure",f"Add a focused regression oracle for repeated fixes in {sub}",cap="tests_run_on_pull_requests",invariant=f"Repeatedly repaired behavior in {sub} must remain stable.",refs=[sub],basis=f"{count} fix-oriented commits touched this subsystem; wording supports correlation, not root cause.",factors={"risk_reduction":3,"implementation_complexity":2},steps=[f"Review bounded fix commits touching {sub}.","Select one reproducible input/output failure mode.","Add a targeted regression test before broadening CI."],code="REPEATED_FIX_SUBSYSTEM",message=f"Subsystem {sub} has recurring fix evidence but may lack a focused oracle.",hint=f"Add a deterministic regression fixture for {sub}."))
    failures=telemetry.get("recurring_failures",[])
    if isinstance(failures,list):
        for x in failures[:3]:
            if not isinstance(x,dict):continue
            wf=str(x.get("workflow") or "unknown"); count=int(x.get("failure_count") or 0)
            out.append(_rec(f"OBS-WORKFLOW-FAILURE-{wf.replace(' ','-').upper()}","observed_failure",f"Repair recurring workflow failures in {wf}",cap="tests_run_on_pull_requests",invariant="A required validation path must execute consistently and fail actionably.",refs=[wf],basis=f"Workflow telemetry recorded {count} unsuccessful runs.",confidence="high",factors={"risk_reduction":3,"regression_detection":3,"evidence_strength":3,"noise_risk":2},steps=["Inspect recurring failing jobs or steps.","Separate product failures from infrastructure flakiness.","Repair or narrow the check while preserving its stable name."],code="RECURRING_WORKFLOW_FAILURE",message=f"Workflow {wf} has recurring unsuccessful outcomes.",hint="Inspect failing steps and make the check deterministic and actionable."))
    return out

def structural_invariant_recommendations(model):
    out=[]; caps=_caps(model); workflows=[str(x.get("path")) for x in model.get("workflows",[]) if isinstance(x,dict) and x.get("path")]
    item=caps.get("schema_validation")
    if item and item.get("state") in {"nominal","partial","absent"}:
        refs=_refs(model,"schemas")+_refs(model,"examples")+_refs(model,"validators")
        out.append(_rec("INV-SCHEMA-PRODUCER-COMPATIBILITY","structural_invariant","Connect schemas, examples, validators, and malformed fixtures",cap="schema_validation",invariant="Structured producers, examples, and validators must agree with the active closed schema.",refs=refs,basis="Schema surfaces were observed but operational compatibility validation was not proven.",confidence="high",factors={"risk_reduction":3,"invariant_criticality":3,"regression_detection":3,"silent_failure_exposure":3,"evidence_strength":3,"maintainability":3},steps=["Use the existing validator or one small deterministic validator.","Validate positive examples and malformed negative fixtures.","Emit schema path, instance path, invariant, and repair location."],code="SCHEMA_COMPATIBILITY_NOT_OPERATIONAL",message="Schema, producer, example, and negative-fixture compatibility is not proven operational.",hint="Connect all contract surfaces to one deterministic validation command."))
    item=caps.get("tests_run_on_pull_requests")
    if item and item.get("state") in {"nominal","partial","absent"}:
        refs=[str(x) for x in model.get("test_suites",{}).get("files",[])]+workflows
        out.append(_rec("INV-TESTS-EXECUTED-ON-PR","structural_invariant","Execute the repository's real tests on pull requests",cap="tests_run_on_pull_requests",invariant="Changes must not merge without executing the deterministic behavioral oracle.",refs=refs,basis="Tests or workflows exist, but PR execution of a recognized test command was not proven.",confidence="high" if refs else "medium",factors={"risk_reduction":3,"invariant_criticality":3,"regression_detection":3,"evidence_strength":3 if refs else 1,"implementation_complexity":1 if refs else 2},steps=["Resolve the canonical test command from executable configuration.","Run it on pull_request with least privilege.","Tie failure output to the component or test."],code="TESTS_NOT_PROVEN_IN_PULL_REQUEST_CI",message="The test suite is not proven operational on pull requests.",hint="Wire the canonical test command into a pull_request workflow."))
    item=caps.get("reproducible_dependency_install")
    if item and item.get("state") in {"partial","absent"} and model.get("manifests"):
        refs=_refs(model,"lockfiles")+[str(x.get("path")) for x in model.get("manifests",[]) if isinstance(x,dict)]
        out.append(_rec("INV-REPRODUCIBLE-INSTALL","structural_invariant","Make dependency installation reproducible",cap="reproducible_dependency_install",invariant="CI must install the declared dependency graph, not a drifting approximation.",refs=refs,basis="Package manifests exist but a lockfile-enforcing install path was not proven.",factors={"risk_reduction":2,"silent_failure_exposure":3},steps=["Use the existing lockfile when present.","Choose the ecosystem-native frozen install command.","Report manifest and lockfile paths on inconsistency."],code="DEPENDENCY_INSTALL_NOT_REPRODUCIBLE",message="Dependency installation may drift.",hint="Add or use the ecosystem lockfile and enforce it in CI."))
    item=caps.get("build_verified")
    if item and item.get("state")=="nominal":
        refs=[str(x.get("path")) for x in model.get("manifests",[]) if isinstance(x,dict)]
        out.append(_rec("INV-BUILD-VERIFICATION","structural_invariant","Execute the declared build in CI",cap="build_verified",invariant="A declared build must remain executable from a clean checkout.",refs=refs,basis="A build script or backend exists but CI execution was not proven.",confidence="high",factors={"risk_reduction":3,"regression_detection":3,"evidence_strength":3,"execution_time":2},steps=["Invoke the existing build after deterministic installation.","Do not duplicate build logic in workflow YAML.","Report component and command on failure."],code="DECLARED_BUILD_NOT_VERIFIED",message="A declared build was not proven to run in CI.",hint="Wire the declared build command into pull-request validation."))
    return out

def baseline_capability_recommendations(model,profiles):
    out=[]; caps=_caps(model); ids=list(profiles.get("selected_profiles",[]))
    for cid in profiles.get("expected_capabilities",[]):
        cid=str(cid); item=caps.get(cid); state=str(item.get("state")) if item else "unknown"
        if state in {"operational","not_applicable"}:continue
        refs=list(ids)
        if item and isinstance(item.get("evidence"),dict):refs += [str(x) for x in item["evidence"].get("references",[])]
        out.append(_rec(f"BASE-{cid.replace('_','-').upper()}","baseline_capability",f"Establish baseline capability: {cid}",cap=cid,invariant=f"Detected profiles expect {cid} unless evidence excludes it.",refs=refs,basis=f"Composable profiles {ids} expect this capability; current state is {state}. Historical failure is not required.",confidence="medium" if ids else "low",factors={"implementation_complexity":2},steps=["Confirm the applicable executable command or oracle.","Implement an operational control rather than a nominal file.","Add a negative or no-op case against overclaiming."],code="BASELINE_CAPABILITY_GAP",message=f"Detected profiles expect {cid}, but its state is {state}.",hint=f"Implement and test operational {cid}, or record an evidence-based exclusion."))
    return out

def assign_decisions(items,*,mode,max_phase_1_items):
    ordered=sorted(items,key=lambda x:(-int(x["ranking"]["ordinal_total"]),str(x["source"]),str(x["recommendation_id"]))); used=0
    for x in ordered:
        band=x["ranking"]["priority_band"]; conf=x["evidence"]["confidence"]
        if mode==MINIMAL_SAFE_CI and x["source"]=="baseline_capability":x["decision"]="deferred"
        elif band=="high" and conf in {"high","medium"} and used<max_phase_1_items:x["decision"]="phase_1"; used+=1
        elif band in {"high","medium"} or band=="low" and mode==DEEP_REPOSITORY_UPGRADE:x["decision"]="phase_2"
        else:x["decision"]="deferred"
    return ordered

def generate_recommendations(model,history,telemetry,profile_contributions,*,mode,max_phase_1_items):
    observed=observed_failure_recommendations(history,telemetry); structural=structural_invariant_recommendations(model); baseline=baseline_capability_recommendations(model,profile_contributions) if mode==DEEP_REPOSITORY_UPGRADE else []
    ranked=assign_decisions([*observed,*structural,*baseline],mode=mode,max_phase_1_items=max_phase_1_items)
    return {"observed_failures":[x for x in ranked if x["source"]=="observed_failure"],"structural_invariants":[x for x in ranked if x["source"]=="structural_invariant"],"baseline_capabilities":[x for x in ranked if x["source"]=="baseline_capability"],"ranked":ranked}
