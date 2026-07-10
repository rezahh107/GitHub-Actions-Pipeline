# GitHub Actions Pipeline

Current version: `0.3.0`.

This repository is an evidence-first repository intelligence and staged-improvement engine. GitHub Actions remains one enforcement surface, not the whole product.

## Operating modes

### `minimal-safe-ci`

Conservative, deterministic, low-noise, and limited to a few strongly justified controls. It remains the default.

### `deep-repository-upgrade`

Adds bounded semantic resolution, composable profiles, structural history, optional telemetry, three recommendation channels, calibrated ordinal ranking, a dry-run implementation package, and review-only profile evolution.

## Repository model v1.1

The model combines:

- manifests, lockfiles, workspaces, and component roots;
- workflow triggers, permissions, jobs, steps, working directories, and commands;
- Python AST imports, literal route decorators, `__main__` guards, and declared `module:function` entry points;
- package-script and workflow-to-script resolution;
- resolved source-to-test relationships when a test imports a local source module;
- explicit inferred or unresolved states where semantic proof is unavailable.

Python AST and declarative package scripts are the first supported semantic analyzers. Other languages remain config-aware but semantically unresolved unless a versioned analyzer is added.

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
- exact expected Git HEAD;
- a clean worktree;
- an explicit recipe allowlist;
- an absent target path;
- report/result paths outside the target repository.

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
  --implementation-result-out /tmp/application-result.json
```

The implementation engine performs only allowlisted atomic file creation. It does **not** execute repository commands because checked-out code is untrusted input. Validation commands are returned for execution in an explicitly trusted environment.

## Profile evolution

Outcome-driven improvement is versioned and review-only, not hidden online learning:

```bash
python tools/profile_evolution.py \
  --outcomes outcomes.json \
  --out /tmp/profile-evolution-proposals.json \
  --minimum-distinct-repositories 3
```

Only exact-head successful outcomes can contribute. Proposals never modify profile or recipe registries automatically.

## Contracts

Backward-compatible contracts:

- `tools/ci_detective.py` and `schemas/ci_detective_report.schema.json`: `0.1.1`;
- `schemas/repository_upgrade_report.v1.schema.json`: legacy upgrade report `1.0.0`;
- `schemas/repository_upgrade_report.v1.1.schema.json`: current upgrade report `1.1.0`.

Supporting registries and schemas:

- `profiles/capability-profiles.v1.json`;
- `profiles/ranking-policy.v1.json`;
- `profiles/implementation-recipes.v1.json`;
- `schemas/ranking_policy.v1.schema.json`;
- `schemas/implementation_recipes.v1.schema.json`;
- `schemas/repository_outcomes.v1.schema.json`;
- `schemas/profile_evolution.v1.schema.json`.

## Validation

```bash
python -m unittest discover -s tests
python tools/ci_detective.py --repo-root . --out /tmp/ci-detective.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode minimal-safe-ci --out /tmp/minimal.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode deep-repository-upgrade --out /tmp/deep.json --implementation-package-out /tmp/package.json --generated-at 2026-07-10T00:00:00Z
```

## Documentation

- Architecture and extension guide: `docs/repository-upgrade.md`
- Canonical implementation tracker: `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md`
- Deep protocol: `pipeline/09-deep-repository-upgrade.md`
- Agent rules: `AGENTS.md`
