# PR #8 Protocol v1.9 Schedule-Semantics Repair Handoff

Action kind: `repair_and_verify`  
Branch: `feat/deep-repository-upgrade-v1`  
Inspector commit: `35e3b398d8e8d6823007540f0a156ff2a3feece6`  
Reviewed source head: `98aa46ece9eb4d31a634cc54c0338437223c5165`  
Validated implementation head: `1381bf60d16e4eed6e27dc4285c3bceea5e4e68d`  
Finding: `PRF-009`  
Finding disposition: `implemented_pending_rereview`

This handoff records a bounded same-PR repair. It does not close `PRF-009`, authorize merge, satisfy independent security/domain-specialist review, or satisfy repository-governance verification.

## Capability handshake

| Capability | Status | Evidence |
|---|---|---|
| GitHub repository read/write | `AVAILABLE` | Connected GitHub application actions. |
| Direct `gh` CLI | `UNAVAILABLE` | `gh` executable is absent in the runtime. |
| Direct local GitHub network clone | `UNAVAILABLE` | Runtime DNS cannot resolve `github.com`. |
| GitHub Actions exact-head execution | `AVAILABLE` | Existing `Validate` workflow on PR source-head commits. |
| Fresh PR Inspector rereview | `REQUIRES_EXTERNAL_TOOL` | Must be requested on the final exact head. |
| Independent security/domain specialist | `UNKNOWN` | No authorized specialist identity is available in this execution context. |

## Invariant extraction

| Field | Record |
|---|---|
| Surface symptom | A structurally valid `schedule` entry could contain cron or timezone semantics rejected by GitHub while a coexisting `pull_request` job still supplied command evidence. |
| Underlying invariant | Every represented schedule entry must be semantically verifiable and accepted before any workflow job, command family, or operational capability can be retained. |
| Failure boundary | Workflow trigger parsing, after event/property shape validation and before permissions, conditions, jobs, commands, or command evidence. |
| Scope | Five-field documented POSIX cron subset, five-minute minimum interval, and optional IANA timezone verification. |
| Explicit non-goals | Complete GitHub service-parser equivalence, expression evaluation, shell emulation, or reusable-workflow body resolution. |

## Implementation architecture

- Added `tools/ci_schedule_semantics.py` with contract version `1.0.0`.
- Added `tools/ci_workflow_schedule_patch.py`, installed after the existing nested and event-specific trigger gates.
- Preserved the existing event/property registry; the new wrapper only refines already represented `schedule` entries.
- Added a versioned compatibility refinement for the nested trigger rule so the official represented schedule shape accepts required `cron` plus optional string `timezone` while all non-schedule trigger validation remains delegated to the previous nested validator.
- A semantic error returns the existing whole-workflow invalid record before delegated parsing.
- No external cron dependency was introduced. The parser is deterministic and bounded.
- Timezone verification uses Python `zoneinfo`; missing runtime data emits an explicit unverifiable diagnostic and fails closed.

## Bounded cron behavior

The parser requires exactly five fields and supports only documented operators:

- wildcard: `*`;
- list: `,`;
- ascending range: `-`;
- positive bounded step: `/`;
- numeric field ranges;
- `JAN`-`DEC` and `SUN`-`SAT` names.

Field ranges are:

```text
minute        0-59
hour          0-23
day of month  1-31
month         1-12 or JAN-DEC
day of week   0-6 or SUN-SAT
```

The minimum interval calculation expands minute/hour values deterministically. It checks same-day gaps directly and checks cross-midnight gaps against matching dates over one complete 400-year Gregorian calendar cycle.

## Stable diagnostics

- `WORKFLOW_SCHEDULE_CRON_INVALID`
- `WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT`
- `WORKFLOW_SCHEDULE_TIMEZONE_INVALID`
- `WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE`

Existing structural diagnostics remain authoritative for malformed schedule containers or unknown schedule properties.

