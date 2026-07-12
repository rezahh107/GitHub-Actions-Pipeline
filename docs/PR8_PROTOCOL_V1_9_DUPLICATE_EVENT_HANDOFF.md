# PR #8 — PRF-013 Duplicate Schedule Event Handoff

## Scope

```yaml
repository: rezahh107/GitHub-Actions-Pipeline
pull_request: 8
branch: feat/deep-repository-upgrade-v1
reviewed_head: d33edf2a6deb2d104c4026271048ecddc47da5f1
protocol: PR Inspector v1.9.0
inspector_commit: 65e6b1b46c3e8da7c782c666cd3562947f2b7923
action: repair_and_verify
finding: PRF-013
status: implemented_pending_rereview
```

No merge, approval, deployment, secret access, repository-setting change, `main` write, PR comment, or unrelated-repository mutation was performed.

## Repaired invariant

Every represented YAML schedule entry remains a distinct trigger. Canonically duplicate entries fail closed because authoritative GitHub Actions evidence establishing duplicate-event deduplication is not represented.

The schedule resource contract was advanced from `1.3.0` to `1.4.0`.

## Design

Before fixed-offset proof or aggregate projection, the analyzer now:

1. Preserves the existing distinct-timezone rejection.
2. Scans every canonical schedule entry as a distinct event.
3. Charges one deterministic logical work unit per entry to both workflow and repository ledgers.
4. Rejects the second occurrence of an identical canonical tuple.
5. Continues aggregate projection only when every canonical event is distinct.

Canonical identity includes:

```text
timezone
expanded local times-of-day
canonical Gregorian date predicate
```

This rejects:

- exact textual duplicates;
- omitted timezone versus explicit `UTC` duplicates;
- syntactically different but semantically equivalent cron expressions;
- equivalent restricted date predicates.

The former `set(schedules)` projection path was removed. Non-duplicate schedules are sorted without collapsing entries.

## Diagnostic

```text
WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED
```

All duplicate rejection paths use the existing complete invalid-workflow result:

```text
parse_status == invalid_shape
triggers == []
jobs == []
commands == []
command_evidence == []
tests_run_on_pull_requests != operational
```

## Commits

```text
d077495c7b7d59e4a1040a99d6c50e106a42fed7
fix: reject duplicate canonical schedule events

2c3fd28a6b5b0c3292be2e4e3de32da632ad635e
test: cover duplicate schedule event rejection
```

## Changed paths

```text
tools/ci_schedule_resource_patch.py
tests/test_repository_upgrade_schedule_aggregate_semantics.py
docs/PR8_PROTOCOL_V1_9_DUPLICATE_EVENT_HANDOFF.md
```

Relative to reviewed head `d33edf2a6deb2d104c4026271048ecddc47da5f1`, the implementation commits modified only the tool and aggregate-schedule test module before this handoff was added.

## Behavioral coverage

Added or changed permanent tests cover:

- identical cron plus identical timezone;
- omitted timezone versus explicit `UTC`;
- `SUN` versus numeric `0` semantic equivalence;
- equivalent active date predicates using named versus numeric month/weekday forms;
- 256-entry duplicate sets;
- deterministic duplicate-scan workflow-budget exhaustion;
- deterministic duplicate-scan repository-budget exhaustion;
- full invalid-workflow clearing and non-operational PR-test capability.

Preserved controls cover:

- two distinct UTC events exactly five minutes apart;
- fixed-offset multi-entry and multi-time schedules;
- single-time `America/New_York` schedules;
- spring-forward and fall-back transition rejection;
- cross-midnight aggregate checks;
- cyclic 400-year Gregorian boundary checks;
- TZif identity mismatch and data unavailability;
- transition-proof cache-warmth-independent charging;
- workflow and repository proof budgets;
- PRF-009 through PRF-012 regression suites.

## Successful implementation-head validation

