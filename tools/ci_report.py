"""Repository inventory and report assembly."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping

from tools.ci_git_evidence import collect_git_evidence, limitation
from tools.ci_models import (
    CANONICALIZATION_VERSION,
    REPORT_VERSION,
    build_run_context,
    compute_evidence_sha256,
    normalize_generated_at,
    optional_env,
)

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".json": "JSON",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".php": "PHP",
    ".toml": "TOML",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".cs": "C#",
    ".java": "Java",
    ".sh": "Shell",
    ".html": "HTML",
    ".css": "CSS",
}
PACKAGE_FILES = {
    "pyproject.toml",
    "package.json",
    "composer.json",
    "Cargo.toml",
    "go.mod",
}
LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "composer.lock",
}
VERSION_FILES = {"CURRENT_VERSION", "VERSION", "version.txt"}
DOC_NAMES = {"README.md", "AGENTS.md", "CHANGELOG.md", "CONTRIBUTING.md"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
}


def iter_files(
    root: Path, excluded_paths: set[Path] | None = None
) -> Iterable[Path]:
    excluded = {path.resolve() for path in (excluded_paths or set())}
    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(directory for directory in dirs if directory not in SKIP_DIRS)
        base = Path(current_root)
        for name in sorted(files):
            candidate = base / name
            if candidate in excluded:
                continue
            yield candidate


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def is_test_file(path: str) -> bool:
    name = path.split('/')[-1].lower()
    lowered = path.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in lowered
        or ".spec." in lowered
        or "/tests/" in f"/{lowered}"
        or "/test/" in f"/{lowered}"
    )


def build_report(
    repo_root: Path,
    *,
    generated_at: str | None = None,
    repository: str | None = None,
    default_branch: str | None = None,
    environ: Mapping[str, str] | None = None,
    excluded_paths: set[Path] | None = None,
) -> dict[str, object]:
    environment = os.environ if environ is None else environ
    repo_root = repo_root.resolve()
    files = sorted(
        iter_files(repo_root, excluded_paths=excluded_paths),
        key=lambda path: rel(repo_root, path),
    )
    rel_files = [rel(repo_root, path) for path in files]

    languages = sorted(
        {
            LANGUAGE_BY_SUFFIX[path.suffix.lower()]
            for path in files
            if path.suffix.lower() in LANGUAGE_BY_SUFFIX
        }
    )
    package_files = sorted(path for path in rel_files if Path(path).name in PACKAGE_FILES)
    lockfiles = sorted(path for path in rel_files if Path(path).name in LOCKFILES)
    test_files = [path for path in rel_files if is_test_file(path)]
    schema_files = [
        path
        for path in rel_files
        if "schema" in path.lower() and path.lower().endswith(".json")
    ]
    validator_files = [
        path
        for path in rel_files
        if "valid" in path.lower() and path.lower().endswith(".py")
    ]
    version_files = sorted(path for path in rel_files if Path(path).name in VERSION_FILES)
    docs = sorted(
        path
        for path in rel_files
        if Path(path).name in DOC_NAMES or path.startswith("pipeline/")
    )
    workflows = sorted(
        path
        for path in rel_files
        if path.startswith(".github/workflows/")
        and path.lower().endswith((".yml", ".yaml"))
    )

    (
        historical,
        persian_signals,
        hotspots,
        git_limitations,
        git_completeness,
        persian_completeness,
    ) = collect_git_evidence(repo_root)

    limitations = [
        *git_limitations,
        limitation(
            "WORKFLOW_TELEMETRY_NOT_COLLECTED",
            "The local collector does not call GitHub APIs for workflow telemetry.",
        ),
        limitation(
            "CROSS_REPO_SCOPE_UNKNOWN",
            "The local collector cannot determine sibling-repository access.",
        ),
    ]

    report: dict[str, object] = {
        "report_version": REPORT_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "generated_at": normalize_generated_at(generated_at, environment),
        "evidence_sha256": "",
        "repository": (
            repository
            or optional_env(environment, "GITHUB_REPOSITORY")
            or repo_root.name
        ),
        "default_branch": (
            default_branch or optional_env(environment, "CI_DEFAULT_BRANCH")
        ),
        "run_context": build_run_context(repo_root, environment),
        "connector_scope": {
            "files": "available",
            "pull_requests": "unknown",
            "workflow_runs": "unknown",
            "artifacts": "unknown",
            "related_repositories": "unknown",
        },
        "inventory": {
            "file_count": len(rel_files),
            "languages": languages,
            "package_files": package_files,
            "lockfiles": lockfiles,
            "test_files": test_files,
            "schema_files": schema_files,
            "validator_files": validator_files,
            "version_files": version_files,
            "docs": docs,
        },
        "workflows": workflows,
        "workflow_runs": [],
        "historical_signals": historical,
        "persian_historical_signals": persian_signals,
        "hotspots": hotspots,
        "cross_repo_evidence": [],
        "limitations": limitations,
        "evidence_completeness": {
            "static_inventory": {
                "status": "bounded",
                "reason": "Inventory uses deterministic filename and suffix heuristics.",
            },
            "git_history": git_completeness,
            "workflow_telemetry": {
                "status": "unavailable",
                "reason": "The local collector does not call GitHub workflow APIs.",
            },
            "cross_repo": {
                "status": "unknown",
                "reason": "Sibling-repository connector scope was not supplied.",
            },
            "persian_search": persian_completeness,
        },
    }
    report["evidence_sha256"] = compute_evidence_sha256(report)
    return report
