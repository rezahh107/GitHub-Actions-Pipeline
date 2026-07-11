# PR #8 Protocol v1.8 Structural Workflow Validation Handoff

Action kind: `repair_and_verify`  
Review package: `6e5f6446918937bf83111adda0d408987c207e2278dc118f2b31916ff97c54cf`  
Reviewed source head: `05efc9cc2084ba5b2a167fbe4ff8a74a72ff51d3`  
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

## Validation still required on resulting final head

- Complete unit suite.
- Minimal and Deep report generation.
- Draft 7 schema validation.
- Canonical evidence-hash recomputation.
- Exact-source-head identity verification and artifact capture.
- Fresh PR Inspector review.
- Required independent security/domain-specialist review after technical Green.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-007: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
