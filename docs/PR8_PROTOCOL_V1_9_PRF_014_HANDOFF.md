# PR #8 Protocol v1.9.0 — PRF-014 Repair Handoff

## Action identity

```yaml
action_kind: repair_and_verify
repository: rezahh107/GitHub-Actions-Pipeline
pull_request: 8
branch: feat/deep-repository-upgrade-v1
reviewed_head_sha: b27a4365fe1422c0bfcd743b2b56f6abe4213a3d
base_sha: ddfc70ab8ed8278e369b191f24a5934e1c281b0e
inspector_commit: 65e6b1b46c3e8da7c782c666cd3562947f2b7923
canonical_review_package_sha256: e0b10f40e253989498c8ddb347f20a94eb6ee12a1ea60c6ccb59d435e44a1d6d
PRF-014: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```

The uploaded review package bytes were inspected before implementation. `review-package.json` matched the declared canonical SHA-256.

## Invariant extraction

```yaml
surface_symptom: predicate_key retained syntactic unrestricted flags, so wildcard and explicit full-domain DOM/DOW aliases produced unequal _CanonicalSchedule objects.
underlying_invariant: duplicate identity must be derived from complete represented occurrence semantics, not syntax-level predicate flags.
failure_boundary: duplicate rejection must complete before fixed-offset TZif proof, aggregate projection, permissions, jobs, commands, command evidence, resolved command families, or operational capabilities are retained.
affected_components:
  - tools package initialization
  - schedule duplicate-event identity
  - complete 400-year Gregorian date masks
  - workflow and repository semantic-work ledgers
  - schedule integration fixtures
assumptions:
  - the existing 146097-day matching_dates mask is the authoritative bounded representation of accepted POSIX DOM/DOW semantics
  - timezone identity and expanded minute tuples remain independently canonicalized by existing contracts
```

## Repair

A final patch layer installs schedule-resource contract `1.5.0` after the existing `1.4.0` resource gate.

Duplicate identity is now:

```text
(timezone, expanded local-minute tuple, complete 400-year matching-date mask)
```

For every represented entry, identity construction and membership comparison each charge one logical work unit to both workflow and repository ledgers, independently of cache warmth. Duplicate rejection occurs before fixed-offset transition proof and aggregate projection.

The stable diagnostic remains:

```text
WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED
```

## Changed paths

```text
tools/ci_schedule_occurrence_identity_patch.py
tools/__init__.py
tests/test_repository_upgrade_schedule_occurrence_identity.py
docs/PR8_PROTOCOL_V1_9_PRF_014_HANDOFF.md
```

## Commits before this handoff

```text
aedbf793da86191708695881fad05f6f8107f126
fix: compare complete schedule occurrence identities

e02ae57f8a60f0a8a73723d0108f906b88b79c11
fix: install complete schedule occurrence identity

5dcfe4308a5288fea3451aa37541149a2886b019
test: cover complete schedule occurrence identity

d4e2466216ad4a56dc1ce76bb7c017c001171769
fix: preserve schedule budget thresholds

db261855244d0c360e2bf0e395da83a2224d5574
test: align occurrence identity fixtures and budgets
```

The implementation slice is five commits ahead and zero behind reviewed head `b27a4365...`.

## Behavioral coverage

Added direct coverage for:

- `0 0 * * *` versus `0 0 1-31 * *`;
- `0 0 * * *` versus `0 0 * * 0-6`;
- duplicate rejection before TZif proof in `America/New_York`;
- semantically distinct `1-30` control remaining operational;
- whole-workflow clearing after rejection;
- cache-warmth-independent identity charging;
- deterministic workflow and repository identity-budget exhaustion.

Existing PRF-009 through PRF-013 controls remain in the complete suite.

## Rejected intermediate validation

```yaml
source_head_sha: 5dcfe4308a5288fea3451aa37541149a2886b019
workflow_run_id: 29188623442
job_id: 86639251551
compile: success
unit_tests: failure
unit_test_count: 197
failures: 3
reports_generated: false
structured_identity_written: false
accepted_as_evidence: false
```

Observed causes:

1. occurrence-identity charge `16` exceeded two established repository-budget control thresholds;
2. one new transition-order fixture used an invalid four-field cron.

The charge was reduced to the smallest explicit logical unit without removing either required charge, and the cron fixture was corrected.

## Successful implementation-head validation

