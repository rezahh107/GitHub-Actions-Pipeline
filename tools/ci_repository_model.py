"""Deterministic repository model from manifests, workflows, tests, and contracts."""
from __future__ import annotations

import json, os, tomllib
from pathlib import Path
from typing import Iterable
from tools.ci_upgrade_models import CAPABILITY_STATES, diagnostic, evidence

SKIP={".git",".venv","venv","node_modules","__pycache__",".pytest_cache",".mypy_cache",".ruff_cache",".tox","dist","build"}
LANG={".py":"Python",".js":"JavaScript",".jsx":"JavaScript",".mjs":"JavaScript",".cjs":"JavaScript",".ts":"TypeScript",".tsx":"TypeScript",".json":"JSON",".md":"Markdown",".yml":"YAML",".yaml":"YAML",".php":"PHP",".toml":"TOML",".go":"Go",".rs":"Rust",".rb":"Ruby",".cs":"C#",".java":"Java",".sh":"Shell",".html":"HTML",".css":"CSS"}
MANIFEST={"pyproject.toml","setup.py","setup.cfg","requirements.txt","package.json","composer.json","Cargo.toml","go.mod","pom.xml","build.gradle"}
LOCK={"uv.lock","poetry.lock","Pipfile.lock","requirements.lock","package-lock.json","pnpm-lock.yaml","yarn.lock","composer.lock","Cargo.lock"}
CONFIG={"tox.ini","pytest.ini","mypy.ini","ruff.toml",".ruff.toml","tsconfig.json","vite.config.js","vite.config.ts","webpack.config.js","webpack.config.ts"}
TEST_CMD=("pytest","python -m unittest","unittest discover","npm test","npm run test","pnpm test","yarn test","vitest","jest")
BUILD_CMD=("npm run build","pnpm build","yarn build","python -m build","cargo build","go build","mvn package","gradle build")
SCHEMA_CMD=("jsonschema","check-jsonschema","schema","validate")
RELEASE_CMD=("twine check","npm pack","python -m build","cargo package","gh release")
GENERATED_CMD=("git diff --exit-code","generated","codegen","generate")


def iter_files(root:Path)->Iterable[Path]:
    for current,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files): yield Path(current)/name

def rel(root:Path,path:Path)->str:return path.relative_to(root).as_posix()

def _text(path:Path,limit:int=2_000_000)->str|None:
    try:
        if path.stat().st_size>limit:return None
        return path.read_text(encoding="utf-8")
    except (OSError,UnicodeDecodeError):return None

def _load(path:Path)->tuple[object|None,str|None]:
    text=_text(path)
    if text is None:return None,"unreadable"
    try:
        if path.suffix.lower()==".json":return json.loads(text),None
        if path.suffix.lower()==".toml":return tomllib.loads(text),None
        import yaml
        return yaml.safe_load(text),None
    except (json.JSONDecodeError,tomllib.TOMLDecodeError,ImportError,Exception) as exc:
        # Keep parser failures as evidence limitations; do not guess the document.
        return None,type(exc).__name__.lower()

def _test(path:str)->bool:
    lower=f"/{path.lower()}"; name=path.rsplit("/",1)[-1].lower()
    return "/tests/" in lower or "/test/" in lower or name.startswith("test_") or name.endswith("_test.py") or ".test." in name or ".spec." in name

def _negative(path:Path)->bool:
    text=(_text(path) or "").lower()
    return any(x.lower() in text for x in ("assertRaises","raises(","rejects","invalid","malformed","negative","error case"))

def _on(value:object)->list[str]:
    if isinstance(value,str):return [value]
    if isinstance(value,list):return sorted(str(x) for x in value)
    if isinstance(value,dict):return sorted(str(x) for x in value)
    return []

