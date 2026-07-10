"""Deterministic, evidence-labelled repository model for CI upgrade analysis."""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any, Iterable

SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "dotnet",
    ".php": "php",
    ".rb": "ruby",
}
MANIFEST_ECOSYSTEMS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "composer.json": "php",
    "Gemfile": "ruby",
}
LOCKFILES = {
    "poetry.lock": "python",
    "uv.lock": "python",
    "Pipfile.lock": "python",
    "requirements.lock": "python",
    "package-lock.json": "node",
    "pnpm-lock.yaml": "node",
    "yarn.lock": "node",
    "bun.lockb": "node",
    "go.sum": "go",
    "Cargo.lock": "rust",
    "composer.lock": "php",
    "Gemfile.lock": "ruby",
}
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "dist", "build", ".next", "coverage",
}
WORKFLOW_COMMAND_MARKERS = (
    "pytest", "unittest", "npm test", "npm run test", "pnpm test", "yarn test",
    "go test", "cargo test", "mvn test", "gradle test", "dotnet test",
    "ruff", "flake8", "pylint", "mypy", "pyright", "eslint", "tsc",
    "go vet", "golangci-lint", "cargo clippy", "cargo fmt",
    "npm run build", "pnpm build", "yarn build", "go build", "cargo build",
    "python -m build", "twine check",
)
TEST_NAME_RE = re.compile(r"(^test_.*\.py$|.*_test\.py$|.*\.(test|spec)\.[^.]+$)", re.I)


def iter_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        base = Path(current_root)
        for name in sorted(files):
            yield base / name


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return value if isinstance(value, dict) else None, None


def _safe_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, str(exc)
    return value if isinstance(value, dict) else None, None


def _component_roots(root: Path, files: list[Path]) -> list[Path]:
    roots: set[Path] = set()
    for path in files:
        if path.name in MANIFEST_ECOSYSTEMS:
            roots.add(path.parent)
        elif path.suffix == ".csproj":
            roots.add(path.parent)
    if not roots:
        roots.add(root)
    return sorted(roots, key=lambda p: (len(p.relative_to(root).parts), p.as_posix()))


def _in_component(path: Path, component_root: Path, all_roots: list[Path]) -> bool:
    try:
        path.relative_to(component_root)
    except ValueError:
        return False
    for other in all_roots:
        if other == component_root:
            continue
        try:
            other.relative_to(component_root)
        except ValueError:
            continue
        try:
            path.relative_to(other)
            return False
        except ValueError:
            pass
    return True


def _frameworks_for_component(component_root: Path, component_files: list[Path]) -> tuple[list[str], list[str]]:
    frameworks: set[str] = set()
    limitations: list[str] = []
    package_json = component_root / "package.json"
    if package_json.exists():
        data, error = _safe_json(package_json)
        if error:
            limitations.append(f"package.json could not be parsed: {error}")
        elif data:
            deps: dict[str, Any] = {}
            for field in ("dependencies", "devDependencies", "peerDependencies"):
                value = data.get(field)
                if isinstance(value, dict):
                    deps.update(value)
            mapping = {
                "react": "react", "next": "nextjs", "vue": "vue", "svelte": "svelte",
                "express": "express", "fastify": "fastify", "nestjs": "nestjs",
                "vitest": "vitest", "jest": "jest",
            }
            for dependency, framework in mapping.items():
                if dependency in deps:
                    frameworks.add(framework)

    pyproject = component_root / "pyproject.toml"
    if pyproject.exists():
        data, error = _safe_toml(pyproject)
        if error:
            limitations.append(f"pyproject.toml could not be parsed: {error}")
        elif data:
            project = data.get("project", {})
            dependency_values: list[str] = []
            if isinstance(project, dict):
                raw = project.get("dependencies", [])
                if isinstance(raw, list):
                    dependency_values.extend(str(item).lower() for item in raw)
                optional = project.get("optional-dependencies", {})
                if isinstance(optional, dict):
                    for items in optional.values():
                        if isinstance(items, list):
                            dependency_values.extend(str(item).lower() for item in items)
            poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
            if isinstance(poetry, dict) and isinstance(poetry.get("dependencies"), dict):
                dependency_values.extend(str(key).lower() for key in poetry["dependencies"])
            joined = "\n".join(dependency_values)
            mapping = {
                "fastapi": "fastapi", "django": "django", "flask": "flask",
                "celery": "celery", "pandas": "data-pipeline", "airflow": "airflow",
                "torch": "ml", "tensorflow": "ml", "pytest": "pytest",
            }
            for token, framework in mapping.items():
                if token in joined:
                    frameworks.add(framework)

    names = {path.name for path in component_files}
    if "manage.py" in names:
        frameworks.add("django")
    if any(path.name == "manifest.json" for path in component_files):
        for path in component_files:
            if path.name == "manifest.json":
                data, _ = _safe_json(path)
                if data and data.get("manifest_version") in {2, 3}:
                    frameworks.add("browser-extension")
                    break
    return sorted(frameworks), limitations


