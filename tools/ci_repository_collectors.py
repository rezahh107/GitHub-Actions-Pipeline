"""Deterministic bounded collectors used by the repository model."""
from __future__ import annotations
import json, os, re, tomllib
from pathlib import Path
import yaml
from tools.ci_upgrade_models import CAPABILITY_STATES, diagnostic, evidence


SKIP={".git",".venv","venv","node_modules","__pycache__",".pytest_cache",".mypy_cache",".ruff_cache",".tox"}
MAX_FILES=25_000
MAX_TEXT_BYTES=2_000_000
LANG={".py":"Python",".js":"JavaScript",".jsx":"JavaScript",".mjs":"JavaScript",".cjs":"JavaScript",".ts":"TypeScript",".tsx":"TypeScript",".json":"JSON",".md":"Markdown",".yml":"YAML",".yaml":"YAML",".php":"PHP",".toml":"TOML",".go":"Go",".rs":"Rust",".rb":"Ruby",".cs":"C#",".java":"Java",".sh":"Shell",".html":"HTML",".css":"CSS"}
MANIFEST={"pyproject.toml","setup.py","setup.cfg","requirements.txt","requirements-dev.txt","requirements-test.txt","package.json","composer.json","Cargo.toml","go.mod","pom.xml","build.gradle"}
LOCK={"uv.lock","poetry.lock","Pipfile.lock","requirements.lock","package-lock.json","pnpm-lock.yaml","yarn.lock","composer.lock","Cargo.lock"}
CONFIG={"tox.ini","pytest.ini","mypy.ini","ruff.toml",".ruff.toml","tsconfig.json","vite.config.js","vite.config.ts","webpack.config.js","webpack.config.ts"}
TEST_PATTERNS=("pytest","python -m pytest","python -m unittest","unittest discover","npm test","npm run test","pnpm test","yarn test","vitest","jest")
BUILD_PATTERNS=("npm run build","pnpm build","yarn build","python -m build","cargo build","go build","mvn package","gradle build")
INSTALL_PATTERNS=("pip install","uv sync","npm ci","pnpm install","yarn install","poetry install")
RELEASE_PATTERNS=("twine check","npm pack","python -m build","cargo package","gh release")


def iter_files(root:Path)->tuple[list[Path],bool]:
    result=[]; truncated=False
    for current,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files):
            result.append(Path(current)/name)
            if len(result)>=MAX_FILES:return result,True
    return result,truncated

def rel(root:Path,path:Path)->str:return path.relative_to(root).as_posix()

def _text(path:Path)->str|None:
    try:
        if path.stat().st_size>MAX_TEXT_BYTES:return None
        return path.read_text(encoding="utf-8")
    except (OSError,UnicodeDecodeError):return None

def _load(path:Path)->tuple[object|None,str|None]:
    text=_text(path)
    if text is None:return None,"unreadable_or_too_large"
    try:
        if path.suffix.lower()==".json":return json.loads(text),None
        if path.suffix.lower()==".toml":return tomllib.loads(text),None
        return yaml.safe_load(text),None
    except (json.JSONDecodeError,tomllib.TOMLDecodeError,yaml.YAMLError) as exc:return None,type(exc).__name__

def _is_test(path:str)->bool:
    name=Path(path).name.lower(); lower=f"/{path.lower()}"
    return "/tests/" in lower or "/test/" in lower or name.startswith("test_") or name.endswith("_test.py") or ".test." in name or ".spec." in name

def _negative(path:Path)->bool:
    text=(_text(path) or "").lower()
    return any(x in text for x in ("assertraises","pytest.raises","rejects","invalid","malformed","negative case","error case"))

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
    jobs=[];commands=[];raw_jobs=data.get("jobs",{})
    if isinstance(raw_jobs,dict):
        for jid,job in sorted(raw_jobs.items(),key=lambda x:str(x[0])):
            if not isinstance(job,dict):continue
            steps=[]
            for index,step in enumerate(job.get("steps",[]) if isinstance(job.get("steps"),list) else []):
                if not isinstance(step,dict):continue
                run=step.get("run");uses=step.get("uses")
                if isinstance(run,str):commands.extend(line.strip() for line in run.splitlines() if line.strip())
                steps.append({"index":index,"name":step.get("name") if isinstance(step.get("name"),str) else None,"uses":uses if isinstance(uses,str) else None,"run":run if isinstance(run,str) else None,"working_directory":step.get("working-directory") if isinstance(step.get("working-directory"),str) else None})
            jobs.append({"job_id":str(jid),"name":job.get("name") if isinstance(job.get("name"),str) else None,"runs_on":job.get("runs-on") if isinstance(job.get("runs-on"),str) else None,"permissions":job.get("permissions") if isinstance(job.get("permissions"),(dict,str)) else None,"steps":steps})
    return {"path":rp,"parse_status":"parsed","name":data.get("name") if isinstance(data.get("name"),str) else None,"triggers":_on(on),"permissions":permissions,"jobs":jobs,"commands":sorted(set(commands))},[]

def _parse_requirement_names(text:str)->list[str]:
    names=[]
    for raw in text.splitlines():
        line=raw.split("#",1)[0].strip()
        if not line or line.startswith(("-","git+","http:" ,"https:")):continue
        name=re.split(r"[<>=!~\[; ]",line,1)[0].strip()
        if name:names.append(name)
    return sorted(set(names))

