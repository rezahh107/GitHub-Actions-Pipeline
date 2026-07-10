#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_STEP_SUMMARY:?GITHUB_STEP_SUMMARY is required}"
: "${TESTED_SHA:?TESTED_SHA is required}"
: "${SOURCE_HEAD_SHA:?SOURCE_HEAD_SHA is required}"

sha_pattern='^[0-9a-f]{40}$'
for name in TESTED_SHA SOURCE_HEAD_SHA; do
  value="${!name}"
  if [[ ! "$value" =~ $sha_pattern ]]; then
    printf '%s must be a lowercase 40-character hexadecimal Git SHA.\n' "$name" >&2
    exit 2
  fi
done
if [[ "${EXACT_SOURCE_HEAD_REQUIRED:-0}" == "1" && "$TESTED_SHA" != "$SOURCE_HEAD_SHA" ]]; then
  printf 'Exact source-head validation requires TESTED_SHA to equal SOURCE_HEAD_SHA.\n' >&2
  exit 3
fi
for name in EVENT_SHA WORKFLOW_SHA; do
  value="${!name:-}"
  if [[ -n "$value" && ! "$value" =~ $sha_pattern ]]; then
    printf '%s must be empty or a lowercase 40-character hexadecimal Git SHA.\n' "$name" >&2
    exit 2
  fi
done

{
  printf '%s\n' '## GitHub Actions Pipeline validation'
  printf '\n'
  printf '%s\n' '- Python modules compiled.'
  printf '%s\n' '- Unit and negative schema tests completed.'
  printf '%s%s%s\n' '- Tested exact source-head SHA: `' "$TESTED_SHA" '`'
  printf '%s%s%s\n' '- PR source head SHA: `' "$SOURCE_HEAD_SHA" '`'
  if [[ -n "${EVENT_SHA:-}" ]]; then
    printf '%s%s%s\n' '- GitHub event SHA: `' "$EVENT_SHA" '`'
  fi
  if [[ -n "${WORKFLOW_SHA:-}" ]]; then
    printf '%s%s%s\n' '- Workflow definition SHA: `' "$WORKFLOW_SHA" '`'
  fi
  printf '%s\n' '- Legacy CI detective report generated.'
  printf '%s\n' '- Minimal Safe CI report generated.'
  printf '%s\n' '- Deep Repository Upgrade report and dry-run implementation package generated.'
  printf '%s\n' '- Remote workflow telemetry was not requested by this validation job.'
} >> "$GITHUB_STEP_SUMMARY"

if [[ -n "${RUN_IDENTITY_OUT:-}" ]]; then
  umask 077
  python - "$RUN_IDENTITY_OUT" <<'PY'
import json
import os
import sys
from pathlib import Path

if os.environ.get("EXACT_SOURCE_HEAD_REQUIRED") == "1":
    payload = {
        "identity_contract_version": "1.0.0",
        "exact_source_head_verified": os.environ["TESTED_SHA"] == os.environ["SOURCE_HEAD_SHA"],
        "source_head_sha": os.environ["SOURCE_HEAD_SHA"],
        "tested_sha": os.environ["TESTED_SHA"],
        "event_sha": os.environ.get("EVENT_SHA") or None,
        "workflow_sha": os.environ.get("WORKFLOW_SHA") or None,
    }
else:
    payload = {"source_head_sha": os.environ["SOURCE_HEAD_SHA"], "tested_sha": os.environ["TESTED_SHA"]}
Path(sys.argv[1]).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
fi
