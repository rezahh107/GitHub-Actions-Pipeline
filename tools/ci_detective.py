#!/usr/bin/env python3
"""CLI for deterministic local CI evidence collection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_models import (
    EvidenceCollectionError,
    compute_evidence_sha256,
    write_report,
)
from tools.ci_report import build_report

__all__ = ["build_report", "compute_evidence_sha256", "main"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect deterministic local CI evidence for a repository."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect")
    parser.add_argument("--out", required=True, help="Path to write JSON report")
    parser.add_argument(
        "--generated-at",
        help="Optional timezone-aware RFC 3339 timestamp for reproducible output",
    )
    parser.add_argument(
        "--repository",
        help="Optional owner/name repository identifier; defaults to GITHUB_REPOSITORY or directory name",
    )
    parser.add_argument(
        "--default-branch",
        help="Optional default branch; defaults to CI_DEFAULT_BRANCH when available",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not root.exists():
        print(
            f"CI_DETECTIVE_ROOT_NOT_FOUND: repository root does not exist: {root}",
            file=sys.stderr,
        )
        return 2
    if not root.is_dir():
        print(
            f"CI_DETECTIVE_ROOT_NOT_DIRECTORY: repository root is not a directory: {root}",
            file=sys.stderr,
        )
        return 2

    output_path = Path(args.out).resolve()
    try:
        report = build_report(
            root,
            generated_at=args.generated_at,
            repository=args.repository,
            default_branch=args.default_branch,
            excluded_paths={output_path},
        )
        write_report(report, output_path)
    except EvidenceCollectionError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 3

    print(
        f"Wrote CI detective report to {output_path} "
        f"(evidence_sha256={report['evidence_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
