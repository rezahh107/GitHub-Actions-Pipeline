# PR #8 Protocol v1.8 Nested Workflow Structure Repair Handoff

Action kind: `repair_and_verify`  
Review package: `4342fd1c9bb57b88a1b9a7ed30ef589d8fad9cf729b622b0aceb1c56805713c5`  
Reviewed source head: `279fcf5f0097307d5d902c7cd84bbc1c715222d2`  
Validated implementation head: `843c451375b9b806200e54950bc99a9663833052`  
Finding disposition after implementation: `implemented_pending_rereview`

This document records implementer evidence. It does not close PR Inspector finding `PRF-008`, approve the pull request, satisfy the required security/domain-specialist review, or authorize merge.

## Invariant extraction

| Field | Record |
|---|---|
| Surface symptom | First-level property whitelists admit nested mappings whose keys or value types are invalid under GitHub Actions, while contained test commands can still resolve. |
| Underlying invariant | Every nested mapping or sequence admitted by the static workflow evidence contract must have an explicit versioned schema or be rejected before any command family can resolve. |
| Failure boundary | Workflow structure validation after YAML composition/loading and before `tools.ci_repository_collectors.parse_workflow`. |
| Affected components | `tools/ci_workflow_nested_patch.py`, `tools/__init__.py`, repository-model workflow loading, command evidence, capability promotion, fixtures, generated reports, and CI evidence. |
| Assumptions | This is a bounded structural contract, not a complete GitHub service-parser clone. Dynamic expression truth and called reusable-workflow bodies remain unresolved. |

## Repair architecture

- Added `WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION = "1.0.0"` in `tools/ci_workflow_nested_patch.py`.
- Installed the wrapper during `tools` package initialization before repository-model modules bind `parse_workflow`; the original parser remains the final delegate only after first-level and nested acceptance.
- Added a machine-checkable `NESTED_SCHEMA_COVERAGE_MAP` for every property admitted at workflow, normal-job, reusable-job, and step surfaces.
- Added runtime coverage validation. A missing, extra, or unknown schema rule emits `WORKFLOW_NESTED_SCHEMA_COVERAGE_GAP` and invalidates the workflow before command parsing.
- Added explicit nested validation for triggers, permissions, environment maps, outputs, `defaults.run`, concurrency, `runs-on`, snapshot, environment, strategy/matrix, container, services, reusable inputs/secrets, step `with`/`env`, and parallel entries.
- Preserved the existing YAML 1.2 scalar loader, YAML merge-key rejection, root/job/step property validation, condition eligibility, runnable-job guards, no-op classification, working-directory guards, and test-target guards.
- Any nested diagnostic returns `parse_status: invalid_shape` with empty `jobs`, `commands`, and `command_evidence` before delegating to the collector parser.

## Stable diagnostics

- `WORKFLOW_NESTED_SCHEMA_COVERAGE_GAP`
- `WORKFLOW_TRIGGER_STRUCTURE_INVALID`
- `WORKFLOW_PERMISSION_STRUCTURE_INVALID`
- `WORKFLOW_DEFAULTS_STRUCTURE_INVALID`
- `WORKFLOW_CONCURRENCY_STRUCTURE_INVALID`
- `WORKFLOW_RUNS_ON_STRUCTURE_INVALID`
- `WORKFLOW_SNAPSHOT_STRUCTURE_INVALID`
- `WORKFLOW_ENVIRONMENT_STRUCTURE_INVALID`
- `WORKFLOW_STRATEGY_STRUCTURE_INVALID`
- `WORKFLOW_CONTAINER_STRUCTURE_INVALID`
- `WORKFLOW_SERVICES_STRUCTURE_INVALID`
- `WORKFLOW_REUSABLE_SECRET_STRUCTURE_INVALID`
- `WORKFLOW_STEP_NESTED_STRUCTURE_INVALID`
- `WORKFLOW_NESTED_VALUE_INVALID`

## Adversarial fixtures

`tests/test_repository_upgrade_workflow_nested_structure.py` covers:

- unknown `strategy` keys and wrong `fail-fast`, `max-parallel`, and `matrix` types;
- unknown and malformed `defaults.run` values;
- unknown and malformed concurrency values and the represented queue/cancel incompatibility;
- unknown and malformed environment values;
- unknown and malformed container and service structures;
- unknown and malformed snapshot structures;
- additional admitted nested values such as trigger filters, permissions, outputs, `runs-on`, and step `with` maps;
- invalid nested reusable-job data alongside a valid normal test job;
- exact coverage-map equality with every admitted property set;
- runtime coverage drift fail-closed behavior;
- positive controls covering every nested form retained by the versioned contract;
- preservation of a simple valid pull-request test workflow.

Every negative fixture asserts that the workflow is invalid, has no jobs/commands/command evidence, retains no resolved test family, emits the expected stable diagnostic, and cannot promote `tests_run_on_pull_requests` to `operational`.

## Adjacent impact audit

