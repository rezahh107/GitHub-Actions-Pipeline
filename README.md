# GitHub Actions Pipeline

A personal, AI-assisted decision pipeline for designing meaningful GitHub Actions CI for real repositories.

This repository is **not** a generic workflow catalog. It is an evidence-first operating system for a GitHub-connected model: inspect a target repository, identify real failure modes, select a small set of high-signal gates, ask only for permission to modify a branch, implement the smallest useful patch, and report validation evidence honestly.

Current version: `0.1.1`.

## Core Question

> What can actually break in this repository, and which small machine-checkable GitHub Actions gates should catch those failures with the least friction?

## Priorities

1. Correctness
2. Determinism
3. Low-friction automation
4. Fast actionable feedback
5. Small number of meaningful gates
6. Maximum useful autonomy from the language model

The pipeline is optimized for personal and solo-maintainer repositories. Enterprise security tooling is not a default priority; minimum permissions and low-cost safety guardrails remain required.

```text
Evidence first → failure modes → meaningful gates → owner permission → branch patch → validation evidence
```

## Owner Model

The owner grants permission to make repository changes. The model makes the technical CI/CD decisions.

Before approval, analysis is read-only. After approval, implementation happens on a dedicated branch and should remain small, reversible, and repository-specific.

## Connector-First Architecture

```text
GitHub-connected model
        ↓
Repository and history inspection
        ↓
GitHub Actions runner executes deterministic tools
        ↓
JSON artifact + step summary + workflow evidence
        ↓
Model selects or rejects CI gates
        ↓
Owner approves branch modification
        ↓
Patch, PR, and exact-SHA validation
```

The model must not assume a local shell exists. Deterministic evidence should run in GitHub Actions or another explicitly available execution environment.

## Repository Structure

```text
README.md
AGENTS.md
CHANGELOG.md
VERSION
.gitattributes

pipeline/
  00-overview.md
  01-target-intake.md
  02-static-inventory.md
  03-evidence-mining.md
  04-failure-mode-discovery.md
  05-ci-gate-map.md
  06-implementation-protocol.md
  07-validation-and-reporting.md
  08-scope-claim-audit.md

prompts/
  00-start.md
  01-audit-only.md
  02-implementation-after-approval.md
  03-post-implementation-validation.md
  04-scope-claim-audit.md

schemas/
  ci_detective_report.schema.json
  ci_gate_map.schema.json
  scope_claim_audit.schema.json

examples/
  ci_detective_report.example.json
  ci_gate_map.example.json
  scope_claim_audit.example.json
  scope_claim_audit.true-negative.example.json
  scope_claim_audit.ambiguous.example.json

tools/
  ci_detective.py
  ci_git_evidence.py
  ci_models.py
  ci_report.py
  scope_claim_audit.py

tests/
  test_ci_detective.py
  test_examples.py
  test_schemas.py
  test_scope_claim_audit_examples.py
  test_scope_claim_audit_schema.py
  test_scope_claim_audit_tool.py
  test_workflow_action_pinning.py
  test_workflow_contract.py

.github/workflows/
  validate.yml
```

JSON is the canonical fixture format. A second hand-maintained YAML copy is intentionally not kept because duplicate fixtures can drift.

## Scope Claim Audit

Scope Claim Audit checks whether a PR claim under-reports actual changed scope, especially when the diff touches sensitive repository surfaces such as schemas, validators, workflows, release locks, package metadata, generated outputs, or protocol files.

It is advisory by default and feeds CI gate design decisions; it is not a generic merge stopper. Future enforced mode is valid only when a target repository has a real wired gate and the audit package declares `enforcement_mode: enforced` plus `wired_enforcement_gate` metadata.

## Pipeline Phases

1. Load this repository and its operating rules.
2. Intake the target repository and connector scope.
3. Build a factual static inventory.
4. Mine bounded English and Persian commit evidence.
5. Inspect workflow telemetry and cross-repository evidence when accessible.
6. Classify failure modes.
7. Apply the Gate Meaningfulness Test.
8. Produce a schema-valid CI Gate Map.
9. Give a short Persian owner briefing.
10. Ask only for permission to modify a branch.
11. Implement the approved gates.
12. Validate the exact tested SHA and report results.

