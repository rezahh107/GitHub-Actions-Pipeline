# GitHub Actions Pipeline

A personal, AI-assisted decision pipeline for designing meaningful GitHub Actions CI for real repositories.

This repository is **not** a generic GitHub Actions template catalog. It is a modular operating system for a GitHub-connected language model: inspect a target repository, collect evidence, identify real failure modes, select small high-signal CI gates, ask only for owner permission to modify a branch, implement the smallest useful patch, and report validation evidence honestly.

## Core Question

For any target repository, the pipeline helps the model answer:

> What can actually break in this repository, and which small machine-checkable GitHub Actions gates should catch those failures with the least friction?

## Priorities

This project is optimized for personal, solo-maintainer repositories.

1. Correctness
2. Determinism
3. Low-friction automation
4. Fast actionable feedback
5. Small number of meaningful gates
6. Maximum useful autonomy from the language model

Enterprise-grade external attacker hardening is not a default priority. Low-cost safety guardrails still matter because they prevent accidental self-inflicted damage.

## Mental Model

Bad CI is like a guard who asks the same generic question at every door.

Good CI is like a smart checkpoint that knows what kind of building it protects.

A small personal script repository does not need airport-level security. A schema or contract repository needs gates that prevent version drift, invalid schemas, fixture regressions, and broken generated outputs. A browser extension repository needs gates that protect manifest integrity, package output, and runtime-sensitive files.

```text
Evidence first → failure modes → meaningful gates → owner permission → branch patch → validation evidence
```

## Owner Model

The owner is not expected to make technical CI/CD decisions.

The model has technical authority to inspect evidence, research current official documentation when needed, choose the best technical approach, reject generic best practices that do not fit the repository, implement the smallest useful patch after permission, and report evidence honestly.

Owner approval means:

```text
permission to make changes on a separate branch
```

Owner approval does **not** mean choosing between technical options.

## GitHub Connector-First Architecture

The intended operating mode is GitHub Connector first.

The language model uses GitHub Connector/API-style operations to inspect files, create branches, update files, open PRs, and inspect workflow status. It must not assume it can directly run local shell commands.

Deterministic evidence mining should run inside GitHub Actions runners or through explicitly available tools, not through model imagination.

```text
Language model with GitHub Connector
        ↓
Orchestrates repository inspection and changes
        ↓
GitHub Actions runner executes deterministic evidence tools
        ↓
Artifacts + step summary + workflow evidence
        ↓
Model reads evidence and makes CI decisions
        ↓
Owner grants permission to modify branch
        ↓
Model applies patch and verifies results
```

## v0.1 Repository Structure

```text
README.md
AGENTS.md
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

prompts/
  00-start.md
  01-audit-only.md
  02-implementation-after-approval.md
  03-post-implementation-validation.md

schemas/
  ci_detective_report.schema.json
  ci_gate_map.schema.json

examples/
  ci_gate_map.example.yaml
  ci_detective_report.example.json

tools/
  ci_detective.py

tests/
  test_schemas.py
  test_examples.py

.github/workflows/
  validate.yml
```

## How to Start a Model Session

Use `prompts/00-start.md` at the beginning of a GitHub-connected model session.

Expected minimal response:

```text
Pipeline loaded. I am ready. Send the target repository.
```

After that, give the target repository URL. The model should run audit-only first and produce a short Persian owner briefing plus a CI Gate Map. It should not ask the owner to choose technical CI options.

## Pipeline Phases

1. Pipeline load
2. Target repository intake
3. Static repository inventory
4. Bilingual historical evidence mining
5. CI failure telemetry and hotspot detection
6. Cross-repo evidence assessment when relevant
7. Failure mode discovery
8. Domain risk pattern matching
9. Risk scoring
10. CI Gate Meaningfulness Test
11. Autonomous CI decision
12. Short Persian owner briefing
13. Owner permission gate
14. GitHub Connector implementation on a separate branch
15. Validation on exact head SHA
16. Final Persian evidence report

## Gate Meaningfulness Rule

A CI gate is allowed only if it catches a real, plausible, repository-specific failure with low noise and acceptable runtime cost.

Before adding a gate, the model must answer:

1. What exact failure does this gate catch?
2. What repository evidence justifies it?
3. Is there already a script, validator, or test that should be wired into CI?
4. If it fails, will the maintainer immediately know what to fix?
5. Should it run on PR, push, release, manual trigger, or scheduled run?
6. Is runtime cost proportional to signal value?
7. Could it be noisy or flaky?
8. Does it actually enforce something, or only document it?

If the answer is unclear, reject the gate or mark it low-priority.

## Personal Repository CI Policy

Do not apply enterprise-grade security tooling by default.

Avoid by default:

- OpenSSF Scorecard;
- CodeQL;
- dependency review gates;
- secret scanning workflows;
- vulnerability gates;
- mandatory full-length SHA pinning for every action;
- heavyweight matrix builds;
- noisy scheduled scans.

Keep low-friction safety guardrails:

- do not use workflow-level `write-all` permissions;
- use minimum required permissions;
- do not print secrets or sensitive values to logs;
- avoid `pull_request_target` unless there is a clear documented reason;
- keep workflow and job names stable if they may become required checks;
- prefer simple readable workflows over clever generalized workflows.

## Evidence Persistence

Raw generated evidence should not be committed by default.

Preferred channels:

```text
raw JSON evidence      → workflow artifact
human-readable summary → GITHUB_STEP_SUMMARY
final decision summary → PR body or PR comment
optional latest.json   → rolling overwrite only, never timestamp spam
```

## Local Validation

This repository intentionally uses Python standard library tests for v0.1.

```bash
python -m unittest discover -s tests
python tools/ci_detective.py --repo-root . --out /tmp/ci_detective_report.json
```

The GitHub workflow in `.github/workflows/validate.yml` runs the same lightweight validation on `pull_request`, `push` to `main`, and manual dispatch.

## What This Repository Is Not

This repository is not:

- a generic CI template dump;
- an enterprise security hardening framework;
- a marketplace of random workflows;
- a replacement for repository-specific evidence;
- a system that asks the owner to choose technical CI options.

## Success Criteria

The pipeline is successful when:

- CI gates are tied to repository evidence;
- the number of required checks stays small;
- failures are actionable;
- the model makes technical decisions autonomously;
- the owner only approves repository modification;
- implementation happens on a separate branch;
- no check is claimed as enforced unless it is wired into GitHub Actions;
- validation evidence is tied to an exact commit or head SHA.
