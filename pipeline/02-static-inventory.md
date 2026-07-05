# 02 — Static Repository Inventory

## Purpose

Build a factual inventory of the target repository before proposing CI gates.

## Inventory Checklist

Record these facts:

- languages and major file types
- package managers and lockfiles
- tests and test directories
- build and release commands
- schemas
- validators
- fixtures
- version files
- workflow files
- generated outputs
- important documentation
- deployment or package artifacts

## Domain Risk Pattern Signal Check

During Static Repository Inventory, check `detection_signals` from every file in `risk-patterns/` against the actual target repository structure.

For each matched file, record:

- `project_type`;
- matched static signals;
- short evidence references such as file paths, package metadata, manifests, or directory names.

A target repository can match more than one `project_type`. Matching project types are additive, not mutually exclusive. Example: a Python package that is also part of a multi-repo ecosystem can activate both `python-package` and `multi-repo-adapter`.

If no project type matches, report this exact limitation:

```text
no domain risk pattern matched — falling back to generic checklist only
```

## Hotspot Candidates

Mark files as hotspot candidates when they are central to correctness or likely to drift.

Common hotspot groups:

- workflow files
- schema files
- validator files
- package metadata
- version files
- generated outputs
- extension manifests
- contract manifests
- adapter mapping files

## Output Fields

The inventory should report languages, packages, lockfiles, tests, build commands, schemas, validators, fixtures, version files, workflows, generated outputs, docs, hotspot candidates, matched domain risk pattern project types, and limitations.

## Rule

Inventory is evidence, not a final CI design. The model uses it to discover failure modes before choosing gates.
