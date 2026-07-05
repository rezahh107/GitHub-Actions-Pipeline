# 08 — Scope Claim Audit

Scope Claim Audit is an advisory module for comparing review claims with deterministic changed-file evidence.

It separates:

- Layer A: deterministic diff facts;
- Layer B: interpretive claim classification.

Default packages use:

- `enforcement_mode: advisory`;
- `wired_enforcement_gate: null`;
- `blocking: false`.

Future enforced packages must identify a real wired gate before `blocking` may be true.

Reviewed head identity must use a full 40-character lowercase hexadecimal SHA.

Sensitive surfaces include protocol, schema, validator, workflow, release lock, package metadata, tests or fixtures, generated output, docs, scripts, and other.

Allowed results are `congruent`, `scope_expanded_but_declared`, `scope_underreported`, `mismatch`, and `not_assessable`.

Large changes are not automatically bad. Scope expansion is not automatically bad. The issue is misleading or incomplete scope framing relative to deterministic evidence.