def _archetypes(ecosystems: list[str], frameworks: list[str], files: list[str]) -> list[str]:
    result: set[str] = set()
    joined = "\n".join(files).lower()
    if "python" in ecosystems:
        if "fastapi" in frameworks or "flask" in frameworks:
            result.add("python-api-service")
        if "django" in frameworks:
            result.add("python-django-application")
        if "celery" in frameworks:
            result.add("python-async-worker")
        if "data-pipeline" in frameworks or "airflow" in frameworks:
            result.add("python-data-pipeline")
        if "ml" in frameworks:
            result.add("python-ml-service")
        if "pyproject.toml" in joined or "setup.py" in joined:
            result.add("python-package")
        if any(path.endswith("__main__.py") or "/cli" in path for path in files):
            result.add("python-cli")
        if not result:
            result.add("python-application")
    if "node" in ecosystems:
        if any(item in frameworks for item in ("react", "nextjs", "vue", "svelte")):
            result.add("node-frontend-application")
        if any(item in frameworks for item in ("express", "fastify", "nestjs")):
            result.add("node-service")
        if "browser-extension" in frameworks:
            result.add("browser-extension")
        if not any(item.startswith("node-") for item in result):
            result.add("node-package")
    if "go" in ecosystems:
        result.add("go-module")
    if "rust" in ecosystems:
        result.add("rust-crate")
    if any("/schemas/" in f"/{p}" or p.startswith("schemas/") for p in files):
        result.add("contract-schema-repository")
    return sorted(result)


def _extract_script_commands(component_root: Path) -> tuple[list[str], list[str], list[str]]:
    test_commands: set[str] = set()
    build_commands: set[str] = set()
    entry_points: set[str] = set()
    package_json = component_root / "package.json"
    if package_json.exists():
        data, _ = _safe_json(package_json)
        scripts = data.get("scripts", {}) if data else {}
        if isinstance(scripts, dict):
            for name, command in scripts.items():
                if not isinstance(command, str):
                    continue
                if "test" in name:
                    test_commands.add(f"npm run {name}")
                if name in {"build", "compile", "package"} or "build" in name:
                    build_commands.add(f"npm run {name}")
        if data:
            for field in ("main", "module", "bin"):
                value = data.get(field)
                if isinstance(value, str):
                    entry_points.add(value)
                elif isinstance(value, dict):
                    entry_points.update(str(v) for v in value.values())

    pyproject = component_root / "pyproject.toml"
    if pyproject.exists():
        data, _ = _safe_toml(pyproject)
        if data:
            project = data.get("project", {})
            if isinstance(project, dict):
                scripts = project.get("scripts", {})
                if isinstance(scripts, dict):
                    entry_points.update(str(value) for value in scripts.values())
            tool = data.get("tool", {})
            if isinstance(tool, dict):
                if "pytest" in tool:
                    test_commands.add("python -m pytest")
                if "hatch" in tool or "poetry" in tool:
                    build_commands.add("python -m build")
    if (component_root / "go.mod").exists():
        test_commands.add("go test ./...")
        build_commands.add("go build ./...")
    if (component_root / "Cargo.toml").exists():
        test_commands.add("cargo test")
        build_commands.add("cargo build")
    return sorted(test_commands), sorted(build_commands), sorted(entry_points)


