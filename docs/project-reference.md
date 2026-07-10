# GitHub Actions Pipeline — Project Reference

Current repository version: `0.3.0`

## Purpose

This repository defines a deterministic, evidence-first system for analyzing target repositories, identifying operational capability gaps, ranking high-leverage improvements, and staging safe implementation. GitHub Actions is one enforcement surface within the wider repository-engineering workflow.

## Product modes

- `minimal-safe-ci`: conservative default for a small number of strongly justified controls.
- `deep-repository-upgrade`: opt-in repository model, semantic resolution, history, optional telemetry, profile composition, ranking, staged plan, and dry-run implementation package.

## Canonical architecture

```text
repository evidence
  → RepositoryModel 1.1
  → profile detection/composition
  → history + optional telemetry
  → observed / structural / baseline recommendations
  → ranking-policy.v1
  → minimal plan or staged deep upgrade
  → explicit recipe-bound implementation when separately authorized
```

## Pipeline Phases

1. Validate the explicit operating mode and repository root.
2. Collect bounded file, manifest, workspace, workflow, and command evidence.
3. Resolve supported Python AST and package-script semantics without guessing dynamic behavior.
4. Build components, relationships, critical paths, and capability states with evidence.
5. Detect and compose profiles while preserving conflicts.
6. Collect bounded structural history and optional read-only telemetry.
7. Generate independent observed-failure, structural-invariant, and baseline-capability recommendations.
8. Rank recommendations with the versioned ordinal policy and factor-level rationale.
9. Produce a minimal plan or staged deep upgrade plus a dry-run implementation package.
10. Apply only explicitly allowlisted recipes under exact-HEAD and clean-worktree guards.
11. Validate on the exact resulting SHA and record outcomes separately for review-only profile evolution.

## Current deterministic capabilities

- JSON, TOML, and YAML configuration parsing;
- manifest, lockfile, workspace, workflow, component, test, schema, validator, release, and capability modeling;
- Python AST import, route, `__main__`, and `module:function` entry-point resolution;
- package-script and workflow-command resolution;
- bounded structural Git-history analysis;
- optional read-only GitHub Actions run telemetry;
- cold-start handling;
- 16 composable profiles with matched-signal evidence and conflict diagnostics;
- capability-specific ordinal ranking with factor rationale;
- dry-run implementation packages;
- exact-HEAD, clean-worktree, allowlisted atomic create-file application;
- review-only profile-evolution proposals from exact-head validated outcomes.

## Safety boundaries

- no direct writes to `main`;
- no PR merge or auto-merge;
- no release or package publication;
- no secret mutation;
- no execution of untrusted repository commands by the implementation engine;
- no automatic registry learning;
- no semantic claim beyond supported parsers or declarations.

## Contract map

| Contract | Version | Path |
|---|---:|---|
| Legacy CI detective | `0.1.1` | `schemas/ci_detective_report.schema.json` |
| Legacy repository upgrade report | `1.0.0` | `schemas/repository_upgrade_report.v1.schema.json` |
| Current repository upgrade report | `1.1.0` | `schemas/repository_upgrade_report.v1.1.schema.json` |
| Capability profiles | `1.0.0` | `profiles/capability-profiles.v1.json` |
| Ranking policy | `1.0.0` | `profiles/ranking-policy.v1.json` |
| Implementation recipes | `1.0.0` | `profiles/implementation-recipes.v1.json` |
| Repository outcomes | `1.0.0` | `schemas/repository_outcomes.v1.schema.json` |
| Profile evolution proposals | `1.0.0` | `schemas/profile_evolution.v1.schema.json` |

## Main entry points

```text
START.md
protocol/start.yaml
tools/ci_detective.py
tools/repository_upgrade.py
tools/profile_evolution.py
```

## Validation

The canonical validation workflow runs the complete unit suite, legacy report generation, both current operating modes, Scope Claim Audit checks, and artifact uploads. Exact-head evidence belongs in the active pull request rather than this file to avoid self-staling SHA claims.

## Continuation contract

Use `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md` for requirement traceability, verified modules, limitations, deferred work, and the next safe continuation step.
