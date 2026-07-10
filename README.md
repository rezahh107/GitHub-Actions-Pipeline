# GitHub Actions Pipeline

Current version: `0.3.0`.

This repository is an evidence-first repository intelligence and staged-improvement engine. GitHub Actions remains one enforcement surface, not the whole product.

## Start contract

Start trigger: `شروع`

Canonical response: `آماده‌ام. آدرس ریپو را برای بررسی بفرست.`

Visible entry and contract sources: `START.md` and `protocol/start.yaml`.

## Operating modes

### `minimal-safe-ci`

Conservative, deterministic, low-noise, and limited to a few strongly justified controls. It remains the default.

### `deep-repository-upgrade`

Adds bounded semantic resolution, composable profiles, structural history, optional telemetry, three recommendation channels, calibrated ordinal ranking, a dry-run implementation package, and review-only profile evolution.

## Repository model v1.1

The model combines:

- manifests, lockfiles, workspaces, and component roots;
- workflow triggers, explicit permission declarations, effective job permissions, steps, working directories, and bounded command evidence;
- Python AST imports, literal route decorators, `__main__` guards, and declared `module:function` entry points;
- package-script and workflow-to-script resolution;
- resolved source-to-test relationships when a test imports a local source module;
- explicit inferred or unresolved states where semantic proof is unavailable.

Python AST and declarative package scripts are the first supported semantic analyzers. Other languages remain config-aware but semantically unresolved unless a versioned analyzer is added.

### Executable-command evidence boundary

A workflow line establishes test, build, install, or release capability only when `tools/ci_command_evidence.py` resolves it to a standalone argv invocation recognized by the bounded classifier. Full-line comments, shell builtins, assignments, substitutions, heredocs, pipes, compound operators, and control-flow bodies never establish executable capability. Unsupported shell constructs remain explicit unresolved evidence; this engine does not emulate a shell.

### Effective permissions

Permission analysis preserves the distinction between a missing declaration and explicit `permissions: {}`. Effective permissions are computed for every job using job-level override over workflow-level declarations. Missing platform defaults, malformed values, and unsupported shapes fail closed as `unknown`; any effective write scope prevents a least-privilege `operational` classification.

## Quick start

```bash
python -m pip install -r requirements-test.txt

python tools/repository_upgrade.py \
  --repo-root . \
  --mode minimal-safe-ci \
  --out /tmp/minimal-upgrade.json \
  --generated-at 2026-07-10T00:00:00Z

python tools/repository_upgrade.py \
  --repo-root . \
  --mode deep-repository-upgrade \
  --out /tmp/deep-upgrade.json \
  --implementation-package-out /tmp/implementation-package.json \
  --generated-at 2026-07-10T00:00:00Z
```

## Opt-in implementation

Analysis never mutates the target repository. Applying a Phase 1 action requires all of the following:

- Deep mode;
- an applicable versioned recipe;
- exact lowercase 40-character expected Git HEAD;
- a clean worktree;
- an explicit recipe allowlist;
- an absent, contained, non-symlink target path;
- report, package, result, and recovery-journal paths outside the target repository.

Example:

```bash
python tools/repository_upgrade.py \
  --repo-root /path/to/trusted/repository \
  --mode deep-repository-upgrade \
  --out /tmp/deep.json \
  --implementation-package-out /tmp/package.json \
  --apply-phase-1 \
  --allow-recipe add-python-pr-test-workflow-v1 \
  --expected-head-sha <40-character-head-sha> \
  --implementation-result-out /tmp/application-result.json \
  --recovery-journal-out /tmp/application-recovery.json
```

The implementation engine performs only allowlisted atomic file creation. It does **not** execute repository commands because checked-out code is untrusted input. Before mutation, it persists an immutable plan outside the target repository. If report, package, or result persistence fails, it rolls back transaction-created files and outputs; incomplete rollback leaves a machine-readable `recovery_required` journal for deterministic continuation.

## Profile evolution

Outcome-driven improvement is versioned and review-only, not hidden online learning:

```bash
python tools/profile_evolution.py \
  --outcomes outcomes.json \
  --out /tmp/profile-evolution-proposals.json \
  --minimum-distinct-repositories 3
```

The entire outcome registry is validated before aggregation. A contributing success requires matching lowercase exact and workflow head SHAs, successful workflow conclusion, applied implementation, and operational post-state. Duplicate or conflicting identities are rejected. Proposals never modify profile or recipe registries automatically.

## Recommendation eligibility

Historical correlation is not a Phase 1 oracle. A recommendation can reach Phase 1 only when it records a concrete failure mode, affected path or contract, the limitation of existing controls, a missing machine-checkable assertion, the smallest proposed oracle, and a validation plan. Generic subsystem names and already-operational duplicate controls are suppressed or deferred.

## Contracts

Backward-compatible contracts:

- `tools/ci_detective.py` and `schemas/ci_detective_report.schema.json`: `0.1.1`;
- `schemas/repository_upgrade_report.v1.schema.json`: legacy upgrade report `1.0.0`;
- `schemas/repository_upgrade_report.v1.1.schema.json`: current closed upgrade report `1.1.0`.

Supporting registries and schemas:

- `profiles/capability-profiles.v1.json`;
- `profiles/ranking-policy.v1.json`;
- `profiles/implementation-recipes.v1.json`;
- `schemas/ranking_policy.v1.schema.json`;
- `schemas/implementation_recipes.v1.schema.json`;
- `schemas/repository_outcomes.v1.schema.json`;
- `schemas/profile_evolution.v1.schema.json`;
- `schemas/implementation_recovery_journal.v1.schema.json`.

## Validation

```bash
python -m py_compile tools/*.py
python -m unittest discover -s tests
python tools/ci_detective.py --repo-root . --out /tmp/ci-detective.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode minimal-safe-ci --out /tmp/minimal.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode deep-repository-upgrade --out /tmp/deep.json --implementation-package-out /tmp/package.json --generated-at 2026-07-10T00:00:00Z
python tools/validate_repository_upgrade_report.py /tmp/minimal.json
python tools/validate_repository_upgrade_report.py /tmp/deep.json
```

## Documentation

- Start entry: `START.md`
- Start contract: `protocol/start.yaml`
- Architecture and extension guide: `docs/repository-upgrade.md`
- PR #8 repair evidence: `docs/PR8_REPAIR_EVIDENCE.md`
- Canonical implementation tracker: `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md`
- Deep protocol: `pipeline/09-deep-repository-upgrade.md`
- Agent rules: `AGENTS.md`