def _parse_workflow(path: Path, root: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "path": rel(root, path), "name": None, "triggers": [], "permissions": {},
            "jobs": [], "commands": [], "actions": [], "evidence_state": "unavailable",
            "limitations": [str(exc)],
        }
    lines = text.splitlines()
    name = None
    triggers: set[str] = set()
    permissions: dict[str, str] = {}
    jobs: set[str] = set()
    commands: list[str] = []
    actions: list[str] = []
    in_permissions = False
    permission_indent = 0
    in_jobs = False
    jobs_indent = 0
    for raw in lines:
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("name:") and name is None:
            name = stripped.split(":", 1)[1].strip().strip("'\"") or None
        if re.match(r"^(pull_request|push|workflow_dispatch|schedule|release|merge_group)\s*:", stripped):
            triggers.add(stripped.split(":", 1)[0])
        if stripped == "permissions:":
            in_permissions = True
            permission_indent = indent
            continue
        if in_permissions:
            if indent <= permission_indent:
                in_permissions = False
            else:
                key, sep, value = stripped.partition(":")
                if sep and value.strip() in {"read", "write", "none"}:
                    permissions[key.strip()] = value.strip()
                    continue
        if stripped == "jobs:":
            in_jobs = True
            jobs_indent = indent
            continue
        if in_jobs:
            if indent <= jobs_indent:
                in_jobs = False
            elif indent == jobs_indent + 2 and stripped.endswith(":"):
                jobs.add(stripped[:-1].strip())
        if stripped.startswith("run:"):
            command = stripped.split(":", 1)[1].strip()
            if command and command not in {"|", ">"}:
                commands.append(command)
        if stripped.startswith("uses:"):
            actions.append(stripped.split(":", 1)[1].strip())
    lower = text.lower()
    for marker in WORKFLOW_COMMAND_MARKERS:
        if marker in lower and marker not in {item.lower() for item in commands}:
            commands.append(marker)
    return {
        "path": rel(root, path),
        "name": name,
        "triggers": sorted(triggers),
        "permissions": dict(sorted(permissions.items())),
        "jobs": sorted(jobs),
        "commands": sorted(set(commands)),
        "actions": sorted(set(actions)),
        "evidence_state": "derived",
        "limitations": [
            "Workflow structure was extracted with a bounded deterministic text parser; YAML anchors and expressions are not fully evaluated."
        ],
    }