## Adversarial coverage

`tests/test_repository_upgrade_workflow_schedule_semantics.py` combines `pull_request`, an executable test job, and schedule fixtures for:

- malformed four-field and macro cron forms;
- `* * * * *`, same-hour sub-five-minute cadence, and cross-midnight one-minute cadence;
- invalid minute, hour, day-of-month, month, and day-of-week ranges;
- non-string cron values;
- unknown/non-IANA timezone values;
- non-string timezone values;
- multiple entries where one entry is invalid;
- valid five-minute-or-slower schedules;
- valid cross-midnight times restricted to non-consecutive matching dates;
- valid `Etc/UTC`, `UTC`, `America/New_York`, and `Asia/Baku` timezone controls;
- missing timezone-database fail-closed behavior.

Every invalid integration fixture asserts:

```text
parse_status == invalid_shape
jobs == []
commands == []
command_evidence == []
no resolved command families
tests_run_on_pull_requests != operational
```

## Local focused development evidence

```text
PYTHONPATH=. python -m unittest discover -s tests -v
Ran 4 focused parser/timezone tests — OK

python -m py_compile \
  tools/ci_schedule_semantics.py \
  tools/ci_workflow_schedule_patch.py \
  tests/test_repository_upgrade_workflow_schedule_semantics.py
exit 0
```

These checks validate the isolated parser and syntax only. They are not substitutes for the repository's complete GitHub Actions suite and artifact pipeline.

## Recovery and validation record

### Initial implementation head

```text
dc6fa2847f1fa6fd150cbe4b077bc949eb7059e3
fix: validate schedule cron and timezone semantics
```

Run `29155502075`, job `86551799774`, checked out the exact implementation head and compiled successfully. The unit suite ran `159` tests but one positive timezone fixture failed because the pre-existing nested trigger validator still required each schedule entry to contain exactly `cron`. Report generation, report schema validation, run identity, and repository-analysis artifact upload were skipped. No output from this failed run is accepted as successful evidence.

The negative semantic fixtures already passed. The failure exposed directly adjacent contract drift between the event-specific registry, which represented optional `timezone`, and nested coverage, which did not.

### Adjacent correction

```text
1381bf60d16e4eed6e27dc4285c3bceea5e4e68d
fix: align nested schedule timezone coverage
```

The correction did not bypass nested validation. It versioned and replaced only the nested schedule branch, accepting required string `cron` plus optional string `timezone`; every other trigger event remains delegated to the prior nested validator.

## Exact-head validation evidence for implementation head

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29155593599
Run number: 104
Job ID: 86552026588
Conclusion: success
Source head SHA: 1381bf60d16e4eed6e27dc4285c3bceea5e4e68d
Tested SHA: 1381bf60d16e4eed6e27dc4285c3bceea5e4e68d
Event SHA: 91525a0b697d7a001284856800b2cbb00eac2499
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 159 tests in 5.463s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

GitHub artifact ZIP digests:

- `repository-analysis-reports`: `sha256:10140109faea9c3bbdeafbbaf058d0d2679ca99695d3827178e3e79a790cb2ae`
- `unit-test-diagnostics`: `sha256:aa73536927684f0a1e15881084d64eda8299fd4956ffee31c1775c233a0ca28f`
- `scope-claim-audit-summary`: `sha256:b2928f102465b6600f8ad3468b5786475c824477b03b8360a822ed838413f6e3`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `45c9aebb69b7a5c06b82f62a6aab6d289146bdff96b167c0428dfdf0d4f6d8e1`
- `repository_upgrade.minimal.json`: `8761eff3900c4defb5b29baf02bf7273386ef980d9cdd32a73b76c1a63cf5057`
- `repository_upgrade.deep.json`: `8ac88d29fedc23a9aeb0a33a7de70f9b35cc909cbfc4a20d0c7e16231b0ebd11`
- `repository_upgrade.implementation-package.json`: `3e3c9e121f3835cb32d48e1ba09ea66dbe2df6f5bad2d232c85b4a535653392b`
- `run-identity.json`: `0fea3effc9fc4049a1ba2cd0a94a7f6a0ad29beff3a2fb9f186498e52791747e`
- `unit-tests.log`: `738d1e36a43e23ecd310e16d7416f47989084befff79d4aa426703daf5d3d07b`

