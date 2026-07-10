"""Independent recommendation channels with evidence-derived ordinal ranking."""
from __future__ import annotations
from typing import Iterable
from tools.ci_ranking import derive_ranking, load_ranking_policy
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI, diagnostic


def _caps(model:dict[str,object])->dict[str,dict[str,object]]:
    return {str(x["capability_id"]):x for x in model.get("capabilities",[]) if isinstance(x,dict) and x.get("capability_id")}

def _refs(model:dict[str,object],key:str)->list[str]:return [str(x) for x in model.get(key,[]) if isinstance(x,str)]

def _confidence_refs(refs:Iterable[str],fallback:str="medium")->tuple[list[str],str]:
    unique=sorted(set(str(x) for x in refs if x));return unique,("high" if len(unique)>=2 else fallback)

def _rec(rid:str,source:str,title:str,*,model:dict[str,object],cap:str|None,invariant:str,refs:Iterable[str],basis:str,confidence:str="medium",steps:list[str]|None=None,code:str="CAPABILITY_GAP",message:str="Repository capability gap detected.",hint:str="Inspect the cited evidence and implement the smallest operational control.",complexity_hint:int|None=None,reversibility_hint:int|None=None,maintainability_hint:int|None=None)->dict[str,object]:
    references=sorted(set(str(x) for x in refs if x));implementation=steps or [];state=str(_caps(model).get(cap,{}).get("state","unknown")) if cap else "unknown"
    ranking=derive_ranking(source=source,capability_id=cap,capability_state=state,confidence=confidence,evidence_references=references,implementation_steps=implementation,policy=load_ranking_policy(),complexity_hint=complexity_hint,reversibility_hint=reversibility_hint,maintainability_hint=maintainability_hint)
    return {"recommendation_id":rid,"source":source,"title":title,"affected_capability":cap,"protected_invariant":invariant,"evidence":{"references":references,"basis":basis,"confidence":confidence},"ranking":ranking,"implementation":implementation,"decision":"deferred","diagnostic":diagnostic(code,message,affected_area=cap or "repository",evidence_references=references,repair_hint=hint)}

def observed_failure_recommendations(model:dict[str,object],history:dict[str,object],telemetry:dict[str,object])->list[dict[str,object]]:
    out=[];reverts=history.get("revert_chains",[])
    if isinstance(reverts,list) and reverts:
        refs=[str(x.get("commit_sha")) for x in reverts if isinstance(x,dict) and x.get("commit_sha")]
        out.append(_rec("OBS-REVERT-REGRESSION-ORACLE","observed_failure","Protect reverted behavior with a deterministic regression oracle",model=model,cap="tests_run_on_pull_requests",invariant="Previously reversed behavior must not regress silently.",refs=refs,basis="Explicit revert commits were observed in bounded local history.",confidence="high",steps=["Identify the reverted behavior from cited commits.","Add one deterministic regression fixture or assertion.","Run it on pull requests with a repair-oriented failure message."],code="OBSERVED_REVERT_WITHOUT_ORACLE",message="Explicit revert evidence exists; verify that the reversed behavior has a machine-checkable oracle.",hint="Trace the revert to its subsystem and add one deterministic regression test.",complexity_hint=2))
    repeated=history.get("repeated_fix_subsystems",[])
    if isinstance(repeated,list):
        for item in repeated[:3]:
            if not isinstance(item,dict):continue
            sub=str(item.get("subsystem") or "unknown");count=int(item.get("fix_commit_count") or 0);token=sub.replace("/","-").replace(".","root").upper()
            out.append(_rec(f"OBS-REPEATED-FIX-{token}","observed_failure",f"Add a focused regression oracle for repeated fixes in {sub}",model=model,cap="tests_run_on_pull_requests",invariant=f"Repeatedly repaired behavior in {sub} must remain stable.",refs=[sub],basis=f"{count} fix-oriented commits touched this subsystem; this is correlation, not root-cause proof.",confidence="medium",steps=[f"Review bounded fix commits touching {sub}.","Select one reproducible input/output failure mode.","Add a targeted regression test before broadening CI."],code="REPEATED_FIX_SUBSYSTEM",message=f"Subsystem {sub} has recurring fix evidence but may lack a focused oracle.",hint=f"Add a deterministic regression fixture for {sub}.",complexity_hint=2))
    failures=telemetry.get("recurring_failures",[])
    if isinstance(failures,list):
        for item in failures[:3]:
            if not isinstance(item,dict):continue
            wf=str(item.get("workflow") or "unknown");count=int(item.get("failure_count") or 0)
            out.append(_rec(f"OBS-WORKFLOW-FAILURE-{wf.replace(' ','-').upper()}","observed_failure",f"Repair recurring workflow failures in {wf}",model=model,cap="tests_run_on_pull_requests",invariant="A required validation path must execute consistently and fail actionably.",refs=[wf],basis=f"Workflow telemetry recorded {count} unsuccessful runs.",confidence="high",steps=["Inspect recurring failing jobs or steps.","Separate product failures from infrastructure flakiness.","Repair or narrow the check while preserving its stable name."],code="RECURRING_WORKFLOW_FAILURE",message=f"Workflow {wf} has recurring unsuccessful outcomes.",hint="Inspect failing steps and make the check deterministic and actionable.",complexity_hint=2,reversibility_hint=2))
    return out

