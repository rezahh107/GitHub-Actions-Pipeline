"""Deterministic structural Git-history analysis beyond commit-message keywords."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

from tools.ci_models import run_git
from tools.ci_upgrade_models import diagnostic, evidence

COMMIT_LIMIT = 200
PAIR_LIMIT = 25
RESULT_LIMIT = 25
FIX_KEYWORDS = (
    "fix",
    "bug",
    "revert",
    "regression",
    "hotfix",
    "repair",
    "patch",
    "رفع",
    "اصلاح",
    "باگ",
    "خرابی",
    "رگرسیون",
)


def _is_test_path(path: str) -> bool:
    lower = f"/{path.lower()}"
    name = path.split("/")[-1].lower()
    return (
        "/tests/" in lower
        or "/test/" in lower
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _is_workflow_or_config(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(".github/workflows/")
        or lower.endswith((".yml", ".yaml", ".toml", ".ini"))
        or lower.split("/")[-1]
        in {"package.json", "pyproject.toml", "setup.cfg", "requirements.txt"}
    )


def _parse_log(output: str) -> list[dict[str, object]]:
    commits: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in output.splitlines():
        if raw_line.startswith("@@@"):
            if current is not None:
                current["paths"] = sorted(set(current["paths"]))
                commits.append(current)
            _, sha, subject = raw_line.split("\t", 2)
            current = {"sha": sha, "subject": subject, "paths": []}
        elif current is not None and raw_line.strip():
            current["paths"].append(raw_line.strip())
    if current is not None:
        current["paths"] = sorted(set(current["paths"]))
        commits.append(current)
    return commits


def collect_structural_history(root: Path) -> dict[str, object]:
    if not (root / ".git").exists():
        return {
            "status": "unavailable",
            "commit_limit": COMMIT_LIMIT,
            "revert_chains": [],
            "co_change_pairs": [],
            "production_without_test_changes": [],
            "workflow_config_churn": [],
            "repeated_fix_subsystems": [],
            "diagnostics": [
                diagnostic(
                    "STRUCTURAL_HISTORY_UNAVAILABLE",
                    "Structural history analysis could not run because .git is unavailable.",
                    affected_area="history_analysis",
                    repair_hint="Run Deep Repository Upgrade from a full Git checkout.",
                )
            ],
        }

    ok, output = run_git(
        root,
        [
            "log",
            f"-n{COMMIT_LIMIT}",
            "--format=@@@%x09%H%x09%s",
            "--name-only",
        ],
        timeout=30,
    )
    if not ok:
        return {
            "status": "unavailable",
            "commit_limit": COMMIT_LIMIT,
            "revert_chains": [],
            "co_change_pairs": [],
            "production_without_test_changes": [],
            "workflow_config_churn": [],
            "repeated_fix_subsystems": [],
            "diagnostics": [
                diagnostic(
                    "STRUCTURAL_HISTORY_FAILED",
                    f"Git structural history collection failed: {output}",
                    affected_area="history_analysis",
                    repair_hint="Verify that Git history is readable and retry from the repository root.",
                )
            ],
        }

    commits = _parse_log(output)
    pair_counts: Counter[tuple[str, str]] = Counter()
    workflow_counts: Counter[str] = Counter()
    subsystem_fix_counts: Counter[str] = Counter()
    reverts: list[dict[str, object]] = []
    prod_without_tests: list[dict[str, object]] = []

    for commit in commits:
        paths = [str(path) for path in commit["paths"]]
        subject = str(commit["subject"])
        lower_subject = subject.lower()
        if lower_subject.startswith("revert ") or "this reverts commit" in lower_subject:
            reverts.append(
                {
                    "commit_sha": commit["sha"],
                    "summary": subject,
                    "evidence_strength": "high",
                    "basis": "The commit subject explicitly identifies a revert.",
                }
            )

        bounded_paths = paths[:40]
        for left, right in combinations(bounded_paths, 2):
            pair_counts[tuple(sorted((left, right)))] += 1

        for path in paths:
            if _is_workflow_or_config(path):
                workflow_counts[path] += 1

        has_production = any(
            not _is_test_path(path)
            and path.endswith((".py", ".js", ".ts", ".php", ".go", ".rs", ".java"))
            for path in paths
        )
        has_test = any(_is_test_path(path) for path in paths)
        if has_production and not has_test:
            prod_without_tests.append(
                {
                    "commit_sha": commit["sha"],
                    "summary": subject,
                    "paths": paths,
                    "evidence_strength": "medium",
                    "basis": "Production-like source changed in this commit without a test-path change; absence of a test-path change is not proof of missing validation.",
                }
            )

        if any(keyword in lower_subject for keyword in FIX_KEYWORDS):
            subsystems = {
                path.split("/", 1)[0] if "/" in path else "."
                for path in paths
                if path
            }
            for subsystem in subsystems:
                subsystem_fix_counts[subsystem] += 1

    co_change_pairs = [
        {
            "paths": [left, right],
            "co_change_count": count,
            "evidence_strength": "medium",
            "basis": "Files changed in the same bounded commit set; correlation is not causation.",
        }
        for (left, right), count in sorted(
            pair_counts.items(), key=lambda item: (-item[1], item[0])
        )
        if count >= 2
    ][:PAIR_LIMIT]

    workflow_config_churn = [
        {
            "path": path,
            "change_count": count,
            "evidence_strength": "medium",
            "basis": "Path recurred in the bounded commit window.",
        }
        for path, count in sorted(
            workflow_counts.items(), key=lambda item: (-item[1], item[0])
        )[:RESULT_LIMIT]
    ]

    repeated_fix_subsystems = [
        {
            "subsystem": subsystem,
            "fix_commit_count": count,
            "evidence_strength": "medium",
            "basis": "Fix-oriented commit subjects repeatedly touched this top-level subsystem.",
        }
        for subsystem, count in sorted(
            subsystem_fix_counts.items(), key=lambda item: (-item[1], item[0])
        )
        if count >= 2
    ][:RESULT_LIMIT]

    return {
        "status": "collected",
        "commit_limit": COMMIT_LIMIT,
        "commit_count_analyzed": len(commits),
        "revert_chains": reverts[:RESULT_LIMIT],
        "co_change_pairs": co_change_pairs,
        "production_without_test_changes": prod_without_tests[:RESULT_LIMIT],
        "workflow_config_churn": workflow_config_churn,
        "repeated_fix_subsystems": repeated_fix_subsystems,
        "diagnostics": [],
        "evidence": evidence(
            "derived",
            [str(item["sha"]) for item in commits],
            "Structural history was derived from a bounded local Git log. Correlations do not establish causation.",
            confidence="medium",
        ),
    }
