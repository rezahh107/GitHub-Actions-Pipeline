# PR #8 Protocol v1.8 YAML Scalar Repair Handoff

Action kind: `repair_and_verify`  
Review package: `ae12704667d51585388ebe4c19a73fdde1d3332c9507bc013ac8c423bd0d0b41`  
Reviewed source head: `b25f67a6434c6a00f0df4292087273658bc3847a`  
Finding disposition after implementation: `implemented_pending_rereview`

This document records implementer evidence. It does not close PR Inspector finding `PRF-005`, approve the pull request, satisfy specialist review, or authorize merge.

## Invariant extraction

| Field | Record |
|---|---|
| Surface symptom | PyYAML YAML 1.1 resolution converts unquoted `yes`, `no`, `on`, and `off` into Python booleans before workflow execution eligibility is classified. |
| Underlying invariant | Workflow loading must preserve GitHub Actions YAML 1.2 scalar semantics; a host YAML library cannot manufacture deterministic condition truth. |
| Failure boundary | GitHub Actions workflow YAML loading before job/step condition eligibility and command-evidence promotion. |
| Affected components | `tools/ci_repository_collectors.py`, repository model callers, semantic workflow-command consumers, generated reports, and focused fixtures. |
| Assumptions | Only bounded literal boolean semantics are modeled. Dynamic GitHub expressions and called reusable-workflow bodies remain unresolved. |

## Repair architecture

- Added an isolated `GitHubWorkflowLoader` derived from `yaml.SafeLoader`.
- Copied resolver tables before modification; global PyYAML resolvers are not mutated.
- Removed YAML 1.1 boolean resolution from the dedicated loader.
- Added only YAML 1.2 core boolean forms: `true`, `True`, `TRUE`, `false`, `False`, and `FALSE`.
- Added a strict boolean constructor so unsupported explicit `!!bool` values fail closed with `ConstructorError`.
- Added `_load_workflow()` and routed only `parse_workflow()` through it.
- Generic JSON, TOML, and YAML manifest loading remains unchanged.
- Existing literal-false, dynamic-condition, `run` plus `uses`, runnable-job, no-op-command, working-directory, and test-target guards remain unchanged.

## Behavioral expectations

- Unquoted and quoted `yes`, `no`, `on`, `off`, `y`, and `n` remain strings.
- Those strings are conditional/unresolved and cannot retain resolved test families or promote `tests_run_on_pull_requests`.
- Case variants of `true` remain eligible; case variants of `false` remain disabled.
- `${{ true }}` and `${{ false }}` retain the existing bounded condition behavior.
- `!!bool true` and `!!bool False` use supported boolean semantics.
- Unsupported explicit forms such as `!!bool yes` fail workflow parsing closed.
- Top-level `on` remains the trigger key rather than being coerced to boolean `True`.

## Adversarial fixtures

`tests/test_repository_upgrade_yaml_scalar_semantics.py` covers job and step conditions for:

- unquoted and quoted `yes`, `no`, `on`, `off`, `y`, and `n`;
- `true` and `false` case variants;
- quoted true/false values;
- expression-wrapped literal true/false values;
- supported and unsupported explicit `!!bool` tags;
- preservation of the global `yaml.safe_load` behavior outside the dedicated loader;
- positive capability controls and negative no-promotion assertions.

## Adjacent impact audit

- Workflow loading: changed only through the dedicated loader.
- Permission parsing: unchanged after parsed scalar delivery.
- Trigger parsing: receives the literal `on` mapping key under workflow YAML semantics.
- Profile detection and semantic graph: consume already-gated repository model evidence; no independent authority was added.
- Schemas/examples: public report shapes and versions are unchanged.
- CLI: no new flags or mutation authority.
- Compatibility: `minimal-safe-ci`, Deep Mode, `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` remain unchanged.
- Rollback/mutation: not modified.

## Local targeted development evidence

```text
python -m py_compile tools/ci_repository_collectors.py tests/test_repository_upgrade_yaml_scalar_semantics.py
exit 0

Focused scalar parser/model assertions
passed for yes/no/on/off/y/n, true/false variants, and explicit bool tags
```

These are development checks only. The complete repository suite, both report modes, schema validation, exact source-head identity, and artifact hashes must be recorded from GitHub Actions on the resulting final head.

## Write recovery note

A contents-API commit `1945bccfe6a29508a661c64f5c79b9a47e0b4489` temporarily replaced `tools/ci_repository_collectors.py` with a placeholder. It was immediately superseded by commit `05d64d20b055386dd16a3050941e778e0baa4a4f`, which restored the complete collector and installed the intended blob `3cad20338f9da5a85ae819d19d559345196c51c6`. No validation result from the placeholder tree is accepted as evidence.

## Remaining verification

- Full exact-source-head GitHub Actions validation on the final documentation head.
- Fresh PR Inspector review on that resulting head.
- Required limited security/domain-specialist review after technical Green.
- Cross-platform filesystem behavior outside the Ubuntu GitHub-hosted runner remains unexecuted unless separately observed.

## Safety record

```yaml
action_kind: repair_and_verify
PRF-005: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```
