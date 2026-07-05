#!/usr/bin/env python3
"""Minimal deterministic evidence collector for GitHub Actions Pipeline v0.1.

This tool uses only the Python standard library. It collects local repository
structure evidence and writes a JSON report compatible with the v0.1 schema.
It does not call GitHub APIs and does not invent remote history.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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
}

PACKAGE_FILES = {"pyproject.toml", "package.json", "composer.json", "Cargo.toml", "go.mod"}
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", "Pipfile.lock", "composer.lock"}
VERSION_FILES = {"CURRENT_VERSION", "VERSION", "version.txt"}
DOC_NAMES = {"README.md", "AGENTS.md", "CHANGELOG.md"}


def iter_files(root: Path) -> Iterable[Path]:
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        base = Path(current_root)
        for name in files:
            path = base / name
            yield path


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_git(root: Path, args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - platform dependent
        return False, str(exc)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, result.stdout.strip()


def collect_git_signals(root: Path) -> tuple[list[dict], list[dict], list[str], str]:
    english = "fix|bug|revert|regression|hotfix|broken|fail|failure|repair|patch"
    persian = "رفع|اصلاح|باگ|خرابی|خراب|شکست|ناموفق|بازگشت|برگشت|رگرسیون|تعمیر|پچ"

    historical: list[dict] = []
    persian_signals: list[dict] = []
    limitations: list[str] = []

    ok, out = run_git(root, ["log", "--oneline", "-i", f"--grep={english}", "-n", "25"])
    if ok and out:
        for line in out.splitlines():
            historical.append({"source": "git_log", "summary": line})
    elif not ok:
        limitations.append(f"git history unavailable: {out}")

    ok, out = run_git(root, ["log", "--oneline", "-i", f"--grep={persian}", "-n", "25"])
    if ok and out:
        for line in out.splitlines():
            persian_signals.append({"source": "git_log", "summary": line})

    completeness = "complete" if (root / ".git").exists() else "unavailable"
    return historical, persian_signals, limitations, completeness


def collect_hotspots(root: Path) -> list[dict]:
    ok, out = run_git(root, ["log", "--name-only", "--pretty=format:", "-n", "200"])
    if not ok or not out:
        return []
    counts = Counter(line.strip() for line in out.splitlines() if line.strip())
    return [
        {"path": path, "change_count": count}
        for path, count in counts.most_common(25)
    ]


def build_report(repo_root: Path) -> dict:
    repo_root = repo_root.resolve()
    files = list(iter_files(repo_root))

    rel_files = [rel(repo_root, p) for p in files]
    languages = sorted({LANGUAGE_BY_SUFFIX[p.suffix] for p in files if p.suffix in LANGUAGE_BY_SUFFIX})

    package_files = sorted(p for p in rel_files if Path(p).name in PACKAGE_FILES)
    lockfiles = sorted(p for p in rel_files if Path(p).name in LOCKFILES)
    test_files = sorted(p for p in rel_files if "/test" in f"/{p}" or Path(p).name.startswith("test_"))
    schema_files = sorted(p for p in rel_files if "schema" in p.lower() and p.endswith(".json"))
    validator_files = sorted(p for p in rel_files if "valid" in p.lower() and p.endswith(".py"))
    version_files = sorted(p for p in rel_files if Path(p).name in VERSION_FILES)
    docs = sorted(p for p in rel_files if Path(p).name in DOC_NAMES or p.startswith("pipeline/"))
    workflows = sorted(p for p in rel_files if p.startswith(".github/workflows/") and (p.endswith(".yml") or p.endswith(".yaml")))

    historical, persian_signals, limitations, git_completeness = collect_git_signals(repo_root)
    hotspots = collect_hotspots(repo_root)

    return {
        "report_version": "0.1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": repo_root.name,
        "default_branch": None,
        "connector_scope": {
            "files": "available",
            "pull_requests": "unknown",
            "workflow_runs": "unknown",
            "artifacts": "unknown",
            "related_repositories": "unknown",
        },
        "inventory": {
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
            "static_inventory": "complete",
            "git_history": git_completeness,
            "workflow_telemetry": "unavailable",
            "cross_repo": "not_applicable",
            "persian_search": "unknown",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect minimal CI evidence for a local repository.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect")
    parser.add_argument("--out", required=True, help="Path to write JSON report")
    args = parser.parse_args()

    root = Path(args.repo_root)
    report = build_report(root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote CI detective report to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