- Workflow loading: remains behind the dedicated YAML 1.2 loader and merge-key scan.
- Root/job/step validation: retained and runs before nested validation.
- Permission and trigger parsing: collector interpretation occurs only after structural acceptance.
- Strategy/matrix: shape and bounded key/value types are validated; matrix values remain data rather than executed expressions.
- Defaults, concurrency, environment, container/services, and snapshot: represented forms are validated explicitly; unknown forms fail closed.
- Reusable jobs: property and nested input/secret/strategy/concurrency shapes are validated; called workflow bodies remain unresolved.
- Command evidence and semantic consumers: receive only structurally accepted workflow records.
- Schemas/examples: public report shapes and versions are unchanged.
- CLI: no new mutation or execution authority.
- Compatibility: `minimal-safe-ci`, Deep Mode, `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` remain unchanged.
- Rollback and implementation recipes: unchanged.

## Local targeted development evidence

```text
python -m py_compile /tmp/ci_workflow_nested_patch.py /tmp/tools_init_new.py /tmp/test_nested_upload.py
exit 0

PYTHONPATH=/tmp/wfcheck python -m unittest -v test_nested_upload
Ran 8 tests in 0.045s
OK
```

These are development checks only. Final evidence must come from the full GitHub Actions workflow on the resulting exact source head.

## Intermediate rejected validation

The first implementation head `1975b9f87af2eb429a2c6beeae6d11bcbfc42887` was checked out and compiled successfully, but GitHub Actions run `29147677139` / job `86531902907` failed the unit suite. No report-generation or schema-validation step ran, and no result from that head is accepted as successful evidence.

The three failures were fixture expectation drift:

- an older test still expected a valid sibling job to remain operational beside a structurally malformed job;
- two new assertions expected diagnostics from the nested layer even though an earlier existing boundary rejected the same input first.

The validator was not weakened. Commit `843c451375b9b806200e54950bc99a9663833052` aligned the fixtures with whole-workflow invalidation and the actual earliest fail-closed diagnostic.

## Exact-head validation evidence

Implementation head `843c451375b9b806200e54950bc99a9663833052` was validated by GitHub Actions before this evidence-only documentation update.

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29147873203
Run number: 97
Job ID: 86532393541
Job: repository-validation
Conclusion: success
Source head SHA: 843c451375b9b806200e54950bc99a9663833052
Tested SHA: 843c451375b9b806200e54950bc99a9663833052
Event SHA: e15a0f64d3b155e82a94dc3e9e03bfa5cf99e80c
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 147 tests in 3.464s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

GitHub artifact ZIP digests:

- `repository-analysis-reports`: `sha256:e6e3d4a54ace26e076c87674a2f7c115a548c2b9d1f47d62ee16da10b394e00c`
- `unit-test-diagnostics`: `sha256:5500fb57e0c5e6bd743989f4023894a6b9cc25e0e51d3142576f725a12f1fe12`
- `scope-claim-audit-summary`: `sha256:ad3e2b10485413dce1ecc623b23ed63a137c394a60817ac0c51efbeb6b3a0f3f`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `09f750fa8b92513939569c503f9dffdf47b99fb1e7606882cd07c98ef7951f21`
- `repository_upgrade.minimal.json`: `ae2f51aa60289cfdda6e4c17ea8208a40f3c7a949d4ce201507d91d49b028047`
- `repository_upgrade.deep.json`: `d90f60a4dab9d32cef96b2632838a04858139c29a209af027a99c173b140ac90`
- `repository_upgrade.implementation-package.json`: `6b66b54510d4d7827af2491ff6271d5b0d089854bf6cfa4effd77492cb56b4b8`
- `run-identity.json`: `9f3cac5a210ebf3407b1e0e650539c9e2a096087dcb610436d3f7256dd2133ab`
- `unit-tests.log`: `51b53cd13fd127a88be7a89497574391de34b95b243fa7b4c336b870efa78e98`

Independently recomputed canonical evidence hashes matched their report fields:

- Minimal: `747ce7de954080389e4aede20477d02493aa201674afdede409d1cd312d2ec97`
- Deep: `a19d66bd62ed52df72f1be84c48649648f45478bc0fcbf60aa393f3190e5cd1d`
- Legacy CI detective: `b643b69d96ce873c28bc7d062333f7008c29585821c3786413003cb3b36fc954`

Generated-report checks:

- selected profile: `contract-schema-repository`;
- the repository workflow remained `parsed`;
- actual workflow command-evidence records: `38`;
- `tests_run_on_pull_requests`: `operational`;
- Deep Phase 1 items: `0`;
- implementation-package actions: `0`;
- no nested-structure diagnostic occurred for the repository's valid workflow.

## Remaining verification

- This evidence-only documentation update creates a new resulting source head; its exact-head CI result must be recorded in the PR action artifact rather than recursively rewriting this file.
- Fresh PR Inspector review on the resulting exact head remains mandatory.
- Required independent security/domain-specialist review remains pending after technical Green.
- Cross-platform behavior outside the Ubuntu GitHub-hosted runner remains unexecuted unless separately observed.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-008: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
