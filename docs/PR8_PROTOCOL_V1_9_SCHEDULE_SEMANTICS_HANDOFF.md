# PR #8 Protocol v1.9 Schedule-Semantics Repair Handoff

Action kind: `repair_and_verify`  
Branch: `feat/deep-repository-upgrade-v1`  
Inspector commit: `35e3b398d8e8d6823007540f0a156ff2a3feece6`  
Reviewed source head: `98aa46ece9eb4d31a634cc54c0338437223c5165`  
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
- `* * * * *` and other sub-five-minute cadences;
- invalid minute, hour, day-of-month, month, and day-of-week ranges;
- non-string cron values;
- unknown/non-IANA timezone values;
- non-string timezone values;
- multiple entries where one entry is invalid;
- valid five-minute-or-slower schedules;
- valid `Etc/UTC`, `America/New_York`, and `Asia/Baku` timezone controls;
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

## Validation still required

- complete unit suite;
- Minimal Safe CI report generation;
- Deep Repository Upgrade report and implementation-package generation;
- generated-report schema validation;
- canonical evidence-hash recomputation;
- structured exact-source-head run identity;
- artifact ZIP and extracted-file SHA-256 capture;
- final exact-head rerun after evidence documentation;
- fresh PR Inspector rereview;
- independent security/domain-specialist review;
- repository-governance verification.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-009: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
