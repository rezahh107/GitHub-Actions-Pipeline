# PR #8 Protocol v1.9.0 — Aggregate Schedule Interval Handoff

```yaml
action_kind: repair_and_verify
branch: feat/deep-repository-upgrade-v1
reviewed_head: dde10e8f4eb236a19fa2824bd7a23fbe413e7477
validated_implementation_head: 7c8a1d8505f602009b65483ac43dea410ab0d8a4
external_advisory: SRF-001
PRF-009: materially_repaired_no_regression_observed
PRF-010: materially_repaired_no_regression_observed
PRF-011: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
merge_performed: false
approval_performed: false
comment_performed: false
deployment_performed: false
repository_settings_changed: false
```

This handoff records bounded implementer evidence only. It does not close `PRF-011`, approve the pull request, establish repository-governance compliance, or authorize merge.

## Repaired invariant

All structurally represented `schedule` entries are parsed and canonicalized before command evidence. The validator now computes the minimum spacing over the union of complete occurrence semantics rather than validating entries only in isolation.

The aggregate comparison covers:

- same-day occurrences contributed by different entries;
- cross-midnight occurrences contributed by different entries;
- distinct cron date predicates;
- adjacency between the final and first day of the complete 400-year Gregorian cycle;
- deterministic semantic duplicate handling;
- workflow and repository semantic-work limits.

The confirmed example now fails closed:

```yaml
on:
  pull_request:
  schedule:
    - cron: "0 * * * *"
      timezone: UTC
    - cron: "1 * * * *"
      timezone: UTC
```

It emits `WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT` before downstream evidence and yields the existing invalid-workflow shape, including empty triggers, jobs, commands, and command evidence.

## Deterministic design

### Complete-cycle occurrence masks

`tools/ci_calendar_bitsets.py` now exposes:

- cached `matching_dates(predicate_key)` masks over all `146097` Gregorian-cycle days;
- `adjacent_date_masks(left, right)` with explicit cycle-boundary wrap;
- the existing cached parser and consecutive-date behavior.

### Aggregate union

`tools/ci_schedule_resource_patch.py` contract `1.1.0` now:

1. charges and parses each represented schedule entry;
2. applies the existing per-entry minimum interval validator;
3. validates explicit timezone identifiers against pinned `tzdata==2026.3` / IANA `2026c`;
4. canonicalizes an omitted timezone as `UTC` for aggregate comparison;
5. deduplicates exact semantic duplicates by `(timezone, times, predicate)`;
6. projects each canonical schedule into minute-of-day occurrence masks;
7. searches exact gaps of one through four minutes over the union;
8. checks both same-day and cross-day adjacency, including the Gregorian-cycle boundary;
9. charges projection and comparison work to both existing ledgers independently of cache warmth.

### Multiple-timezone policy

This implementation selects the permitted fail-closed option. A workflow with more than one canonical timezone identifier is rejected until deterministic transition-data normalization to a common timeline is represented.

Stable diagnostic:

```text
WORKFLOW_SCHEDULE_TIMEZONE_SET_UNSUPPORTED
```

The policy does not weaken individual pinned-timezone validation. `Etc/UTC`, `UTC`, `America/New_York`, and `Asia/Baku` remain valid individual controls.

### Duplicate behavior

Exact semantic duplicate entries are accepted as one aggregate occurrence set. Duplicates do not create an artificial zero-minute interval. Entry-reading work is still charged for every represented entry, while canonical projection work is deduplicated deterministically.

## Changed paths

Relative to reviewed head `dde10e8f4eb236a19fa2824bd7a23fbe413e7477`:

- `tools/ci_calendar_bitsets.py`
- `tools/ci_schedule_resource_patch.py`
- `tests/test_repository_upgrade_schedule_aggregate_semantics.py`
- `tests/test_repository_upgrade_schedule_budget_lifecycle.py`
- `tests/test_repository_upgrade_schedule_identity_and_budget.py`
- `tests/test_repository_upgrade_workflow_schedule_semantics.py`
- `docs/PR8_PROTOCOL_V1_9_AGGREGATE_SCHEDULE_HANDOFF.md`

## Commits

```text
067bfb0ba9c7fae66cf622f147b6da7f5aee66a4
fix: expose aggregate Gregorian date-mask semantics

54b769fa12c8fdb458a50a7075f604b6f500738f
fix: validate aggregate schedule cadence

d135bc6ab3d84f4f6ebf9e155c0f1b0d94f5c850
test: preserve timezone controls under aggregate policy

1f6a8e521034e02511408e81576cb41b3b9a8fb0
test: align valid schedules with single-timezone aggregate policy

a7ee8a0f036cff1701458458c33a41b5ab3bda2d
test: cover aggregate schedule interval semantics

f8893fcc1405d52b159f468ddd69d741a4a9108a
test: isolate repository budget lifecycle from aggregate cadence

7c8a1d8505f602009b65483ac43dea410ab0d8a4
test: isolate repository budget from aggregate cadence
```

## Mandatory behavioral coverage

The aggregate fixture covers:

- `0 * * * *` plus `1 * * * *` in `UTC`;
- `23:59` plus `00:00` on consecutive active dates;
- explicit adjacency at the complete Gregorian-cycle boundary;
- duplicate entries;
- multiple different timezones;
- deterministic charging with warm and cold caches;
- aggregate workflow-budget exhaustion;
- aggregate repository-budget exhaustion across workflow files;
- valid multi-entry schedules whose union remains at least five minutes apart.

Invalid integration fixtures assert:

```text
parse_status == invalid_shape
triggers == []
jobs == []
commands == []
command_evidence == []
tests_run_on_pull_requests != operational
```