def _manifest(path:Path,rp:str)->dict[str,object]:
    if path.name=="package.json":
        data,error=_load(path);data=data if isinstance(data,dict) else {};scripts=data.get("scripts",{}) if isinstance(data.get("scripts"),dict) else {};work=data.get("workspaces",[])
        if isinstance(work,dict):work=work.get("packages",[])
        deps={**(data.get("dependencies") if isinstance(data.get("dependencies"),dict) else {}),**(data.get("devDependencies") if isinstance(data.get("devDependencies"),dict) else {})}
        return {"path":rp,"kind":"package_json","parse_status":error or "parsed","scripts":{str(k):str(v) for k,v in sorted(scripts.items())},"dependencies":sorted(str(k) for k in deps),"workspaces":sorted(str(x) for x in work) if isinstance(work,list) else [],"package_name":data.get("name") if isinstance(data.get("name"),str) else None}
    if path.name=="pyproject.toml":
        data,error=_load(path);data=data if isinstance(data,dict) else {};project=data.get("project",{}) if isinstance(data.get("project"),dict) else {};scripts=project.get("scripts",{}) if isinstance(project.get("scripts"),dict) else {};deps=project.get("dependencies",[]) if isinstance(project.get("dependencies"),list) else [];build=data.get("build-system",{}) if isinstance(data.get("build-system"),dict) else {};tool=data.get("tool",{}) if isinstance(data.get("tool"),dict) else {}
        workspace=[]
        for value in tool.values():
            if isinstance(value,dict) and isinstance(value.get("workspace"),dict) and isinstance(value["workspace"].get("members"),list):workspace.extend(str(x) for x in value["workspace"]["members"])
        return {"path":rp,"kind":"pyproject","parse_status":error or "parsed","scripts":{str(k):str(v) for k,v in sorted(scripts.items())},"dependencies":sorted(str(x) for x in deps),"build_backend":build.get("build-backend"),"workspaces":sorted(set(workspace)),"package_name":project.get("name") if isinstance(project.get("name"),str) else None}
    if path.name.startswith("requirements") and path.suffix==".txt":
        text=_text(path) or ""
        return {"path":rp,"kind":"requirements","parse_status":"parsed" if text else "empty_or_unreadable","dependencies":_parse_requirement_names(text),"scripts":{},"workspaces":[]}
    return {"path":rp,"kind":path.name,"parse_status":"observed_only","scripts":{},"dependencies":[],"workspaces":[]}

def _has(commands:list[str],patterns:tuple[str,...])->bool:
    text="\n".join(commands).lower();return any(x.lower() in text for x in patterns)

def _cap(cid:str,state:str,refs:list[str],why:str,hint:str|None=None)->dict[str,object]:
    if state not in CAPABILITY_STATES:raise ValueError(f"invalid capability state: {state}")
    out={"capability_id":cid,"state":state,"evidence":evidence("observed" if refs else "unavailable",refs,why,confidence="high" if state in {"operational","not_applicable"} else "medium")}
    if hint:out["repair_hint"]=hint
    return out

def _expand_workspace_roots(root:Path,patterns:list[str])->list[str]:
    roots=set()
    for pattern in patterns:
        for match in sorted(root.glob(pattern)):
            if match.is_dir():roots.add(match.relative_to(root).as_posix())
    return sorted(roots)

def _nearest_component(path:str,roots:list[str])->str:
    matches=[r for r in roots if r=="." or path==r or path.startswith(r.rstrip("/")+"/")]
    return max(matches,key=lambda x:(len(x),x)) if matches else "."

def _command_candidates(parsed:list[dict[str,object]],paths:list[str],tests:list[str])->dict[str,list[dict[str,object]]]:
    out={"install":[],"test":[],"build":[],"schema":[],"release":[]}
    names={Path(p).name for p in paths}
    if any(m.get("kind") in {"pyproject","requirements"} for m in parsed):
        if "requirements-test.txt" in names:out["install"].append({"command":"python -m pip install -r requirements-test.txt","basis":"requirements-test.txt","confidence":"high"})
        elif "requirements.txt" in names:out["install"].append({"command":"python -m pip install -r requirements.txt","basis":"requirements.txt","confidence":"high"})
        elif any(m.get("kind")=="pyproject" for m in parsed):out["install"].append({"command":"python -m pip install .","basis":"pyproject.toml","confidence":"medium"})
        if tests:
            if any("pytest" in str(m.get("dependencies",[])).lower() for m in parsed) or "pytest.ini" in names:out["test"].append({"command":"python -m pytest","basis":"pytest dependency/config","confidence":"high"})
            else:out["test"].append({"command":"python -m unittest discover -s tests","basis":"Python test paths without pytest evidence","confidence":"medium"})
        if any(m.get("build_backend") for m in parsed):out["build"].append({"command":"python -m build","basis":"pyproject build-system","confidence":"high"})
    for manifest in parsed:
        if manifest.get("kind")!="package_json":continue
        source=str(manifest.get("path"));scripts=manifest.get("scripts",{})
        if "package-lock.json" in names:out["install"].append({"command":"npm ci","basis":"package-lock.json","component":str(Path(source).parent),"confidence":"high"})
        for key,category in (("test","test"),("build","build")):
            if isinstance(scripts,dict) and key in scripts:out[category].append({"command":f"npm run {key}" if key!="test" else "npm test","basis":source,"component":str(Path(source).parent),"confidence":"high"})
    for test in tests:
        text=(Path(test).name+" "+test).lower()
        if "schema" in text:out["schema"].append({"command":"canonical test command","basis":test,"confidence":"medium"})
    return {key:sorted(value,key=lambda x:(str(x.get("component","")),str(x["command"]),str(x["basis"]))) for key,value in out.items()}
