"""Deterministic repository model from bounded collectors and source semantics."""
from __future__ import annotations
from pathlib import Path
from tools.ci_semantic_analysis import analyze_semantics
from tools.ci_upgrade_models import diagnostic, evidence
from tools.ci_repository_collectors import (
    MAX_FILES, LANG, MANIFEST, LOCK, CONFIG, TEST_PATTERNS, BUILD_PATTERNS,
    INSTALL_PATTERNS, RELEASE_PATTERNS, iter_files, rel, _text, _is_test,
    _negative, parse_workflow, _manifest, _has, _cap, _expand_workspace_roots,
    _nearest_component, _command_candidates,
)

def build_repository_model(root:Path)->dict[str,object]:
    root=root.resolve();files,truncated=iter_files(root);paths=sorted(rel(root,p) for p in files);pmap={rel(root,p):p for p in files};diags=[]
    if truncated:diags.append(diagnostic("FILE_INVENTORY_TRUNCATED",f"Repository inventory stopped at {MAX_FILES} files.",affected_area="repository_model",repair_hint="Narrow generated/vendor directories or increase the versioned collector limit after performance validation.",severity="warning"))
    languages=sorted({LANG[p.suffix.lower()] for p in files if p.suffix.lower() in LANG})
    manifests=sorted(p for p in paths if Path(p).name in MANIFEST);locks=sorted(p for p in paths if Path(p).name in LOCK);configs=sorted(p for p in paths if Path(p).name in CONFIG)
    tests=sorted(p for p in paths if _is_test(p));negative=sorted(p for p in tests if _negative(pmap[p]));schemas=sorted(p for p in paths if p.lower().endswith(".json") and "schema" in p.lower());validators=sorted(p for p in paths if any(x in p.lower() for x in ("validat","check_","audit")) and p.lower().endswith((".py",".js",".ts",".sh")));examples=sorted(p for p in paths if p.startswith("examples/") or "/examples/" in f"/{p}")
    generated=sorted(p for p in paths if any(part in {"generated","dist","build"} for part in Path(p).parts));releases=sorted(p for p in paths if any(x in p.lower() for x in ("release","publish","deploy","changelog")))
    parsed=[];frameworks=set();builds=set();entries=[];workspace_patterns=[]
    for rp in manifests:
        item=_manifest(pmap[rp],rp);parsed.append(item);deps="\n".join(str(x) for x in item.get("dependencies",[])).lower()
        for token,name in (("fastapi","FastAPI"),("django","Django"),("flask","Flask"),("celery","Celery"),("pyside","PySide"),("pyqt","PyQt"),("torch","PyTorch"),("tensorflow","TensorFlow"),("react","React"),("next","Next.js"),("vite","Vite"),("express","Express"),("fastify","Fastify")):
            if token in deps:frameworks.add(name)
        if item.get("build_backend"):builds.add(str(item["build_backend"]))
        if item.get("scripts"):builds.add("package_scripts")
        for name,target in item.get("scripts",{}).items():
            if item["kind"]=="pyproject" or name in {"start","serve","dev","cli"}:entries.append({"source":rp,"name":name,"target":target,"evidence":evidence("observed",[rp],"Entry point was declared by a parsed manifest.",confidence="high")})
        workspace_patterns.extend(str(x) for x in item.get("workspaces",[]))
    wf_paths=sorted(p for p in paths if p.startswith(".github/workflows/") and p.lower().endswith((".yml",".yaml")));workflows=[]
    for rp in wf_paths:
        wf,ds=parse_workflow(root,pmap[rp]);workflows.append(wf);diags.extend(ds)
    semantic=analyze_semantics(root,paths,parsed,workflows,entries);diags.extend(semantic["limitations"])
    commands=sorted({c for w in workflows for c in w.get("commands",[]) if isinstance(c,str)})
    manifest_roots=sorted({Path(p).parent.as_posix() for p in manifests});manifest_roots=["." if x=="." else x for x in manifest_roots]
    declared_roots=_expand_workspace_roots(root,workspace_patterns);roots=sorted(set(manifest_roots+declared_roots)) or ["."]
    if "." not in roots and any(Path(p).parent.as_posix()=="." for p in manifests):roots.insert(0,".")
    components=[]
    for cr in roots:
        cms=[p for p in manifests if _nearest_component(p,roots)==cr];cts=[p for p in tests if _nearest_component(p,roots)==cr];basis="workspace_declared" if cr in declared_roots else "manifest_root"
        components.append({"component_id":"root" if cr=="." else cr.replace("/","::"),"root":cr,"boundary_basis":basis,"manifests":cms,"tests":cts,"evidence":evidence("observed" if basis=="workspace_declared" else "derived",cms+cts+[p for p in manifests if any(cr==d or cr.startswith(d.rstrip("/")+"/") for d in declared_roots)],"Component boundary comes from an explicit workspace declaration or nearest manifest root; semantic ownership beyond that boundary is not inferred.",confidence="high" if basis=="workspace_declared" else "medium")})
    monorepo=len([r for r in roots if r!="."])>1 or bool(declared_roots);archetypes=[]
    if "Python" in languages:archetypes.append("python")
    if {"JavaScript","TypeScript"}&set(languages):archetypes.append("javascript-typescript")
    if schemas:archetypes.append("contract-schema")
    if languages and set(languages)<={"Markdown","YAML","JSON"} and not manifests:archetypes.append("documentation-only")
    if monorepo:archetypes.append("monorepo")
    if any(Path(p).name=="manifest.json" for p in paths):archetypes.append("browser-extension")
    candidates=_command_candidates(parsed,paths,tests);pr=any("pull_request" in w.get("triggers",[]) for w in workflows);test_ok=_has(commands,TEST_PATTERNS);build_ok=_has(commands,BUILD_PATTERNS);release_ok=_has(commands,RELEASE_PATTERNS);install_ok=_has(commands,INSTALL_PATTERNS)
    schema_test_refs=[p for p in tests if "schema" in p.lower() or "jsonschema" in ((_text(pmap[p]) or "").lower())];schema_ok=bool(schemas and schema_test_refs and test_ok)
    gen_ok=bool(generated and any("git diff --exit-code" in c.lower() or "generate" in c.lower() for c in commands));explicit=[str(w["path"]) for w in workflows if w.get("permissions")];weak=any(w.get("permissions")=="write-all" or isinstance(w.get("permissions"),dict) and any(str(v).lower()=="write" for v in w["permissions"].values()) for w in workflows)
    caps=[
      _cap("tests_present","operational" if tests else "absent",tests,"Test files were observed." if tests else "No test files were observed.","Add deterministic tests for critical behavior." if not tests else None),
      _cap("tests_run_on_pull_requests","operational" if test_ok and pr else "nominal" if tests and workflows else "absent",[w["path"] for w in workflows if "pull_request" in w.get("triggers",[])]+tests,"A pull-request workflow executes a recognized test command." if test_ok and pr else "Tests or workflows exist, but no pull-request workflow was proven to execute a recognized test command.","Wire one resolved canonical test command into pull_request validation."),
      _cap("build_verified","operational" if build_ok else "nominal" if candidates["build"] else "absent",wf_paths+[str(x.get("basis")) for x in candidates["build"]],"A declared build command is executed in CI." if build_ok else "A build command is declared or inferable, but CI execution was not proven." if candidates["build"] else "No build command was established.","Execute the declared build from a clean checkout."),
      _cap("reproducible_dependency_install","operational" if install_ok and locks else "partial" if locks or candidates["install"] else "absent",locks+wf_paths,"A lockfile and deterministic install command were both observed in CI." if install_ok and locks else "A lockfile or deterministic install command is missing or disconnected.","Use the ecosystem-native frozen install command and lockfile."),
      _cap("schema_validation","operational" if schema_ok else "nominal" if schemas else "not_applicable",schemas+schema_test_refs+wf_paths,"Schemas are exercised by schema-aware tests within the CI test command." if schema_ok else "Schemas exist but executable compatibility validation was not proven." if schemas else "No schema surface was observed.","Connect schemas, examples, validators, and malformed fixtures to one deterministic command." if schemas else None),
      _cap("negative_parser_validator_tests","operational" if negative else "nominal" if validators or schemas else "not_applicable",negative+validators+schemas,"Negative or malformed-input tests were observed." if negative else "Validator/schema surfaces exist, but negative coverage was not observed." if validators or schemas else "No applicable parser or validator surface was observed.","Add malformed, boundary, and rejected-input fixtures with stable diagnostics." if validators or schemas else None),
      _cap("generated_artifact_validation","operational" if gen_ok else "nominal" if generated else "unknown",generated+wf_paths,"Generated outputs and a regeneration/diff check were both observed." if gen_ok else "Generated-looking paths exist, but source linkage or verification was not proven." if generated else "No declaratively detectable generated artifacts were found.","Declare source-to-generated relationships and verify a clean diff after regeneration."),
      _cap("release_artifact_validation","operational" if release_ok else "nominal" if releases else "unknown",releases+wf_paths,"A package/release verification command was observed." if release_ok else "Release-related paths exist, but artifact verification was not proven." if releases else "Release applicability could not be established.","Validate package metadata and produced artifacts before release."),
      _cap("least_privilege_workflow_permissions","operational_but_weak" if weak else "operational" if explicit else "unknown" if workflows else "not_applicable",explicit,"Explicit permissions exist, but at least one workflow grants write scope." if weak else "Explicit workflow permissions were observed." if explicit else "Workflows exist without a proven explicit permission contract." if workflows else "No workflows were observed.","Declare only the permissions needed by each workflow or job." if workflows else None)]
    relationships=list(semantic["relationships"])
    if schemas and examples:relationships.append({"relationship_id":"schema-example-directory-candidate","relationship_type":"schema_to_example","sources":schemas,"targets":examples,"resolution_state":"inferred","evidence":evidence("inferred",schemas+examples,"Directory and naming proximity suggests a relationship; semantic compatibility still requires validator execution.",confidence="low")})
    return {"model_version":"1.1.0","root":".","file_count":len(paths),"inventory_truncated":truncated,"path_index":paths,"repository_archetypes":sorted(set(archetypes)),"components":components,"languages":languages,"frameworks":sorted(frameworks),"build_systems":sorted(builds),"manifests":parsed,"lockfiles":locks,"config_files":configs,"entry_points":sorted(entries,key=lambda x:(x["source"],x["name"],x["target"])),"command_candidates":candidates,"test_suites":{"files":tests,"negative_files":negative,"schema_test_files":schema_test_refs,"commands_observed_in_ci":[c for c in commands if any(x.lower() in c.lower() for x in TEST_PATTERNS)]},"validators":validators,"schemas":schemas,"examples":examples,"generated_artifacts":generated,"release_paths":releases,"workflows":workflows,"semantic_model":semantic,"critical_execution_paths":semantic["critical_paths"],"relationships":sorted(relationships,key=lambda x:str(x.get("relationship_id"))),"capabilities":sorted(caps,key=lambda x:str(x["capability_id"])),"unresolved_evidence":sorted(diags,key=lambda x:(str(x["code"]),str(x["message"]))),"model_evidence":evidence("derived",paths,"Repository model combines bounded file/config parsing, explicit workspace boundaries, Python AST resolution, and workflow/package command resolution; unsupported runtime semantics remain unresolved.",confidence="high")}