```yaml
source_head_sha: db261855244d0c360e2bf0e395da83a2224d5574
tested_sha: db261855244d0c360e2bf0e395da83a2224d5574
event_sha: 97d0453ce1b24fad96b4d1ca6bd5d25e82dca8a4
workflow_id: 307479558
workflow_run_id: 29188700764
run_number: 140
job_id: 86639450326
exact_source_head_verified: true
compile: success
unit_tests: "197 tests — OK"
legacy_report: success
minimal_report: success
deep_report_and_package: success
generated_schema_validation: success
scope_claim_audit: success
structured_run_identity: success
artifact_uploads: success
```

## Artifact evidence for implementation head

GitHub artifact ZIP digests and downloaded bytes matched:

```text
repository-analysis-reports  a160b1b0b3bb5e16f356ba1161ee7d8633cb3073962bc4c1e3ba72512ac416af
unit-test-diagnostics        a81577dea0ba35ddb6c7d3d7776c16a52c96737b9d039e823230525549e6f105
scope-claim-audit-summary    58ea6b215f28760a1dfff3cabf921a79deaf2aa432751369591e14417404edc2
```

Downloaded artifact member SHA-256:

```text
ci_detective_report.json                         43d9b2356c79fbf0f4d651c88857ce1abeb69c17a800db4c8272e07649a85e62
repository_upgrade.deep.json                    a8b747e2cf7746de32c28ab72ff82d650451698549ff6a6172b12149c9fd086e
repository_upgrade.minimal.json                 1577b5636424b6086d0d1cbe4e6420d3c5864e2ad8909e0b5b40fb6452a5b79d
repository_upgrade.implementation-package.json  6f4aaa435293758273a8a5b16dab9b2c073044a8a3042760a214c064ee24294d
run-identity.json                               7d5d251bfb02a46e8c5a43344a2194fdfc709cb3609210388209acbc3a0fa673
unit-tests.log                                  46e5682bc1fc1575177532b498d965c7c6d90f7a8a0725939c79a954670d4c7b
scope_claim_audit.summary.md                    ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3
```

Canonical evidence hashes independently recomputed and matched report fields:

```text
legacy   f8afc0b1a0c0d9efbfc6709b1c1fb7351357361983b653f836f61636e509e9f0
Minimal  0210d5c000bb88e7783f9ca2e25f180ad3e809416d972e486288086983c402a4
Deep     9f60be7a82decb6c9e6b5b679254c50109a50e0d3bf698c943ee4ae11b231c71
```

Analysis-basis hashes independently recomputed and matched:

```text
Minimal  ee52e16fa218b5c9182cf2e0c02fc3f61e6b26a8355bf61e71b927e845857ff5
Deep     5fb836c1733d746b0b9c9f384d385ef1184e9781d8a3efc58871e290044d1697
```

## Adjacent-impact audit

- Callers: `tools/__init__.py` installs the occurrence-identity gate after resource hardening; all submodule imports execute package initialization first.
- Dependencies: no dependency was added.
- Schemas and validators: no schema shape changed; existing invalid-workflow and diagnostic envelopes are reused.
- Fixtures: one focused permanent test module was added; historical schedule fixtures remain unchanged.
- Configuration and CLI: unchanged.
- Release locks and versions: repository/package versions are unchanged; the internal schedule-resource contract reports `1.5.0` at runtime.
- CI: permanent `Validate` workflow remains unchanged.
- Compatibility: accepted cron grammar, timezone registry, fixed-offset proof, five-minute cadence, cycle-boundary behavior, and default limits are unchanged.
- Rollback: remove the final initializer block and the occurrence-identity patch/test module.

## Adversarial self-audit

No recipient drift, approval bypass, main write, merge, deployment, secret access, repository-setting change, external command execution, or unrelated repair was performed. The rejected run is not represented as successful evidence. The implementation-head artifact bytes and identity were checked independently.

This self-audit is implementer evidence only and does not replace PR Inspector.

## Limitations and unexecuted validation

- Fresh PR Inspector v1.9.0 rereview is `REQUIRES_EXTERNAL_TOOL` and was not executed by this implementer environment.
- Eligible non-bot security/domain-specialist approval remains pending.
- Repository ruleset, branch-protection, required-review and bypass enforcement remain unverified.
- Cross-platform execution outside Ubuntu 24.04 GitHub-hosted Actions was not run.
- Direct local execution of the target suite was unavailable; permanent exact-head CI is the execution evidence.
- No claim of complete GitHub parser equivalence, shell emulation, reusable-workflow resolution, OS sandboxing, or production containment is made.

## Required next gate

Run PR Inspector `v1.9.0` on the final exact PR head after this handoff commit, specifically verifying complete occurrence identity, wildcard/full-domain DOM and DOW aliases, distinct `1-30` control, charging, ordering, and PRF-009 through PRF-013 regressions.

```yaml
PRF-014: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
```