## Gate Meaningfulness Test

A gate is allowed only if it catches a real, plausible, repository-specific failure with acceptable runtime and noise.

Before adding one, answer:

1. What exact failure does it catch?
2. What repository evidence supports it?
3. Is there an existing validator or test to wire into CI?
4. Will a failure immediately tell the maintainer what to fix?
5. Which event should trigger it?
6. Is its runtime proportional to its signal?
7. Is it noisy or flaky?
8. Does it enforce something rather than merely document it?

A gate must be classified as:

- `proposed_gates`: supported and ready for owner approval;
- `rejected_gates`: not meaningful for current evidence;
- `deferred_gates`: potentially useful but blocked on named missing evidence.

Each proposed gate contains explicit evidence, execution events, permissions, command, affected files, and structured risk assessment. Numeric risk scoring is intentionally deferred until a versioned formula exists.

## Evidence Contract

`tools/ci_detective.py` writes a strict JSON report validated by `schemas/ci_detective_report.schema.json`.

The contract requires:

- shallow clones are never reported as complete history;
- completeness states include a reason;
- `tested_sha`, `source_head_sha`, and `base_sha` remain separate;
- synthetic PR merge refs are identified as `pull_request_merge`;
- evidence items use closed schemas;
- hotspots use deterministic path tie-breakers;
- JSON keys are stable and NaN or infinities are rejected;
- `evidence_sha256` is SHA-256 over canonical evidence content, excluding generation time and run context;
- a fixed `--generated-at` value or `SOURCE_DATE_EPOCH` makes the full artifact reproducible.

The local collector does not call GitHub APIs. Workflow telemetry is therefore `unavailable`, and sibling-repository scope is `unknown`, until connector evidence is supplied.

## Evidence Persistence

```text
raw JSON evidence      → workflow artifact
human-readable summary → GITHUB_STEP_SUMMARY
final decision summary → PR body or PR comment
```

Generated reports are not committed by default. The validation workflow retains artifacts for 14 days.

## Validation Workflow

`.github/workflows/validate.yml` runs on pull requests, pushes to `main`, and manual dispatch.

It uses:

- read-only repository permission;
- full Git history for evidence mining;
- checkout without persisted credentials;
- a fixed Ubuntu runner image;
- a ten-minute timeout;
- full-SHA action pinning;
- exact tested and source head SHA reporting.

Markdown, pipeline protocol files, and prompts are intentionally **not** excluded because they are part of the product contract.

## Local Validation

The runtime collector uses only the Python standard library. Tests use `jsonschema`.

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests
python tools/ci_detective.py \
  --repo-root . \
  --out /tmp/ci_detective_report.json \
  --generated-at 2026-07-05T00:00:00Z
python tools/scope_claim_audit.py --check examples/scope_claim_audit.example.json
python tools/scope_claim_audit.py --check examples/scope_claim_audit.true-negative.example.json
python tools/scope_claim_audit.py --check examples/scope_claim_audit.ambiguous.example.json
python tools/scope_claim_audit.py --input examples/scope_claim_audit.example.json --out /tmp/scope_claim_audit.summary.md
```

## Intentionally Not Added by Default

- CodeQL, OpenSSF Scorecard, dependency review, or broad vulnerability gates;
- heavyweight Python matrices without compatibility evidence;
- generic linters without a repository-specific failure mode;
- pre-commit as a required dependency;
- Makefile wrappers for already-short commands;
- reusable workflows before repeated pilot evidence exists;
- pip cache without runtime telemetry showing material benefit;
- Markdown `paths-ignore` filters.

## Success Criteria

The pipeline succeeds when:

- each gate traces to evidence;
- required checks remain few and actionable;
- missing evidence is explicit;
- producer output, schemas, examples, tests, and documentation stay aligned;
- no check is called enforced until it runs in GitHub Actions;
- validation identifies the exact tested commit and the source head;
- incomplete evidence is never silently promoted to complete evidence.
