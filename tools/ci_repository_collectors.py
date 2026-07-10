"""Deterministic bounded collectors used by the repository model.

All repository-controlled paths are treated as untrusted. Files and workspace
roots are admitted only after lexical containment, per-component ``lstat``
checks, resolved containment, type checks, and bounded expansion. Symlinks are
never followed for repository evidence.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import stat
import tomllib
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from tools.ci_command_evidence import parse_run_block, resolved_family
from tools.ci_upgrade_models import CAPABILITY_STATES, diagnostic, evidence

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
MAX_FILES = 25_000
MAX_TEXT_BYTES = 2_000_000
MAX_WORKSPACE_PATTERNS = 256
MAX_WORKSPACE_MATCHES = 1_000
WORKFLOW_EXECUTION_ELIGIBILITY_VERSION = "1.0.0"
LANG = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".json": "JSON", ".md": "Markdown", ".yml": "YAML", ".yaml": "YAML", ".php": "PHP", ".toml": "TOML", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".cs": "C#", ".java": "Java", ".sh": "Shell", ".html": "HTML", ".css": "CSS"}
MANIFEST = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt", "requirements-test.txt", "package.json", "composer.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"}
LOCK = {"uv.lock", "poetry.lock", "Pipfile.lock", "requirements.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock", "Cargo.lock"}
CONFIG = {"tox.ini", "pytest.ini", "mypy.ini", "ruff.toml", ".ruff.toml", "tsconfig.json", "vite.config.js", "vite.config.ts", "webpack.config.js", "webpack.config.ts"}
TEST_PATTERNS = ("pytest", "python -m pytest", "python -m unittest", "unittest discover", "npm test", "npm run test", "pnpm test", "yarn test", "vitest", "jest")
BUILD_PATTERNS = ("npm run build", "pnpm build", "yarn build", "python -m build", "cargo build", "go build", "mvn package", "gradle build")
INSTALL_PATTERNS = ("pip install", "uv sync", "npm ci", "pnpm install", "yarn install", "poetry install")
RELEASE_PATTERNS = ("twine check", "npm pack", "python -m build", "cargo package", "gh release")

PERMISSION_SCOPES = {"actions", "attestations", "checks", "contents", "deployments", "discussions", "id-token", "issues", "models", "packages", "pages", "pull-requests", "security-events", "statuses"}
PERMISSION_VALUES = {"read", "write", "none"}


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def repository_path(root: Path, candidate: Path, *, require_file: bool = False, require_directory: bool = False) -> tuple[Path | None, str | None]:
    """Validate one existing path without following repository symlinks."""
    canonical_root = root.resolve(strict=True)
    lexical = _lexical_absolute(candidate if candidate.is_absolute() else canonical_root / candidate)
    try:
        relative = lexical.relative_to(canonical_root)
    except ValueError:
        return None, "path_escape"
    current = canonical_root
    final_stat = None
    try:
        for part in relative.parts:
            current = current / part
            final_stat = current.lstat()
            if stat.S_ISLNK(final_stat.st_mode):
                return None, "symlink_component"
    except OSError:
        return None, "unreadable_or_missing"
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(canonical_root)
    except (OSError, ValueError, RuntimeError):
        return None, "resolved_path_escape"
    if final_stat is None:
        try:
            final_stat = canonical_root.lstat()
        except OSError:
            return None, "unreadable_or_missing"
    if require_file and not stat.S_ISREG(final_stat.st_mode):
        return None, "not_regular_file"
    if require_directory and not stat.S_ISDIR(final_stat.st_mode):
        return None, "not_directory"
    return resolved, None


def _path_reference(root: Path, path: Path) -> str:
    lexical = _lexical_absolute(path)
    try:
        return lexical.relative_to(root.resolve()).as_posix()
    except ValueError:
        return lexical.as_posix()


def _path_diagnostic(root: Path, path: Path, reason: str, *, area: str = "repository_inventory") -> dict[str, object]:
    code = "REPOSITORY_PATH_SYMLINK_REJECTED" if reason == "symlink_component" else "REPOSITORY_PATH_OUTSIDE_ROOT" if "escape" in reason else "REPOSITORY_PATH_REJECTED"
    reference = _path_reference(root, path)
    return diagnostic(code, f"Rejected repository-controlled path {reference!r}: {reason}.", affected_area=area, evidence_references=[reference], repair_hint="Use a regular file or directory contained beneath the canonical repository root; symlink evidence is not followed.", severity="warning")


def collect_repository_files(root: Path) -> tuple[list[Path], bool, list[dict[str, object]]]:
    canonical_root = root.resolve(strict=True)
    result: list[Path] = []
    diagnostics: list[dict[str, object]] = []
    for current_raw, dirs, files in os.walk(canonical_root, topdown=True, followlinks=False):
        current = Path(current_raw)
        retained_dirs: list[str] = []
        for directory in sorted(dirs):
            if directory in SKIP:
                continue
            candidate = current / directory
            safe, reason = repository_path(canonical_root, candidate, require_directory=True)
            if safe is None:
                diagnostics.append(_path_diagnostic(canonical_root, candidate, reason or "rejected"))
                continue
            retained_dirs.append(directory)
        dirs[:] = retained_dirs
        for name in sorted(files):
            candidate = current / name
            safe, reason = repository_path(canonical_root, candidate, require_file=True)
            if safe is None:
                diagnostics.append(_path_diagnostic(canonical_root, candidate, reason or "rejected"))
                continue
            result.append(safe)
            if len(result) >= MAX_FILES:
                return result, True, sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"])))
    return result, False, sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"])))


def iter_files(root: Path) -> tuple[list[Path], bool]:
    files, truncated, _ = collect_repository_files(root)
    return files, truncated


def rel(root: Path, path: Path) -> str:
    safe, reason = repository_path(root, path)
    if safe is None:
        raise ValueError(f"unsafe repository path: {reason}")
    return safe.relative_to(root.resolve()).as_posix()


def _text(path: Path, root: Path | None = None) -> str | None:
    try:
        safe = path
        if root is not None:
            safe, reason = repository_path(root, path, require_file=True)
            if safe is None:
                return None
        else:
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                return None
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(safe, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_TEXT_BYTES:
                return None
            with os.fdopen(descriptor, "r", encoding="utf-8", errors="strict", newline=None) as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except (OSError, UnicodeDecodeError):
        return None


def _load(path: Path, root: Path | None = None) -> tuple[object | None, str | None]:
    text = _text(path, root)
    if text is None:
        return None, "unreadable_or_too_large_or_unsafe"
    try:
        if path.suffix.lower() == ".json":
            return json.loads(text), None
        if path.suffix.lower() == ".toml":
            return tomllib.loads(text), None
        return yaml.safe_load(text), None
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as exc:
        return None, type(exc).__name__


def _is_test(path: str) -> bool:
    name = Path(path).name.lower()
    lower = f"/{path.lower()}"
    return "/tests/" in lower or "/test/" in lower or "/src/test/" in lower or name.startswith("test_") or name.endswith(("_test.py", "_test.go")) or ".test." in name or ".spec." in name


def _negative(path: Path, root: Path | None = None) -> bool:
    text = (_text(path, root) or "").lower()
    return any(token in text for token in ("assertraises", "pytest.raises", "rejects", "invalid", "malformed", "negative case", "error case"))


def _on(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    if isinstance(value, dict):
        return sorted(str(item) for item in value)
    return []


def _raw_permissions(value: object, present: bool) -> object:
    if not present:
        return None
    if isinstance(value, dict):
        normalized = {str(key): str(item).lower() for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
        if all(key in PERMISSION_SCOPES and item in PERMISSION_VALUES for key, item in normalized.items()):
            return normalized
        return None
    if isinstance(value, str) and value.lower() in {"read-all", "write-all"}:
        return value.lower()
    return None


def parse_permission_declaration(container: dict[str, object], *, source: str) -> dict[str, object]:
    if "permissions" not in container:
        return {"presence": "missing", "form": "missing", "values": {}, "source": source, "supported": False, "reason": "GitHub defaults are repository- and organization-dependent."}
    raw = container.get("permissions")
    if isinstance(raw, dict):
        normalized: dict[str, str] = {}
        malformed = False
        reasons: list[str] = []
        for key, value in sorted(raw.items(), key=lambda pair: str(pair[0])):
            scope = str(key)
            level = str(value).lower()
            normalized[scope] = level
            if scope not in PERMISSION_SCOPES:
                malformed = True
                reasons.append(f"unsupported scope {scope}")
            if level not in PERMISSION_VALUES:
                malformed = True
                reasons.append(f"unsupported value {level} for {scope}")
        form = "malformed" if malformed else "empty" if not normalized else "map"
        return {"presence": "explicit", "form": form, "values": normalized, "source": source, "supported": not malformed, "reason": "; ".join(reasons) if reasons else "Explicit permission mapping."}
    if isinstance(raw, str):
        value = raw.lower()
        supported = value in {"read-all", "write-all"}
        return {"presence": "explicit", "form": value if supported else "malformed", "values": {}, "source": source, "supported": supported, "reason": "Explicit permission shorthand." if supported else f"Unsupported permission shorthand {raw!r}."}
    return {"presence": "explicit", "form": "malformed", "values": {}, "source": source, "supported": False, "reason": f"Permissions must be a mapping, read-all, or write-all; received {type(raw).__name__}."}


def effective_permissions(workflow: dict[str, object], job: dict[str, object]) -> dict[str, object]:
    job_decl = job["permission_declaration"]
    workflow_decl = workflow["permission_declaration"]
    chosen = job_decl if job_decl["presence"] == "explicit" else workflow_decl
    inherited = job_decl["presence"] != "explicit" and workflow_decl["presence"] == "explicit"
    if chosen["form"] == "write-all" or any(value == "write" for value in chosen["values"].values()):
        access = "write"
    elif chosen["supported"] and chosen["form"] in {"empty", "map", "read-all"}:
        access = "read_or_none"
    else:
        access = "unknown"
    return {"source_scope": "job" if job_decl["presence"] == "explicit" else "workflow" if inherited else "platform_default", "form": chosen["form"], "values": chosen["values"], "access": access, "source": chosen["source"], "inherited": inherited, "supported": chosen["supported"], "reason": chosen["reason"]}


def _runs_on_supported(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, str) and item.strip() for item in value)
    if isinstance(value, dict):
        if not value or not set(value).issubset({"group", "labels"}):
            return False
        group = value.get("group")
        labels = value.get("labels")
        group_ok = group is None or (isinstance(group, str) and bool(group.strip()))
        labels_ok = labels is None or (isinstance(labels, str) and bool(labels.strip())) or (isinstance(labels, list) and bool(labels) and all(isinstance(item, str) and item.strip() for item in labels))
        return group_ok and labels_ok and (group is not None or labels is not None)
    return False


def _job_shape(raw_job: dict[str, object]) -> tuple[str, str]:
    reusable = isinstance(raw_job.get("uses"), str) and bool(str(raw_job.get("uses")).strip())
    has_runs_on = "runs-on" in raw_job
    has_steps = "steps" in raw_job
    if reusable:
        if has_runs_on or has_steps:
            return "invalid", "reusable_job_mixes_uses_with_runs_on_or_steps"
        return "reusable", "reusable_workflow_body_not_resolved"
    if not _runs_on_supported(raw_job.get("runs-on")):
        return "invalid", "missing_or_unsupported_runs_on"
    if not isinstance(raw_job.get("steps"), list):
        return "invalid", "normal_job_steps_must_be_array"
    return "normal", "runnable_normal_job"


def _condition_eligibility(container: dict[str, object]) -> tuple[str, str]:
    """Classify a bounded condition without evaluating GitHub expressions."""
    if "if" not in container:
        return "eligible", "condition_absent"
    value = container.get("if")
    if isinstance(value, bool):
        return ("eligible", "literal_true") if value else ("disabled", "literal_false")
    if not isinstance(value, str):
        return "invalid", "condition_must_be_boolean_or_string"
    normalized = value.strip()
    if normalized.startswith("${{") and normalized.endswith("}}"):
        normalized = normalized[3:-2].strip()
    lowered = normalized.lower()
    if lowered == "true":
        return "eligible", "literal_true"
    if lowered == "false":
        return "disabled", "literal_false"
    return "conditional", "dynamic_condition_unresolved"


def _gate_records(records: list[dict[str, object]], state: str, reason: str) -> list[dict[str, object]]:
    if state == "eligible":
        return records
    target_status = "inert" if state == "disabled" else "unsupported"
    gated: list[dict[str, object]] = []
    for record in records:
        if record.get("status") == "resolved":
            gated.append({**record, "status": target_status, "reason": reason, "families": []})
        else:
            gated.append(record)
    return gated


def _condition_diagnostic(scope: str, reference: str, state: str, reason: str) -> dict[str, object] | None:
    if state == "eligible":
        return None
    if state == "disabled":
        return diagnostic(
            f"WORKFLOW_{scope.upper()}_CONDITION_DISABLED",
            f"{scope.title()} {reference} is deterministically disabled by a literal-false condition under execution-eligibility model {WORKFLOW_EXECUTION_ELIGIBILITY_VERSION}.",
            affected_area="workflow_execution",
            evidence_references=[reference],
            repair_hint="Remove the literal-false condition before treating this execution path as operational evidence.",
            severity="info",
        )
    if state == "conditional":
        return diagnostic(
            f"WORKFLOW_{scope.upper()}_CONDITION_UNRESOLVED",
            f"{scope.title()} {reference} uses a dynamic condition that the bounded analyzer does not evaluate under execution-eligibility model {WORKFLOW_EXECUTION_ELIGIBILITY_VERSION}.",
            affected_area="workflow_execution",
            evidence_references=[reference],
            repair_hint="Use an absent or literal-true condition for unconditional static proof, or model this expression under a separately versioned condition evaluator.",
            severity="info",
        )
    return diagnostic(
        f"WORKFLOW_{scope.upper()}_CONDITION_MALFORMED",
        f"{scope.title()} {reference} has a malformed condition: {reason}.",
        affected_area="workflow_execution",
        evidence_references=[reference],
        repair_hint="Use a valid GitHub Actions boolean or expression string; malformed conditions cannot establish execution evidence.",
        severity="warning",
    )


def parse_workflow(root: Path, path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    data, error = _load(path, root)
    rp = rel(root, path)
    base = {"path": rp, "parse_status": error or "invalid_shape", "name": None, "triggers": [], "permissions": None, "permission_declaration": {"presence": "missing", "form": "malformed", "values": {}, "source": f"{rp}#permissions", "supported": False, "reason": "Workflow could not be parsed."}, "jobs": [], "commands": [], "command_evidence": []}
    if error or not isinstance(data, dict):
        return base, [diagnostic("WORKFLOW_PARSE_FAILED", f"Could not parse workflow {rp}: {error or 'invalid shape'}.", affected_area="workflow_model", evidence_references=[rp], repair_hint=f"Repair YAML syntax or shape in {rp}.")]
    workflow_decl = parse_permission_declaration(data, source=f"{rp}#permissions")
    workflow: dict[str, object] = {"path": rp, "parse_status": "parsed", "name": data.get("name") if isinstance(data.get("name"), str) else None, "triggers": _on(data.get("on", data.get(True))), "permissions": _raw_permissions(data.get("permissions"), "permissions" in data), "permission_declaration": workflow_decl, "jobs": [], "commands": [], "command_evidence": []}
    diagnostics: list[dict[str, object]] = []
    if workflow_decl["form"] == "malformed":
        diagnostics.append(diagnostic("WORKFLOW_PERMISSIONS_MALFORMED", workflow_decl["reason"], affected_area="workflow_permissions", evidence_references=[workflow_decl["source"]], repair_hint="Use a supported GitHub Actions permissions mapping, read-all, write-all, or an explicit empty mapping."))
    raw_jobs = data.get("jobs", {})
    if not isinstance(raw_jobs, dict):
        diagnostics.append(diagnostic("WORKFLOW_JOBS_MALFORMED", f"Workflow {rp} jobs must be a mapping.", affected_area="workflow_model", evidence_references=[rp], repair_hint=f"Repair the jobs mapping in {rp}."))
        raw_jobs = {}
    jobs: list[dict[str, object]] = []
    all_records: list[dict[str, object]] = []
    for jid, raw_job in sorted(raw_jobs.items(), key=lambda pair: str(pair[0])):
        reference = f"{rp}#jobs.{jid}"
        if not isinstance(raw_job, dict):
            diagnostics.append(diagnostic("WORKFLOW_JOB_MALFORMED", f"Job {jid!r} in {rp} must be a mapping.", affected_area="workflow_model", evidence_references=[reference], repair_hint="Replace the malformed job with a valid normal or reusable GitHub Actions job mapping."))
            continue
        shape, shape_reason = _job_shape(raw_job)
        job_condition_state, job_condition_reason = _condition_eligibility(raw_job)
        condition_diagnostic = _condition_diagnostic("job", reference, job_condition_state, job_condition_reason)
        if condition_diagnostic is not None:
            diagnostics.append(condition_diagnostic)
        if shape == "invalid":
            diagnostics.append(diagnostic("WORKFLOW_JOB_NOT_RUNNABLE", f"Job {jid!r} in {rp} is not structurally runnable: {shape_reason}.", affected_area="workflow_execution", evidence_references=[reference], repair_hint="Provide a supported runs-on plus steps normal job, or a standalone reusable-workflow uses job."))
        elif shape == "reusable":
            diagnostics.append(diagnostic("REUSABLE_WORKFLOW_JOB_UNRESOLVED", f"Reusable workflow job {jid!r} is structurally recognized but its called workflow body is outside local command evidence.", affected_area="workflow_execution", evidence_references=[reference], repair_hint="Analyze the called workflow under a separate versioned trust boundary before using it as executable capability evidence.", severity="info"))
        job: dict[str, object] = {"job_id": str(jid), "name": raw_job.get("name") if isinstance(raw_job.get("name"), str) else None, "runs_on": raw_job.get("runs-on") if isinstance(raw_job.get("runs-on"), str) else None, "permissions": _raw_permissions(raw_job.get("permissions"), "permissions" in raw_job), "permission_declaration": parse_permission_declaration(raw_job, source=f"{rp}#jobs.{jid}.permissions"), "steps": []}
        job["effective_permissions"] = effective_permissions(workflow, job)
        if job["permission_declaration"]["form"] == "malformed":
            diagnostics.append(diagnostic("JOB_PERMISSIONS_MALFORMED", job["permission_declaration"]["reason"], affected_area="workflow_permissions", evidence_references=[job["permission_declaration"]["source"]], repair_hint="Use a supported job-level permissions mapping, read-all, write-all, or an explicit empty mapping."))
        raw_steps = raw_job.get("steps", []) if shape != "reusable" else []
        if not isinstance(raw_steps, list):
            raw_steps = []
        steps: list[dict[str, object]] = []
        for index, raw_step in enumerate(raw_steps):
            step_reference = f"{reference}.steps[{index}]"
            if not isinstance(raw_step, dict):
                diagnostics.append(diagnostic("WORKFLOW_STEP_MALFORMED", f"Step {index} in job {jid!r} must be a mapping.", affected_area="workflow_execution", evidence_references=[step_reference], repair_hint="Replace the malformed step with a valid run, uses, or supported non-command step mapping."))
                continue
            run = raw_step.get("run")
            uses = raw_step.get("uses")
            has_run = isinstance(run, str)
            has_uses = isinstance(uses, str)
            invalid_execution_form = has_run and has_uses
            if invalid_execution_form:
                diagnostics.append(diagnostic("WORKFLOW_STEP_EXECUTION_FORM_INVALID", f"Step {index} in job {jid!r} contains both run and uses and cannot establish command execution evidence.", affected_area="workflow_execution", evidence_references=[step_reference], repair_hint="Choose exactly one execution form for this step: run or uses.", severity="warning"))
            step_condition_state, step_condition_reason = _condition_eligibility(raw_step)
            step_condition_diagnostic = _condition_diagnostic("step", step_reference, step_condition_state, step_condition_reason)
            if step_condition_diagnostic is not None:
                diagnostics.append(step_condition_diagnostic)
            working_directory = raw_step.get("working-directory") if isinstance(raw_step.get("working-directory"), str) else None
            records = parse_run_block(run, working_directory=working_directory) if has_run else []
            if shape != "normal":
                records = _gate_records(records, "invalid", "job_not_runnable")
            elif job_condition_state != "eligible":
                records = _gate_records(records, job_condition_state, f"job_condition_{job_condition_reason}")
            elif invalid_execution_form:
                records = _gate_records(records, "invalid", "step_mixes_run_and_uses")
            elif step_condition_state != "eligible":
                records = _gate_records(records, step_condition_state, f"step_condition_{step_condition_reason}")
            all_records.extend({**record, "workflow": rp, "job_id": str(jid), "step_index": index} for record in records)
            steps.append({"index": index, "name": raw_step.get("name") if isinstance(raw_step.get("name"), str) else None, "uses": uses if isinstance(uses, str) else None, "run": run if isinstance(run, str) else None, "working_directory": working_directory, "command_evidence": records})
        job["steps"] = steps
        jobs.append(job)
    workflow["jobs"] = jobs
    workflow["command_evidence"] = sorted(all_records, key=lambda item: (str(item["job_id"]), int(item["step_index"]), int(item["line"]), str(item["raw"])))
    workflow["commands"] = sorted({str(item["normalized"]) for item in all_records if item.get("status") == "resolved" and item.get("normalized")})
    return workflow, diagnostics


def _parse_requirement_names(text: str) -> list[str]:
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:")):
            continue
        name = re.split(r"[<>=!~\[; ]", line, 1)[0].strip()
        if name:
            names.append(name)
    return sorted(set(names))


def _manifest(path: Path, rp: str, root: Path | None = None) -> dict[str, object]:
    if path.name == "package.json":
        data, error = _load(path, root); data = data if isinstance(data, dict) else {}
        scripts = data.get("scripts", {}) if isinstance(data.get("scripts"), dict) else {}
        work = data.get("workspaces", [])
        if isinstance(work, dict): work = work.get("packages", [])
        deps = {**(data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}), **(data.get("devDependencies") if isinstance(data.get("devDependencies"), dict) else {})}
        return {"path": rp, "kind": "package_json", "parse_status": error or "parsed", "scripts": {str(key): str(value) for key, value in sorted(scripts.items())}, "dependencies": sorted(str(key) for key in deps), "workspaces": sorted(str(item) for item in work) if isinstance(work, list) else [], "package_name": data.get("name") if isinstance(data.get("name"), str) else None}
    if path.name == "pyproject.toml":
        data, error = _load(path, root); data = data if isinstance(data, dict) else {}
        project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
        scripts = project.get("scripts", {}) if isinstance(project.get("scripts"), dict) else {}
        deps = project.get("dependencies", []) if isinstance(project.get("dependencies"), list) else []
        build = data.get("build-system", {}) if isinstance(data.get("build-system"), dict) else {}
        tool = data.get("tool", {}) if isinstance(data.get("tool"), dict) else {}
        workspace: list[str] = []
        for value in tool.values():
            if isinstance(value, dict) and isinstance(value.get("workspace"), dict) and isinstance(value["workspace"].get("members"), list):
                workspace.extend(str(item) for item in value["workspace"]["members"])
        return {"path": rp, "kind": "pyproject", "parse_status": error or "parsed", "scripts": {str(key): str(value) for key, value in sorted(scripts.items())}, "dependencies": sorted(str(item) for item in deps), "build_backend": build.get("build-backend"), "workspaces": sorted(set(workspace)), "package_name": project.get("name") if isinstance(project.get("name"), str) else None}
    if path.name.startswith("requirements") and path.suffix == ".txt":
        text = _text(path, root) or ""
        return {"path": rp, "kind": "requirements", "parse_status": "parsed" if text else "empty_or_unreadable", "dependencies": _parse_requirement_names(text), "scripts": {}, "workspaces": []}
    return {"path": rp, "kind": path.name, "parse_status": "observed_only", "scripts": {}, "dependencies": [], "workspaces": []}


def _has(records: list[dict[str, object]], family_or_patterns: object) -> bool:
    if isinstance(family_or_patterns, str): family = family_or_patterns
    elif family_or_patterns is TEST_PATTERNS: family = "test"
    elif family_or_patterns is BUILD_PATTERNS: family = "build"
    elif family_or_patterns is INSTALL_PATTERNS: family = "install"
    elif family_or_patterns is RELEASE_PATTERNS: family = "release"
    else: return False
    return resolved_family(records, family)


def _cap(cid: str, state: str, refs: list[str], why: str, hint: str | None = None) -> dict[str, object]:
    if state not in CAPABILITY_STATES: raise ValueError(f"invalid capability state: {state}")
    out = {"capability_id": cid, "state": state, "evidence": evidence("observed" if refs else "unavailable", refs, why, confidence="high" if state in {"operational", "not_applicable"} else "medium")}
    if hint: out["repair_hint"] = hint
    return out


def _normalize_workspace_pattern(pattern: str) -> tuple[str | None, str | None]:
    if not pattern or "\x00" in pattern or "\\" in pattern:
        return None, "empty_nul_or_non_posix_pattern"
    posix = PurePosixPath(pattern)
    windows = PureWindowsPath(pattern)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None, "absolute_workspace_pattern"
    if any(part == ".." for part in posix.parts):
        return None, "parent_workspace_pattern"
    normalized_parts = [part for part in posix.parts if part not in {"", "."}]
    if not normalized_parts:
        return None, "empty_workspace_pattern"
    return "/".join(normalized_parts), None


def _workspace_pattern_matches(relative: str, pattern: str) -> bool:
    path_parts = PurePosixPath(relative).parts
    pattern_parts = PurePosixPath(pattern).parts
    def match(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        token = pattern_parts[pattern_index]
        if token == "**":
            return match(path_index, pattern_index + 1) or (path_index < len(path_parts) and match(path_index + 1, pattern_index))
        return path_index < len(path_parts) and fnmatch.fnmatchcase(path_parts[path_index], token) and match(path_index + 1, pattern_index + 1)
    return match(0, 0)


def _safe_repository_directories(root: Path) -> tuple[list[str], list[dict[str, object]]]:
    canonical_root = root.resolve(strict=True)
    directories: set[str] = {"."}
    diagnostics: list[dict[str, object]] = []
    for current_raw, dirs, _ in os.walk(canonical_root, topdown=True, followlinks=False):
        current = Path(current_raw)
        retained: list[str] = []
        for directory in sorted(dirs):
            if directory in SKIP:
                continue
            candidate = current / directory
            safe, reason = repository_path(canonical_root, candidate, require_directory=True)
            if safe is None:
                diagnostics.append(_path_diagnostic(canonical_root, candidate, reason or "rejected", area="workspace_boundaries"))
                continue
            retained.append(directory)
            directories.add(safe.relative_to(canonical_root).as_posix())
        dirs[:] = retained
    return sorted(directories), diagnostics


def expand_workspace_roots(root: Path, patterns: list[str]) -> tuple[list[str], list[dict[str, object]]]:
    canonical_root = root.resolve(strict=True)
    roots: set[str] = set()
    safe_directories, directory_diagnostics = _safe_repository_directories(canonical_root)
    diagnostics: list[dict[str, object]] = list(directory_diagnostics)
    if len(patterns) > MAX_WORKSPACE_PATTERNS:
        diagnostics.append(diagnostic("WORKSPACE_PATTERN_LIMIT_EXCEEDED", f"Workspace pattern collection was truncated at {MAX_WORKSPACE_PATTERNS} entries.", affected_area="workspace_boundaries", repair_hint="Reduce or consolidate workspace declarations before increasing the versioned bound.", severity="warning"))
    match_count = 0
    for raw_pattern in patterns[:MAX_WORKSPACE_PATTERNS]:
        pattern, reason = _normalize_workspace_pattern(raw_pattern)
        if pattern is None:
            diagnostics.append(diagnostic("WORKSPACE_PATTERN_REJECTED", f"Rejected workspace pattern {raw_pattern!r}: {reason}.", affected_area="workspace_boundaries", evidence_references=[raw_pattern], repair_hint="Use a normalized relative POSIX pattern without parent traversal, drive, absolute root, backslash, or NUL.", severity="warning"))
            continue
        matches = [directory for directory in safe_directories if directory != "." and _workspace_pattern_matches(directory, pattern)]
        for relative in matches:
            if match_count >= MAX_WORKSPACE_MATCHES:
                diagnostics.append(diagnostic("WORKSPACE_MATCH_LIMIT_EXCEEDED", f"Workspace expansion stopped at {MAX_WORKSPACE_MATCHES} matched directories.", affected_area="workspace_boundaries", repair_hint="Narrow workspace globs before increasing the versioned expansion bound.", severity="warning"))
                return sorted(roots), sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"])))
            safe, path_reason = repository_path(canonical_root, canonical_root / relative, require_directory=True)
            if safe is None:
                diagnostics.append(_path_diagnostic(canonical_root, canonical_root / relative, path_reason or "rejected", area="workspace_boundaries"))
                continue
            roots.add(relative)
            match_count += 1
    return sorted(roots), sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"])))


def _expand_workspace_roots(root: Path, patterns: list[str]) -> list[str]:
    return expand_workspace_roots(root, patterns)[0]


def _nearest_component(path: str, roots: list[str]) -> str:
    matches = [root for root in roots if root == "." or path == root or path.startswith(root.rstrip("/") + "/")]
    return max(matches, key=lambda item: (len(item), item)) if matches else "."


def _command_candidates(parsed: list[dict[str, object]], paths: list[str], tests: list[str]) -> dict[str, list[dict[str, object]]]:
    out: dict[str, list[dict[str, object]]] = {"install": [], "test": [], "build": [], "schema": [], "release": []}
    names = {Path(path).name for path in paths}
    if any(manifest.get("kind") in {"pyproject", "requirements"} for manifest in parsed):
        if "requirements-test.txt" in names: out["install"].append({"command": "python -m pip install -r requirements-test.txt", "basis": "requirements-test.txt", "confidence": "high"})
        elif "requirements.txt" in names: out["install"].append({"command": "python -m pip install -r requirements.txt", "basis": "requirements.txt", "confidence": "high"})
        elif any(manifest.get("kind") == "pyproject" for manifest in parsed): out["install"].append({"command": "python -m pip install .", "basis": "pyproject.toml", "confidence": "medium"})
        if tests:
            if any("pytest" in str(manifest.get("dependencies", [])).lower() for manifest in parsed) or "pytest.ini" in names: out["test"].append({"command": "python -m pytest", "basis": "pytest dependency/config", "confidence": "high"})
            else: out["test"].append({"command": "python -m unittest discover -s tests", "basis": "Python test paths without pytest evidence", "confidence": "medium"})
        if any(manifest.get("build_backend") for manifest in parsed): out["build"].append({"command": "python -m build", "basis": "pyproject build-system", "confidence": "high"})
    for manifest in parsed:
        if manifest.get("kind") != "package_json": continue
        source = str(manifest.get("path")); scripts = manifest.get("scripts", {})
        if "package-lock.json" in names: out["install"].append({"command": "npm ci", "basis": "package-lock.json", "component": str(Path(source).parent), "confidence": "high"})
        for key, category in (("test", "test"), ("build", "build")):
            if isinstance(scripts, dict) and key in scripts: out[category].append({"command": f"npm run {key}" if key != "test" else "npm test", "basis": source, "component": str(Path(source).parent), "confidence": "high"})
    for test in tests:
        if "schema" in (Path(test).name + " " + test).lower(): out["schema"].append({"command": "canonical test command", "basis": test, "confidence": "medium"})
    return {key: sorted(value, key=lambda item: (str(item.get("component", "")), str(item["command"]), str(item["basis"]))) for key, value in out.items()}
