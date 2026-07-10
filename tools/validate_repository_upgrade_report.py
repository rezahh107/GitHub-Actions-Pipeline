#!/usr/bin/env python3
"""Validate a Repository Upgrade Report v1.1 against its closed canonical schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_upgrade_engine import compute_upgrade_sha256

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "repository_upgrade_report.v1.1.schema.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    args = parser.parse_args()
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        errors = sorted(Draft7Validator(schema).iter_errors(report), key=lambda error: list(error.absolute_path))
        if errors:
            for error in errors[:20]:
                path = "/".join(str(part) for part in error.absolute_path) or "<root>"
                print(f"REPORT_SCHEMA_INVALID {path}: {error.message}", file=sys.stderr)
            return 2
        expected = compute_upgrade_sha256(report)
        if report.get("evidence_sha256") != expected:
            print(f"REPORT_HASH_MISMATCH expected={expected} actual={report.get('evidence_sha256')}", file=sys.stderr)
            return 3
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REPORT_VALIDATION_IO_ERROR: {exc}", file=sys.stderr)
        return 4
    print(f"VALID {args.report} evidence_sha256={expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
