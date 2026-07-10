"""Deterministic structural Git-history analysis with collision-free framing."""
from __future__ import annotations

import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from tools.ci_models import run_git
from tools.ci_upgrade_models import diagnostic, evidence

COMMIT_LIMIT = 200
PAIR_LIMIT = 25
RESULT_LIMIT = 25
PATHS_PER_COMMIT_LIMIT = 40
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
FIX_KEYWORDS = (
    "fix", "bug", "revert", "regression", "hotfix", "repair", "patch",
    "رفع", "اصلاح", "باگ", "خرابی", "رگرسیون",
)


def _is_test_path(path: str) -> bool:
    lower = f"/{path.lower()}"
    name = path.split("/")[-1].lower()
    return (
        "/tests/" in lower
        or "/test/" in lower
        or "/src/test/" in lower
        or name.startswith("test_")
        or name.endswith("_test.go")
        or ".test." in name
        or ".spec." in name
    )


def _is_workflow_or_config(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(".github/workflows/")
        or lower.endswith((".yml", ".yaml", ".toml", ".ini"))
        or lower.split("/")[-1] in {"package.json", "pyproject.toml", "setup.cfg", "requirements.txt"}
    )


def _empty_history(code: str, message: str, hint: str) -> dict[str, object]:
    return {
        "status": "unavailable",
        "commit_limit": COMMIT_LIMIT,
        "commit_count_analyzed": 0,
        "revert_chains": [],
        "co_change_pairs": [],
        "production_without_test_changes": [],
        "workflow_config_churn": [],
        "repeated_fix_subsystems": [],
        "diagnostics": [diagnostic(code, message, affected_area="history_analysis", repair_hint=hint)],
    }


def _parse_commit_records(output: str) -> tuple[list[dict[str, object]] | None, str | None]:
    """Parse NUL-delimited ``sha, subject`` records; filenames are collected separately."""
    if not output:
        return [], None
    fields = output.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        return None, "Git log returned a truncated NUL-delimited metadata record."
    commits: list[dict[str, object]] = []
    for index in range(0, len(fields), 2):
        sha, subject = fields[index], fields[index + 1]
        if not _GIT_SHA.fullmatch(sha):
            return None, f"Git log returned an invalid commit identity at record {index // 2}."
        commits.append({"sha": sha, "subject": subject, "paths": []})
    return commits, None


def _parse_paths(output: str) -> tuple[list[str] | None, str | None]:
    if not output:
        return [], None
    fields = output.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    paths: list[str] = []
    for index, value in enumerate(fields):
        if not value:
            return None, f"Git diff-tree returned an empty path at record {index}."
        paths.append(value)
    return sorted(set(paths)), None


def _collect_commits(root: Path) -> tuple[list[dict[str, object]] | None, dict[str, object] | None]:
    ok, output = run_git(root, ["log", f"-n{COMMIT_LIMIT}", "--format=%H%x00%s", "-z"], timeout=30)
    if not ok:
        return None, _empty_history("STRUCTURAL_HISTORY_FAILED", f"Git structural history collection failed: {output}", "Verify that Git history is readable and retry from the repository root.")
    commits, parse_error = _parse_commit_records(output)
    if parse_error is not None or commits is None:
        return None, _empty_history("STRUCTURAL_HISTORY_MALFORMED", parse_error or "Git history metadata could not be parsed.", "Retry with a complete Git checkout; malformed or truncated NUL-framed output is not used as evidence.")
    for commit in commits:
        sha = str(commit["sha"])
        ok, path_output = run_git(root, ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", sha], timeout=15)
        if not ok:
            return None, _empty_history("STRUCTURAL_HISTORY_PATHS_FAILED", f"Could not collect changed paths for commit {sha}: {path_output}", "Verify that the commit object and tree are readable in the local checkout.")
        paths, path_error = _parse_paths(path_output)
        if path_error is not None or paths is None:
            return None, _empty_history("STRUCTURAL_HISTORY_MALFORMED", f"Could not parse NUL-delimited paths for commit {sha}: {path_error}", "Retry with a complete Git checkout; malformed path records are not used as evidence.")
        commit["paths"] = paths
    return commits, None


def collect_structural_history(root: Path) -> dict[str, object]:
    if not (root / ".git").exists():
        return _empty_history("STRUCTURAL_HISTORY_UNAVAILABLE", "Structural history analysis could not run because .git is unavailable.", "Run Deep Repository Upgrade from a full Git checkout.")
    commits, unavailable = _collect_commits(root)
    if unavailable is not None or commits is None:
        return unavailable or _empty_history("STRUCTURAL_HISTORY_UNAVAILABLE", "Structural history evidence was unavailable.", "Run from a complete readable Git checkout.")

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
            reverts.append({"commit_sha": commit["sha"], "summary": subject, "evidence_strength": "high", "basis": "The commit subject explicitly identifies a revert."})
        bounded_paths = paths[:PATHS_PER_COMMIT_LIMIT]
        for left, right in combinations(bounded_paths, 2):
            pair_counts[tuple(sorted((left, right)))] += 1
        for path in paths:
            if _is_workflow_or_config(path):
                workflow_counts[path] += 1
        has_production = any(not _is_test_path(path) and path.endswith((".py", ".js", ".ts", ".php", ".go", ".rs", ".java")) for path in paths)
        has_test = any(_is_test_path(path) for path in paths)
        if has_production and not has_test:
            prod_without_tests.append({"commit_sha": commit["sha"], "summary": subject, "paths": paths, "evidence_strength": "medium", "basis": "Production-like source changed in this commit without a test-path change; absence of a test-path change is not proof of missing validation."})
        if any(keyword in lower_subject for keyword in FIX_KEYWORDS):
            subsystems = {path.split("/", 1)[0] if "/" in path else "." for path in paths if path}
            for subsystem in subsystems:
                subsystem_fix_counts[subsystem] += 1

    co_change_pairs = [{"paths": [left, right], "co_change_count": count, "evidence_strength": "medium", "basis": "Files changed in the same bounded commit set; correlation is not causation."} for (left, right), count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0])) if count >= 2][:PAIR_LIMIT]
    workflow_config_churn = [{"path": path, "change_count": count, "evidence_strength": "medium", "basis": "Path recurred in the bounded commit window."} for path, count in sorted(workflow_counts.items(), key=lambda item: (-item[1], item[0]))[:RESULT_LIMIT]]
    repeated_fix_subsystems = [{"subsystem": subsystem, "fix_commit_count": count, "evidence_strength": "medium", "basis": "Fix-oriented commit subjects repeatedly touched this top-level subsystem."} for subsystem, count in sorted(subsystem_fix_counts.items(), key=lambda item: (-item[1], item[0])) if count >= 2][:RESULT_LIMIT]

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
        "evidence": evidence("derived", [str(item["sha"]) for item in commits], "Structural history was derived from bounded NUL-delimited Git metadata and path records. Correlations do not establish causation.", confidence="medium"),
    }
