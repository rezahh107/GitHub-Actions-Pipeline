# PR #8 Protocol v1.8 Nested Workflow Structure Repair Handoff

Action kind: `repair_and_verify`  
Review package: `4342fd1c9bb57b88a1b9a7ed30ef589d8fad9cf729b622b0aceb1c56805713c5`  
Reviewed source head: `279fcf5f0097307d5d902c7cd84bbc1c715222d2`  
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

## Final validation evidence

Pending exact-source-head GitHub Actions execution after the implementation commit.

## Remaining verification

- Full unit suite, both report modes, schema validation, and canonical hash verification on the resulting exact head.
- Fresh PR Inspector review on the resulting exact head.
- Required independent security/domain-specialist review after technical Green.
- Cross-platform behavior outside the Ubuntu GitHub-hosted runner remains unexecuted unless separately observed.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-008: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