def structural_invariant_recommendations(model:dict[str,object])->list[dict[str,object]]:
    out=[];caps=_caps(model);workflows=[str(x.get("path")) for x in model.get("workflows",[]) if isinstance(x,dict) and x.get("path")]
    item=caps.get("schema_validation")
    if item and item.get("state") in {"nominal","partial","absent"}:
        refs=_refs(model,"schemas")+_refs(model,"examples")+_refs(model,"validators")
        out.append(_rec("INV-SCHEMA-PRODUCER-COMPATIBILITY","structural_invariant","Connect schemas, examples, validators, and malformed fixtures",model=model,cap="schema_validation",invariant="Structured producers, examples, and validators must agree with the active closed schema.",refs=refs,basis="Schema surfaces were observed but operational compatibility validation was not proven.",confidence="high" if len(refs)>=2 else "medium",steps=["Use the existing validator or one small deterministic validator.","Validate positive examples and malformed negative fixtures.","Emit schema path, instance path, invariant, and repair location."],code="SCHEMA_COMPATIBILITY_NOT_OPERATIONAL",message="Schema, producer, example, and negative-fixture compatibility is not proven operational.",hint="Connect all contract surfaces to one deterministic validation command.",complexity_hint=2,maintainability_hint=3))
    item=caps.get("tests_run_on_pull_requests")
    if item and item.get("state") in {"nominal","partial","absent"}:
        refs=[str(x) for x in model.get("test_suites",{}).get("files",[])]+workflows
        out.append(_rec("INV-TESTS-EXECUTED-ON-PR","structural_invariant","Execute the repository's resolved test command on pull requests",model=model,cap="tests_run_on_pull_requests",invariant="Changes must not merge without executing the deterministic behavioral oracle.",refs=refs,basis="Tests or workflows exist, but pull-request execution of a resolved test command was not proven.",confidence="high" if refs else "medium",steps=["Resolve one canonical test command from executable configuration.","Run it on pull_request with least privilege.","Tie failure output to the component or test."],code="TESTS_NOT_PROVEN_IN_PULL_REQUEST_CI",message="The test suite is not proven operational on pull requests.",hint="Use the implementation package only when one unambiguous command and component are resolved.",complexity_hint=1,reversibility_hint=3))
    item=caps.get("reproducible_dependency_install")
    if item and item.get("state") in {"partial","absent"} and model.get("manifests"):
        refs=_refs(model,"lockfiles")+[str(x.get("path")) for x in model.get("manifests",[]) if isinstance(x,dict)]
        out.append(_rec("INV-REPRODUCIBLE-INSTALL","structural_invariant","Make dependency installation reproducible",model=model,cap="reproducible_dependency_install",invariant="CI must install the declared dependency graph, not a drifting approximation.",refs=refs,basis="Package manifests exist but a lockfile-enforcing install path was not proven.",confidence="medium",steps=["Use the existing lockfile when present.","Choose the ecosystem-native frozen install command.","Report manifest and lockfile paths on inconsistency."],code="DEPENDENCY_INSTALL_NOT_REPRODUCIBLE",message="Dependency installation may drift.",hint="Add or use the ecosystem lockfile and enforce it in CI.",complexity_hint=2))
    item=caps.get("build_verified")
    if item and item.get("state")=="nominal":
        refs=[str(x.get("path")) for x in model.get("manifests",[]) if isinstance(x,dict)]
        out.append(_rec("INV-BUILD-VERIFICATION","structural_invariant","Execute the declared build in CI",model=model,cap="build_verified",invariant="A declared build must remain executable from a clean checkout.",refs=refs,basis="A build script or backend exists but CI execution was not proven.",confidence="high",steps=["Invoke the existing build after deterministic installation.","Do not duplicate build logic in workflow YAML.","Report component and command on failure."],code="DECLARED_BUILD_NOT_VERIFIED",message="A declared build was not proven to run in CI.",hint="Wire the declared build command into pull-request validation.",complexity_hint=1))
    return out

