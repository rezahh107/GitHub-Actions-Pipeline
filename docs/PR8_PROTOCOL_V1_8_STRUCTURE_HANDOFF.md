# PR #8 Protocol v1.8 Structural Workflow Validation Handoff

Action kind: `repair_and_verify`  
Review package: `6e5f6446918937bf83111adda0d408987c207e2278dc118f2b31916ff97c54cf`  
Reviewed source head: `05efc9cc2084ba5b2a167fbe4ff8a74a72ff51d3`  
Validated implementation head: `aa7c94c8920b8ea27ca04ad7d91c5a123aef74c8`  
Finding disposition after implementation: `implemented_pending_rereview`

This document records implementer evidence for `PRF-007`. It does not close the finding, approve the pull request, satisfy the required security/domain-specialist review, or authorize merge.

## Invariant extraction

| Field | Record |
|---|---|
| Surface symptom | Successful YAML deserialization allowed unsupported workflow, job, or step properties to be silently ignored while contained commands still established execution evidence. |
| Underlying invariant | Only a structurally valid GitHub Actions workflow, job, and step may contribute resolved command families or operational capability. |
| Failure boundary | Workflow structure validation immediately after bounded YAML loading and before any call to `parse_run_block`. |
| Affected components | Workflow loading, root/job/step validation, reusable-job recognition, command evidence, repository capability derivation, semantic consumers, generated reports, and focused fixtures. |
| Assumptions | The static structural contract is intentionally narrower than the complete GitHub service parser and accepts only versioned properties represented by this repository. Dynamic expressions and reusable-workflow bodies remain unresolved. |

## Repair architecture

- Added `tools/ci_workflow_structure.py` with structural contract version `1.0.0`.
- Defined explicit allowed-property sets for workflow roots, normal jobs, reusable-workflow jobs, and steps.
- Added fail-closed incompatibility rules for step execution forms and their dependent properties.
- Added bounded YAML-node composition before construction to detect and reject `<<` merge keys.
- Routed `tools/ci_repository_model.py` through the structural wrapper rather than calling the collector parser directly.
- Structural validation occurs before the existing collector reaches `parse_run_block`.
- Any structural diagnostic invalidates the complete workflow for execution evidence and returns empty jobs, commands, and command-evidence collections.
- Existing YAML 1.2 scalar behavior, condition eligibility, job-shape checks, no-op detection, working-directory checks, test-target requirements, permission parsing, and command parser behavior remain in place.

## Stable diagnostics

- `WORKFLOW_ROOT_PROPERTY_UNSUPPORTED`
- `WORKFLOW_NORMAL_JOB_PROPERTY_UNSUPPORTED`
- `WORKFLOW_REUSABLE_JOB_PROPERTY_UNSUPPORTED`
- `WORKFLOW_STEP_PROPERTY_UNSUPPORTED`
- `WORKFLOW_STEP_EXECUTION_FORM_INVALID`
- `WORKFLOW_YAML_MERGE_KEY_UNSUPPORTED`

## Behavioral coverage

`tests/test_repository_upgrade_workflow_structure.py` covers:

- an unknown top-level property around an otherwise valid pull-request test job;
- an unknown normal-job property with valid `runs-on`, `steps`, and test command;
- an unknown reusable-workflow job property alongside an otherwise valid normal job;
- an unknown step property;
- incompatible execution forms and dependent properties;
- YAML `<<` merge-key input;
- positive controls for every versioned root, normal-job, reusable-job, and step property set;
- assertions that invalid workflows retain no jobs, commands, resolved test families, or operational `tests_run_on_pull_requests` capability.

## Exact-head validation evidence

Implementation head `aa7c94c8920b8ea27ca04ad7d91c5a123aef74c8` was validated by GitHub Actions before this evidence-only documentation update.

