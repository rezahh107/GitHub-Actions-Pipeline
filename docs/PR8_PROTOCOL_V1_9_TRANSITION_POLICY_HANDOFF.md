# PR #8 Protocol v1.9.0 — Transition-Safe Aggregate Schedule Handoff

```yaml
action_kind: repair_and_verify
branch: feat/deep-repository-upgrade-v1
reviewed_head: 67f5b29d608c0df076d16f2d5074efb3964dbc22
validated_implementation_head: ee93064b34548427ae72fee850daa7610c699209
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

## Confirmed defect repaired

The prior aggregate validator compared local minute-of-day masks for a shared timezone identifier without applying that timezone's offset transitions. A multi-entry `America/New_York` set could therefore appear widely spaced in local wall time while GitHub's spring-forward advancement placed actual occurrences fewer than five minutes apart.

The implementation selects the deterministic fail-closed **fixed-offset-only aggregate policy**:

- single schedule entries remain valid in any individually accepted pinned IANA timezone;
- multi-entry sets are accepted only when their shared timezone has an exact pinned TZif SHA-256 and its verified TZif payload proves one non-DST type, zero transitions, zero leap records, and a fixed POSIX tail;
- timezone names alone are never treated as fixed-offset proof;
- transition-observing or unregistered multi-entry timezone sets fail closed before command evidence;
- unavailable, malformed, or identity-mismatched transition bytes fail closed separately.

The confirmed spring-forward fixture now fails closed:

```yaml
on:
  pull_request:
  schedule:
    - cron: "30 2 * * *"
      timezone: America/New_York
    - cron: "4 3 * * *"
      timezone: America/New_York
```

Stable diagnostics:

```text
WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED
WORKFLOW_SCHEDULE_TIMEZONE_TRANSITION_UNVERIFIABLE
```

Existing diagnostics remain unchanged, including:

```text
WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT
WORKFLOW_SCHEDULE_TIMEZONE_SET_UNSUPPORTED
WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED
```

## Deterministic fixed-offset proof

`tools/ci_pinned_timezone.py` now pins exact TZif bytes for the bounded aggregate proof registry:

```text
UTC
Etc/UTC
Etc/GMT
Etc/GMT+5
```

Each candidate must pass all existing `tzdata==2026.3` / IANA `2026c` package identity and identifier checks, exact TZif SHA-256 verification, path containment and regular-file checks, and an independent TZif structural proof.

The TZif proof rejects:

- any transition timestamp;
- multiple local-time types;
- a DST type;
- leap records;
- malformed or truncated TZif blocks;
- a missing 64-bit TZif contract;
- a POSIX tail that can represent future offset transitions.

`America/New_York` and other transition-observing or unregistered zones remain valid for single-entry schedules but are rejected for multi-entry aggregation. Fall-back repeated-hour behavior is explicitly unsupported for multi-entry sets rather than silently normalized.

## Work-budget behavior

`tools/ci_schedule_resource_patch.py` contract is now `1.2.0`.

A multi-entry fixed-offset proof charges `64` logical units to both the workflow and repository ledgers using a deterministic timezone key. The charge occurs independently of cache warmth. Existing predicate projection, duplicate handling, complete-cycle date masks, same-day comparison, cross-midnight comparison, and repository lifecycle semantics remain charged under their prior rules.

Budget exhaustion still emits `WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED` and returns the existing invalid-workflow shape before downstream evidence.

## Mandatory behavioral coverage

`tests/test_repository_upgrade_schedule_aggregate_semantics.py` covers:

- the original UTC `00` / `01` aggregate violation;
- original cross-midnight union handling;
- complete 400-year cycle wrap;
- semantic duplicate behavior;
- distinct-timezone rejection;
- `America/New_York` spring-forward `02:30` plus `03:04` rejection;
- explicit fall-back repeated-hour rejection;
- valid single-entry `America/New_York` preservation;
- valid fixed-offset `Etc/GMT+5` multi-entry control;
- transition-data identity mismatch;
- transition-data unavailability;
- workflow transition-proof budget exhaustion;
- repository transition-proof/projection budget exhaustion;
- cache-warmth-independent logical charging;
- valid UTC multi-entry unions at five minutes or slower.

Invalid integration fixtures assert:

```text
parse_status == invalid_shape
triggers == []
jobs == []
commands == []
command_evidence == []
tests_run_on_pull_requests != operational
```

## Changed paths

Relative to reviewed head `67f5b29d608c0df076d16f2d5074efb3964dbc22`:

- `tools/ci_pinned_timezone.py`
- `tools/ci_schedule_resource_patch.py`
- `tests/test_repository_upgrade_schedule_aggregate_semantics.py`
- `docs/PR8_PROTOCOL_V1_9_TRANSITION_POLICY_HANDOFF.md`

## Commits

```text
c8e49d7eb50186bdfb28419a98371a3f7f651cfd
fix: pin fixed-offset timezone transition proofs

8a9382af6aa56fc9056fc78e3582e0599cc48f45
fix: gate aggregate cadence on fixed-offset proof

83a550010fd7aa58fb3f15deb483db6beef5e29c
test: cover transition-aware aggregate fail-closed policy

