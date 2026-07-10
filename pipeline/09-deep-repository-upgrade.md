# Deep Repository Upgrade Protocol

## Preconditions

- explicit mode: `deep-repository-upgrade`;
- readable repository root;
- versioned profile catalog;
- optional Git history;
- optional read-only workflow telemetry.

## Stages

1. Validate operating mode and input paths.
2. Build the deterministic repository model.
3. Parse workflows and commands.
4. Detect and compose profiles.
5. Collect bounded structural history.
6. Collect or explicitly decline remote telemetry.
7. Classify capability states.
8. Generate three independent recommendation channels.
9. Apply cold-start confidence rules.
10. Rank with bounded ordinal factors.
11. Decide Phase 1, Phase 2, deferred, rejected, and intentionally uncovered items.
12. Emit the closed v1 report with canonical SHA-256.
13. Validate schemas, fixtures, diagnostics, and mode separation.

## Implementation scope

A justified improvement may change workflows, tests, negative fixtures, validators, deterministic scripts, package verification, generated-file checks, configuration consistency, or testability. New dependencies require concrete purpose and compatibility evidence.

## Safety

Do not modify default branches, merge PRs, publish artifacts, or change secrets. Remote telemetry is read-only and optional.
