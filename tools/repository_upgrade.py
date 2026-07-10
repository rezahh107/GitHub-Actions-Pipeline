#!/usr/bin/env python3
"""CLI for repository analysis and explicit recoverable recipe application."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_models import EvidenceCollectionError, serialize_report
from tools.ci_transaction import execute_recoverable_implementation
from tools.ci_upgrade_engine import build_upgrade_report
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI, SUPPORTED_MODES, UpgradeContractError


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a repository and optionally apply explicitly allowlisted Phase 1 recipes as a recoverable operation.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", choices=SUPPORTED_MODES, default=MINIMAL_SAFE_CI)
    parser.add_argument("--generated-at")
    parser.add_argument("--repository")
    parser.add_argument("--telemetry-json")
    parser.add_argument("--collect-telemetry", action="store_true")
    parser.add_argument("--implementation-package-out", help="Optional in dry-run mode; required for mutation")
    parser.add_argument("--apply-phase-1", action="store_true", help="Apply applicable Phase 1 create-file recipes; requires allowlist, canonical exact HEAD, and recovery journal")
    parser.add_argument("--allow-recipe", action="append", default=[], help="Recipe ID explicitly allowed for mutation; repeat as needed")
    parser.add_argument("--expected-head-sha", help="Canonical lowercase exact current Git HEAD required before mutation")
    parser.add_argument("--implementation-result-out", help="Required external output path when --apply-phase-1 is used")
    parser.add_argument("--recovery-journal-out", help="Required external recovery journal path when --apply-phase-1 is used")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    output = Path(args.out).resolve()
    telemetry = Path(args.telemetry_json).resolve() if args.telemetry_json else None
    package_out = Path(args.implementation_package_out).resolve() if args.implementation_package_out else None
    result_out = Path(args.implementation_result_out).resolve() if args.implementation_result_out else None
    journal_out = Path(args.recovery_journal_out).resolve() if args.recovery_journal_out else None
    try:
        if args.apply_phase_1:
            if args.mode != DEEP_REPOSITORY_UPGRADE:
                raise UpgradeContractError("IMPLEMENTATION_REQUIRES_DEEP_MODE", "--apply-phase-1 requires --mode deep-repository-upgrade.")
            if not args.expected_head_sha:
                raise UpgradeContractError("IMPLEMENTATION_EXPECTED_HEAD_REQUIRED", "--expected-head-sha is required for mutation.")
            if package_out is None:
                raise UpgradeContractError("IMPLEMENTATION_PACKAGE_PATH_REQUIRED", "--implementation-package-out is required for mutation.")
            if result_out is None:
                raise UpgradeContractError("IMPLEMENTATION_RESULT_PATH_REQUIRED", "--implementation-result-out is required for mutation.")
            if journal_out is None:
                raise UpgradeContractError("IMPLEMENTATION_RECOVERY_JOURNAL_REQUIRED", "--recovery-journal-out is required for mutation.")

        report = build_upgrade_report(root, mode=args.mode, generated_at=args.generated_at, repository=args.repository, telemetry_json=telemetry, collect_telemetry=args.collect_telemetry)
        result = None
        if args.apply_phase_1:
            result = execute_recoverable_implementation(root, report, report["implementation_package"], allowed_recipe_ids=set(args.allow_recipe), expected_head_sha=args.expected_head_sha, report_out=output, package_out=package_out, result_out=result_out, journal_out=journal_out)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialize_report(report), encoding="utf-8")
            if package_out is not None:
                if "implementation_package" not in report:
                    raise UpgradeContractError("IMPLEMENTATION_PACKAGE_REQUIRES_DEEP_MODE", "Implementation package exists only in Deep Repository Upgrade mode.")
                package_out.parent.mkdir(parents=True, exist_ok=True)
                package_out.write_text(serialize_report(report["implementation_package"]), encoding="utf-8")
    except FileNotFoundError:
        print(f"REPOSITORY_UPGRADE_ROOT_NOT_FOUND: repository root does not exist: {root}", file=sys.stderr)
        return 2
    except NotADirectoryError:
        print(f"REPOSITORY_UPGRADE_ROOT_NOT_DIRECTORY: repository root is not a directory: {root}", file=sys.stderr)
        return 2
    except (UpgradeContractError, EvidenceCollectionError) as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"REPOSITORY_UPGRADE_WRITE_FAILED: {exc}", file=sys.stderr)
        return 4

    print(f"Wrote {args.mode} report to {output} (evidence_sha256={report['evidence_sha256']})")
    if result is not None:
        print(f"Applied {sum(1 for item in result['results'] if item['status'] == 'applied')} allowlisted actions through recovery transaction {result['transaction_id']}; repository commands were not executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
