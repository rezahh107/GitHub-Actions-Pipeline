# Changelog

## Unreleased

- Load GitHub Actions workflows with an isolated YAML 1.2 boolean resolver so YAML 1.1 words such as `yes`, `no`, `on`, and `off` remain text and unsupported explicit boolean tags fail closed.
- Gate workflow command evidence through a versioned execution-eligibility model: literal-false jobs/steps are inert, dynamic conditions remain unresolved, and steps mixing `run` with `uses` cannot establish operational capability.
- Preserve NUL-framed Git metadata and filename streams byte-for-byte through collection; decode individual fields strictly without trimming leading or trailing filename whitespace.
- Reject repository symlink files and symlinked parents before metadata/content reads, constrain workspace patterns to bounded contained relative paths, and emit stable path diagnostics without serializing external content.
- Require behavioral command modes, structurally runnable GitHub Actions jobs, and discovered test targets before pull-request testing becomes operational.
- Treat path names as supporting profile evidence only and retain path-only domain correlations as diagnostics rather than selected profiles.
- Replace collision-prone structural-history line sentinels with validated NUL-delimited commit and filename records.
- Check out and verify the exact pull-request source head before validation and publish a structured identity record that distinguishes the event SHA from the tested source SHA.
- Replace text-like workflow command matching with a bounded standalone argv evidence parser; comments, inert shell text, control flow, substitutions, heredocs, pipes, and ambiguous constructs no longer establish operational capability.
- Preserve missing versus explicit-empty GitHub Actions permissions and compute effective permissions for every job using job-over-workflow precedence.
- Close all contract-bearing Repository Upgrade Report `1.1.0` objects and add mutation-negative schema coverage.
- Validate complete outcome registries before aggregation, require lowercase exact 40-character Git identities, reject duplicate/conflicting outcomes, and tie successful workflow evidence to the exact outcome head.
- Require behavior-specific `oracle_gap` evidence for Phase 1 and suppress correlation-only or already-operational duplicate controls.
- Add an external recovery journal and recoverable repository-plus-evidence transaction with failure injection across every mutation and persistence boundary.
- Render tested and source-head SHAs safely in `GITHUB_STEP_SUMMARY` and persist exact run identity with generated report artifacts.

## 0.3.0

- Add Repository Model `1.1.0` with explicit workspace boundaries and bounded semantic graphs.
- Resolve Python AST imports, literal route decorators, `__main__` guards, declared `module:function` entry points, and package/workflow script edges.
- Resolve source-to-test relationships only when local Python imports provide direct evidence; keep proximity-only relationships inferred.
- Add evidence-rich profile matches and conflict-aware expected/excluded capability composition.
- Add `ranking-policy.v1` with capability-specific ordinal factors, policy inputs, and factor-level rationale.
- Add a real but narrow implementation engine: dry-run by default, exact-HEAD, clean-worktree, explicit recipe allowlist, atomic non-overwriting writes, and no execution of untrusted repository commands.
- Add the first versioned implementation recipe for an unambiguous Python pull-request test workflow.
- Add exact-head validated outcome aggregation and deterministic review-only profile-evolution proposals without automatic registry mutation.
- Add report schema `1.1.0` while retaining legacy report `1.0.0` and `ci_detective` `0.1.1`.
- Add semantic, profile-conflict, ranking-policy, implementation-safety, outcome-threshold, and negative schema tests.

## 0.2.0

- Add explicit `minimal-safe-ci` and `deep-repository-upgrade` policy modes.
- Add an executable repository model with manifest, workflow, command, component, test, schema, validator, release, and capability evidence.
- Add optional read-only GitHub Actions telemetry and explicit unavailable fallbacks.
- Add structural Git-history analysis beyond commit-message keywords.
- Add independent observed-failure, structural-invariant, and baseline-capability recommendation channels.
- Add cold-start handling and composable capability profiles.
- Add bounded ordinal high-leverage ranking and staged Phase 1/Phase 2 output.
- Add closed v1 schemas, positive examples, malformed-input tests, fixtures, and actionable diagnostics.
- Preserve the `ci_detective` report `0.1.1` as a backward-compatible contract.

## 0.1.1

- Prevent shallow Git history from being reported as complete.
- Add explicit bounded, partial, unavailable, unknown, and not-applicable evidence states.
- Separate tested SHA, source head SHA, base SHA, and tested ref kind.
- Add canonical evidence SHA-256 and reproducible JSON serialization.
- Close evidence-item schemas and align producer output with fixtures.
- Add deferred gates, structured risk assessment, and execution contracts to the CI Gate Map.
- Remove the duplicate hand-maintained YAML example.
- Add deterministic, shallow-clone, CLI, schema-drift, and workflow-contract tests.
- Bound validation runtime and artifact retention while keeping product Markdown in CI scope.
