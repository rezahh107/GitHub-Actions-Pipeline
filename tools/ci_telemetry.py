"""Optional GitHub Actions telemetry collection with explicit unavailable fallbacks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

from tools.ci_upgrade_models import diagnostic, evidence

Transport = Callable[[str, dict[str, str]], dict[str, object]]


def _default_transport(url: str, headers: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_runs(runs: list[dict[str, object]]) -> dict[str, object]:
    normalized: list[dict[str, object]] = []
    failure_counts: dict[str, int] = {}
    durations: list[int] = []
    branches: set[str] = set()
    events: set[str] = set()

    for run in runs:
        name = str(run.get("name") or run.get("workflow_name") or "unknown")
        conclusion = run.get("conclusion")
        status = str(run.get("status") or "unknown")
        branch = run.get("head_branch")
        event_name = run.get("event")
        created = _parse_timestamp(run.get("created_at"))
        updated = _parse_timestamp(run.get("updated_at"))
        duration_seconds = None
        if created is not None and updated is not None:
            duration_seconds = max(0, int((updated - created).total_seconds()))
            durations.append(duration_seconds)
        if conclusion in {"failure", "timed_out", "cancelled"}:
            failure_counts[name] = failure_counts.get(name, 0) + 1
        if isinstance(branch, str):
            branches.add(branch)
        if isinstance(event_name, str):
            events.add(event_name)
        normalized.append(
            {
                "run_id": run.get("id"),
                "name": name,
                "event": event_name if isinstance(event_name, str) else None,
                "status": status,
                "conclusion": conclusion if isinstance(conclusion, str) else None,
                "head_sha": run.get("head_sha")
                if isinstance(run.get("head_sha"), str)
                else None,
                "branch": branch if isinstance(branch, str) else None,
                "duration_seconds": duration_seconds,
            }
        )

    recurring = [
        {"workflow": name, "failure_count": count}
        for name, count in sorted(
            failure_counts.items(), key=lambda item: (-item[1], item[0])
        )
        if count >= 2
    ]
    average_duration = sum(durations) // len(durations) if durations else None
    return {
        "status": "collected",
        "runs": sorted(
            normalized,
            key=lambda item: (
                str(item["name"]),
                int(item["run_id"]) if isinstance(item["run_id"], int) else -1,
            ),
        ),
        "recurring_failures": recurring,
        "average_duration_seconds": average_duration,
        "covered_branches": sorted(branches),
        "covered_events": sorted(events),
        "evidence": evidence(
            "observed",
            [str(item["run_id"]) for item in normalized if item["run_id"] is not None],
            "Workflow telemetry was normalized from GitHub Actions run records.",
            confidence="high",
        ),
        "diagnostics": [],
    }


def load_telemetry_snapshot(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_FILE_UNREADABLE",
            f"Could not read telemetry snapshot {path}: {exc}",
            f"Provide a readable JSON snapshot at {path}.",
        )
    except json.JSONDecodeError as exc:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_FILE_INVALID",
            f"Telemetry snapshot {path} is invalid JSON: {exc}",
            f"Regenerate {path} as valid JSON.",
        )
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_FILE_INVALID_SHAPE",
            "Telemetry snapshot must contain a workflow_runs array.",
            "Provide the documented workflow telemetry snapshot shape.",
        )
    return summarize_runs([item for item in runs if isinstance(item, dict)])


def unavailable_telemetry(
    code: str = "WORKFLOW_TELEMETRY_NOT_COLLECTED",
    message: str = "No GitHub workflow telemetry was collected.",
    repair_hint: str = "Supply --telemetry-json or allow read-only GitHub Actions API collection.",
) -> dict[str, object]:
    return {
        "status": "unavailable",
        "runs": [],
        "recurring_failures": [],
        "average_duration_seconds": None,
        "covered_branches": [],
        "covered_events": [],
        "evidence": evidence("unavailable", [], message),
        "diagnostics": [
            diagnostic(
                code,
                message,
                affected_area="workflow_telemetry",
                repair_hint=repair_hint,
                severity="info",
            )
        ],
    }


def collect_github_telemetry(
    repository: str | None,
    *,
    token: str | None = None,
    transport: Transport | None = None,
    limit: int = 30,
) -> dict[str, object]:
    if repository is None or "/" not in repository:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_REPOSITORY_UNKNOWN",
            "Repository owner/name is required for GitHub workflow telemetry.",
            "Pass --repository owner/name or set GITHUB_REPOSITORY.",
        )
    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    if not resolved_token:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_TOKEN_UNAVAILABLE",
            "Read-only GitHub Actions telemetry was not collected because no token was available.",
            "Provide a token with actions:read and contents:read, or supply --telemetry-json.",
        )
    if not 1 <= limit <= 100:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_LIMIT_INVALID",
            "Telemetry run limit must be between 1 and 100.",
            "Use a bounded limit from 1 through 100.",
        )

    sender = transport or _default_transport
    encoded_repo = "/".join(
        urllib.parse.quote(part, safe="") for part in repository.split("/", 1)
    )
    url = f"https://api.github.com/repos/{encoded_repo}/actions/runs?per_page={limit}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {resolved_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-actions-pipeline-deep-upgrade",
    }
    try:
        payload = sender(url, headers)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_REQUEST_FAILED",
            f"GitHub Actions telemetry request failed: {exc}",
            "Verify actions:read access or provide an offline telemetry snapshot.",
        )
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return unavailable_telemetry(
            "WORKFLOW_TELEMETRY_RESPONSE_INVALID",
            "GitHub Actions telemetry response did not contain workflow_runs.",
            "Inspect API permissions and response shape.",
        )
    return summarize_runs([item for item in runs if isinstance(item, dict)])