def parse_workflow(root:Path,path:Path)->tuple[dict[str,object],list[dict[str,object]]]:
    data,error=_load(path); rp=rel(root,path)
    base={"path":rp,"parse_status":error or "invalid_shape","name":None,"triggers":[],"permissions":{},"jobs":[],"commands":[]}
    if error or not isinstance(data,dict):
        return base,[diagnostic("WORKFLOW_PARSE_FAILED",f"Could not parse workflow {rp}: {error or 'invalid shape'}.",affected_area="workflow_model",evidence_references=[rp],repair_hint=f"Repair YAML syntax or shape in {rp}.")]
    on=data.get("on",data.get(True)); permissions=data.get("permissions",{})
    if isinstance(permissions,dict):permissions={str(k):str(v) for k,v in sorted(permissions.items())}
    elif not isinstance(permissions,str):permissions={}
    jobs=[]; commands=[]
    raw_jobs=data.get("jobs",{})
    if isinstance(raw_jobs,dict):
        for jid,job in sorted(raw_jobs.items(),key=lambda x:str(x[0])):
            if not isinstance(job,dict):continue
            steps=[]
            for index,step in enumerate(job.get("steps",[]) if isinstance(job.get("steps"),list) else []):
                if not isinstance(step,dict):continue
                run=step.get("run"); uses=step.get("uses")
                if isinstance(run,str):commands += [line.strip() for line in run.splitlines() if line.strip()]
                steps.append({"index":index,"name":step.get("name") if isinstance(step.get("name"),str) else None,"uses":uses if isinstance(uses,str) else None,"run":run if isinstance(run,str) else None})
            jobs.append({"job_id":str(jid),"name":job.get("name") if isinstance(job.get("name"),str) else None,"runs_on":job.get("runs-on") if isinstance(job.get("runs-on"),str) else None,"permissions":job.get("permissions") if isinstance(job.get("permissions"),(dict,str)) else None,"steps":steps})
    return {"path":rp,"parse_status":"parsed","name":data.get("name") if isinstance(data.get("name"),str) else None,"triggers":_on(on),"permissions":permissions,"jobs":jobs,"commands":sorted(set(commands))},[]

def _manifest(path:Path,rp:str)->dict[str,object]:
    if path.name=="package.json":
        data,error=_load(path); data=data if isinstance(data,dict) else {}
        scripts=data.get("scripts",{}) if isinstance(data.get("scripts"),dict) else {}
        work=data.get("workspaces",[])
        if isinstance(work,dict):work=work.get("packages",[])
        return {"path":rp,"kind":"package_json","parse_status":error or "parsed","scripts":{str(k):str(v) for k,v in sorted(scripts.items())},"dependencies":sorted(str(k) for k in (data.get("dependencies") or {}) if isinstance(data.get("dependencies"),dict)),"dev_dependencies":sorted(str(k) for k in (data.get("devDependencies") or {}) if isinstance(data.get("devDependencies"),dict)),"workspaces":sorted(str(x) for x in work) if isinstance(work,list) else []}
    if path.name=="pyproject.toml":
        data,error=_load(path); data=data if isinstance(data,dict) else {}; project=data.get("project",{}) if isinstance(data.get("project"),dict) else {}; scripts=project.get("scripts",{}) if isinstance(project.get("scripts"),dict) else {}; deps=project.get("dependencies",[]) if isinstance(project.get("dependencies"),list) else []; build=data.get("build-system",{}) if isinstance(data.get("build-system"),dict) else {}
        return {"path":rp,"kind":"pyproject","parse_status":error or "parsed","scripts":{str(k):str(v) for k,v in sorted(scripts.items())},"dependencies":sorted(str(x) for x in deps),"build_backend":build.get("build-backend")}
    return {"path":rp,"kind":path.name,"parse_status":"observed_only"}

def _has(commands:list[str],patterns:tuple[str,...])->bool:
    text="\n".join(commands).lower(); return any(x.lower() in text for x in patterns)

def _cap(cid:str,state:str,refs:list[str],why:str,hint:str|None=None)->dict[str,object]:
    if state not in CAPABILITY_STATES:raise ValueError(f"invalid capability state: {state}")
    out={"capability_id":cid,"state":state,"evidence":evidence("observed" if refs else "unavailable",refs,why)}
    if hint:out["repair_hint"]=hint
    return out

