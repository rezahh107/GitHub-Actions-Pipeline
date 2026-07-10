"""Deterministic bounded collectors used by the repository model."""
from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path

import yaml

from tools.ci_command_evidence import parse_run_block, resolved_family
from tools.ci_upgrade_models import CAPABILITY_STATES, diagnostic, evidence

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
MAX_FILES = 25_000
MAX_TEXT_BYTES = 2_000_000
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


def iter_files(root: Path) -> tuple[list[Path], bool]:
    result: list[Path] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(directory for directory in dirs if directory not in SKIP)
        for name in sorted(files):
            result.append(Path(current) / name)
            if len(result) >= MAX_FILES:
                return result, True
    return result, False


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _load(path: Path) -> tuple[object | None, str | None]:
    text = _text(path)
    if text is None:
        return None, "unreadable_or_too_large"
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
    return "/tests/" in lower or "/test/" in lower or name.startswith("test_") or name.endswith("_test.py") or ".test." in name or ".spec." in name


def _negative(path: Path) -> bool:
    text = (_text(path) or "").lower()
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


def parse_workflow(root: Path, path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    data, error = _load(path)
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
        if not isinstance(raw_job, dict):
            diagnostics.append(diagnostic("WORKFLOW_JOB_MALFORMED", f"Job {jid!r} in {rp} must be a mapping.", affected_area="workflow_model", evidence_references=[f"{rp}#jobs.{jid}"], repair_hint="Replace the malformed job with a valid GitHub Actions job mapping."))
            continue
        job: dict[str, object] = {"job_id": str(jid), "name": raw_job.get("name") if isinstance(raw_job.get("name"), str) else None, "runs_on": raw_job.get("runs-on") if isinstance(raw_job.get("runs-on"), str) else None, "permissions": _raw_permissions(raw_job.get("permissions"), "permissions" in raw_job), "permission_declaration": parse_permission_declaration(raw_job, source=f"{rp}#jobs.{jid}.permissions"), "steps": []}
        job["effective_permissions"] = effective_permissions(workflow, job)
        if job["permission_declaration"]["form"] == "malformed":
            diagnostics.append(diagnostic("JOB_PERMISSIONS_MALFORMED", job["permission_declaration"]["reason"], affected_area="workflow_permissions", evidence_references=[job["permission_declaration"]["source"]], repair_hint="Use a supported job-level permissions mapping, read-all, write-all, or an explicit empty mapping."))
        raw_steps = raw_job.get("steps", [])
        if not isinstance(raw_steps, list):
            raw_steps = []
        steps: list[dict[str, object]] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                continue
            run = raw_step.get("run")
            uses = raw_step.get("uses")
            working_directory = raw_step.get("working-directory") if isinstance(raw_step.get("working-directory"), str) else None
            records = parse_run_block(run, working_directory=working_directory) if isinstance(run, str) else []
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


def _manifest(path: Path, rp: str) -> dict[str, object]:
    if path.name == "package.json":
        data, error = _load(path); data = data if isinstance(data, dict) else {}
        scripts = data.get("scripts", {}) if isinstance(data.get("scripts"), dict) else {}
        work = data.get("workspaces", [])
        if isinstance(work, dict): work = work.get("packages", [])
        deps = {**(data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}), **(data.get("devDependencies") if isinstance(data.get("devDependencies"), dict) else {})}
        return {"path": rp, "kind": "package_json", "parse_status": error or "parsed", "scripts": {str(key): str(value) for key, value in sorted(scripts.items())}, "dependencies": sorted(str(key) for key in deps), "workspaces": sorted(str(item) for item in work) if isinstance(work, list) else [], "package_name": data.get("name") if isinstance(data.get("name"), str) else None}
    if path.name == "pyproject.toml":
        data, error = _load(path); data = data if isinstance(data, dict) else {}
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
        text = _text(path) or ""
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


def _expand_workspace_roots(root: Path, patterns: list[str]) -> list[str]:
    roots: set[str] = set()
    for pattern in patterns:
        for match in sorted(root.glob(pattern)):
            if match.is_dir(): roots.add(match.relative_to(root).as_posix())
    return sorted(roots)


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