def build_repository_model(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = list(iter_files(root))
    relative_files = sorted(rel(root, path) for path in files)
    component_roots = _component_roots(root, files)
    components: list[dict[str, Any]] = []
    all_languages = sorted({
        SOURCE_EXTENSIONS[path.suffix.lower()]
        for path in files
        if path.suffix.lower() in SOURCE_EXTENSIONS
    })

    for component_root in component_roots:
        component_files = [path for path in files if _in_component(path, component_root, component_roots)]
        component_rel_files = sorted(rel(root, path) for path in component_files)
        manifests = sorted(
            rel(root, path) for path in component_files
            if path.name in MANIFEST_ECOSYSTEMS or path.suffix == ".csproj"
        )
        ecosystems = sorted({
            MANIFEST_ECOSYSTEMS[path.name]
            for path in component_files if path.name in MANIFEST_ECOSYSTEMS
        } | ({"dotnet"} if any(path.suffix == ".csproj" for path in component_files) else set()))
        locks = sorted(rel(root, path) for path in component_files if path.name in LOCKFILES)
        tests = sorted(
            rel(root, path) for path in component_files
            if TEST_NAME_RE.match(path.name) or "tests" in path.parts or "test" in path.parts
        )
        schemas = sorted(
            rel(root, path) for path in component_files
            if path.name.endswith(".schema.json") or "schemas" in path.parts
        )
        validators = sorted(
            rel(root, path) for path in component_files
            if any(token in path.name.lower() for token in ("validat", "check", "lint"))
            and path.suffix.lower() in (set(SOURCE_EXTENSIONS) | {".sh"})
        )
        release_files = sorted(
            rel(root, path) for path in component_files
            if path.name in {"VERSION", "CHANGELOG.md", "release.yml", "release.yaml"}
            or "release" in path.parts
        )
        generated = sorted(
            rel(root, path) for path in component_files
            if "generated" in path.parts or path.name.lower().startswith("generated_")
        )
        frameworks, limitations = _frameworks_for_component(component_root, component_files)
        test_commands, build_commands, entry_points = _extract_script_commands(component_root)
        component_id = rel(root, component_root) if component_root != root else "."
        components.append({
            "component_id": component_id,
            "root": component_id,
            "evidence_state": "observed",
            "ecosystems": ecosystems,
            "frameworks": frameworks,
            "archetypes": _archetypes(ecosystems, frameworks, component_rel_files),
            "manifests": manifests,
            "lockfiles": locks,
            "entry_points": entry_points,
            "test_files": tests,
            "test_commands": test_commands,
            "build_commands": build_commands,
            "validators": validators,
            "schemas": schemas,
            "generated_artifacts": generated,
            "release_files": release_files,
            "source_files": sorted(
                rel(root, path) for path in component_files
                if path.suffix.lower() in SOURCE_EXTENSIONS
            ),
            "limitations": limitations,
        })

    workflow_paths = [
        path for path in files
        if rel(root, path).startswith(".github/workflows/")
        and path.suffix.lower() in {".yml", ".yaml"}
    ]
    workflows = [_parse_workflow(path, root) for path in workflow_paths]
    archetypes = sorted({item for component in components for item in component["archetypes"]})
    root_package = root / "package.json"
    if root_package.exists():
        package_data, _ = _safe_json(root_package)
        if package_data and package_data.get("workspaces"):
            archetypes.append("node-monorepo")
    if any(
        any(token in path.lower() for token in ("adapter", "mapping", "integration"))
        for path in relative_files
    ) and any(path.startswith("contracts/") or "schema" in path.lower() for path in relative_files):
        archetypes.append("multi-repository-adapter")
    if relative_files and all(
        path.endswith((".md", ".rst", ".txt", ".adoc")) or path.startswith(".github/")
        for path in relative_files
    ):
        archetypes.append("documentation-only-repository")
    archetypes = sorted(set(archetypes))

    source_to_test: list[dict[str, Any]] = []
    all_tests = [p for component in components for p in component["test_files"]]
    for component in components:
        for source in component["source_files"]:
            source_stem = Path(source).stem.lower()
            matches = sorted(test for test in all_tests if source_stem in Path(test).stem.lower())
            if matches:
                source_to_test.append({
                    "source": source, "tests": matches, "evidence_state": "derived",
                    "confidence": "medium",
                })

    return {
        "model_version": "1",
        "repository_root": ".",
        "file_count": len(relative_files),
        "languages": all_languages,
        "archetypes": archetypes,
        "components": components,
        "workflows": workflows,
        "source_to_test_relationships": source_to_test,
        "unresolved_evidence": [
            "Dynamic workflow expressions, runtime imports, and generated-source relationships are not executed by the local model.",
            "Remote workflow telemetry is not part of local repository modelling.",
        ],
    }