ee93064b34548427ae72fee850daa7610c699209
test: calibrate transition repository budget fixture
```

## Rejected intermediate validation

Run `29167734008`, run number `126`, job `86583703905`, on exact head `83a550010fd7aa58fb3f15deb483db6beef5e29c` compiled successfully but failed one repository-budget fixture.

The failure was not accepted as evidence. The fixture's first workflow projected 48 minute slots and legitimately exceeded the provisional `170`-unit repository limit. The limit was corrected to `200`, which allows the first workflow and rejects the second during the distinct fixed-offset proof/projection path. Report generation and downstream artifact evidence from the failed run were not accepted.

## Exact-head implementation validation

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29167785471
Run number: 127
Job ID: 86583835103
Conclusion: success
Source head SHA: ee93064b34548427ae72fee850daa7610c699209
Tested SHA: ee93064b34548427ae72fee850daa7610c699209
Event SHA: 7ebf124c2b0b2960fdce13960535d50a75d04d0c
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 184 tests in 8.455s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

Checkout used exact ref `ee93064b34548427ae72fee850daa7610c699209` with `persist-credentials: false`.

## Artifact evidence

GitHub artifact ZIP digests, independently matched against downloaded bytes:

- `repository-analysis-reports`: `sha256:2b397e424b3135484e3bfa0dfec9eda3c95bc1ee5de78652a4f7606a8300a20d`
- `unit-test-diagnostics`: `sha256:580e3d336a25cc94536032b7a227b7b6fa6041f24532c2679d30522524c46c19`
- `scope-claim-audit-summary`: `sha256:b90b930739cf818b17231d9badb56d816eeaa0f0a6bd9afe02655f2be619bfe6`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `14ae4a5ad3e686b4c2c881656b23564e2050a2ea643367d7627b50a2434d4e78`
- `repository_upgrade.minimal.json`: `00b3aa51d0e01ae7097795c7aaa52c3def3450488d95e0dacdcf8aefa081d4a3`
- `repository_upgrade.deep.json`: `724c6190c241f895ded7dde40ff1e74dc54d132fcefd49229c0aaa1499763f56`
- `repository_upgrade.implementation-package.json`: `16a8e12731999e50778ec55dc0bbbb2fd3a716b383cb20a4263b19f74fde0243`
- `run-identity.json`: `ed372a4c482a488612e428d51305306363cc0e2da4b3332d1b2b8687f7e9b4e3`
- `unit-tests.log`: `8cc11197040a963d3db13570b26a576491467fe3acc7b97d9630c60aeb1ea819`
- `scope_claim_audit.summary.md`: `ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3`

Structured identity:

```json
{"event_sha":"7ebf124c2b0b2960fdce13960535d50a75d04d0c","exact_source_head_verified":true,"identity_contract_version":"1.0.0","source_head_sha":"ee93064b34548427ae72fee850daa7610c699209","tested_sha":"ee93064b34548427ae72fee850daa7610c699209","workflow_sha":null}
```

Canonical evidence hashes were independently recomputed and matched report fields:

- legacy CI detective: `a8e425ff56d82aff7e1fb5dee1d3c2b0bf5f0ce7f6f8d869c72b0c3e77127211`
- Minimal: `831977946c7208c4e8e35ec8c2e7d3f13e22c9bf794c8b525fba90f43420fe07`
- Deep: `6f6485ec43ad3effdc487285e44f7ef715536be592ff5a5f7a41855eec903f50`

Analysis-basis hashes were independently recomputed and matched:

- Minimal: `bc289d964cfe3f97da290eece527269fe4c90c767bc764ae5ade0779be9ce4b3`
- Deep: `1fe148b4d5d14017b3a3f34459c085ae65f1dbad1c0ed1ad98bd1884ae0ed60a`

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

The implementation package retains its non-execution boundary: no repository command is executed; applying remains conditional on canonical exact `HEAD`, a clean worktree, an explicit recipe allowlist, path containment, non-overwriting writes, and an external recovery journal.

## Regression status

No regression was observed in:

- pinned `tzdata==2026.3` / IANA `2026c` identity;
- host-special timezone exclusions;
- valid individual `Etc/UTC`, `UTC`, `America/New_York`, and `Asia/Baku` controls;
- original UTC aggregate cadence rejection;
- cross-midnight and complete-cycle adjacency;
- duplicate semantics;
- distinct-timezone rejection;
- complete-cycle bitset behavior;
- per-workflow and per-repository deterministic budgets;
- repository-budget lifecycle reset;
- whole-workflow invalidation before command evidence.

## Preserved boundaries

The patch does not add target-repository command execution, a GitHub service-parser clone, expression evaluation, shell emulation, reusable-workflow body resolution, permission broadening, secret access, deployment, package publication, automatic registry mutation, repository-setting changes, approval, merge, close, comment, or write to `main`.

## Remaining independent gates

- This documentation-only resulting head requires its own complete exact-source-head CI run; that final run is reported outside this file to avoid recursively changing the validated head.
- A fresh PR Inspector `v1.9.0` rereview is required on the final resulting exact head.
- The current runtime has no PR Inspector adapter/tool. Because PR comments are prohibited, no GitHub comment was used as a substitute. Rereview request execution remains `REQUIRES_EXTERNAL_TOOL`.
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
