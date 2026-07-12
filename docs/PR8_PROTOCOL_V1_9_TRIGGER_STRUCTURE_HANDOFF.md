# PR #8 Protocol v1.9 Trigger-Schema Repair Handoff

Action kind: `repair_and_verify`  
Inspector commit: `35e3b398d8e8d6823007540f0a156ff2a3feece6`  
Reviewed source head: `6a4f71312cba5fdd11fb8996aaeb66b9f95c6752`  
Validated implementation head: `f727cb5ebe321a4fbf302e136a6c5422aa22ce51`  
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

These checks were development evidence only; GitHub Actions evidence follows.

## Write and validation recovery record

- Contents-API commit `aa71dffb203cfa8d225fce68c27752b04cf658cf` accidentally introduced an empty unrelated file named `DO_NOT_USE`.
- The next fast-forward commit `49190415ecc83495ac568f0be21a6fe791200af5` installed the intended repair tree and removed that file from the effective tree. The file is absent from the reviewed-head-to-resulting-head diff.
- Run `29150720731`, job `86539682422`, on `49190415ecc83495ac568f0be21a6fe791200af5` compiled successfully but failed one legacy assertion because the new event-specific diagnostic now precedes the earlier global trigger diagnostic. Report generation and schema validation were skipped, and no output from that run is accepted as successful evidence.
- Commit `f727cb5ebe321a4fbf302e136a6c5422aa22ce51` aligned the legacy assertion to accept the new fail-closed diagnostic without weakening validation.

## Exact-head validation evidence for implementation head

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29150774469
Run number: 101
Job ID: 86539809915
Conclusion: success
Source head SHA: f727cb5ebe321a4fbf302e136a6c5422aa22ce51
Tested SHA: f727cb5ebe321a4fbf302e136a6c5422aa22ce51
Event SHA: 7e8f295639b8f6a7a983a2aaa77356d9d6ec80b0
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 154 tests in 4.761s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

GitHub artifact ZIP digests:

- `repository-analysis-reports`: `sha256:aa624471c013fb5c51b491e5ad7edb67a7a2b2917b4eb6f9b5efdf5c61bdc07f`
- `unit-test-diagnostics`: `sha256:2d724f388ec3aaad10ea6498b819b1c4c0ecbd739f08b88b6022c5c196a36189`
- `scope-claim-audit-summary`: `sha256:8487ed0ec84a570f7a834892dcf9e3d880d6cc69cb447971dc6e0f93167f7373`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `8ff0c569fcf482ed5ef6f97ca3372319ef6f6b8146e42498f23aaa6b2649ab09`
- `repository_upgrade.minimal.json`: `fa7a9e42731bba69e1c008cd6c99c5d4b3e14dfc8732c39a4d5100885b4aefc4`
- `repository_upgrade.deep.json`: `42d6aafd989c005d78e8710e83af1870f5291232ae3088ecffe94f33310980e3`
- `repository_upgrade.implementation-package.json`: `2307d1781bd08eed18dcf9b7a3e61294841c4d9f2d1c80ed28d1abf6500300a4`
- `run-identity.json`: `5c8f252ca4b0695892a1efe0e966652cd0819a7891664f856833147ca288cacc`
- `unit-tests.log`: `eae9f3e67e7c6524c664c0ad978e43d7ed97ccf997aa214273898da9c7a4608b`

Canonical evidence hashes were independently recomputed after excluding the contract-defined volatile fields and matched the report values:

- legacy CI detective: `87053d5059c4300f1b8243ffe7dd203d0b4708fb5593487f1782b66d88ff4bdb`
- Minimal: `309930ef571caa13587ca9dc4626716c190577f44125735ddcf736b9ca98026c`
- Deep: `a06ed53a4a98326f8756bdad1f57a7f45f1634d86d352e7ef144efb3035c4f61`

Generated-report checks:

- selected profile: `contract-schema-repository`;
- repository workflow remained `parsed` with triggers `pull_request`, `push`, and `workflow_dispatch`;
- repository workflow command-evidence records: `38`;
- `tests_run_on_pull_requests`: `operational`;
- no trigger-schema diagnostics occurred for the repository's valid workflow;
- Deep Phase 1 items: `0`;
- implementation-package actions: `0`.

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

## Remaining independent verification

- This documentation-only resulting head requires its own exact-source-head CI; that final run is recorded in the PR action artifact rather than recursively rewriting this file.
- Fresh PR Inspector rereview is mandatory on the resulting final exact head.
- Required independent security/domain-specialist and repository-governance verification remain pending.
- Cross-platform behavior outside the Ubuntu GitHub-hosted runner was not executed.
- Complete GitHub service-parser equivalence, expression evaluation, shell emulation, and reusable-workflow body resolution are not claimed.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-009: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
