#!/usr/bin/env python3
"""Repository capability audit and staged improvement CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.deep_git_evidence import collect_deep_git_evidence
from tools.repository_model import build_repository_model
from tools.upgrade_engine import (
    MODE_POLICIES,
    build_recommendations,
    build_staged_plan,
    evaluate_capabilities,
    load_profiles,
    select_profiles,
    summarize_baseline,
)

REPORT_VERSION = "0.2.0"
HASH_EXCLUDED_FIELDS = {"generated_at", "report_sha256"}


def _generated_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be a timezone-aware RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def report_sha256(report: dict[str, Any]) -> str:
    payload = {key: value for key, value in report.items() if key not in HASH_EXCLUDED_FIELDS}
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _load_telemetry(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_collected",
            "reason": "No connector-fed workflow telemetry file was supplied.",
            "runs": [],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"telemetry input could not be read: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("runs", []), list):
        raise ValueError("telemetry input must be an object with a runs array")
    return {
        "status": value.get("status", "available"),
        "reason": value.get("reason", "Connector-fed telemetry was supplied."),
        "runs": value.get("runs", []),
    }


def build_upgrade_report(
    repo_root: Path,
    *,
    mode: str,
    generated_at: str | None = None,
    repository: str | None = None,
    profile_root: Path | None = None,
    telemetry_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in MODE_POLICIES:
        raise ValueError(f"unsupported mode: {mode}")
    root = repo_root.resolve()
    if not root.exists():
        raise ValueError(f"repository root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")

    model = build_repository_model(root)
    deep_history = collect_deep_git_evidence(root)
    profiles_path = profile_root or (Path(__file__).resolve().parents[1] / "profiles")
    all_profiles = load_profiles(profiles_path)
    selected_profiles = select_profiles(model, all_profiles)
    capabilities = evaluate_capabilities(model, selected_profiles)
    policy = MODE_POLICIES[mode]
    recommendations = build_recommendations(model, capabilities, deep_history, policy)
    staged_plan = build_staged_plan(recommendations, policy)
    telemetry = _load_telemetry(telemetry_path)

    limitations = list(model.get("unresolved_evidence", []))
    if deep_history["status"] != "complete":
        limitations.append(deep_history["reason"])
    if telemetry["status"] != "available":
        limitations.append(telemetry["reason"])
    if not selected_profiles:
        limitations.append("No capability profile matched; only generic repository evidence is available.")

    report: dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "generated_at": _generated_at(generated_at),
        "report_sha256": "",
        "repository": repository or root.name,
        "mode": mode,
        "mode_policy": {
            "include_baseline_capabilities": policy.include_baseline_capabilities,
            "maximum_phase1_items": policy.maximum_phase1_items,
            "allow_testability_changes": policy.allow_testability_changes,
            "minimum_evidence": policy.minimum_evidence,
        },
        "repository_model": model,
        "selected_profiles": [profile["profile_id"] for profile in selected_profiles],
        "workflow_telemetry": telemetry,
        "historical_analysis": deep_history,
        "current_engineering_baseline": summarize_baseline(model, capabilities),
        "capability_gaps": capabilities,
        "recommendations": recommendations,
        "staged_upgrade_plan": staged_plan,
        "intentionally_uncovered": [
            "Remote runtime behavior that was not represented in supplied telemetry.",
            "Dynamic architecture relationships that require execution or domain credentials.",
        ],
        "limitations": sorted(set(limitations)),
    }
    report["report_sha256"] = report_sha256(report)
    return report


def render_persian_summary(report: dict[str, Any]) -> str:
    phase1 = report["staged_upgrade_plan"]["phase_1"]
    gaps = [
        item for item in report["capability_gaps"]
        if item["state"] not in {"operational", "not_applicable"}
    ]
    lines = [
        "# خلاصهٔ ارتقای ریپو",
        "",
        f"- حالت: `{report['mode']}`",
        f"- تعداد مؤلفه‌ها: {report['current_engineering_baseline']['component_count']}",
        f"- شکاف‌های قابلیت: {len(gaps)}",
        f"- پیشنهادهای معتبر: {len(report['recommendations'])}",
        f"- اقدامات فاز اول: {len(phase1)}",
        "",
    ]
    if phase1:
        lines.append("## فاز اول")
        lines.append("")
        by_id = {item["recommendation_id"]: item for item in report["recommendations"]}
        for item in phase1:
            recommendation = by_id[item["recommendation_id"]]
            lines.append(
                f"- **{recommendation['title']}** — {recommendation['problem']}"
            )
    else:
        lines.extend([
            "## نتیجه",
            "",
            "در این حالت، هیچ تغییر با شواهد و ارزش کافی برای فاز اول پیدا نشد.",
        ])
    if report["limitations"]:
        lines.extend(["", "## محدودیت‌های شواهد", ""])
        lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit repository capabilities and produce a staged CI/repository upgrade report."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--mode",
        choices=sorted(MODE_POLICIES),
        default="minimal-safe-ci",
    )
    parser.add_argument("--generated-at")
    parser.add_argument("--repository")
    parser.add_argument("--profiles-root")
    parser.add_argument("--telemetry-json")
    parser.add_argument("--summary-out")
    args = parser.parse_args()

    try:
        report = build_upgrade_report(
            Path(args.repo_root),
            mode=args.mode,
            generated_at=args.generated_at,
            repository=args.repository,
            profile_root=Path(args.profiles_root).resolve() if args.profiles_root else None,
            telemetry_path=Path(args.telemetry_json).resolve() if args.telemetry_json else None,
        )
        output = Path(args.out).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if args.summary_out:
            summary = Path(args.summary_out).resolve()
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text(render_persian_summary(report), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"REPOSITORY_UPGRADE_FAILED: {exc}", file=sys.stderr)
        return 2

    print(
        f"Wrote {report['mode']} report to {output} "
        f"(report_sha256={report['report_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
