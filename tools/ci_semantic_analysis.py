"""Bounded semantic resolution for Python sources and package/workflow commands.

The analyzer deliberately supports only deterministic, documented syntax. Unsupported
languages and dynamic imports remain explicit limitations rather than guessed facts.
"""
from __future__ import annotations
import ast
import shlex
from pathlib import Path
from typing import Iterable
from tools.ci_upgrade_models import diagnostic, evidence

MAX_SOURCE_BYTES = 1_000_000


def _module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    parts = list(Path(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else None


def _is_test(path: str) -> bool:
    name=Path(path).name.lower(); lower=f"/{path.lower()}"
    return "/tests/" in lower or "/test/" in lower or name.startswith("test_") or name.endswith("_test.py")


def _read_ast(root: Path, relative: str) -> tuple[ast.AST | None, dict[str, object] | None]:
    path=root/relative
    try:
        if path.stat().st_size>MAX_SOURCE_BYTES:
            return None, diagnostic("PYTHON_SOURCE_TOO_LARGE",f"Skipped semantic parsing for {relative}; file exceeds {MAX_SOURCE_BYTES} bytes.",affected_area="semantic_model",evidence_references=[relative],repair_hint="Provide a smaller declarative entry-point or component manifest for this source.",severity="info")
        text=path.read_text(encoding="utf-8")
        return ast.parse(text,filename=relative),None
    except (OSError,UnicodeDecodeError,SyntaxError) as exc:
        return None, diagnostic("PYTHON_AST_PARSE_FAILED",f"Could not parse Python source {relative}: {type(exc).__name__}.",affected_area="semantic_model",evidence_references=[relative],repair_hint=f"Repair Python syntax or encoding in {relative}, or mark the source unsupported.")


def _import_targets(tree: ast.AST) -> list[str]:
    result:set[str]=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module:
            result.add(node.module)
    return sorted(result)


def _has_main_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node,ast.If):continue
        test=node.test
        if not isinstance(test,ast.Compare) or len(test.ops)!=1 or not isinstance(test.ops[0],ast.Eq):continue
        if not isinstance(test.left,ast.Name) or test.left.id!="__name__":continue
        if len(test.comparators)==1 and isinstance(test.comparators[0],ast.Constant) and test.comparators[0].value=="__main__":return True
    return False


def _functions(tree: ast.AST)->set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}


def _routes(tree: ast.AST,module:str,source:str)->list[dict[str,object]]:
    routes=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        for decorator in node.decorator_list:
            if not isinstance(decorator,ast.Call) or not isinstance(decorator.func,ast.Attribute):continue
            method=decorator.func.attr.lower()
            if method not in {"get","post","put","patch","delete","options","head","route","websocket"}:continue
            route_path=None
            if decorator.args and isinstance(decorator.args[0],ast.Constant) and isinstance(decorator.args[0].value,str): route_path=decorator.args[0].value
            if route_path is None:continue
            routes.append({"signal_id":f"python_route:{module}:{method}:{route_path}","signal_type":"python_route","module":module,"method":method,"route":route_path,"callable":node.name,"source":source,"evidence":evidence("observed",[source],"A literal route decorator was parsed from Python AST.",confidence="high")})
    return sorted(routes,key=lambda x:str(x["signal_id"]))


def _resolve_local(target:str,modules:set[str])->str|None:
    if target in modules:return target
    candidates=sorted((m for m in modules if target.startswith(m+".") or m.startswith(target+".")),key=lambda x:(len(x),x))
    return candidates[0] if candidates else None


def _workflow_command_nodes(workflows:list[dict[str,object]])->tuple[list[dict[str,object]],list[dict[str,object]]]:
    nodes=[]; commands=[]
    for workflow in workflows:
        path=str(workflow.get("path",""))
        for job in workflow.get("jobs",[]) if isinstance(workflow.get("jobs"),list) else []:
            if not isinstance(job,dict):continue
            jid=str(job.get("job_id","unknown"))
            for step in job.get("steps",[]) if isinstance(job.get("steps"),list) else []:
                if not isinstance(step,dict) or not isinstance(step.get("run"),str):continue
                index=int(step.get("index",0)); node_id=f"workflow_command:{path}:{jid}:{index}"
                nodes.append({"node_id":node_id,"node_type":"workflow_command","label":step.get("name") or node_id,"source":path})
                for line in step["run"].splitlines():
                    line=line.strip()
                    if line:commands.append({"node_id":node_id,"command":line,"source":path,"working_directory":step.get("working_directory")})
    return sorted(nodes,key=lambda x:str(x["node_id"])),sorted(commands,key=lambda x:(str(x["node_id"]),str(x["command"])))


