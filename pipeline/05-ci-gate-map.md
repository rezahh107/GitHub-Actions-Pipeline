# 05 — CI Gate Map

## Purpose

Define which CI gates are worth adding and which are intentionally rejected.

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

If the answer is unclear, reject the gate or mark it low priority.

## Risk Scoring

Score each candidate gate with:

- evidence count;
- likelihood;
- impact;
- estimated added seconds;
- maintenance cost;
- noise risk;
- priority.

Priority values: critical, high, medium, low, reject.

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
