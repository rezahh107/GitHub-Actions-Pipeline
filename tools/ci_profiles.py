"""Composable capability-profile loading, evidence-rich detection, and conflict-aware merging."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable
from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

DEFAULT_PATH=Path(__file__).resolve().parents[1]/"profiles"/"capability-profiles.v1.json"


def load_profiles(path:Path|None=None)->dict[str,object]:
    source=path or DEFAULT_PATH
    try:data=json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:raise UpgradeContractError("PROFILE_CATALOG_UNAVAILABLE",f"Could not read capability profile catalog {source}: {exc}") from exc
    except json.JSONDecodeError as exc:raise UpgradeContractError("PROFILE_CATALOG_INVALID_JSON",f"Capability profile catalog {source} is not valid JSON: {exc}") from exc
    if not isinstance(data,dict) or not isinstance(data.get("profiles"),list):raise UpgradeContractError("PROFILE_CATALOG_INVALID_SHAPE","Capability profile catalog must contain a profiles array.")
    ids=set()
    for profile in data["profiles"]:
        if not isinstance(profile,dict) or not isinstance(profile.get("profile_id"),str):raise UpgradeContractError("PROFILE_CATALOG_INVALID_SHAPE","Every capability profile must contain profile_id.")
        if profile["profile_id"] in ids:raise UpgradeContractError("PROFILE_ID_DUPLICATE",f"Duplicate capability profile id: {profile['profile_id']}.")
        ids.add(profile["profile_id"])
    return data


def _all_paths(model:dict[str,object])->list[str]:
    result=set(str(x) for x in model.get("path_index",[]) if isinstance(x,str))
    for key in ("lockfiles","config_files","validators","schemas","examples","generated_artifacts","release_paths"):
        value=model.get(key)
        if isinstance(value,list):result.update(str(x) for x in value)
    for key in ("manifests","workflows"):
        for item in model.get(key,[]) if isinstance(model.get(key),list) else []:
            if isinstance(item,dict) and isinstance(item.get("path"),str):result.add(item["path"])
    for collection in ("signals","nodes"):
        for signal in model.get("semantic_model",{}).get(collection,[]) if isinstance(model.get("semantic_model"),dict) else []:
            if isinstance(signal,dict) and isinstance(signal.get("source"),str):result.add(signal["source"])
    return sorted(result)


def _manifest_refs(model:dict[str,object],kind:str|None=None,dependency_token:str|None=None)->list[str]:
    refs=[]
    for item in model.get("manifests",[]) if isinstance(model.get("manifests"),list) else []:
        if not isinstance(item,dict):continue
        if kind and item.get("kind")!=kind:continue
        if dependency_token and dependency_token.lower() not in "\n".join(str(x).lower() for x in item.get("dependencies",[])):continue
        if item.get("path"):refs.append(str(item["path"]))
    return sorted(set(refs))


def _criterion(key:str,requested:list[object],observed:set[str],refs:dict[str,list[str]])->dict[str,object]:
    values=sorted(str(x) for x in requested);matched=sorted(set(values)&observed);references=sorted({ref for value in matched for ref in refs.get(value,[])})
    return {"criterion":key,"requested":values,"matched":matched,"references":references,"satisfied":bool(matched)}


def _evaluate_rule(model:dict[str,object],rule:dict[str,object])->tuple[bool,list[dict[str,object]]]:
    languages=set(str(x) for x in model.get("languages",[]));frameworks=set(str(x) for x in model.get("frameworks",[]));archetypes=set(str(x) for x in model.get("repository_archetypes",[]));manifest_kinds={str(x.get("kind")) for x in model.get("manifests",[]) if isinstance(x,dict)};paths=_all_paths(model);entry_points=model.get("entry_points",[]);semantic_signals={str(x.get("signal_type")) for x in model.get("semantic_model",{}).get("signals",[]) if isinstance(x,dict)}
    language_refs={lang:[p for p in paths if Path(p).suffix.lower() in {ext for ext,name in {".py":"Python",".js":"JavaScript",".jsx":"JavaScript",".ts":"TypeScript",".tsx":"TypeScript",".php":"PHP",".go":"Go",".rs":"Rust"}.items() if name==lang}] for lang in languages}
    framework_refs={fw:_manifest_refs(model,dependency_token=fw.lower().replace(".js","")) for fw in frameworks}
    archetype_refs={a:(_manifest_refs(model) if a in {"python","javascript-typescript","monorepo"} else [*model.get("schemas",[])] if a=="contract-schema" else paths) for a in archetypes}
    kind_refs={kind:_manifest_refs(model,kind=kind) for kind in manifest_kinds}
    signal_refs={sig:sorted(str(x.get("source")) for x in model.get("semantic_model",{}).get("signals",[]) if isinstance(x,dict) and x.get("signal_type")==sig and x.get("source")) for sig in semantic_signals}
    checks=[]
    for key,observed,refs in (("languages_any",languages,language_refs),("frameworks_any",frameworks,framework_refs),("archetypes_any",archetypes,archetype_refs),("manifest_kinds_any",manifest_kinds,kind_refs),("semantic_signals_any",semantic_signals,signal_refs)):
        if key in rule:
            values=rule[key]
            if not isinstance(values,list):return False,[]
            checks.append(_criterion(key,values,observed,refs))
    if "entry_point_required" in rule:
        required=bool(rule["entry_point_required"]);present=bool(entry_points);refs=sorted(str(x.get("source")) for x in entry_points if isinstance(x,dict) and x.get("source"));checks.append({"criterion":"entry_point_required","requested":[required],"matched":[present] if present==required else [],"references":refs,"satisfied":present==required})
    if "path_tokens_any" in rule:
        values=rule["path_tokens_any"]
        if not isinstance(values,list):return False,[]
        matches=sorted({p for p in paths if any(str(token).lower() in p.lower() for token in values)});checks.append({"criterion":"path_tokens_any","requested":sorted(str(x) for x in values),"matched":matches,"references":matches,"satisfied":bool(matches)})
    return bool(checks) and all(bool(x["satisfied"]) for x in checks),checks


def detect_profiles(model:dict[str,object],catalog:dict[str,object])->list[dict[str,object]]:
    matches=[]
    for profile in sorted(catalog["profiles"],key=lambda x:str(x.get("profile_id",""))):
        rule=profile.get("detect")
        if not isinstance(rule,dict):continue
        matched,signals=_evaluate_rule(model,rule)
        if not matched:continue
        refs=sorted({ref for signal in signals for ref in signal.get("references",[])})
        independent=len([s for s in signals if s.get("satisfied")]);authoritative=any(s["criterion"] in {"frameworks_any","manifest_kinds_any","entry_point_required","semantic_signals_any"} for s in signals)
        confidence="high" if independent>=2 or authoritative and any(s["criterion"]=="semantic_signals_any" for s in signals) else "medium"
        matches.append({"profile_id":profile["profile_id"],"category":profile["category"],"matched_signals":signals,"evidence":evidence("derived",refs,"Profile matched all explicit catalog criteria. Confidence is based on the number and authority of independent signals.",confidence=confidence)})
    return matches


def compose_profile_contributions(matches:Iterable[dict[str,object]],catalog:dict[str,object])->dict[str,object]:
    by_id={p["profile_id"]:p for p in catalog["profiles"] if isinstance(p,dict)};selected=[];invariants=set();failures=set();checks=set();notes=set();expected_by={};excluded_by={}
    for match in sorted(matches,key=lambda x:str(x["profile_id"])):
        pid=str(match["profile_id"]);profile=by_id[pid];selected.append(pid)
        invariants.update(str(x) for x in profile.get("structural_invariants",[]));failures.update(str(x) for x in profile.get("common_failure_modes",[]));checks.update(str(x) for x in profile.get("candidate_checks",[]))
        if isinstance(profile.get("cost_noise"),str):notes.add(str(profile["cost_noise"]))
        for cap in profile.get("expected_capabilities",[]):expected_by.setdefault(str(cap),set()).add(pid)
        for cap in profile.get("exclusions",[]):excluded_by.setdefault(str(cap),set()).add(pid)
    contributions=[];conflicts=[];all_caps=sorted(set(expected_by)|set(excluded_by));expected=[];exclusions=[]
    for cap in all_caps:
        exp=sorted(expected_by.get(cap,set()));exc=sorted(excluded_by.get(cap,set()))
        if exp and exc:resolution="conflict";conflicts.append({"capability_id":cap,"expected_by":exp,"excluded_by":exc,"resolution":"unresolved"})
        elif exp:resolution="expected";expected.append(cap)
        else:resolution="excluded";exclusions.append(cap)
        contributions.append({"capability_id":cap,"expected_by":exp,"excluded_by":exc,"resolution":resolution})
    return {"profile_contract_version":catalog["profile_contract_version"],"selected_profiles":selected,"expected_capabilities":expected,"structural_invariants":sorted(invariants),"common_failure_modes":sorted(failures),"candidate_checks":sorted(checks),"exclusions":exclusions,"cost_noise_notes":sorted(notes),"capability_contributions":contributions,"profile_conflicts":conflicts}


def profile_conflict_diagnostics(composition:dict[str,object])->list[dict[str,object]]:
    return [diagnostic("PROFILE_CAPABILITY_CONFLICT",f"Capability {item['capability_id']} is expected and excluded by different matched profiles.",affected_area="profile_composition",evidence_references=[*item["expected_by"],*item["excluded_by"]],repair_hint="Refine profile detection or add a versioned precedence/exclusion rule before using this capability for recommendations.") for item in composition.get("profile_conflicts",[]) if isinstance(item,dict)]
