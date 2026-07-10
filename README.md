# GitHub Actions Pipeline

Current version: `0.2.0`.

This repository provides an evidence-first repository-analysis and staged-improvement engine. It preserves the existing conservative CI collector and adds an explicit opt-in deep mode.

## Start contract

Start trigger: `شروع`

Canonical response: `آماده‌ام. آدرس ریپو را برای بررسی بفرست.`

References: `START.md` and `protocol/start.yaml`.

## Operating modes

### `minimal-safe-ci`

Conservative, fast, deterministic, low-noise, and limited to a few strongly justified controls.

### `deep-repository-upgrade`

Builds an executable repository model, composes capability profiles, separates recommendation sources, detects capability gaps and CI blind spots, ranks high-leverage improvements, and produces a staged implementation package.

The modes are policy objects, not scattered workflow flags.

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
  --generated-at 2026-07-10T00:00:00Z
```

Optional workflow telemetry can be supplied through `--telemetry-json`. Deep mode can also use `--collect-telemetry` with a read-only `GITHUB_TOKEN`; local analysis remains fully usable when telemetry is unavailable.

## Backward compatibility

`tools/ci_detective.py` and `schemas/ci_detective_report.schema.json` remain on contract `0.1.1`. Existing consumers do not need to migrate.

The new contract is:

- CLI: `tools/repository_upgrade.py`
- report schema: `schemas/repository_upgrade_report.v1.schema.json`
- profile catalog: `profiles/capability-profiles.v1.json`
- profile schema: `schemas/capability_profiles.v1.schema.json`
- fixtures: `fixtures/repository-upgrade/scenarios.v1.json`

## Recommendation channels

Every recommendation identifies exactly one source:

1. `observed_failure`
2. `structural_invariant`
3. `baseline_capability`

A repository with no recorded failures is treated as cold-start or limited-history. That does not disable structural invariants or profile baselines.

## Capability states

```text
absent
nominal
partial
operational
operational_but_weak
unknown
not_applicable
```

A file's existence does not prove a capability is operational. The model inspects executable configuration and commands run by workflows.

## Validation

```bash
python -m unittest discover -s tests
python tools/ci_detective.py --repo-root . --out /tmp/ci-detective.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode minimal-safe-ci --out /tmp/minimal.json --generated-at 2026-07-10T00:00:00Z
python tools/repository_upgrade.py --repo-root . --mode deep-repository-upgrade --out /tmp/deep.json --generated-at 2026-07-10T00:00:00Z
```

## Documentation

- Architecture and extension guide: `docs/repository-upgrade.md`
- Canonical implementation tracker: `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md`
- Existing start contract: `START.md` and `protocol/start.yaml`
- Agent rules: `AGENTS.md`
