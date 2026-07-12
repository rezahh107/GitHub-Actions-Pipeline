# PR #8 — PR Inspector v1.9.0 — PRF-015 Repair Handoff

## Action identity

```yaml
action_kind: repair_and_verify
repository: rezahh107/GitHub-Actions-Pipeline
pull_request: 8
branch: feat/deep-repository-upgrade-v1
reviewed_head_sha: ac95c23daae04091d6dc2beeeb87b3f27f0119e6
base_sha: ddfc70ab8ed8278e369b191f24a5934e1c281b0e
canonical_review_package_sha256: b5a4c0bf550c88c6dd05d90d370725b136f95ebe730307f36d2b22faa8314f74
implementation_evidence_head: 63dbb2edd4c597196f72c0944893aaca798c8698
PRF-015: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```

The uploaded review package bytes were inspected. The SHA-256 of `review-package.json` matched the canonical review-package digest above. The outer ZIP digest was different, as expected for a container archive, and was not substituted for the canonical package digest.

## Invariant extraction

### Surface symptom

The previous contract rejected only equal complete occurrence identities. Distinct schedule entries with intersecting occurrence sets could remain accepted, including:

```text
0,5 * * * * UTC
5,10 * * * * UTC
```

and:

```text
0 0 * * * UTC
0 0 1-30 * * UTC
```

### Underlying invariant

Every represented schedule entry remains an independent trigger. If two entries can fire at the same local minute on any shared active date, simultaneous event delivery and multiplicity are not represented. The complete workflow must fail closed before TZif proof, aggregate projection, jobs, commands, command evidence, resolved command families or operational capabilities are retained.

### Failure boundary

The failure was in the pre-projection schedule-event gate installed by `tools/ci_schedule_occurrence_identity_patch.py`. Equality of `(timezone, times, complete_date_mask)` was insufficient; intersection of occurrence sets is required.

### Assumptions

- Existing mixed-timezone rejection remains authoritative before occurrence comparison.
- A complete 400-year Gregorian date mask is the bounded semantic carrier already used by aggregate cadence logic.
- No authoritative GitHub service evidence was introduced to justify accepting simultaneous duplicate schedule events.

## Repair

Schedule occurrence contract advanced from `1.5.0` to `1.6.0`.

For each canonical schedule entry, the gate now:

1. Charges and computes its complete-cycle date mask exactly once.
2. Maintains an accumulated date mask for each expanded local minute.
3. Charges every minute-mask overlap check to both workflow and repository ledgers.
4. Rejects when `accumulated_masks[minute] & entry_date_mask` is non-zero.
5. Mutates accumulated state only after every check for the entry succeeds.

The existing diagnostic remains stable:

```text
WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED
```

The overlap gate remains before fixed-offset TZif proof and aggregate projection.

## Changed paths

```text
tools/ci_schedule_occurrence_identity_patch.py
tests/test_repository_upgrade_schedule_occurrence_identity.py
tests/test_repository_upgrade_workflow_schedule_semantics.py
tests/test_repository_upgrade_schedule_budget_lifecycle.py
tests/test_repository_upgrade_schedule_identity_and_budget.py
tests/test_repository_upgrade_schedule_aggregate_semantics.py
docs/PR8_PROTOCOL_V1_9_PRF_015_HANDOFF.md
```

## Commits before this handoff

```text
48b2511e78fcbcc67d92c7a2b9d71c9ec340b53a
fix: reject overlapping schedule occurrences

befb796f790cab5e0b7a86b93478dd9f7356e12d
test: cover partial schedule occurrence overlap

af6c90609571ea2bfbd5558ffa74fe5036e4a84b
test: remove overlapping positive schedule fixture

3b73537ab16b9696162f6b1aebbc698936faa309
test: account for occurrence overlap work in lifecycle budget

80ca7719a3e791a3482c3e9045f20b4f277634e4
test: account for occurrence overlap work in repository budget

b106cf7e7de23a0508722b656783c2de6e8b6265
test: account for overlap checks in transition budget

63dbb2edd4c597196f72c0944893aaca798c8698
test: align expanded-minute overlap charging evidence
```

## Behavioral coverage

Permanent tests now cover:

- partial-minute overlap: `0,5` versus `5,10`;
- partial-date overlap: wildcard versus `1-30`;
- exact complete duplicates;
- full-domain DOM and DOW aliases;
- same minute on disjoint date masks;
- disjoint minutes exactly five minutes apart;
- overlap rejection before transition-zone TZif proof;
- deterministic workflow and repository budget exhaustion;
- cache-warmth-independent charging;
- complete invalid-workflow clearing of triggers, jobs, commands and command evidence;
- non-operational `tests_run_on_pull_requests` after rejection.

Existing positive fixed-offset, single-time transition-zone, cross-midnight, Gregorian-cycle, TZif identity and default-budget behavior remain covered.

The artificial low-limit fixtures were raised only enough to account for the newly mandatory per-minute overlap work. Production defaults remain unchanged:

