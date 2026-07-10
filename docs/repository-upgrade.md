# Repository Upgrade Architecture

Contract version: `1.0.0`  
Repository version: `0.2.0`

## Architecture

```text
repository files + executable configuration
                 ↓
        RepositoryModel v1
                 ↓
  profile detection and composition
                 ↓
history structure     optional telemetry
        ↘               ↙
 three independent recommendation channels
                 ↓
      bounded ordinal ranking
                 ↓
 minimal gate plan OR staged deep upgrade
```

## Modules

| Module | Responsibility |
|---|---|
| `tools/ci_upgrade_models.py` | mode policy, evidence/capability vocabulary, diagnostics, ranking contract |
| `tools/ci_repository_model.py` | layered deterministic repository and workflow collector |
| `tools/ci_profiles.py` | profile loading, detection, and composition |
| `tools/ci_history_analysis.py` | reverts, co-change, source-without-test, workflow churn, repeated fix evidence |
| `tools/ci_telemetry.py` | offline snapshots and optional read-only GitHub Actions collection |
| `tools/ci_recommendations.py` | independent channels, ranking, and decisions |
| `tools/ci_upgrade_engine.py` | orchestration and mode-specific output |
| `tools/repository_upgrade.py` | CLI |

## Repository model

The model records:

- repository archetypes;
- components derived from manifest boundaries;
- languages, frameworks, and build systems;
- manifests and lockfiles;
- executable entry points;
- tests and commands actually observed in workflows;
- schemas, validators, examples, and generated candidates;
- workflow triggers, permissions, jobs, steps, and commands;
- release paths;
- critical execution paths;
- source/test and schema/example relationships with evidence state;
- capability states and unresolved evidence.

Path or naming proximity may support an `inferred` relationship, but never a resolved semantic claim.

## Profiles

`profiles/capability-profiles.v1.json` is a versioned, data-driven catalog. Multiple profiles may match the same repository. Contributions are unioned deterministically, then explicit exclusions are applied.

To add a profile:

1. add one profile object with a unique stable `profile_id`;
2. use only documented detection fields;
3. declare expected capabilities, invariants, common failures, candidate checks, exclusions, and cost/noise notes;
4. validate against `schemas/capability_profiles.v1.schema.json`;
5. add a fixture and profile-composition test.

## Ranking model

Each factor is an integer ordinal from `0` through `3`.

Benefits are added:

- risk reduction;
- invariant criticality;
- regression detection;
- silent-failure exposure;
- evidence strength;
- maintainability;
- reversibility.

Costs are subtracted:

- implementation complexity;
- execution time;
- noise risk;
- maintenance cost;
- overlap with existing controls.

The result is an ordering aid, not a probability or exact risk estimate. Confidence may reduce the priority band.

## Cold-start

History states include limited history, cold start, no recorded failures, and informative history. Structural and baseline channels remain active even when observed-failure evidence is absent.

## Telemetry

Deep mode supports:

```bash
--telemetry-json path/to/snapshot.json
```

or:

```bash
--collect-telemetry
```

The latter uses `GITHUB_TOKEN` and the read-only Actions runs endpoint. Missing access produces `status: unavailable` plus an actionable diagnostic. It never blocks local analysis.

## Migration

Existing `ci_detective` consumers remain on report `0.1.1`.

New consumers should invoke `tools/repository_upgrade.py` and validate against `schemas/repository_upgrade_report.v1.schema.json`.

No silent conversion between the two report contracts is performed.
