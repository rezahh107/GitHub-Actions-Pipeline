"""Shared deterministic models and serialization helpers for CI evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

REPORT_VERSION = "0.1.1"
CANONICALIZATION_VERSION = "1"
SIGNAL_MATCH_LIMIT = 25
HOTSPOT_COMMIT_LIMIT = 200
HOTSPOT_RESULT_LIMIT = 25
SHA_FIELDS_EXCLUDED_FROM_EVIDENCE_HASH = {
    "generated_at",
    "evidence_sha256",
    "run_context",
}


class EvidenceCollectionError(RuntimeError):
    """Expected evidence collection failure with a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def run_git(root: Path, args: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        result = subprocess.run(
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
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, result.stdout.strip()


def optional_env(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: str | None, field_name: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise EvidenceCollectionError(
            "INVALID_RUN_CONTEXT",
            f"{field_name} must be an integer when provided.",
        ) from exc
    if parsed < 1:
        raise EvidenceCollectionError(
            "INVALID_RUN_CONTEXT",
            f"{field_name} must be greater than zero when provided.",
        )
    return parsed


def _validate_sha(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if len(value) != 40 or any(
        character not in "0123456789abcdefABCDEF" for character in value
    ):
        raise EvidenceCollectionError(
            "INVALID_RUN_CONTEXT",
            f"{field_name} must be a 40-character hexadecimal Git SHA.",
        )
    return value.lower()


def _tested_ref_kind(ref: str | None) -> str:
    if ref is None:
        return "unknown"
    if ref.startswith("refs/pull/") and ref.endswith("/merge"):
        return "pull_request_merge"
    if ref.startswith("refs/heads/"):
        return "branch_head"
    if ref.startswith("refs/tags/"):
        return "tag"
    return "other"


def build_run_context(root: Path, environ: Mapping[str, str]) -> dict[str, object]:
    tested_sha = optional_env(environ, "GITHUB_SHA")
    if tested_sha is None and (root / ".git").exists():
        ok, output = run_git(root, ["rev-parse", "HEAD"])
        if ok:
            tested_sha = output

    ref = optional_env(environ, "GITHUB_REF")
    return {
        "event_name": optional_env(environ, "GITHUB_EVENT_NAME"),
        "tested_sha": _validate_sha(tested_sha, "tested_sha"),
        "source_head_sha": _validate_sha(
            optional_env(environ, "CI_SOURCE_HEAD_SHA"), "source_head_sha"
        ),
        "base_sha": _validate_sha(
            optional_env(environ, "CI_BASE_SHA"), "base_sha"
        ),
        "ref": ref,
        "tested_ref_kind": _tested_ref_kind(ref),
        "run_id": _optional_int(optional_env(environ, "GITHUB_RUN_ID"), "run_id"),
        "run_attempt": _optional_int(
            optional_env(environ, "GITHUB_RUN_ATTEMPT"), "run_attempt"
        ),
    }


def normalize_generated_at(value: str | None, environ: Mapping[str, str]) -> str:
    if value is None:
        source_date_epoch = optional_env(environ, "SOURCE_DATE_EPOCH")
        if source_date_epoch is not None:
            try:
                timestamp = int(source_date_epoch)
            except ValueError as exc:
                raise EvidenceCollectionError(
                    "INVALID_GENERATED_AT",
                    "SOURCE_DATE_EPOCH must be an integer Unix timestamp.",
                ) from exc
            return (
                datetime.fromtimestamp(timestamp, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceCollectionError(
            "INVALID_GENERATED_AT",
            "generated_at must be a timezone-aware RFC 3339 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        raise EvidenceCollectionError(
            "INVALID_GENERATED_AT",
            "generated_at must include a timezone.",
        )
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compute_evidence_sha256(report: Mapping[str, object]) -> str:
    payload = deepcopy(dict(report))
    for field in SHA_FIELDS_EXCLUDED_FROM_EVIDENCE_HASH:
        payload.pop(field, None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def serialize_report(report: Mapping[str, object]) -> str:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def write_report(report: Mapping[str, object], output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialize_report(report), encoding="utf-8")
    except OSError as exc:
        raise EvidenceCollectionError(
            "REPORT_WRITE_FAILED",
            f"Could not write report to {output_path}: {exc}",
        ) from exc
