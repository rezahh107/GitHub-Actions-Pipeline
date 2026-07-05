# 05 — CI Gate Map

## Purpose

Define which CI gates are worth adding, which are rejected, and which are deferred pending evidence.

The CI Gate Map is produced before implementation.

## Gate Meaningfulness Test

Before recommending a gate, answer:

1. What exact real or structural failure does this gate catch?
2. What evidence justifies it in this repository?
3. Is there already a script, validator, or test that should be wired into CI?
4. If it fails, will the maintainer immediately know what to fix?
5. Should it run on PR, push, release, manual trigger, or scheduled run?
6. Is runtime cost proportional to signal value?
7. Could it be noisy or flaky?
8. Does it actually enforce something, or only document it?

If the answer is unclear, reject the gate or defer it with named missing evidence.

## Gate Outcomes

### Proposed

A proposed gate is supported by current evidence and is ready for owner approval.

### Rejected

A rejected gate is not meaningful for the current repository evidence. Rejected gates do not use `priority: reject` inside the proposed-gate collection.

### Deferred

A deferred gate may become meaningful later. It must include:

- stable gate ID;
- reason for deferral;
- required missing evidence;
- an explicit reconsideration condition;
- a Persian owner explanation.

## Risk Assessment

Each proposed gate includes:

```text
evidence_count
likelihood: low|medium|high
impact: low|medium|high
estimated_added_seconds
maintenance_cost: low|medium|high
noise_risk: low|medium|high
priority: critical|high|medium|low
```

These fields remain structured judgments. Do not collapse them into a numeric score until a versioned formula contract exists.

## Execution Contract

Each proposed gate also defines:

- workflow events;
- minimum required permissions;
- runner when known;
- timeout when known;
- command or tool;
- files expected to change.

Do not guess unknown execution values. Use `null` where the schema permits it or defer the gate when correctness depends on missing information.

## Reject Conditions

Reject a gate when:

- no repository evidence supports it;
- it duplicates an existing validator without improving enforcement;
- it adds slow feedback without proportional signal;
- it is likely noisy or flaky;
- it is enterprise security theater for a personal repository;
- it only documents a rule but does not enforce anything.

## Required Sections

A gate map must include:

- target repository;
- evidence summary;
- proposed gates;
- rejected gates;
- deferred gates;
- required-check recommendations;
- owner permission requirement;
- limitations.
