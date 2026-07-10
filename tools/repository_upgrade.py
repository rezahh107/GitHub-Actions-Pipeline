#!/usr/bin/env python3
"""CLI for Minimal Safe CI and Deep Repository Upgrade analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_models import EvidenceCollectionError, serialize_report
from tools.ci_upgrade_engine import build_upgrade_report
from tools.ci_upgrade_models import (
    MINIMAL_SAFE_CI,
    SUPPORTED_MODES,
    UpgradeContractError,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a repository using Minimal Safe CI or Deep Repository Upgrade."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect")
    parser.add_argument("--out", required=True, help="Path to write the JSON report")
    parser.add_argument(
        "--mode",
        choices=SUPPORTED_MODES,
        default=MINIMAL_SAFE_CI,
        help="Explicit operating mode; defaults to the backward-compatible conservative mode",
    )
    parser.add_argument(
        "--generated-at",
        help="Optional timezone-aware RFC 3339 timestamp for reproducible output",
    )
    parser.add_argument(
        "--repository",
        help="Optional owner/name identifier; defaults to GITHUB_REPOSITORY or directory name",
    )
    parser.add_argument(
        "--telemetry-json",
        help="Optional offline GitHub Actions telemetry snapshot",
    )
    parser.add_argument(
        "--collect-telemetry",
        action="store_true",
        help="In deep mode, collect read-only GitHub Actions runs using GITHUB_TOKEN",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    output = Path(args.out).resolve()
    telemetry_path = (
        Path(args.telemetry_json).resolve() if args.telemetry_json else None
    )

    try:
        report = build_upgrade_report(
            root,
            mode=args.mode,
            generated_at=args.generated_at,
            repository=args.repository,
            telemetry_json=telemetry_path,
            collect_telemetry=args.collect_telemetry,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_report(report), encoding="utf-8")
    except FileNotFoundError:
        print(
            f"REPOSITORY_UPGRADE_ROOT_NOT_FOUND: repository root does not exist: {root}",
            file=sys.stderr,
        )
        return 2
    except NotADirectoryError:
        print(
            f"REPOSITORY_UPGRADE_ROOT_NOT_DIRECTORY: repository root is not a directory: {root}",
            file=sys.stderr,
        )
        return 2
    except (UpgradeContractError, EvidenceCollectionError) as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(
            f"REPOSITORY_UPGRADE_WRITE_FAILED: could not write {output}: {exc}",
            file=sys.stderr,
        )
        return 4

    print(
        f"Wrote {args.mode} report to {output} "
        f"(evidence_sha256={report['evidence_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
