"""Deterministic repository model from bounded collectors and source semantics."""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from tools.ci_repository_collectors import (
    CONFIG,
    LANG,
    LOCK,
    MANIFEST,
    MAX_FILES,
    _cap,
    _command_candidates,
    _is_test,
    _manifest,
    _nearest_component,
    _negative,
    _text,
    collect_repository_files,
    expand_workspace_roots,
    parse_workflow,
    rel,
)
from tools.ci_semantic_analysis import analyze_semantics
from tools.ci_upgrade_models import diagnostic, evidence


def _records(workflows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [record for workflow in workflows for record in workflow.get("command_evidence", []) if isinstance(record, dict)]


def _family(records: list[dict[str, object]], family: str) -> bool:
    return any(record.get("status") == "resolved" and family in record.get("families", []) for record in records)


def _normalize_working_directory(value: object) -> str | None:
    if value in (None, "", ".", "./"):
        return "."
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        return None
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(part == ".." for part in posix.parts):
        return None
    parts = [part for part in posix.parts if part not in {"", "."}]
    return "/".join(parts) if parts else "."


def _record_has_test_target(record: dict[str, object], tests: list[str]) -> bool:
    if record.get("status") != "resolved" or "test" not in record.get("families", []) or not tests:
        return False
    directory = _normalize_working_directory(record.get("working_directory"))
    if directory is None:
        return False
    if directory == ".":
        return True
    prefix = directory.rstrip("/") + "/"
    return any(test == directory or test.startswith(prefix) for test in tests)


def _permission_capability(workflows: list[dict[str, object]]) -> dict[str, object]:
    if not workflows:
        return _cap("least_privilege_workflow_permissions", "not_applicable", [], "No workflows were observed.")
    effective = [job["effective_permissions"] for workflow in workflows for job in workflow.get("jobs", []) if isinstance(job, dict) and isinstance(job.get("effective_permissions"), dict)]
    if not effective:
        return _cap("least_privilege_workflow_permissions", "unknown", [str(workflow["path"]) for workflow in workflows], "Workflow permissions could not be evaluated because no valid jobs were parsed.", "Repair workflow job shapes and declare explicit workflow or job permissions.")
    refs = sorted({str(item["source"]) for item in effective})
    writes = [item for item in effective if item.get("access") == "write"]
    unknown = [item for item in effective if item.get("access") == "unknown"]
    if writes:
        unsafe_refs = sorted({str(item["source"]) for item in writes})
        return _cap("least_privilege_workflow_permissions", "operational_but_weak", unsafe_refs, "At least one job has effective write permission after applying job-over-workflow precedence.", "Narrow the cited effective job permission only if the job does not require write access.")
    if unknown:
        unknown_refs = sorted({str(item["source"]) for item in unknown})
        return _cap("least_privilege_workflow_permissions", "unknown", unknown_refs, "One or more jobs inherit platform defaults or use malformed/unsupported permissions, so least privilege is not proven.", "Declare a supported explicit workflow or job permissions contract for every job.")
    return _cap("least_privilege_workflow_permissions", "operational", refs, "Every parsed job has effective read-or-none permissions after applying workflow/job precedence, including explicit empty declarations.")


def build_repository_model(root: Path) -> dict[str, object]:
    root = root.resolve()
    files, truncated, path_diagnostics = collect_repository_files(root)
    paths = sorted(rel(root, path) for path in files)
    path_map = {rel(root, path): path for path in files}
    diagnostics: list[dict[str, object]] = list(path_diagnostics)
    if truncated:
        diagnostics.append(diagnostic("FILE_INVENTORY_TRUNCATED", f"Repository inventory stopped at {MAX_FILES} files.", affected_area="repository_model", repair_hint="Narrow generated/vendor directories or increase the versioned collector limit after performance validation.", severity="warning"))

    languages = sorted({LANG[path.suffix.lower()] for path in files if path.suffix.lower() in LANG})
    manifests = sorted(path for path in paths if Path(path).name in MANIFEST)
    locks = sorted(path for path in paths if Path(path).name in LOCK)
    configs = sorted(path for path in paths if Path(path).name in CONFIG)
    tests = sorted(path for path in paths if _is_test(path))
    negative = sorted(path for path in tests if _negative(path_map[path], root))
    schemas = sorted(path for path in paths if path.lower().endswith(".json") and "schema" in path.lower())
    validators = sorted(path for path in paths if any(token in path.lower() for token in ("validat", "check_", "audit")) and path.lower().endswith((".py", ".js", ".ts", ".sh")))
    examples = sorted(path for path in paths if path.startswith("examples/") or "/examples/" in f"/{path}")
    generated = sorted(path for path in paths if any(part in {"generated", "dist", "build"} for part in Path(path).parts))
    releases = sorted(path for path in paths if any(token in path.lower() for token in ("release", "publish", "deploy", "changelog")))

    parsed: list[dict[str, object]] = []
    frameworks: set[str] = set()
    builds: set[str] = set()
    entries: list[dict[str, object]] = []
    workspace_patterns: list[str] = []
    for rp in manifests:
        item = _manifest(path_map[rp], rp, root)
        parsed.append(item)
        dependencies = "\n".join(str(value) for value in item.get("dependencies", [])).lower()
        for token, name in (("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"), ("celery", "Celery"), ("pyside", "PySide"), ("pyqt", "PyQt"), ("torch", "PyTorch"), ("tensorflow", "TensorFlow"), ("react", "React"), ("next", "Next.js"), ("vite", "Vite"), ("express", "Express"), ("fastify", "Fastify")):
            if token in dependencies:
                frameworks.add(name)
        if item.get("build_backend"):
            builds.add(str(item["build_backend"]))
        if item.get("scripts"):
            builds.add("package_scripts")
        for name, target in item.get("scripts", {}).items():
            if item["kind"] == "pyproject" or name in {"start", "serve", "dev", "cli"}:
                entries.append({"source": rp, "name": name, "target": target, "evidence": evidence("observed", [rp], "Entry point was declared by a parsed manifest.", confidence="high")})
        workspace_patterns.extend(str(value) for value in item.get("workspaces", []))

    workflow_paths = sorted(path for path in paths if path.startswith(".github/workflows/") and path.lower().endswith((".yml", ".yaml")))
    workflows: list[dict[str, object]] = []
    for rp in workflow_paths:
        workflow, workflow_diagnostics = parse_workflow(root, path_map[rp])
        workflows.append(workflow)
        diagnostics.extend(workflow_diagnostics)

    semantic = analyze_semantics(root, paths, parsed, workflows, entries)
    diagnostics.extend(semantic["limitations"])
    records = _records(workflows)
    resolved_records = [record for record in records if record.get("status") == "resolved"]

    manifest_roots = sorted({Path(path).parent.as_posix() for path in manifests})
    manifest_roots = ["." if item == "." else item for item in manifest_roots]
    declared_roots, workspace_diagnostics = expand_workspace_roots(root, workspace_patterns)
    diagnostics.extend(workspace_diagnostics)
    roots = sorted(set(manifest_roots + declared_roots)) or ["."]
    if "." not in roots and any(Path(path).parent.as_posix() == "." for path in manifests):
        roots.insert(0, ".")
    components = []
    for component_root in roots:
        component_manifests = [path for path in manifests if _nearest_component(path, roots) == component_root]
        component_tests = [path for path in tests if _nearest_component(path, roots) == component_root]
        basis = "workspace_declared" if component_root in declared_roots else "manifest_root"
        components.append({
            "component_id": "root" if component_root == "." else component_root.replace("/", "::"),
            "root": component_root,
            "boundary_basis": basis,
            "manifests": component_manifests,
            "tests": component_tests,
            "evidence": evidence("observed" if basis == "workspace_declared" else "derived", component_manifests + component_tests + [path for path in manifests if any(component_root == declared or component_root.startswith(declared.rstrip("/") + "/") for declared in declared_roots)], "Component boundary comes from an explicit contained workspace declaration or nearest manifest root; semantic ownership beyond that boundary is not inferred.", confidence="high" if basis == "workspace_declared" else "medium"),
        })

    monorepo = len([item for item in roots if item != "."]) > 1 or bool(declared_roots)
    archetypes: list[str] = []
    if "Python" in languages:
        archetypes.append("python")
    if {"JavaScript", "TypeScript"} & set(languages):
        archetypes.append("javascript-typescript")
    if schemas:
        archetypes.append("contract-schema")
    if languages and set(languages) <= {"Markdown", "YAML", "JSON"} and not manifests:
        archetypes.append("documentation-only")
    if monorepo:
        archetypes.append("monorepo")
    if any(Path(path).name == "manifest.json" for path in paths):
        archetypes.append("browser-extension")

    candidates = _command_candidates(parsed, paths, tests)
    pr_test_records = [record for workflow in workflows if "pull_request" in workflow.get("triggers", []) for record in workflow.get("command_evidence", []) if isinstance(record, dict)]
    target_test_records = [record for record in pr_test_records if _record_has_test_target(record, tests)]
    unresolved_target_records = [record for record in pr_test_records if record.get("status") == "resolved" and "test" in record.get("families", []) and record not in target_test_records]
    if unresolved_target_records:
        diagnostics.append(diagnostic("WORKFLOW_TEST_TARGET_UNRESOLVED", f"{len(unresolved_target_records)} resolved test invocation(s) were excluded because no concrete test target was discovered in the invocation working directory.", affected_area="workflow_command_evidence", evidence_references=sorted({f"{record.get('workflow')}#jobs.{record.get('job_id')}.steps[{record.get('step_index')}]" for record in unresolved_target_records}), repair_hint="Add concrete test files under the command working directory or correct the working-directory evidence.", severity="warning"))
    test_ok = bool(target_test_records)
    build_ok = _family(resolved_records, "build")
    release_ok = _family(resolved_records, "release")
    install_ok = _family(resolved_records, "install")
    pr = any("pull_request" in workflow.get("triggers", []) for workflow in workflows)
    schema_test_refs = [path for path in tests if "schema" in path.lower() or "jsonschema" in ((_text(path_map[path], root) or "").lower())]
    schema_ok = bool(schemas and schema_test_refs and test_ok)
    generated_ok = bool(generated and any(record.get("executable") == "git" and record.get("argv", [])[1:3] == ["diff", "--exit-code"] for record in resolved_records))

    capabilities = [
        _cap("tests_present", "operational" if tests else "absent", tests, "Test files were observed." if tests else "No test files were observed.", "Add deterministic tests for critical behavior." if not tests else None),
        _cap("tests_run_on_pull_requests", "operational" if test_ok and pr else "nominal" if tests and workflows else "absent", sorted({str(record.get("workflow")) for record in target_test_records}) + tests, "A structurally runnable pull-request job contains a bounded behavioral test invocation with a discovered test target." if test_ok and pr else "Tests or workflows exist, but no runnable pull-request job was proven to execute a behavioral recognized test invocation against a discovered test target.", "Wire one resolved behavioral test command into a runnable pull_request job with concrete test files."),
        _cap("build_verified", "operational" if build_ok else "nominal" if candidates["build"] else "absent", sorted({str(record.get("workflow")) for record in resolved_records if "build" in record.get("families", [])}) + [str(item.get("basis")) for item in candidates["build"]], "A bounded behavioral build invocation executes in a structurally runnable CI job." if build_ok else "A build command is declared or inferable, but CI execution was not proven." if candidates["build"] else "No build command was established.", "Execute the declared build from a clean checkout."),
        _cap("reproducible_dependency_install", "operational" if install_ok and locks else "partial" if locks or candidates["install"] else "absent", locks + sorted({str(record.get("workflow")) for record in resolved_records if "install" in record.get("families", [])}), "A lockfile and bounded behavioral install invocation were both observed in a structurally runnable CI job." if install_ok and locks else "A lockfile or deterministic install invocation is missing or disconnected.", "Use the ecosystem-native frozen install command and lockfile."),
        _cap("schema_validation", "operational" if schema_ok else "nominal" if schemas else "not_applicable", schemas + schema_test_refs + sorted({str(record.get("workflow")) for record in target_test_records}), "Schemas are exercised by schema-aware tests within a runnable pull-request test invocation with discovered targets." if schema_ok else "Schemas exist but executable compatibility validation was not proven." if schemas else "No schema surface was observed.", "Connect schemas, examples, validators, and malformed fixtures to one deterministic command." if schemas else None),
        _cap("negative_parser_validator_tests", "operational" if negative else "nominal" if validators or schemas else "not_applicable", negative + validators + schemas, "Negative or malformed-input tests were observed." if negative else "Validator/schema surfaces exist, but negative coverage was not observed." if validators or schemas else "No applicable parser or validator surface was observed.", "Add malformed, boundary, and rejected-input fixtures with stable diagnostics." if validators or schemas else None),
        _cap("generated_artifact_validation", "operational" if generated_ok else "nominal" if generated else "unknown", generated + sorted({str(record.get("workflow")) for record in resolved_records}), "Generated outputs and a resolved regeneration/diff check were both observed." if generated_ok else "Generated-looking paths exist, but source linkage or verification was not proven." if generated else "No declaratively detectable generated artifacts were found.", "Declare source-to-generated relationships and verify a clean diff after regeneration."),
        _cap("release_artifact_validation", "operational" if release_ok else "nominal" if releases else "unknown", releases + sorted({str(record.get("workflow")) for record in resolved_records if "release" in record.get("families", [])}), "A bounded behavioral package/release verification invocation was observed in a structurally runnable CI job." if release_ok else "Release-related paths exist, but artifact verification was not proven." if releases else "Release applicability could not be established.", "Validate package metadata and produced artifacts before release."),
        _permission_capability(workflows),
    ]

    relationships = list(semantic["relationships"])
    if schemas and examples:
        relationships.append({"relationship_id": "schema-example-directory-candidate", "relationship_type": "schema_to_example", "sources": schemas, "targets": examples, "resolution_state": "inferred", "evidence": evidence("inferred", schemas + examples, "Directory and naming proximity suggests a relationship; semantic compatibility still requires validator execution.", confidence="low")})

    unsupported = [record for record in records if record.get("status") == "unsupported"]
    if unsupported:
        diagnostics.append(diagnostic("WORKFLOW_COMMAND_EVIDENCE_UNSUPPORTED", f"{len(unsupported)} workflow lines use unsupported shell constructs or non-runnable job shapes and were excluded from executable capability evidence.", affected_area="workflow_command_evidence", evidence_references=sorted({f"{record.get('workflow')}#jobs.{record.get('job_id')}.steps[{record.get('step_index')}]:{record.get('line')}" for record in unsupported}), repair_hint="Use a standalone behavioral command in a structurally runnable job or extend the bounded parser with fixtures; do not infer full shell semantics.", severity="info"))

    return {
        "model_version": "1.1.0",
        "root": ".",
        "file_count": len(paths),
        "inventory_truncated": truncated,
        "path_index": paths,
        "repository_archetypes": sorted(set(archetypes)),
        "components": components,
        "languages": languages,
        "frameworks": sorted(frameworks),
        "build_systems": sorted(builds),
        "manifests": parsed,
        "lockfiles": locks,
        "config_files": configs,
        "entry_points": sorted(entries, key=lambda item: (item["source"], item["name"], item["target"])),
        "command_candidates": candidates,
        "command_evidence_boundary": {"version": "1.0.0", "resolved_record_count": len(resolved_records), "unsupported_record_count": len(unsupported), "policy": "Only standalone behavioral argv invocations in structurally runnable jobs can establish executable capabilities; test claims additionally require a discovered target in the command working directory."},
        "test_suites": {"files": tests, "negative_files": negative, "schema_test_files": schema_test_refs, "commands_observed_in_ci": sorted({str(record["normalized"]) for record in target_test_records if record.get("normalized")})},
        "validators": validators,
        "schemas": schemas,
        "examples": examples,
        "generated_artifacts": generated,
        "release_paths": releases,
        "workflows": workflows,
        "semantic_model": semantic,
        "critical_execution_paths": semantic["critical_paths"],
        "relationships": sorted(relationships, key=lambda item: str(item.get("relationship_id"))),
        "capabilities": sorted(capabilities, key=lambda item: str(item["capability_id"])),
        "unresolved_evidence": sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"]))),
        "model_evidence": evidence("derived", paths, "Repository model combines contained no-symlink file collection, bounded config parsing, explicit workspace boundaries, Python AST resolution, behavioral workflow command evidence, runnable-job checks, and effective GitHub permission analysis; unsupported runtime semantics remain unresolved.", confidence="high"),
    }