def baseline_capability_recommendations(model:dict[str,object],profiles:dict[str,object])->list[dict[str,object]]:
    out=[];caps=_caps(model);ids=list(profiles.get("selected_profiles",[]))
    conflicts={str(x.get("capability_id")) for x in profiles.get("profile_conflicts",[]) if isinstance(x,dict)}
    for cid in profiles.get("expected_capabilities",[]):
        cid=str(cid)
        if cid in conflicts:continue
        item=caps.get(cid);state=str(item.get("state")) if item else "unknown"
        if state in {"operational","not_applicable"}:continue
        refs=list(ids)
        if item and isinstance(item.get("evidence"),dict):refs += [str(x) for x in item["evidence"].get("references",[])]
        out.append(_rec(f"BASE-{cid.replace('_','-').upper()}","baseline_capability",f"Establish baseline capability: {cid}",model=model,cap=cid,invariant=f"Detected profiles expect {cid} unless evidence excludes it.",refs=refs,basis=f"Composable profiles {ids} expect this capability; current state is {state}. Historical failure is not required.",confidence="medium" if ids else "low",steps=["Confirm the applicable executable command or oracle.","Implement an operational control rather than a nominal file.","Add a negative or no-op case against overclaiming."],code="BASELINE_CAPABILITY_GAP",message=f"Detected profiles expect {cid}, but its state is {state}.",hint=f"Implement and test operational {cid}, or record an evidence-based exclusion.",complexity_hint=2))
    return out

def assign_decisions(items:list[dict[str,object]],*,mode:str,max_phase_1_items:int)->list[dict[str,object]]:
    ordered=sorted(items,key=lambda x:(-int(x["ranking"]["ordinal_total"]),str(x["source"]),str(x["recommendation_id"])));used=0
    for item in ordered:
        band=item["ranking"]["priority_band"];confidence=item["evidence"]["confidence"]
        if mode==MINIMAL_SAFE_CI and item["source"]=="baseline_capability":item["decision"]="deferred"
        elif band=="high" and confidence in {"high","medium"} and used<max_phase_1_items:item["decision"]="phase_1";used+=1
        elif band in {"high","medium"} or (band=="low" and mode==DEEP_REPOSITORY_UPGRADE):item["decision"]="phase_2"
        else:item["decision"]="deferred"
    return ordered

def generate_recommendations(model:dict[str,object],history:dict[str,object],telemetry:dict[str,object],profile_contributions:dict[str,object],*,mode:str,max_phase_1_items:int)->dict[str,object]:
    observed=observed_failure_recommendations(model,history,telemetry);structural=structural_invariant_recommendations(model);baseline=baseline_capability_recommendations(model,profile_contributions) if mode==DEEP_REPOSITORY_UPGRADE else []
    ranked=assign_decisions([*observed,*structural,*baseline],mode=mode,max_phase_1_items=max_phase_1_items)
    return {"observed_failures":[x for x in ranked if x["source"]=="observed_failure"],"structural_invariants":[x for x in ranked if x["source"]=="structural_invariant"],"baseline_capabilities":[x for x in ranked if x["source"]=="baseline_capability"],"ranked":ranked}