def _script_invocation(command:str)->str|None:
    try: tokens=shlex.split(command,posix=True)
    except ValueError:return None
    if not tokens:return None
    if tokens[:2] in (["npm","test"],["pnpm","test"],["yarn","test"]):return "test"
    if len(tokens)>=3 and tokens[0] in {"npm","pnpm","yarn"} and tokens[1]=="run":return tokens[2]
    if len(tokens)>=2 and tokens[0] in {"pnpm","yarn"} and tokens[1] not in {"install","add","remove","exec","dlx"}:return tokens[1]
    return None


def analyze_semantics(root:Path,paths:Iterable[str],manifests:list[dict[str,object]],workflows:list[dict[str,object]],declared_entry_points:list[dict[str,object]])->dict[str,object]:
    root=root.resolve(); path_list=sorted(set(str(p) for p in paths)); py_paths=[p for p in path_list if p.endswith(".py")]
    module_by_path={p:_module_name(p) for p in py_paths}; module_by_path={p:m for p,m in module_by_path.items() if m}; modules=set(module_by_path.values())
    nodes=[]; edges=[]; relationships=[]; signals=[]; limitations=[]; functions_by_module={}
    parsed={}
    for path,module in sorted(module_by_path.items()):
        tree,diag=_read_ast(root,path)
        if diag:limitations.append(diag)
        if tree is None:continue
        parsed[path]=tree; functions_by_module[module]=_functions(tree)
        nodes.append({"node_id":f"python_module:{module}","node_type":"python_module","label":module,"source":path})
        if _has_main_guard(tree):
            sig={"signal_id":f"python_main_guard:{module}","signal_type":"python_main_guard","module":module,"source":path,"evidence":evidence("observed",[path],"A literal __main__ guard was parsed from Python AST.",confidence="high")};signals.append(sig)
            nodes.append({"node_id":f"python_entry:{module}","node_type":"python_entry","label":module,"source":path})
            edges.append({"edge_id":f"entry-to-module:{module}","from":f"python_entry:{module}","to":f"python_module:{module}","relationship":"executes","resolution_state":"resolved","evidence":evidence("derived",[path],"The __main__ guard resolves this file as an executable entry.",confidence="high")})
        signals.extend(_routes(tree,module,path))
        for target in _import_targets(tree):
            resolved=_resolve_local(target,modules)
            if not resolved:continue
            target_path=next((p for p,m in module_by_path.items() if m==resolved),resolved)
            edge={"edge_id":f"python-import:{module}:{resolved}","from":f"python_module:{module}","to":f"python_module:{resolved}","relationship":"imports","resolution_state":"resolved","evidence":evidence("observed",[path,str(target_path)],"A Python import was resolved to a local module from AST.",confidence="high")}
            edges.append(edge)
            if _is_test(path) and not _is_test(str(target_path)):
                relationships.append({"relationship_id":f"test-imports-source:{path}:{resolved}","relationship_type":"source_to_test","sources":[str(target_path)],"targets":[path],"resolution_state":"resolved","evidence":edge["evidence"]})
    # Resolve declared console entry points such as module:function.
    for entry in declared_entry_points:
        target=str(entry.get("target","")); source=str(entry.get("source","")); name=str(entry.get("name","")); module,sep,callable_name=target.partition(":")
        resolved=_resolve_local(module,modules) if module else None
        valid=bool(resolved and (not sep or callable_name in functions_by_module.get(resolved,set())))
        state="resolved" if valid else "unresolved"
        refs=[source]+[p for p,m in module_by_path.items() if m==resolved]
        signals.append({"signal_id":f"declared_entry:{source}:{name}","signal_type":"declared_entry_point","name":name,"target":target,"resolution_state":state,"source":source,"evidence":evidence("derived" if valid else "unavailable",refs,"Declared entry point resolved to a local Python module and callable." if valid else "Declared entry point could not be resolved to a local Python module and callable.",confidence="high" if valid else "low")})
        if valid:
            node_id=f"declared_entry:{source}:{name}";nodes.append({"node_id":node_id,"node_type":"declared_entry","label":name,"source":source})
            edges.append({"edge_id":f"declared-entry:{source}:{name}","from":node_id,"to":f"python_module:{resolved}","relationship":"resolves_to","resolution_state":"resolved","evidence":evidence("derived",refs,"Manifest entry point target was resolved against parsed Python definitions.",confidence="high")})
        else:
            limitations.append(diagnostic("ENTRY_POINT_UNRESOLVED",f"Declared entry point {name!r} in {source} could not be resolved: {target!r}.",affected_area="entry_points",evidence_references=refs,repair_hint="Correct the declared module:function target or add the missing source callable."))
    # Resolve package scripts and workflow command invocation.
    script_index={}
    for manifest in manifests:
        source=str(manifest.get("path","")); scripts=manifest.get("scripts",{})
        if not isinstance(scripts,dict):continue
        for name,command in sorted(scripts.items()):
            node_id=f"package_script:{source}:{name}"; script_index[(source,str(name))]=node_id
            nodes.append({"node_id":node_id,"node_type":"package_script","label":str(name),"source":source})
    workflow_nodes,workflow_commands=_workflow_command_nodes(workflows);nodes.extend(workflow_nodes)
    package_manifests=[m for m in manifests if m.get("kind")=="package_json"]
    for item in workflow_commands:
        invoked=_script_invocation(str(item["command"]))
        if not invoked:continue
        working_directory=item.get("working_directory")
        eligible=package_manifests
        if isinstance(working_directory,str) and working_directory.strip():
            wd=working_directory.strip().strip("./")
            eligible=[m for m in package_manifests if Path(str(m.get("path"))).parent.as_posix().strip("./")==wd]
        matches=[(str(m.get("path")),script_index.get((str(m.get("path")),invoked))) for m in eligible if (str(m.get("path")),invoked) in script_index]
        if len(matches)==1:
            source,target=matches[0]
            edges.append({"edge_id":f"workflow-script:{item['node_id']}:{source}:{invoked}","from":item["node_id"],"to":target,"relationship":"invokes","resolution_state":"resolved","evidence":evidence("observed",[str(item["source"]),source],f"Workflow command invokes declared package script {invoked}.",confidence="high")})
        elif len(matches)>1:
            limitations.append(diagnostic("WORKFLOW_SCRIPT_AMBIGUOUS",f"Workflow command {item['command']!r} matches script {invoked!r} in multiple package manifests.",affected_area="execution_graph",evidence_references=[str(item["source"]),*[x[0] for x in matches]],repair_hint="Run the command from an explicit working directory or identify the target component."))
    for manifest in package_manifests:
        source=str(manifest.get("path",""));scripts=manifest.get("scripts",{})
        if not isinstance(scripts,dict):continue
        for name,command in sorted(scripts.items()):
            invoked=_script_invocation(str(command))
            if invoked and (source,invoked) in script_index:
                edges.append({"edge_id":f"script-script:{source}:{name}:{invoked}","from":script_index[(source,str(name))],"to":script_index[(source,invoked)],"relationship":"invokes","resolution_state":"resolved","evidence":evidence("observed",[source],f"Package script {name} invokes script {invoked}.",confidence="high")})
    nodes=sorted({str(n["node_id"]):n for n in nodes}.values(),key=lambda x:str(x["node_id"])); edges=sorted({str(e["edge_id"]):e for e in edges}.values(),key=lambda x:str(x["edge_id"]));relationships=sorted({str(r["relationship_id"]):r for r in relationships}.values(),key=lambda x:str(x["relationship_id"]));signals=sorted({str(s["signal_id"]):s for s in signals}.values(),key=lambda x:str(x["signal_id"]))
    entry_nodes=sorted(n["node_id"] for n in nodes if n["node_type"] in {"python_entry","declared_entry","workflow_command"})
    outgoing={node:[] for node in entry_nodes}
    for edge in edges:
        if edge["from"] in outgoing:outgoing[edge["from"]].append(edge["edge_id"])
    critical_paths=[{"path_id":f"critical:{node}","entry_node":node,"edge_ids":sorted(outgoing[node]),"resolution_state":"resolved" if outgoing[node] else "partial","evidence":evidence("derived",[str(next(n["source"] for n in nodes if n["node_id"]==node))],"Critical path begins at an observed executable entry or workflow command; only statically resolved edges are included.",confidence="high" if outgoing[node] else "medium")} for node in entry_nodes]
    return {"semantic_model_version":"1.0.0","nodes":nodes,"edges":edges,"relationships":relationships,"signals":signals,"critical_paths":critical_paths,"limitations":sorted(limitations,key=lambda x:(str(x["code"]),str(x["message"]))),"evidence":evidence("derived",py_paths+[str(w.get("path")) for w in workflows],"Semantic model uses bounded Python AST and declarative package/workflow command resolution; dynamic behavior is not inferred.",confidence="high")}