Structured identity:

```json
{"event_sha":"91525a0b697d7a001284856800b2cbb00eac2499","exact_source_head_verified":true,"identity_contract_version":"1.0.0","source_head_sha":"1381bf60d16e4eed6e27dc4285c3bceea5e4e68d","tested_sha":"1381bf60d16e4eed6e27dc4285c3bceea5e4e68d","workflow_sha":null}
```

Canonical evidence hashes were independently recomputed after excluding the contract-defined volatile fields and matched the report values:

- legacy CI detective: `0dac50920b900820ce9aad94a41a95fe7609107a97a2a81308fd5bd34c998807`
- Minimal: `1dab1e6db948a8337a5e3970ff81892e46270c95e993946097232db485cf8044`
- Deep: `54950b772f9f49187d43979e1dac9f8db7bf42b1eb853862822621faf7bec9d2`

Generated-report checks:

- selected profile: `contract-schema-repository`;
- repository workflow remained `parsed` with triggers `pull_request`, `push`, and `workflow_dispatch`;
- repository workflow command-evidence records: `38`;
- `tests_run_on_pull_requests`: `operational`;
- no schedule-semantic diagnostic occurred for the repository's valid workflow;
- Minimal Phase 1 items: `0`;
- Deep Phase 1 items: `0`;
- implementation-package actions: `0`.

## Files in this repair slice

- `CHANGELOG.md`
- `docs/PR8_PROTOCOL_V1_9_SCHEDULE_SEMANTICS_HANDOFF.md`
- `tests/test_repository_upgrade_workflow_schedule_semantics.py`
- `tools/__init__.py`
- `tools/ci_schedule_semantics.py`
- `tools/ci_workflow_schedule_patch.py`

## Official sources used

- GitHub Docs, **Workflow syntax for GitHub Actions — `on.schedule`**: five-field POSIX cron form, supported operators, optional IANA timezone string, and minimum interval of five minutes.
- Python Documentation, **`zoneinfo` — IANA time zone support**: system/tzdata sources, normalized keys, and `ZoneInfoNotFoundError` when verification data is unavailable.

## Adjacent impact and compatibility audit

- Event/property registry: unchanged.
- Dispatch/call validation: unchanged.
- YAML 1.2 scalar loader and merge-key rejection: unchanged.
- Root/job/step property validation: unchanged.
- Nested schedule coverage: narrowed to the official represented `cron` plus optional `timezone` shape; all other nested rules remain delegated unchanged.
- Condition eligibility, runnable-job/execution-form checks, no-op, working-directory, and test-target guards: unchanged.
- Path containment, symlink controls, byte-preserving history, and profile authority: unchanged.
- Exact-source-head CI identity: unchanged.
- CLI, report versions, schemas, implementation recipes, mutation defaults, transactions, and rollback behavior: unchanged.
- No external dependency was added.

## Remaining independent verification

- This evidence-documentation commit requires its own exact-source-head CI; that final run is recorded in the PR action artifact rather than recursively rewriting this file.
- Fresh PR Inspector rereview is mandatory on the resulting final exact head.
- Required independent security/domain-specialist review remains pending.
- Repository-governance verification remains pending.
- Cross-platform behavior outside the Ubuntu GitHub-hosted runner was not executed.
- Complete GitHub service-parser equivalence, expression evaluation, shell emulation, reusable-workflow body resolution, OS sandboxing, cryptographic containment, and complete TOCTOU resistance are not claimed.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-009: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
