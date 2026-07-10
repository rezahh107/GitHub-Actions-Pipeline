"""Opt-in, recipe-bound implementation planning and atomic application.

Report generation is read-only. Mutation requires an explicit recipe allowlist, a clean
Git worktree, and an exact expected HEAD SHA. Repository commands are never executed by
this module because checked-out code and scripts are untrusted input.
"""
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from tools.ci_models import run_git
from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

DEFAULT_RECIPES=Path(__file__).resolve().parents[1]/"profiles"/"implementation-recipes.v1.json"
CHECKOUT_SHA="11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_PYTHON_SHA="a26af69be951a213d495a4c3e4e4022e16d87065"


def _sha(text:str)->str:return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_recipes(path:Path|None=None)->dict[str,object]:
    source=path or DEFAULT_RECIPES
    try:data=json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:raise UpgradeContractError("IMPLEMENTATION_RECIPES_UNAVAILABLE",f"Could not read implementation recipes {source}: {exc}") from exc
    except json.JSONDecodeError as exc:raise UpgradeContractError("IMPLEMENTATION_RECIPES_INVALID_JSON",f"Implementation recipes {source} are invalid JSON: {exc}") from exc
    if not isinstance(data,dict) or data.get("implementation_recipe_version")!="1.0.0" or not isinstance(data.get("recipes"),list):raise UpgradeContractError("IMPLEMENTATION_RECIPES_INVALID_SHAPE","Implementation recipe registry must use version 1.0.0 and contain recipes.")
    return data


def _cap_state(model:dict[str,object],capability_id:str)->str:
    for item in model.get("capabilities",[]):
        if isinstance(item,dict) and item.get("capability_id")==capability_id:return str(item.get("state"))
    return "unknown"

def _unique_candidate(model:dict[str,object],category:str,prefix:str)->tuple[str|None,list[dict[str,object]]]:
    candidates=[x for x in model.get("command_candidates",{}).get(category,[]) if isinstance(x,dict) and isinstance(x.get("command"),str) and str(x["command"]).startswith(prefix)]
    unique={str(x["command"]):x for x in candidates}
    return (next(iter(unique)) if len(unique)==1 else None),sorted(unique.values(),key=lambda x:str(x["command"]))

def _python_workflow(install_command:str,test_command:str)->str:
    return f'''name: Repository Upgrade Tests

on:
  pull_request:

permissions:
  contents: read

concurrency:
  group: repository-upgrade-tests-${{{{ github.event.pull_request.number || github.ref }}}}
  cancel-in-progress: true

jobs:
  tests:
    name: repository-upgrade-tests
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - name: Checkout
        uses: actions/checkout@{CHECKOUT_SHA}
        with:
          fetch-depth: 1
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@{SETUP_PYTHON_SHA}
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: {install_command}
      - name: Run tests
        run: {test_command}
'''

def build_implementation_package(report:dict[str,object],repo_root:Path,recipe_catalog:dict[str,object]|None=None)->dict[str,object]:
    catalog=recipe_catalog or load_recipes();model=report["repository_model"];root=repo_root.resolve();phase1=report.get("staged_upgrade",{}).get("phase_1",[]);by_rec={str(x.get("recommendation_id")):x for x in phase1 if isinstance(x,dict)};actions=[]
    for recipe in sorted(catalog["recipes"],key=lambda x:str(x.get("recipe_id"))):
        matched=next((rid for rid in recipe.get("recommendation_ids",[]) if rid in by_rec),None)
        if not matched:continue
        rid=str(recipe["recipe_id"]);target=str(recipe["target_path"]);pre=[];cap=str(recipe["affected_capability"]);state=_cap_state(model,cap)
        pre.append({"precondition_id":"capability_not_operational","status":"pass" if state not in {"operational","not_applicable"} else "fail","evidence":[cap,state]})
        pre.append({"precondition_id":"supported_language","status":"pass" if recipe.get("supported_language") in model.get("languages",[]) else "fail","evidence":[str(recipe.get("supported_language"))]})
        install,install_evidence=_unique_candidate(model,"install","python ");test,test_evidence=_unique_candidate(model,"test","python ")
        pre.append({"precondition_id":"unique_install_command","status":"pass" if install else "fail","evidence":[str(x.get("basis")) for x in install_evidence]})
        pre.append({"precondition_id":"unique_test_command","status":"pass" if test else "fail","evidence":[str(x.get("basis")) for x in test_evidence]})
        destination=root/target
        pre.append({"precondition_id":"target_absent","status":"pass" if not destination.exists() else "fail","evidence":[target]})
        content=_python_workflow(install,test) if install and test else None;status="applicable" if content and all(x["status"]=="pass" for x in pre) else "blocked"
        diags=[]
        if status=="blocked":diags.append(diagnostic("IMPLEMENTATION_RECIPE_BLOCKED",f"Recipe {rid} cannot be applied because one or more deterministic preconditions failed.",affected_area=target,evidence_references=[str(x) for p in pre for x in p["evidence"]],repair_hint="Resolve ambiguous commands, unsupported language, existing target path, or operational capability before applying."))
        actions.append({"action_id":f"action:{rid}:{matched}","recipe_id":rid,"recommendation_id":matched,"status":status,"operation":"create_file","path":target,"content_sha256":_sha(content) if content else None,"proposed_content":content,"preconditions":pre,"validation_commands":list(recipe.get("validation_commands",[])),"diagnostics":diags,"evidence":evidence("derived",[matched,*[str(x.get("basis")) for x in install_evidence+test_evidence]],"Action was produced only from a versioned recipe and deterministic command-resolution preconditions.",confidence="high" if status=="applicable" else "medium")})
    counts={state:sum(1 for x in actions if x["status"]==state) for state in ("applicable","blocked","unsupported")}
    return {"implementation_contract_version":"1.0.0","mutation_default":"dry_run","repository":report.get("repository"),"analysis_basis_sha256":report.get("analysis_basis_sha256"),"actions":actions,"summary":counts,"security_boundary":"No repository command is executed. Applying requires exact HEAD, clean worktree, explicit recipe allowlist, and non-overwriting atomic writes."}