def build_repository_model(root:Path)->dict[str,object]:
    root=root.resolve(); files=list(iter_files(root)); paths=sorted(rel(root,p) for p in files); pmap={rel(root,p):p for p in files}
    languages=sorted({LANG[p.suffix.lower()] for p in files if p.suffix.lower() in LANG})
    manifests=sorted(p for p in paths if p.rsplit("/",1)[-1] in MANIFEST); locks=sorted(p for p in paths if p.rsplit("/",1)[-1] in LOCK); configs=sorted(p for p in paths if p.rsplit("/",1)[-1] in CONFIG)
    tests=sorted(p for p in paths if _test(p)); negative=sorted(p for p in tests if _negative(pmap[p])); schemas=sorted(p for p in paths if p.lower().endswith(".json") and "schema" in p.lower()); validators=sorted(p for p in paths if any(x in p.lower() for x in ("validat","check_","audit")) and p.lower().endswith((".py",".js",".ts",".sh"))); examples=sorted(p for p in paths if p.startswith("examples/") or "/examples/" in f"/{p}")
    generated=sorted(p for p in paths if any(x in p.lower() for x in ("generated","dist/","build/"))); releases=sorted(p for p in paths if any(x in p.lower() for x in ("release","publish","deploy","changelog")))
    parsed=[]; frameworks=set(); builds=set(); entries=[]; workspaces=[]
    for rp in manifests:
        item=_manifest(pmap[rp],rp); parsed.append(item); deps="\n".join(str(x) for x in item.get("dependencies",[])+item.get("dev_dependencies",[])).lower()
        for token,name in (("fastapi","FastAPI"),("django","Django"),("flask","Flask"),("celery","Celery"),("pyside","PySide"),("pyqt","PyQt"),("torch","PyTorch"),("tensorflow","TensorFlow"),("react","React"),("next","Next.js"),("vite","Vite"),("express","Express"),("fastify","Fastify")):
            if token in deps:frameworks.add(name)
        if item.get("build_backend"):builds.add(str(item["build_backend"]))
        if item.get("scripts"):builds.add("package_scripts")
        for name,target in item.get("scripts",{}).items():
            if item["kind"]=="pyproject" or name in {"start","serve","dev","cli"}:entries.append({"source":rp,"name":name,"target":target})
        workspaces += list(item.get("workspaces",[]))
    wf_paths=sorted(p for p in paths if p.startswith(".github/workflows/") and p.lower().endswith((".yml",".yaml"))); workflows=[]; diags=[]
    for rp in wf_paths:
        wf,ds=parse_workflow(root,pmap[rp]); workflows.append(wf); diags+=ds
    commands=sorted({c for w in workflows for c in w.get("commands",[]) if isinstance(c,str)}); roots=sorted({str(Path(p).parent.as_posix()) for p in manifests}) or ["."]
    components=[]
    for cr in roots:
        prefix="" if cr=="." else cr.rstrip("/")+"/"; cms=[p for p in manifests if p.startswith(prefix)]; cts=[p for p in tests if p.startswith(prefix)]
        components.append({"component_id":"root" if cr=="." else cr.replace("/","::"),"root":cr,"manifests":cms,"tests":cts,"evidence":evidence("observed",cms or cts,"Component boundary derived from manifest locations; no semantic boundary is inferred beyond those files.",confidence="medium")})
    monorepo=len(roots)>1 or bool(workspaces); archetypes=[]
    if "Python" in languages:archetypes.append("python")
    if {"JavaScript","TypeScript"}&set(languages):archetypes.append("javascript-typescript")
    if schemas:archetypes.append("contract-schema")
    if languages and set(languages)<={"Markdown","YAML","JSON"} and not manifests:archetypes.append("documentation-only")
    if monorepo:archetypes.append("monorepo")
    if any("manifest.json" in p.lower() for p in paths):archetypes.append("browser-extension")
    test_ok=_has(commands,TEST_CMD); build_ok=_has(commands,BUILD_CMD); schema_ok=_has(commands,SCHEMA_CMD); release_ok=_has(commands,RELEASE_CMD); gen_ok=_has(commands,GENERATED_CMD); pr=any("pull_request" in w.get("triggers",[]) for w in workflows)
    installs=[c for c in commands if any(x in c.lower() for x in ("pip install","npm ci","pnpm install","yarn install","uv sync"))]; reproducible=bool(locks and any(x in "\n".join(installs).lower() for x in ("npm ci","--frozen-lockfile","uv sync","pip install -r")))
    explicit=[str(w["path"]) for w in workflows if w.get("permissions")]; weak=any(w.get("permissions")=="write-all" or isinstance(w.get("permissions"),dict) and any(str(v).lower()=="write" for v in w["permissions"].values()) for w in workflows)
    caps=[
      _cap("tests_present","operational" if tests else "absent",tests,"Test files are present." if tests else "No test files were observed.","Add deterministic tests for critical behavior." if not tests else None),
      _cap("tests_run_on_pull_requests","operational" if test_ok and pr else "nominal" if tests and workflows else "absent",[w["path"] for w in workflows if "pull_request" in w.get("triggers",[])]+tests,"A pull-request workflow executes a recognized test command." if test_ok and pr else "Tests or workflows exist, but no pull-request workflow was proven to execute a recognized test command.","Wire the repository's real test command into a pull_request workflow."),
      _cap("build_verified","operational" if build_ok else "nominal" if any("build" in str(i.get("scripts",{})).lower() for i in parsed) else "absent",wf_paths+[i["path"] for i in parsed if "build" in str(i.get("scripts",{})).lower()],"Build command execution was inspected in workflow steps.","Add the existing build command to CI and report its component path."),
      _cap("reproducible_dependency_install","operational" if reproducible else "partial" if locks else "absent",locks+wf_paths,"A lockfile and deterministic install command were both observed." if reproducible else "A lockfile or deterministic install command is missing or not connected.","Use the ecosystem's frozen or lockfile-enforcing install command."),
      _cap("schema_validation","operational" if schemas and schema_ok else "nominal" if schemas else "not_applicable",schemas+wf_paths,"Schemas exist and a validation-oriented CI command was observed." if schemas and schema_ok else "Schemas exist but operational CI validation was not proven." if schemas else "No schema files were observed.","Connect schema, examples, and malformed-input tests to one deterministic validator." if schemas else None),
      _cap("negative_parser_validator_tests","operational" if negative else "nominal" if validators or schemas else "not_applicable",negative+validators+schemas,"Negative or malformed-input tests were observed." if negative else "Validators or schemas exist, but negative coverage was not observed." if validators or schemas else "No parser, validator, or schema surface was observed.","Add malformed, boundary, and rejected-input fixtures with stable diagnostics." if validators or schemas else None),
      _cap("generated_artifact_validation","operational" if generated and gen_ok else "nominal" if generated else "unknown",generated+wf_paths,"Generated candidates and a regeneration or diff check were observed." if generated and gen_ok else "Generated-looking paths exist, but source linkage or verification was not proven." if generated else "No declaratively detectable generated artifacts were found.","Declare source-to-generated relationships and verify a clean diff after regeneration."),
      _cap("release_artifact_validation","operational" if release_ok else "nominal" if releases else "unknown",releases+wf_paths,"A release or package verification command was observed." if release_ok else "Release-related files exist, but artifact verification was not proven." if releases else "Release applicability could not be established.","Validate package metadata and produced artifacts before release."),
      _cap("least_privilege_workflow_permissions","operational_but_weak" if weak else "operational" if explicit else "unknown" if workflows else "not_applicable",explicit,"Explicit permissions exist, but at least one workflow grants write scope." if weak else "Explicit workflow permissions were observed." if explicit else "Workflows exist without a proven explicit permission contract." if workflows else "No workflows were observed.","Declare only the permissions needed by each workflow or job." if workflows else None)]
    relationships=[]
    if schemas and examples:relationships.append({"relationship_type":"schema_to_example","sources":schemas,"targets":examples,"state":"derived","rationale":"Relationship is directory- and naming-based; semantic compatibility still requires validator execution."})
    if tests:relationships.append({"relationship_type":"source_to_test","sources":[p for p in paths if p.endswith((".py",".js",".ts",".php",".go",".rs")) and not _test(p)],"targets":tests,"state":"inferred","rationale":"Only path and naming proximity is available; direct coverage is not claimed."})
    return {"model_version":"1.0.0","root":".","file_count":len(paths),"repository_archetypes":sorted(set(archetypes)),"components":components,"languages":languages,"frameworks":sorted(frameworks),"build_systems":sorted(builds),"manifests":parsed,"lockfiles":locks,"config_files":configs,"entry_points":sorted(entries,key=lambda x:(x["source"],x["name"],x["target"])),"test_suites":{"files":tests,"negative_files":negative,"commands_observed_in_ci":[c for c in commands if any(x.lower() in c.lower() for x in TEST_CMD)]},"validators":validators,"schemas":schemas,"examples":examples,"generated_artifacts":generated,"release_paths":releases,"workflows":workflows,"critical_execution_paths":sorted({str(x["target"]) for x in entries}|set(commands)),"relationships":relationships,"capabilities":sorted(caps,key=lambda x:str(x["capability_id"])),"unresolved_evidence":diags,"model_evidence":evidence("derived",paths,"Repository model was deterministically derived from readable files and executable configuration; unsupported semantics remain unresolved.",confidence="high")}
