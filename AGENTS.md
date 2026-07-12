# AGENTS.md

This file defines operating instructions for AI agents working in this repository.

## Mission

`GitHub-Actions-Pipeline` is an evidence-first repository intelligence and staged-improvement engine. It is not a catalog of generic checks and it is not authorized to invent repository behavior.

Preserve:

- evidence/inference separation;
- deterministic validation and serialization;
- exact-SHA awareness;
- proposed, rejected, deferred, blocked, and intentionally uncovered decisions;
- least-privilege workflow design;
- reversible branch-based changes;
- closed schema and registry discipline;
- explicit limitations;
- resistance to CI theater.

## Source precedence

1. Versioned schemas and executable contracts.
2. Validated fixtures and deterministic assertions.
3. Versioned registries and architecture protocols.
4. Current implementation.
5. Unverified proposals or conversation notes.

Report conflicts. Do not silently merge incompatible rules.

## Operating modes

### `minimal-safe-ci`

Default conservative mode. No baseline expansion, remote telemetry requirement, implementation package, or semantic-history expansion beyond what the policy enables.

### `deep-repository-upgrade`

Explicit opt-in. Adds bounded semantic modeling, profile composition, structural history, optional telemetry, capability gaps, calibrated ranking, staged output, and a dry-run implementation package.

Mode behavior must remain policy-driven rather than scattered conditionals.

## Evidence and relationship rules

Evidence states:

```text
observed
derived
inferred
unavailable
not_applicable
```

Relationship resolution states are separate:

```text
resolved
partial
inferred
unresolved
```

Do not call a relationship resolved unless a versioned parser or declarative reference establishes it. File/path proximity is `inferred` at most.

Component boundaries follow explicit workspace declarations, then nearest manifest roots. A manifest boundary is not proof of semantic ownership.

## Capability rules

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

A similarly named file never proves operational capability. Confirm executable configuration or a command actually connected to CI.

Recommendation channels remain independent:

- `observed_failure`;
- `structural_invariant`;
- `baseline_capability`.

No recorded failure means `not_yet_observed`, not `not_needed`. Co-change and repeated fixes are correlation, not causation.

## Semantic analyzer boundary

Current semantic authority is limited to:

- bounded Python AST parsing;
- local Python import resolution;
- literal route decorators;
- `__main__` guards;
- declared Python `module:function` entry points;
- package scripts and workflow commands that invoke them.

Do not infer dynamic imports, reflection, dependency injection, runtime routes, generated code, JavaScript call graphs, or network behavior.

## Profile rules

Every profile match must preserve matched criteria and references. Confidence must reflect independent and authoritative signals.

Expected and excluded capability contributions must be retained separately. If both occur, emit a conflict diagnostic and withhold the capability from baseline recommendations until a versioned rule resolves it.

## Ranking

Use `profiles/ranking-policy.v1.json`. Each factor is an integer from `0` through `3`. Preserve:

- ranking-policy version;
- current capability state;
- evidence confidence and reference count;
- factor values;
- factor-level rationale;
- deterministic tie-breakers.

The total is an ordering aid, not probability or calibrated monetary risk. Do not optimize primarily for patch size or use fractional pseudo-precision.

## Implementation engine boundary

Analysis is read-only by default. A dry-run implementation package does not authorize mutation.

Mutation requires all of:

- explicit `deep-repository-upgrade` mode;
- `--apply-phase-1`;
- exact current HEAD supplied through `--expected-head-sha`;
- clean Git worktree;
- explicit `--allow-recipe` entries;
- applicable versioned recipe preconditions;
- absent non-symlink target path;
- content-hash verification;
- output/report paths outside the target repository.

Current mutation supports non-overwriting atomic file creation only. Never execute repository commands in the generic implementation engine; repository code is untrusted input. Return validation commands for an explicitly trusted environment.

## Outcome-driven profile evolution

No hidden online learning or mutable memory is allowed.

Only exact-head successful outcomes from distinct privacy-preserving repository fingerprints may produce review-only proposals. Proposals must never update profile, ranking, or recipe registries automatically. Registry changes require a separate versioned PR, schemas, fixtures, tests, and migration notes.

## Telemetry

Remote telemetry is optional and read-only. Missing token, permission, response shape, jobs, or logs must produce explicit unavailable evidence. Do not fabricate flakiness, branch coverage, durations, or failing steps.

## Determinism

Required:

- sorted unordered collections;
- stable JSON key order;
- versioned canonicalization;
- UTF-8 and timezone-explicit behavior;
- SHA-256 over canonical content;
- rejection of NaN and infinities;
- deterministic tie-breakers;
- bounded file, Git-history, and API collection;
- no hidden mutable global state.

## Repository safety

Never:

- write directly to `main`;
- merge or enable auto-merge;
- publish packages or trigger releases;
- alter secrets;
- expose credentials;
- delete branches;
- claim CI success before exact-head evidence exists.

Use coherent commits and keep unrelated changes out of scope.

## Validation

Before finalizing:

1. run targeted unit and malformed-input tests;
2. run `python -m unittest discover -s tests`;
3. validate all schemas and registries;
4. generate both mode reports at a fixed timestamp;
5. verify canonical hashes;
6. test implementation dry-run and exact-HEAD guards in temporary Git fixtures;
7. test outcome thresholds and no-auto-mutation behavior;
8. inspect exact exit codes;
9. inspect GitHub Actions on the exact PR head SHA.

Fixture success is not production proof. State verification scope precisely.

## Diagnostics

Important failures must identify what failed, where, the affected invariant or capability, evidence references, why it matters, and a repair or next diagnostic step. Avoid bare messages such as `validation failed`.

## Documentation and traceability

Keep README, architecture, tracker, protocols, prompts, schemas, registries, fixtures, tests, workflow commands, changelog, and version metadata aligned. Do not mark a tracker item `verified` without executed evidence.

## User-facing reports

Write owner-facing implementation reports in Persian. Preserve technical identifiers, paths, commands, schema names, branch names, SHAs, and code symbols. Do not expose private chain-of-thought; provide conclusions, evidence, decisions, limitations, and the next safe action.