```text
Workflow: Validate
Run ID: 29145414057
Run number: 94
Job ID: 86526018787
Job: repository-validation
Conclusion: success
Source head SHA: aa7c94c8920b8ea27ca04ad7d91c5a123aef74c8
Tested SHA: aa7c94c8920b8ea27ca04ad7d91c5a123aef74c8
Event SHA: 198c141e45535842480dede7eded3ed444bdbbe7
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 139 tests in 3.677s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

GitHub artifact ZIP digests:

- `repository-analysis-reports`: `sha256:e652da8d4d54874fd724e7c7cadb79e7f2a8a82d00350b1b00b9cfd4265fff4b`
- `unit-test-diagnostics`: `sha256:71ee772167878fc376aa52c8071a0027a6ada1f45d8caead4f3749c5d5ec3e42`
- `scope-claim-audit-summary`: `sha256:0b59fc494fd9c757552a865c5143bc1f1a960f40d803e4d3f38fa3998834d911`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `2db1a59eaf25b93b5b9da177a15333aa055a22f0ad5f109c16c093c127f2da7e`
- `repository_upgrade.minimal.json`: `e532a44a1d4eb60ab82d2412483e6cd15d79ffbb715c11da62364e4d106b2486`
- `repository_upgrade.deep.json`: `f53a57cc7039e550d434f8fe019f4b6de7e367ccbf7fb6f66a1f5197ab24aaa3`
- `repository_upgrade.implementation-package.json`: `e5b12910134d2516a653b8f11a66f86fae0a616d2b864e962a155e93080bfd5b`
- `run-identity.json`: `b3ee5cd046f1392d39bae6df232714b166d095d94c093c897da0a10402f3e6f7`
- `unit-tests.log`: `bc6aa56e81b080262e50d6e66e90b1836b5bbf233dbb12bab91282d5e63d311f`

Independently recomputed canonical evidence hashes matched their report fields:

- Minimal: `afe9640b4a602028a6bb4e4b8c836bf0352c322b09ec80fa1b9d7ec7085cf2d2`
- Deep: `eff229ad13774bfdd69582c5ed23ca66cde48dd7df44add17031460071ce01a1`
- Legacy CI detective: `7b9f059d65c92e446a6ef66c2e1a26312b32a4c914163661d5e1cec9d0f71ec9`

Generated report checks:

- selected profile: `contract-schema-repository`;
- actual repository workflow remained `parsed` under structural contract `1.0.0`;
- `tests_run_on_pull_requests`: `operational`;
- Deep Phase 1 items: `0`;
- implementation-package actions: `0`;
- no structural-property, execution-form, or merge-key diagnostics occurred for the repository's valid workflow.

## Adjacent-impact audit

- Workflow loading: dedicated YAML 1.2 loader remains authoritative.
- Root/job/step validation: new pre-command boundary is fail-closed for the whole workflow.
- Permissions and triggers: parsed only after structural acceptance; no permission broadening.
- Reusable jobs: property set is validated but called workflow bodies remain unresolved.
- Command evidence: unchanged parser; invalid containers never reach it.
- Semantic graph consumers: continue consuming already-gated workflow records.
- Schemas/examples: no public report shape or version change.
- CLI and implementation behavior: no new flags, command execution, or mutation authority.
- Compatibility: `minimal-safe-ci`, Deep Mode, `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` remain unchanged.

## Consulted primary sources

- GitHub Actions workflow syntax reference for root, job, reusable-job, and step property surfaces.
- GitHub Actions syntax reference for `background`, `wait`, `wait-all`, `cancel`, and `parallel` execution forms.

## Remaining limitations and required independent verification

- The documentation-only resulting head requires its own exact-source-head CI run; that final run is recorded in the PR action artifact rather than recursively rewriting this file.
- This validator is not the complete GitHub service parser. Nested value schemas beyond the represented fail-closed boundaries remain outside its claims.
- Dynamic GitHub Actions expression evaluation remains unsupported.
- Called reusable-workflow bodies remain unresolved.
- Cross-platform behavior outside the Ubuntu GitHub-hosted runner remains unexecuted.
- Fresh PR Inspector review on the resulting final head remains mandatory.
- Required independent security/domain-specialist review remains pending after technical Green.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-007: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
