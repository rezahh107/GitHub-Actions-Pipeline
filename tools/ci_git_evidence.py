"""Bounded and explicit Git evidence collection."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from tools.ci_models import (
    HOTSPOT_COMMIT_LIMIT,
    HOTSPOT_RESULT_LIMIT,
    SIGNAL_MATCH_LIMIT,
    run_git,
)

ENGLISH_SIGNAL_KEYWORDS = [
    "fix",
    "bug",
    "revert",
    "regression",
    "hotfix",
    "broken",
    "fail",
    "failure",
    "repair",
    "patch",
]

PERSIAN_SIGNAL_KEYWORDS = [
    "رفع",
    "اصلاح",
    "باگ",
    "خرابی",
    "خراب",
    "شکست",
    "ناموفق",
    "بازگشت",
    "برگشت",
    "رگرسیون",
    "تعمیر",
    "پچ",
]


def _git_log_grep_args(keywords: list[str]) -> list[str]:
    args = [
        "log",
        "--format=%H%x09%s",
        "-i",
        "-n",
        str(SIGNAL_MATCH_LIMIT + 1),
    ]
    for keyword in keywords:
        args.append(f"--grep={keyword}")
    return args


def _parse_git_log_lines(output: str) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        commit_sha, separator, summary = line.partition("\t")
        if not separator:
            continue
        signals.append(
            {
                "source": "git_log",
                "commit_sha": commit_sha,
                "summary": summary,
            }
        )
    return signals


def _collect_signal_group(
    root: Path, keywords: list[str]
) -> tuple[list[dict[str, str]], bool, str | None]:
    ok, output = run_git(root, _git_log_grep_args(keywords))
    if not ok:
        return [], False, output
    signals = _parse_git_log_lines(output)
    truncated = len(signals) > SIGNAL_MATCH_LIMIT
    return signals[:SIGNAL_MATCH_LIMIT], truncated, None


def _read_commit_count(root: Path) -> int | None:
    ok, output = run_git(root, ["rev-list", "--count", "HEAD"])
    if not ok:
        return None
    try:
        return int(output)
    except ValueError:
        return None


def _read_shallow_state(root: Path) -> bool | None:
    ok, output = run_git(root, ["rev-parse", "--is-shallow-repository"])
    if not ok:
        return None
    normalized = output.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def collect_hotspots(root: Path) -> tuple[list[dict[str, int | str]], str | None]:
    ok, output = run_git(
        root,
        [
            "log",
            "--name-only",
            "--pretty=format:",
            "-n",
            str(HOTSPOT_COMMIT_LIMIT),
        ],
    )
    if not ok:
        return [], output
    counts = Counter(line.strip() for line in output.splitlines() if line.strip())
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"path": path, "change_count": count}
        for path, count in ordered[:HOTSPOT_RESULT_LIMIT]
    ], None


def limitation(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def collect_git_evidence(
    root: Path,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, int | str]],
    list[dict[str, str]],
    dict[str, object],
    dict[str, str],
]:
    limitations: list[dict[str, str]] = []
    unavailable = {
        "status": "unavailable",
        "reason": "No readable Git repository history is available.",
        "is_shallow": None,
        "available_commit_count": None,
        "signal_match_limit": SIGNAL_MATCH_LIMIT,
        "hotspot_commit_limit": HOTSPOT_COMMIT_LIMIT,
        "signal_search_truncated": False,
    }
    persian_unavailable = {
        "status": "unavailable",
        "reason": "Persian commit-message search could not run without Git history.",
    }

    if not (root / ".git").exists():
        limitations.append(
            limitation(
                "GIT_HISTORY_UNAVAILABLE",
                "Repository root does not contain a .git directory.",
            )
        )
        return [], [], [], limitations, unavailable, persian_unavailable

    ok, inside_work_tree = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if not ok or inside_work_tree.strip().lower() != "true":
        limitations.append(
            limitation(
                "GIT_HISTORY_UNAVAILABLE",
                "Git did not identify the repository root as a work tree.",
            )
        )
        return [], [], [], limitations, unavailable, persian_unavailable

    is_shallow = _read_shallow_state(root)
    commit_count = _read_commit_count(root)
    historical, historical_truncated, historical_error = _collect_signal_group(
        root, ENGLISH_SIGNAL_KEYWORDS
    )
    persian, persian_truncated, persian_error = _collect_signal_group(
        root, PERSIAN_SIGNAL_KEYWORDS
    )
    hotspots, hotspot_error = collect_hotspots(root)

    if historical_error:
        limitations.append(
            limitation(
                "ENGLISH_HISTORY_SEARCH_FAILED",
                f"English commit-message search failed: {historical_error}",
            )
        )
    if persian_error:
        limitations.append(
            limitation(
                "PERSIAN_HISTORY_SEARCH_FAILED",
                f"Persian commit-message search failed: {persian_error}",
            )
        )
    if hotspot_error:
        limitations.append(
            limitation(
                "HOTSPOT_ANALYSIS_FAILED",
                f"Git hotspot analysis failed: {hotspot_error}",
            )
        )

    any_signal_truncated = historical_truncated or persian_truncated
    if is_shallow is True:
        history_status = "partial"
        history_reason = (
            "The repository is a shallow clone; available commit evidence is not "
            "the complete repository history."
        )
        limitations.append(
            limitation(
                "GIT_HISTORY_SHALLOW",
                "Historical and hotspot evidence is partial because the clone is shallow.",
            )
        )
    elif is_shallow is None:
        history_status = "bounded"
        history_reason = "Git history was readable, but shallow-state detection was inconclusive."
    elif (
        commit_count is None
        or commit_count > HOTSPOT_COMMIT_LIMIT
        or any_signal_truncated
    ):
        history_status = "bounded"
        history_reason = (
            "Git history is available, but one or more configured evidence limits "
            "bounded the collected results."
        )
    else:
        history_status = "complete"
        history_reason = (
            "The clone is not shallow and all available commits fit within the configured "
            "history limits."
        )

    git_completeness: dict[str, object] = {
        "status": history_status,
        "reason": history_reason,
        "is_shallow": is_shallow,
        "available_commit_count": commit_count,
        "signal_match_limit": SIGNAL_MATCH_LIMIT,
        "hotspot_commit_limit": HOTSPOT_COMMIT_LIMIT,
        "signal_search_truncated": any_signal_truncated,
    }

    if persian_error:
        persian_status = "unavailable"
        persian_reason = "Persian commit-message search failed."
    elif is_shallow is True or persian_truncated:
        persian_status = "bounded"
        persian_reason = (
            "Persian search covered only the available shallow history or reached its match limit."
        )
    else:
        persian_status = "complete"
        persian_reason = "Persian search covered all available local commit messages."

    return (
        historical,
        persian,
        hotspots,
        limitations,
        git_completeness,
        {"status": persian_status, "reason": persian_reason},
    )
