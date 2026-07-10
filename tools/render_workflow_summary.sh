#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_STEP_SUMMARY:?GITHUB_STEP_SUMMARY is required}"
: "${TESTED_SHA:?TESTED_SHA is required}"
: "${SOURCE_HEAD_SHA:?SOURCE_HEAD_SHA is required}"

sha_pattern='^[0-9a-f]{40}$'
if [[ ! "$TESTED_SHA" =~ $sha_pattern ]]; then
  printf '%s\n' 'TESTED_SHA must be a lowercase 40-character hexadecimal Git SHA.' >&2
  exit 2
fi
if [[ ! "$SOURCE_HEAD_SHA" =~ $sha_pattern ]]; then
  printf '%s\n' 'SOURCE_HEAD_SHA must be a lowercase 40-character hexadecimal Git SHA.' >&2
  exit 2
fi

{
  printf '%s\n' '## GitHub Actions Pipeline validation'
  printf '\n'
  printf '%s\n' '- Python modules compiled.'
  printf '%s\n' '- Unit and negative schema tests completed.'
  printf '%s%s%s\n' '- Tested SHA: `' "$TESTED_SHA" '`'
  printf '%s%s%s\n' '- Source head SHA: `' "$SOURCE_HEAD_SHA" '`'
  printf '%s\n' '- Legacy CI detective report generated.'
  printf '%s\n' '- Minimal Safe CI report generated.'
  printf '%s\n' '- Deep Repository Upgrade report and dry-run implementation package generated.'
  printf '%s\n' '- Remote workflow telemetry was not requested by this validation job.'
} >> "$GITHUB_STEP_SUMMARY"

if [[ -n "${RUN_IDENTITY_OUT:-}" ]]; then
  umask 077
  printf '{"source_head_sha":"%s","tested_sha":"%s"}\n' "$SOURCE_HEAD_SHA" "$TESTED_SHA" > "$RUN_IDENTITY_OUT"
fi
