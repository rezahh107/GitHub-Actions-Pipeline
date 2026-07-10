# AGENTS.md

This file defines operating instructions for AI agents working in this repository.

## Mission

`GitHub-Actions-Pipeline` is an evidence-first repository-analysis and staged-improvement engine. It is not a catalog of generic checks.

The agent must preserve:

- evidence/inference separation;
- deterministic validation and serialization;
- exact-SHA awareness;
- proposed, rejected, deferred, and intentionally uncovered decisions;
- least-privilege workflow design;
- reversible branch-based changes;
- closed schema discipline;
- explicit evidence limitations;
- resistance to CI theater.

## Source precedence

1. Versioned schemas and executable contracts.
2. Validated fixtures and deterministic assertions.
3. Architecture and protocol documents.
4. Current implementation.
5. Unverified proposals or conversation notes.

Report conflicts. Do not silently merge incompatible rules.

## Explicit operating modes

### Minimal Safe CI — `minimal-safe-ci`

Use when the goal is a conservative, fast, low-noise set of strongly justified controls.

Policy:

- bounded repository modeling;
- no remote telemetry requirement;
- no baseline-capability expansion;
- only strongly supported, reversible Phase 1 items;
- existing `ci_detective` contract remains valid.

### Deep Repository Upgrade — `deep-repository-upgrade`

Use only when explicitly selected.

Policy:

- executable repository model;
- layered collector;
- bounded structural history;
- optional read-only workflow telemetry;
- composable capability profiles;
- three independent recommendation sources;
- cold-start handling;
- capability-gap and blind-spot analysis;
- testability-first decisions;
- bounded ordinal ranking;
- staged Phase 1 and Phase 2 output.

Do not implement the modes through scattered conditionals. Use the versioned policy and strategy modules.

## Evidence rules

Separate:

- `observed`;
- `derived`;
- `inferred`;
- `unavailable`;
- `not_applicable`.

Never claim a capability is operational because a similarly named file exists. Confirm executable configuration or a command actually run by CI.

Recommendation sources are independent:

- `observed_failure`;
- `structural_invariant`;
- `baseline_capability`.

No recorded historical failure means `not_yet_observed`, not `not_needed`.

Correlation such as co-change or hotspot evidence must not be described as causation.

## Capability states

Use only:

```text
absent
nominal
partial
operational
operational_but_weak
unknown
not_applicable
```

`nominal` means an artifact exists but operational execution is not proven.

## Determinism

Required:

- sort unordered collections before serialization;
- stable JSON key order;
- versioned canonicalization;
- reject NaN and infinities;
- SHA-256 over canonical content;
- explicit UTF-8 and timezone handling;
- deterministic tie-breakers;
- no hidden mutable global state;
- bounded Git history and API collection.

## Ranking

Do not optimize primarily for patch size.

Rank with bounded ordinal factors for:

- risk reduction;
- invariant criticality;
- regression-detection value;
- silent-failure exposure;
- evidence strength;
- maintainability;
- reversibility;
- implementation complexity;
- execution time;
- noise risk;
- maintenance cost;
- overlap with existing controls.

Do not use fractional pseudo-precision.

## Repository-model boundary

The repository model may represent only evidence available from:

- manifests and lockfiles;
- parsed configuration;
- workflow triggers, permissions, jobs, steps, and commands;
- component and workspace declarations;
- tests, schemas, validators, examples, and release configuration;
- declaratively detectable generated paths;
- bounded local Git history;
- explicitly supplied or read-only GitHub telemetry.

Unknown semantic relationships remain unresolved.

## Telemetry

Remote telemetry is optional. Local operation must not require network access.

When requested, use only read permissions. If access, token, or response shape is unavailable, emit an actionable unavailable state. Do not fabricate runs, jobs, durations, branch coverage, or flakiness.

## Implementation authority and safety

For explicit implementation prompts, a dedicated branch is authorization for normal reversible changes.

Never:

- write directly to `main`;
- merge a pull request;
- enable auto-merge;
- trigger a release;
- publish packages;
- alter secrets;
- expose credentials;
- delete branches;
- claim CI success before exact-head evidence exists.

Use coherent commits and keep unrelated changes out of scope.

## Validation

Before finalizing:

1. run targeted tests;
2. run `python -m unittest discover -s tests`;
3. validate schemas and positive/negative fixtures;
4. generate both mode reports at a fixed timestamp;
5. verify canonical hashes;
6. inspect exact exit codes;
7. inspect GitHub Actions on the exact PR head SHA when available.

A fixture-only pass is not production proof. Label validation scope precisely.

## Diagnostics

Every important failure should identify:

- what failed;
- where;
- affected invariant or capability;
- evidence references;
- why it matters;
- likely repair location or next diagnostic step.

Avoid bare messages such as `validation failed`.

## Documentation and traceability

Keep these aligned:

- `README.md`;
- `docs/repository-upgrade.md`;
- `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md`;
- schemas;
- profile catalog;
- examples and fixtures;
- tests;
- workflow commands;
- `CHANGELOG.md`;
- `VERSION`.

Do not mark tracker items `verified` without executed evidence.

## User-facing reports

Write owner-facing implementation reports in Persian. Preserve technical identifiers, paths, commands, schema names, branch names, SHAs, and code symbols in their original form.

Do not expose private chain-of-thought. Provide concise conclusions, evidence, decisions, limitations, and next safe action.