## Rejected intermediate validation

Run `29165262943`, run number `120`, job `86577172328`, on exact head `a7ee8a0f036cff1701458458c33a41b5ab3bda2d` compiled successfully but failed two legacy budget fixtures.

The failures were not accepted as evidence. Legacy report generation, Minimal and Deep report generation, schema validation, structured identity, and repository-analysis artifact upload were skipped.

The aggregate validator correctly exposed that those fixtures independently encoded a one-minute cross-midnight union by combining consecutive calendar days with `23:59` and `00:00`. The fixtures were repaired to use nonconsecutive active days so they test boundedness rather than violating the newly enforced cadence invariant.

## Exact-head implementation validation

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29165319816
Run number: 122
Job ID: 86577324204
Conclusion: success
Source head SHA: 7c8a1d8505f602009b65483ac43dea410ab0d8a4
Tested SHA: 7c8a1d8505f602009b65483ac43dea410ab0d8a4
Event SHA: 78f920653a0d22ec1b880364e4f9101b248c9180
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 178 tests in 7.009s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

The checkout used exact ref `7c8a1d8505f602009b65483ac43dea410ab0d8a4` with `persist-credentials: false`.

## Artifact evidence

GitHub artifact ZIP digests, independently matched against downloaded bytes:

- `repository-analysis-reports`: `sha256:12f77ea0967ed507bf69879d2893c68c84fec9cf486dfce082b123c95acfb7af`
- `unit-test-diagnostics`: `sha256:52175eb6b47213fe28962229471647f0f5d40250651011f3d980bd3c6628e1b1`
- `scope-claim-audit-summary`: `sha256:7b96552da38c2db6365d2a2560ee02923ce1b75f328b771d675197989da69753`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `c26ac571be3943d436c362472ff9fbed88d2214cb3e3814bf508a4b5cc3ebf4a`
- `repository_upgrade.minimal.json`: `c7e472d88c89bc734eefa59baf2a79dc017e63b69341fb5e3a2431480d5e2661`
- `repository_upgrade.deep.json`: `5f370cc2ffc00297156caec7d3711a83c208f56bccd453baef2329fad2440d8f`
- `repository_upgrade.implementation-package.json`: `f84acc634972b733a2a03a06e3e34d01a0079c3ae2f216b84b654dbb88f43421`
- `run-identity.json`: `7293902f524708cc44a18381cbcc1d57e7f7e3b8236e36b3546490274d6ca6db`
- `unit-tests.log`: `b363e91354e3950d3b1e1242b7d048fe5c21c8d89dfc5ea97f7aac986843e214`
- `scope_claim_audit.summary.md`: `ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3`

Structured identity:

```json
{"event_sha":"78f920653a0d22ec1b880364e4f9101b248c9180","exact_source_head_verified":true,"identity_contract_version":"1.0.0","source_head_sha":"7c8a1d8505f602009b65483ac43dea410ab0d8a4","tested_sha":"7c8a1d8505f602009b65483ac43dea410ab0d8a4","workflow_sha":null}
```

Canonical evidence hashes were independently recomputed and matched report fields:

- legacy CI detective: `8099f590d2f5d63c919dc29ad4a618a0f2507064893cdcccfdfd6d318d97223b`
- Minimal: `563066a6048983451b6e635c4a369ee392e03c938cd8ac40a28a1dab7021b1d8`
- Deep: `0a62db914ea0e097485303907eb1b0c84d3cf19d0c91ce7f1570a1b7fd682d65`

Analysis-basis hashes were independently recomputed and matched:

- Minimal: `c3c6dba2214ec3957ec4cbd71a9810413298d089e3946841e77cd76533b45ea2`
- Deep: `f784753271cc52b1c1ca50fb4cb5dbc777f829528b23927477fb1c0d9d95c679`

## Generated-report checks

```yaml
selected_profiles:
  - contract-schema-repository
workflow_parse_status: parsed
parsed_triggers:
  - pull_request
  - push
  - workflow_dispatch
parsed_jobs: 1
parsed_commands: 13
command_evidence_records: 38
tests_run_on_pull_requests: operational
schedule_diagnostics_for_repository_workflow: 0
minimal_phase_1_items: 0
deep_phase_1_items: 0
implementation_package_actions: 0
mutation_default: dry_run
```

The implementation package retains its non-execution security boundary: no repository command is executed; applying requires canonical exact `HEAD`, a clean worktree, explicit recipe allowlist, path containment, non-overwriting writes, and an external recovery journal.

## PRF-009 and PRF-010 regression status

No regression was observed in:

- pinned timezone package/version/hash/count/grammar verification;
- host-special timezone exclusions;
- valid individual timezone controls;
- complete-cycle bitset semantics;
- per-workflow and per-repository deterministic budgets;
- fresh repository-budget lifecycle;
- whole-workflow invalidation before command evidence.

## Preserved boundaries

The patch does not add target-repository command execution, a GitHub service-parser clone, expression evaluation, shell emulation, reusable-workflow body resolution, permission broadening, secret access, deployment, package publication, automatic registry mutation, repository-setting changes, approval, merge, close, comment, or write to `main`.

## Remaining independent gates

- A fresh PR Inspector `v1.9.0` rereview is required on the final resulting exact head.
- The current runtime has no PR Inspector adapter/tool. Because PR comments are prohibited, no GitHub comment was used as a substitute. This action is `REQUIRES_EXTERNAL_TOOL`.
- Independent human security/domain-specialist approval remains incomplete.
- Repository governance, including branch protection/ruleset and required-check enforcement, remains unverified.
- Cross-platform execution outside the Ubuntu GitHub-hosted runner was not performed.

```yaml
PRF-011: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
```
