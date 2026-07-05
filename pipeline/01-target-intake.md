# 01 — Target Repository Intake

## Purpose

Collect the minimum information needed to inspect a target repository and design meaningful CI gates.

The owner should not be asked to choose technical CI options.

## Required Fields

- repository URL
- repository full name
- default branch
- target branch or target state
- repository purpose, if known
- priority profile: correctness, determinism, low friction

## Connector Capability Check

Before analysis, record which areas are accessible:

- repository files
- workflow files
- pull requests
- workflow runs
- artifacts or summaries
- related repositories, if the target is part of a larger system

If a source is not accessible, say so in the report. Do not silently skip it.

## Ecosystem Detection

Check whether the target repository is standalone or part of a larger system.

Signals include:

- links to related repositories;
- shared contracts;
- adapter or contract wording;
- audit documents;
- drift reports;
- changelogs that mention other repositories.

## Incomplete Evidence Rule

Continue with incomplete evidence only when the missing evidence is not needed for a safe reversible audit.

Pause and request expanded access only when missing evidence affects correctness or verification.

## Owner-Facing Summary

Use Persian and keep it short.

Example:

```text
ریپوی هدف را شناختم. شواهد داخلی در دسترس است، اما شواهد بین‌ریپویی کامل نیست. audit داخلی را انجام می‌دهم و این محدودیت را در گزارش نگه می‌دارم.
```
