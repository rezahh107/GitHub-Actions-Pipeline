"""Deterministic historical signals beyond commit-message keyword matching."""

from __future__ import annotations

import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
    ".cs", ".php", ".rb", ".sh",
}
FIX_TOKENS = (
    "fix", "bug", "regression", "revert", "repair", "hotfix", "patch",
    "رفع", "اصلاح", "باگ", "خرابی", "رگرسیون", "تعمیر",
)


def _run_git(root: Path, args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        process = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if process.returncode != 0:
        return False, process.stderr.strip() or process.stdout.strip()
    return True, process.stdout


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (
        "/tests/" in f"/{lowered}"
        or "/test/" in f"/{lowered}"
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def _subsystem(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[0] if len(parts) > 1 else "."


def _parse_commits(output: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in output.splitlines():
        if raw.startswith("@@@"):
            if current is not None:
                current["files"] = sorted(set(current["files"]))
                commits.append(current)
            payload = raw[3:]
            sha, _, remainder = payload.partition("\t")
            parents, _, subject = remainder.partition("\t")
            current = {
                "commit_sha": sha,
                "parents": [item for item in parents.split() if item],
                "subject": subject,
                "files": [],
            }
        elif current is not None and raw.strip():
            current["files"].append(raw.strip())
    if current is not None:
        current["files"] = sorted(set(current["files"]))
        commits.append(current)
    return commits


def collect_deep_git_evidence(root: Path, limit: int = 200) -> dict[str, Any]:
    if not (root / ".git").exists():
        return {
            "status": "unavailable",
            "reason": "No .git directory is available for deep historical analysis.",
            "commit_limit": limit,
            "revert_signals": [],
            "co_change_pairs": [],
            "production_changes_without_tests": [],
            "repeated_fix_subsystems": [],
            "workflow_configuration_churn": [],
        }
    ok, output = _run_git(
        root,
        [
            "log",
            f"-n{limit}",
            "--format=@@@%H%x09%P%x09%s",
            "--name-only",
        ],
    )
    if not ok:
        return {
            "status": "unavailable",
            "reason": f"Git history analysis failed: {output}",
            "commit_limit": limit,
            "revert_signals": [],
            "co_change_pairs": [],
            "production_changes_without_tests": [],
            "repeated_fix_subsystems": [],
            "workflow_configuration_churn": [],
        }

    commits = _parse_commits(output)
    revert_signals: list[dict[str, Any]] = []
    production_without_tests: list[dict[str, Any]] = []
    pair_counts: Counter[tuple[str, str]] = Counter()
    fix_subsystems: Counter[str] = Counter()
    config_churn: Counter[str] = Counter()

    for commit in commits:
        subject_lower = commit["subject"].lower()
        files = commit["files"]
        if "revert" in subject_lower or "بازگشت" in subject_lower or "برگشت" in subject_lower:
            revert_signals.append({
                "commit_sha": commit["commit_sha"],
                "subject": commit["subject"],
                "files": files[:20],
                "evidence_strength": "high",
            })

        source_files = [
            path for path in files
            if Path(path).suffix.lower() in SOURCE_SUFFIXES and not _is_test_path(path)
        ]
        test_files = [path for path in files if _is_test_path(path)]
        if source_files and not test_files:
            production_without_tests.append({
                "commit_sha": commit["commit_sha"],
                "subject": commit["subject"],
                "source_files": source_files[:20],
                "evidence_strength": "medium",
                "interpretation_guard": "This is change-coupling evidence, not proof that tests were required.",
            })

        if 1 < len(files) <= 40:
            for left, right in combinations(files, 2):
                pair_counts[(left, right)] += 1

        if any(token in subject_lower for token in FIX_TOKENS):
            for subsystem in {_subsystem(path) for path in source_files or files}:
                fix_subsystems[subsystem] += 1

        for path in files:
            lowered = path.lower()
            if lowered.startswith(".github/workflows/") or any(
                token in lowered for token in ("config", "pyproject.toml", "package.json", "schema")
            ):
                config_churn[path] += 1

    co_change_pairs = [
        {
            "left": pair[0],
            "right": pair[1],
            "co_change_count": count,
            "evidence_strength": "high" if count >= 4 else "medium",
            "interpretation_guard": "Co-change correlation does not establish a causal dependency.",
        }
        for pair, count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ][:25]
    repeated_fix_subsystems = [
        {
            "subsystem": subsystem,
            "fix_commit_count": count,
            "evidence_strength": "high" if count >= 4 else "medium",
        }
        for subsystem, count in sorted(fix_subsystems.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ][:20]
    workflow_configuration_churn = [
        {
            "path": path,
            "change_count": count,
            "evidence_strength": "high" if count >= 5 else "medium",
        }
        for path, count in sorted(config_churn.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ][:25]

    return {
        "status": "bounded" if len(commits) >= limit else "complete",
        "reason": (
            f"Deep analysis inspected the most recent {limit} commits."
            if len(commits) >= limit
            else f"Deep analysis inspected all {len(commits)} available commits."
        ),
        "commit_limit": limit,
        "revert_signals": revert_signals[:25],
        "co_change_pairs": co_change_pairs,
        "production_changes_without_tests": production_without_tests[:25],
        "repeated_fix_subsystems": repeated_fix_subsystems,
        "workflow_configuration_churn": workflow_configuration_churn,
    }
