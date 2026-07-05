# 04 — Failure Mode Discovery

## Purpose

Convert collected evidence into repository-specific failure modes.

Do not start from generic CI checklists.

## Failure Mode Classes

Use these classes:

- historical: observed in commits, PRs, issues, or CI failures;
- structural: implied by repository file relationships;
- domain_pattern: known risk for this project type;
- cross_repo: found through related repositories or shared contracts;
- hypothetical: plausible but weakly evidenced.

A risk must not be called real without evidence.

## Domain Pattern Examples

Python package:

- package version drift;
- import failure;
- missing test execution;
- metadata mismatch.

Browser extension MV3:

- manifest drift;
- missing build artifact;
- content script path mismatch;
- package output missing expected files.

Contract or schema repository:

- invalid schema;
- fixture pass/fail inversion;
- version or manifest drift;
- generated output mismatch.

Docs-only repository:

- broken references;
- missing required sections;
- stale generated index.

LLM workflow repository:

- prompt contract drift;
- schema mismatch;
- unclear handoff format.

Multi-repo adapter:

- producer and consumer contract mismatch;
- silent field loss;
- unsupported variant crossing repository boundary.

## Output Rule

Each failure mode must include an evidence class, a short evidence reference, and a possible machine-checkable gate if one exists.
