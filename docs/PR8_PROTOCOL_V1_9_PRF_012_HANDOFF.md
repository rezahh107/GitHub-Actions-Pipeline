# PR #8 — PRF-012 Repair Handoff

## Status

```yaml
repository: rezahh107/GitHub-Actions-Pipeline
pull_request: 8
branch: feat/deep-repository-upgrade-v1
reviewed_head: 76e6aeb4c781d29de10ec685eeefbbeefedbfc69
validated_implementation_head: 07123eb6934ebe17fe37a2c07f609d1f095e7b3c
PRF-009: materially_repaired_no_regression_observed
PRF-010: materially_repaired_no_regression_observed
PRF-011: materially_repaired_no_regression_observed
PRF-012: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
```

## Design decision

The fixed-offset-only policy is preserved. Transition proof is now required from expanded schedule semantics rather than YAML entry count:

```python
local_times = {minute for item in schedules for minute in item.times}
if len(local_times) > 1:
    _require_fixed_offset_aggregate_timezone(...)
```

A schedule set with one distinct local minute remains accepted in any pinned IANA timezone. Any set representing multiple distinct local minutes—including one cron entry that expands to several times—must prove that the exact pinned TZif bytes are fixed-offset before local minute masks are used as an absolute-timeline surrogate.

Distinct timezone identifiers are still rejected before comparison. Proof charging remains deterministic and ledger-backed independently of cache warmth.

## Repaired adversarial case

```yaml
schedule:
  - cron: "4,30 2,3 * * *"
    timezone: America/New_York
```

The workflow now fails closed with:

```text
WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED
parse_status == invalid_shape
triggers == []
jobs == []
commands == []
command_evidence == []
tests_run_on_pull_requests != operational
```

## Commits

```text
0461241cf4412d21259a0ed0ac935de6cae26be0
fix: require transition proof for expanded multi-time schedules

73705929a9dcabc5ef5e9c6f906c8712de135e8c
test: cover single-entry expanded transition policy

07123eb6934ebe17fe37a2c07f609d1f095e7b3c
test: align transition-zone controls with single-time policy
```

## Files changed

- `tools/ci_schedule_resource_patch.py`
- `tests/test_repository_upgrade_schedule_aggregate_semantics.py`
- `tests/test_repository_upgrade_schedule_identity_and_budget.py`
- `docs/PR8_PROTOCOL_V1_9_PRF_012_HANDOFF.md`

## Coverage advanced

- single-entry cron expansion into multiple local times in a transition-observing timezone;
- complete invalid-workflow evidence boundary for that case;
- positive single-time `America/New_York` control;
- positive multi-time fixed-offset controls;
- pinned transition identity mismatch and unavailable-data failure on a single expanded entry;
- workflow proof-budget exhaustion on a single expanded entry;
- repository proof-budget accumulation across single expanded entries;
- cache-warmth-independent logical charging on a single expanded entry;
- preserved UTC aggregate, cross-midnight, cycle-boundary, duplicate, mixed-timezone, spring-forward, fall-back, PRF-009, PRF-010 and PRF-011 coverage.

## Rejected intermediate validation

Run `29184648149`, job `86628432223`, exact head `73705929a9dcabc5ef5e9c6f906c8712de135e8c`:

- exact checkout: success;
- compile: success;
- unit suite: `185` tests, one failure;
- generated reports and identity: skipped;
- accepted as evidence: no.

The failure was a stale positive fixture that treated a multi-time `America/New_York` cron as valid. It was corrected by retaining the worst-case cron on a fixed-offset control and using a single-time New York control.

## Successful implementation-head validation

Run `29184690211`, run number `131`, job `86628545864`, workflow `Validate`, workflow ID `307479558`:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
Compile Python modules                             success
Run unit tests                                     185 tests in 7.314s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

Structured identity:

```json
{"event_sha":"0b36010c9accb65c24dcc7cf0f6b91e3d1cdea4c","exact_source_head_verified":true,"identity_contract_version":"1.0.0","source_head_sha":"07123eb6934ebe17fe37a2c07f609d1f095e7b3c","tested_sha":"07123eb6934ebe17fe37a2c07f609d1f095e7b3c","workflow_sha":null}
```

## Artifact evidence

GitHub ZIP digests, independently matched against downloaded bytes:

- `repository-analysis-reports`: `aedb5f2cc10189b76c838328d717662ce36226b07592055e05225441e82d07f7`
- `unit-test-diagnostics`: `0a9f9582e5ecfe8ba58e3080461d087b68e3723df725eb29c08c6d5256d6d209`
- `scope-claim-audit-summary`: `74961a0f9fce50455df931c99e05c680099192163be34438c0410d00a1dad4f4`

Downloaded file SHA-256:

- `ci_detective_report.json`: `c46a2484fcd8f60514da429f4c41fa9aa3b88ad4400b289ed06badb620e10b11`
- `repository_upgrade.minimal.json`: `3c5837427a9cd1096e0b95d2260c84b9c58f1694ddf43de613c90cd243208f7f`
- `repository_upgrade.deep.json`: `44ad86d88ce5144c50a1f45a0015a1ca54eb9a131cf694832cfcfc572b5d3b`
- `repository_upgrade.implementation-package.json`: `049b7b19789967e5319ee44befe3662cb0b6b6a41fac265fd867793349fd68b3`
- `run-identity.json`: `2f2bb7f7c45a28d35a310e298ce85a611b5b4fcec6c22f18639625d24f80c994`
- `unit-tests.log`: `e1a3c6979e41b6a6ce9759f91b0ab3517e5b54f50edfd2464f31c052cd75b483`
- `scope_claim_audit.summary.md`: `ef7cabf57e0a50f4c85064d3f4e5649e754759968b9dfa16090e7691d70188f3`

Canonical evidence hashes were independently recomputed and matched:

- legacy: `27198dd8ec85335255130bfddadd9cc977ef1f5f7deeeb30e732bb6eded43aeb`
- Minimal: `313a3a25c31b6002c58de2555afaaf7ae5c8cba3d94317cc248a601abe032f27`
- Deep: `3c611000ea7a87dff76f4447d63bf0259fad62ca99666c5fadf6aab1c520bffa`

Analysis-basis hashes were independently recomputed and matched:

- Minimal: `63a1fa98690ddd33b29f6dca76a4bfe319657b89870861607546e5143a556a08`
- Deep: `99fe48ca93e4d42a307377ac80be6ddf2b2cf302954e8d54dc9bd21c9137d6cf`

## Generated-report regression checks

- selected profile: `contract-schema-repository`;
- `.github/workflows/validate.yml`: `parsed`;
- triggers: `pull_request`, `push`, `workflow_dispatch`;
- jobs: `1`;
- commands: `13`;
- command-evidence records: `38`;
- `tests_run_on_pull_requests`: `operational`;
- Minimal Phase 1 items: `0`;
- Deep Phase 1 items: `0`;
- implementation actions: `0`;
- mutation default: `dry_run`.

## Actions not performed

No merge, approval, close, PR comment, deployment, secret access, repository-setting change, `main` write, or PR-body update occurred.

A fresh PR Inspector `v1.9.0` exact-head rereview remains required. The available implementation connector does not expose the PR Inspector adapter, and posting a request as a PR comment was explicitly prohibited for this task.

## Remaining gates

```yaml
PRF-012: implemented_pending_rereview
technical_acceptance: pending
human_specialist_approval_complete: false
repository_governance_verified: false
merge_authorized: false
remaining_insufficient_evidence:
  - fresh PR Inspector v1.9.0 rereview on the final exact head
  - qualified non-author human APPROVED review on that same head
  - repository governance / ruleset verification
```
