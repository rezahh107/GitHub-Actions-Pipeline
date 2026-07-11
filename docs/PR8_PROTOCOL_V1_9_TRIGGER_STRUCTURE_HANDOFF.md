# PR #8 Protocol v1.9 Trigger-Schema Repair Handoff

Action kind: `repair_and_verify`  
Inspector commit: `35e3b398d8e8d6823007540f0a156ff2a3feece6`  
Reviewed source head: `6a4f71312cba5fdd11fb8996aaeb66b9f95c6752`  
Finding: `PRF-009`  
Finding disposition: `implemented_pending_rereview`

This handoff records bounded implementation evidence. It does not close the finding, approve or merge the pull request, satisfy repository governance, or satisfy the required independent security/domain-specialist review.

## Invariant extraction

| Field | Record |
|---|---|
| Surface symptom | A global trigger-property allowlist permitted event/property combinations that GitHub rejects, such as `push.workflows`, while retaining valid test commands. |
| Underlying invariant | Every trigger event admitted by the evidence model must have an explicit event-specific schema; any unsupported or malformed trigger must invalidate the entire workflow before capability evidence is produced. |
| Failure boundary | Workflow `on` parsing before permissions, jobs, conditions, command extraction, and capability promotion. |
| Affected components | Trigger loading, nested structural validation, workflow command evidence, repository-model capability derivation, fixtures, CI artifacts, and implementer evidence. |
| Assumptions | The validator is a bounded fail-closed contract, not a complete GitHub service-parser or expression evaluator. |

## Repair architecture

- Added `tools/ci_workflow_trigger_patch.py` with trigger schema contract `1.0.0`.
- Added an event-to-schema registry and machine-checkable form-handler coverage.
- Installed the event-specific gate after the existing nested structural gate and before repository-model modules bind `parse_workflow`.
- Trigger diagnostics return `parse_status: invalid_shape` with empty jobs, commands, and command-evidence records.
- Preserved the dedicated YAML 1.2 loader, merge-key rejection, root/job/step and nested validation, condition eligibility, runnable-job checks, no-op checks, working-directory checks, test-target checks, path containment, history framing, and non-mutating defaults.

## Retained bounded event schemas

- `push`
- `pull_request`
- `pull_request_target`
- `workflow_run`
- `repository_dispatch`
- `workflow_dispatch`
- `workflow_call`
- `schedule`
- types-only: `branch_protection_rule`, `watch`
- null-only: `fork`, `gollum`, `page_build`, `public`, `status`

`workflow_dispatch` and `workflow_call` use separate input, secret, and output validators. Invalid activity values, unknown nested keys, incompatible filter pairs, unsupported event/property combinations, malformed options/defaults, and registry coverage drift fail closed.

## Stable diagnostics

- `WORKFLOW_TRIGGER_SCHEMA_COVERAGE_GAP`
- `WORKFLOW_TRIGGER_EVENT_UNSUPPORTED`
- `WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID`
- `WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED`
- `WORKFLOW_TRIGGER_ACTIVITY_INVALID`
- `WORKFLOW_TRIGGER_FILTER_CONFLICT`
- `WORKFLOW_DISPATCH_INPUT_INVALID`
- `WORKFLOW_CALL_INPUT_INVALID`
- `WORKFLOW_CALL_SECRET_INVALID`
- `WORKFLOW_CALL_OUTPUT_INVALID`
- `WORKFLOW_SCHEDULE_STRUCTURE_INVALID`

## Adversarial validation added

`tests/test_repository_upgrade_workflow_trigger_structure.py` covers:

- `push.workflows` and `push.types`;
- `workflow_run.paths`, missing workflows, and invalid activities;
- `workflow_dispatch.outputs`, `workflow_dispatch.secrets`, malformed inputs, unsupported input types, invalid options/default combinations, and wrong required types;
- distinct `workflow_call` input, secret, and output schemas;
- invalid pull-request, workflow-run, branch-protection, and watch activities;
- conflicting branch, tag, and path include/exclude filters;
- malformed repository-dispatch and schedule structures;
- unsupported events and unknown nested keys;
- machine-checkable registry/handler coverage;
- positive controls for every retained event schema;
- whole-workflow invalidation with no jobs, commands, resolved families, or operational pull-request-test capability.

## Local development evidence

```text
python -m py_compile tools/ci_workflow_trigger_patch.py tools/__init__.py tests/test_repository_upgrade_workflow_trigger_structure.py
exit 0

Standalone event-schema harness
validated 14 negative and 17 positive trigger cases
```

These are development checks only. Full repository validation and exact-head artifacts must come from GitHub Actions on the implementation and final handoff heads.

## Adjacent impact audit

- Workflow loading: dedicated YAML 1.2 loader retained.
- Trigger validation: event-specific and fail-closed before downstream workflow parsing.
- Permissions and conditions: unchanged and unreachable after trigger rejection.
- Reusable workflows: trigger declaration validated; called workflow bodies remain unresolved.
- Command evidence and semantic graph: continue to consume structurally gated repository-model records.
- Reports and schemas: public versions/shapes unchanged.
- CLI and mutation: no new command execution or mutation authority.
- Compatibility: `minimal-safe-ci`, Deep Mode, `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` retained.
- Rollback and transaction paths: unchanged.

## Validation pending at implementation commit

- Complete unit suite.
- Minimal and Deep report generation.
- Generated-report schema validation.
- Canonical evidence-hash recomputation.
- Exact-source-head run identity.
- Artifact digest capture.
- Fresh PR Inspector rereview.
- Required independent security/domain-specialist and repository-governance verification.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-009: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
