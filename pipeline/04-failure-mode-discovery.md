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

## Domain Risk Pattern Match

`risk-patterns/` is the concrete library for `domain_pattern` evidence.

During Static Repository Inventory, the agent checks `detection_signals` from every `risk-patterns/*.yaml` file against the actual target repository structure. Any `project_type` whose signals match contributes its `risk_patterns` to the failure-mode candidate list.

Each activated pattern is tagged with:

```yaml
evidence_level: domain_pattern
```

A target repository can match more than one `project_type`. Matching project types are additive, not mutually exclusive.

Example: a Python package that is also part of a multi-repo ecosystem can activate both `python-package` and `multi-repo-adapter`.

If no project type matches, report:

```text
no domain risk pattern matched — falling back to generic checklist only
```

Domain patterns are candidate risks, not automatic CI gates.

A pattern becomes a proposed gate only after the existing Gate Meaningfulness Test confirms:

- repository evidence;
- practical machine-checkability;
- acceptable runtime/noise;
- clear maintainer actionability.

## Current Library

The initial domain risk-pattern library covers:

- `python-package`;
- `python-desktop`;
- `browser-extension-mv3`;
- `wordpress-plugin`;
- `contract-schema-repo`;
- `docs-only-repo`;
- `multi-repo-adapter`.

## Output Rule

Each failure mode must include an evidence class, a short evidence reference, and a possible machine-checkable gate if one exists.
