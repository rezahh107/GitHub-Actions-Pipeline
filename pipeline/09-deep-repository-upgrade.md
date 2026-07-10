# Deep Repository Upgrade Protocol

## Preconditions

- explicit mode: `deep-repository-upgrade`;
- readable repository root;
- versioned profile, ranking, and recipe registries;
- optional full Git history;
- optional read-only workflow telemetry.

## Read-only analysis stages

1. Validate mode and input paths.
2. Parse manifests, lockfiles, workspaces, workflows, and command candidates.
3. Resolve bounded Python AST and package-script semantics.
4. Build evidence-bearing components, relationships, critical paths, and capability states.
5. Detect profiles with matched-signal evidence.
6. Preserve expected/excluded contributions and diagnose composition conflicts.
7. Collect bounded structural history.
8. Collect or explicitly decline remote telemetry.
9. Generate independent observed-failure, structural-invariant, and baseline-capability channels.
10. Apply cold-start confidence rules.
11. Derive ranking factors from `ranking-policy.v1` and record factor rationale.
12. Produce Phase 1, Phase 2, deferred, rejected, and intentionally uncovered decisions.
13. Build a dry-run implementation package from versioned recipes.
14. Emit report `1.1.0` with canonical SHA-256.

## Optional mutation stage

Mutation is not implied by analysis. It requires:

- `--apply-phase-1`;
- `--allow-recipe` for each permitted recipe;
- `--expected-head-sha` matching current HEAD;
- clean worktree;
- applicable preconditions;
- outputs outside the target repository.

Only non-overwriting atomic file creation is currently supported. Repository commands are never executed by the implementation engine.

## Outcome-driven evolution

Validated outcomes may be aggregated into review-only profile proposals. No online learning, hidden memory, or automatic registry mutation is allowed.

## Safety

Do not modify default branches, merge PRs, enable auto-merge, publish packages, alter secrets, execute untrusted repository commands, or present inferred relationships as resolved.