```text
WORKFLOW_LIMIT = 4096
REPOSITORY_LIMIT = 8192
TRANSITION_PROOF_WORK_UNITS = 64
```

## Rejected intermediate run

```yaml
head_sha: befb796f790cab5e0b7a86b93478dd9f7356e12d
workflow_run_id: 29190195519
job_id: 86643388519
compile: success
unit_tests: failure
report_generation: skipped
structured_identity: skipped
accepted_as_successful_evidence: false
```

The run had five test failures. One expected charge incorrectly counted cron expressions rather than their expanded minute sets. Four older fixtures either contained overlap now forbidden by the repaired invariant or used artificial budget thresholds that did not include the newly mandatory overlap-check work.

## Successful implementation-head validation

```yaml
workflow: Validate
workflow_id: 307479558
workflow_run_id: 29190354241
run_number: 148
job_id: 86643820753
source_head_sha: 63dbb2edd4c597196f72c0944893aaca798c8698
tested_sha: 63dbb2edd4c597196f72c0944893aaca798c8698
event_sha: 51c5b5a2fc3304bc6e9e16e86ed209b86dd474ad
exact_source_head_verified: true
compile: success
unit_tests: 201 tests — OK
legacy_report: success
minimal_report: success
deep_report_and_package: success
generated_report_validation: success
scope_claim_audit: success
structured_run_identity: success
artifact_uploads: success
```

## Implementation-head artifact evidence

GitHub artifact ZIP digests, independently matched against downloaded bytes:

```text
repository-analysis-reports
c68419b0f51e246ecea0b80833d9787fe5e1aab9894a74c676c207933a5f4f13

unit-test-diagnostics
21ebbd316d737eaaf222f0a1c995366b126d74c962ff580a8038fbd67d7c506f

scope-claim-audit-summary
6d7b2a0953f25aad6eb555a33322aedbaee3c35a2f6dd43eab1cf3b8f653a371
```

Downloaded artifact file SHA-256 values:

```text
ci_detective_report.json
ac762394d4d027bd3d54936049122372b62a29a4edc9331cd3cd903273f5bc69

repository_upgrade.minimal.json
ffe137b2d2d5647a98667384093d0dced00e115b92ac2db5cfec0cbc6f413068

repository_upgrade.deep.json
b39f5455748e5fa0fb74a42cd2d76efbe28373ce9204f3ccebb7460ff53a50bc

repository_upgrade.implementation-package.json
a47d5adc3ff54fe3f17efcf76d990b145c6d6c5205e5379a871f31dd68ffeb22

run-identity.json
6bb00ce425027d585e8bf9b6c1006772310ddbebef681e3bcaa464ba585d0086

unit-tests.log
f9755cd2b96da5628fea3a09984d1b0d14f326457aae36c3e7c84c87a4a06538

scope_claim_audit.summary.md
ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3
```

Canonical evidence hashes were recomputed using the repository contract excluding `generated_at`, `evidence_sha256` and `run_context`, and matched:

```text
legacy
5844164466baa07087b6b785d870d2f7cbff28cc3df6e02b5619e2ba488c0024

Minimal
c3db37c91bc3318c05c6f4cb7a4e6f0f556329157e07bfa49e37fc1cf4ad9671

Deep
7ad862a5e07738d67a111092225b6fce5d9c270a76ce7341bacf13e757101825
```

Analysis-basis hashes recorded by the generated reports:

```text
Minimal
b737a12730184a27a5dcb5785e47e1df1bcc03dfa053d2cfba37977e566d3046

Deep
2ac530e9d9c860e969c80b3a97cee7e9561753a87f7063472c80cf9b86758fd3
```

## Adjacent-impact audit

Confirmed unchanged:

- accepted cron grammar;
- pinned timezone identifier and TZif-byte provenance;
- mixed-timezone rejection;
- fixed-offset proof and transition-zone fail-closed behavior;
- five-minute positive-gap validation;
- same-day, cross-midnight and 400-year cycle boundaries;
- workflow and repository default limits;
- invalid-workflow result envelope;
- report schemas and CLI surfaces;
- target command non-execution and dry-run defaults.

No schema, dependency, configuration, CLI, release-lock or unrelated repository changes were required.

## Limitations and unexecuted checks

- A direct local clone and target-suite run were attempted but unavailable because the execution environment could not resolve `github.com`; exact-head GitHub Actions is the execution evidence.
- Cross-platform execution outside Ubuntu 24.04 was not performed.
- Fresh PR Inspector v1.9.0 rereview is not available through the current connector and remains required on the final exact head.
- Eligible non-bot security/domain-specialist approval remains pending.
- Repository ruleset, branch-protection, required-check app identity, required-review enforcement and bypass restrictions remain unverified.
- No complete GitHub service parser, shell emulator, expression evaluator, reusable-workflow body resolver, OS sandbox or production execution is claimed.

## Final disposition

```yaml
action_kind: repair_and_verify
PRF-015: implemented_pending_rereview
technical_acceptance: pending
fresh_pr_inspector_review: required
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
merge_performed: false
approval_performed: false
deployment_performed: false
```