def _git_head_and_clean(root:Path)->tuple[str,str]:
    ok,head=run_git(root,["rev-parse","HEAD"])
    if not ok:raise UpgradeContractError("IMPLEMENTATION_GIT_HEAD_UNAVAILABLE",f"Could not resolve Git HEAD: {head}")
    ok,status=run_git(root,["status","--porcelain"])
    if not ok:raise UpgradeContractError("IMPLEMENTATION_GIT_STATUS_UNAVAILABLE",f"Could not inspect Git status: {status}")
    return head,status

def apply_implementation_package(repo_root:Path,package:dict[str,object],*,allowed_recipe_ids:set[str],expected_head_sha:str)->dict[str,object]:
    if len(expected_head_sha)!=40 or any(c not in "0123456789abcdefABCDEF" for c in expected_head_sha):raise UpgradeContractError("IMPLEMENTATION_EXPECTED_HEAD_INVALID","expected_head_sha must be a 40-character hexadecimal Git SHA.")
    root=repo_root.resolve();head,status=_git_head_and_clean(root)
    if head.lower()!=expected_head_sha.lower():raise UpgradeContractError("IMPLEMENTATION_HEAD_MISMATCH",f"Expected HEAD {expected_head_sha}, found {head}.")
    if status.strip():raise UpgradeContractError("IMPLEMENTATION_WORKTREE_DIRTY","Refusing implementation because the Git worktree is not clean.")
    if not allowed_recipe_ids:raise UpgradeContractError("IMPLEMENTATION_RECIPE_ALLOWLIST_REQUIRED","At least one --allow-recipe value is required.")
    results=[];created=[]
    try:
        for action in package.get("actions",[]):
            if not isinstance(action,dict):continue
            recipe=str(action.get("recipe_id"));path=str(action.get("path"));content=action.get("proposed_content")
            if recipe not in allowed_recipe_ids:results.append({"action_id":action.get("action_id"),"status":"skipped","reason":"recipe_not_allowlisted"});continue
            if action.get("status")!="applicable" or action.get("operation")!="create_file" or not isinstance(content,str):results.append({"action_id":action.get("action_id"),"status":"skipped","reason":"action_not_applicable"});continue
            destination=(root/path).resolve()
            try:destination.relative_to(root)
            except ValueError:raise UpgradeContractError("IMPLEMENTATION_PATH_ESCAPE",f"Action path escapes repository root: {path}")
            if destination.exists() or destination.is_symlink():raise UpgradeContractError("IMPLEMENTATION_TARGET_EXISTS",f"Refusing to overwrite or follow existing target: {path}")
            if _sha(content)!=action.get("content_sha256"):raise UpgradeContractError("IMPLEMENTATION_CONTENT_HASH_MISMATCH",f"Proposed content hash mismatch for {path}.")
            destination.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix=destination.name+".",dir=destination.parent,text=True)
            try:
                with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as handle:handle.write(content)
                os.chmod(tmp,0o644)
                os.link(tmp,destination)
                os.unlink(tmp);created.append(destination)
            except Exception:
                try:os.unlink(tmp)
                except OSError:pass
                raise
            results.append({"action_id":action.get("action_id"),"status":"applied","path":path,"content_sha256":_sha(content),"validation_commands":action.get("validation_commands",[]),"validation_status":"not_executed_untrusted_repository_boundary"})
    except Exception:
        for destination in reversed(created):
            try:destination.unlink()
            except OSError:pass
        raise
    return {"implementation_contract_version":"1.0.0","expected_head_sha":expected_head_sha.lower(),"observed_head_sha":head.lower(),"results":results,"repository_commands_executed":False,"transactional_create_rollback":True,"next_step":"Review the diff and run the listed validation commands in an explicitly trusted execution environment."}
