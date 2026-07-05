# 06 — Implementation Protocol

## Purpose

Define how an approved CI improvement is applied.

The model chooses the technical approach from evidence. The owner only grants permission for branch work.

## Permission Gate

Before implementation, give a short Persian briefing and ask for permission to continue on a separate branch.

## Branch Rule

After approval:

- use a dedicated branch;
- keep the change small and reversible;
- touch only related files;
- open or update a PR when possible.

## Smallest Useful Patch

Prefer this order:

1. connect existing validators or tests to CI;
2. strengthen existing tests only when evidence justifies it;
3. add a tiny deterministic test for a missing invariant;
4. add a new tool only when repository evidence requires it.

## Avoid

- broad template workflows;
- large matrix builds without evidence;
- heavyweight security gates by default;
- duplicate validator logic inside workflow YAML;
- committed raw generated evidence.

## PR Body

The PR body should include summary, files changed, accepted gates, rejected gates, validation evidence, remaining gaps, and exact head SHA when available.