```yaml
implementation_head: 2c3fd28a6b5b0c3292be2e4e3de32da632ad635e
workflow: Validate
workflow_id: 307479558
run_id: 29186024328
run_number: 134
job_id: 86632147907
conclusion: success
compile: success
unit_tests: 191 tests — OK
generated_legacy_report: success
generated_minimal_report: success
generated_deep_report_and_package: success
generated_schema_validation: success
scope_claim_audit: success
structured_identity: success
artifact_uploads: success
```

Structured identity:

```json
{"event_sha":"4e9a4373e8235369ccf12c4fc86bfa4c63c398a0","exact_source_head_verified":true,"identity_contract_version":"1.0.0","source_head_sha":"2c3fd28a6b5b0c3292be2e4e3de32da632ad635e","tested_sha":"2c3fd28a6b5b0c3292be2e4e3de32da632ad635e","workflow_sha":null}
```

## Artifact evidence

GitHub artifact ZIP SHA-256 values, independently matched against downloaded bytes:

```text
repository-analysis-reports  73d1eab5209451dd19c7767794e072aba541f488a3c0cbf269696e4eaf17d30f
unit-test-diagnostics        91f83741a7b08cc2ff0440f4ecfa7572e5a809d2bba34a5f06ad8ba3017acad5
scope-claim-audit-summary    50710dd19efc873d51aeda5b89f81d0ce175fd098e51d58438921233ffa752eb
```

Downloaded artifact file SHA-256 values:

```text
ci_detective_report.json                       c191ee4daca2c8a98204b919820b8ff719fa1a88b68b2dbd5b1ca5dcf5470e66
repository_upgrade.minimal.json                d86a6605d5832c1eb2ca02b8bfc54bed2721ae00e762d580bc4eb68ca7cbdce4
repository_upgrade.deep.json                   edac774c815961ccb25904ba76229f337efb008717ed422221af2e12a7ef5166
repository_upgrade.implementation-package.json 9f0d8e217190b5b429b1e405353d6a2fa79cd279eb48eb04d7b6ef0461be2cdb
run-identity.json                              66f1861cf80412edb97f89597afd5a44f50cc37829131cc6272e1f1187f6479e
unit-tests.log                                 dd04f99da9e9344763252af0704aa722700733e5b663aeeca0a0f8076b8ed478
scope_claim_audit.summary.md                   ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3
```

Canonical evidence hashes were independently recomputed and matched:

```text
legacy   d49ec0afbf70436649f5c18a44eae7a97693246f32eb47bcb923fbb39208b7d3
Minimal  8e8d97046aa22f1958fac4862b7b1c1b7106e7f190711cc33b4654b56a74111f
Deep     711a9609ca10ce29c8821a6bc323bb69e5e5f350b38e90acf3c212b932163a58
```

Analysis-basis hashes were independently recomputed and matched:

```text
Minimal  f0aafab26619605bb49caf609a7f29e10a6744d7e394cdaffb04c11f1348301f
Deep     3985a99ca234de6d64a5348e9acc436733fd18e82b00060e425daeb4aa0c00c1
```

Generated repository reports retained:

```text
profile: contract-schema-repository
workflow parse status: parsed
triggers: pull_request, push, workflow_dispatch
jobs: 1
commands: 13
command_evidence: 38
tests_run_on_pull_requests: operational
Minimal Phase 1 items: 0
Deep Phase 1 items: 0
implementation actions: 0
mutation_default: dry_run
```

## Rejected or unavailable evidence

- Local clone and local execution were unavailable because the execution environment could not resolve `github.com`; validation therefore relied on exact-head GitHub Actions and independently downloaded artifacts.
- No Windows or macOS execution was performed.
- No complete GitHub service-parser equivalence, expression evaluation, shell emulation, reusable-workflow body resolution, or authoritative duplicate-event delivery behavior is claimed.
- A fresh PR Inspector `v1.9.0` rereview cannot be executed by the available connector and remains `REQUIRES_EXTERNAL_TOOL`.
- Independent qualified human specialist approval remains pending.
- Repository governance, required-check enforcement, and bypass-actor verification remain pending.

## Final disposition

```yaml
PRF-013: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
```
