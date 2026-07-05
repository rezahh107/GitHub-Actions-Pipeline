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

The inventory should report languages, packages, lockfiles, tests, build commands, schemas, validators, fixtures, version files, workflows, generated outputs, docs, hotspot candidates, and limitations.

## Rule

Inventory is evidence, not a final CI design. The model must use it to discover failure modes before choosing gates.
