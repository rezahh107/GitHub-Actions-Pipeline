# PR #8 Protocol v1.9 Timezone Identity and Schedule Budget Handoff

```yaml
action_kind: repair_and_verify
branch: feat/deep-repository-upgrade-v1
reviewed_head: f8e7e7a3a2e320174eae0d92bb81999a4dadab14
adopted_concurrent_head: a3701389fed6ec2678dece77ddfde938533859e9
validated_implementation_head: 49553a491e7a6a54108c810e0a5c3687632dcaf3
PRF-009: implemented_pending_rereview
PRF-010: implemented_pending_rereview
merge_performed: false
approval_performed: false
comment_performed: false
deployment_performed: false
```

This records bounded implementer evidence only. It does not close either finding, establish merge readiness, or satisfy PR Inspector, security/domain-specialist, or repository-governance review.

## Capability and concurrency record

- GitHub repository read/write and GitHub Actions execution were available through the connected GitHub application.
- Direct `gh` CLI and direct network clone were unavailable in the execution runtime.
- Before the first write, the PR head advanced by eight commits from the reviewed head to `a3701389fed6ec2678dece77ddfde938533859e9`.
- Those commits addressed the same timezone-identity and schedule-budget findings. They were inspected and adopted rather than overwritten.
- A directly adjacent lifecycle defect was then repaired in commit `49553a491e7a6a54108c810e0a5c3687632dcaf3`.

## PRF-009 — deterministic timezone identity

Validation is pinned to `tzdata==2026.3` / IANA `2026c`. Acceptance requires all of the following to match the versioned contract:

- distribution version;
- strict contained regular files;
- `tzdata/zones` SHA-256;
- `tzdata/__init__.py` SHA-256;
- embedded IANA version;
- identifier count and uniqueness;
- identifier grammar and exclusion rules.

Pinned identity evidence:

```text
tzdata version: 2026.3
IANA version: 2026c
identifier count: 598
tzdata/zones SHA-256: 5027e610a10d1983d286e21fa1fb718f0d34704446cb37f707e81707bb3c1244
tzdata/__init__.py SHA-256: e2bfe056345bcf835f032f930539fb7f113b4d6e94c16e596ed30f09ee48e09a
```

Host-special identifiers including `posixrules`, `localtime`, `posix/`, `right/`, and `SystemV/` fail closed even if host `TZPATH` can load them. An attacker-selected `PYTHONTZPATH` key was proven loadable by `ZoneInfo` but rejected by the pinned identifier contract. Missing, mismatched, unreadable, or unverifiable pinned data emits `WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE`.

Valid retained controls include `Etc/UTC`, `UTC`, `America/New_York`, and `Asia/Baku`.

## PRF-010 — cumulative schedule boundedness

Repeated date-by-date scans across all `146097` Gregorian-cycle days were replaced by a lazily built bitset index covering the complete 400-year cycle. This preserves leap-cycle correctness without using a sampled date window.

The bounded design includes:

- cached Gregorian month, month-day, and weekday masks;
- memoized parsed cron expressions;
- memoized equivalent date predicates;
- deduplication of repeated cron expressions, predicates, and timezone identifiers;
- explicit `4096`-unit per-workflow limit;
- explicit `8192`-unit per-repository-model-build limit;
- stable diagnostic `WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED`;
- whole-workflow invalidation before command evidence when a limit is reached.

The worst-case valid expression `0,59 0,23 31 * *`, 256 repeated entries, distinct worst-case predicates, and multiple workflow files are covered. Logical work charging is deterministic and independent of cache warmth.

## Adjacent lifecycle repair

The concurrent implementation kept repository budget state in a `ContextVar` and reset it using workflow path ordering. That allowed stale budget state to survive across two separate `build_repository_model` calls on the same root when the second first-path sorted after the prior build's final path.

Commit:

```text
49553a491e7a6a54108c810e0a5c3687632dcaf3
fix: reset schedule budget per repository build
```

The repair scopes `_STATE` explicitly to one `build_repository_model` invocation and restores the prior context afterward. It does not alter the work limits, cron grammar, timezone contract, or command-evidence behavior.

Regression fixture:

```text
tests/test_repository_upgrade_schedule_budget_lifecycle.py
```

The fixture performs two separate model builds on the same repository root with lexically increasing workflow paths and a low deterministic repository limit. Both builds receive independent budgets and remain parsed.

## Implementation paths

Relative to the reviewed head, the PRF-009/PRF-010 slice includes:

- `docs/PR8_PROTOCOL_V1_9_IDENTITY_BUDGET_HANDOFF.md`
- `requirements-test.txt`
- `tests/test_repository_upgrade_schedule_budget_lifecycle.py`
- `tests/test_repository_upgrade_schedule_identity_and_budget.py`
- `tests/test_repository_upgrade_workflow_schedule_semantics.py`
- `tools/__init__.py`
- `tools/ci_calendar_bitsets.py`
- `tools/ci_pinned_timezone.py`
- `tools/ci_schedule_resource_patch.py`

## Exact-head implementation validation

```text
Workflow: Validate
Workflow ID: 307479558
Run ID: 29161700455
Run number: 114
Job ID: 86567772119
Conclusion: success
Source head SHA: 49553a491e7a6a54108c810e0a5c3687632dcaf3
Tested SHA: 49553a491e7a6a54108c810e0a5c3687632dcaf3
Event SHA: 6db0d79b54f75cfc72536c49f3f71e5d86d3b6eb
exact_source_head_verified: true
```

Successful gates:

```text
Checkout exact source head                         success
Verify exact source-head checkout                  success
python -m py_compile tools/*.py                     success
python -m unittest discover -s tests               Ran 169 tests in 4.283s — OK
Generate legacy CI detective report                success
Generate Minimal Safe CI report                    success
Generate Deep Repository Upgrade report/package   success
Validate generated v1.1 reports                    success
Scope Claim Audit examples/summary                 success
Write structured run identity                      success
Upload all artifacts                               success
```

GitHub artifact ZIP digests:

- `repository-analysis-reports`: `sha256:1a22d37b1b4f510bc0096780a1b1a7b0a550d74b6b00363540b6b6f35312eaa5`
- `unit-test-diagnostics`: `sha256:f109456989144eaf7b713becf4999e196853c8f2b38f7a13247131081dcad9d3`
- `scope-claim-audit-summary`: `sha256:0c65bc13484a1ee4e7d3d9efffea1a060556fdd3afd9a4dce0d236fe84437e63`

Downloaded artifact file SHA-256:

- `ci_detective_report.json`: `5226ebb1d5fdc88631287fb8bceaddec620600693a1dbab10643890e9e5b8754`
- `repository_upgrade.minimal.json`: `d5a0e8306662a2812b9755a47d75b1ddc7c1e2b6b1aea02df4968735e882e081`
- `repository_upgrade.deep.json`: `1496b6c8ec0965194ec86ee239633947ab23950f02371fc199699a5482a77502`
- `repository_upgrade.implementation-package.json`: `d5d8b79a171965fb28802e916054b9341d23299f0e6e62336db778890c456544`
- `run-identity.json`: `083770e985e8fd221cbffbeb187bda2335c49a0dbe1562defe5ea8deda4d1a09`
- `unit-tests.log`: `c40d15596f75df73c1e4af322c136ca9fc09a86b26e7e7637345958242e496cc`

Canonical evidence hashes were independently recomputed using the repository contract and matched report fields:

- legacy CI detective: `b0a06a85bb21e92d2edb34ce7afb1b50063888121cf77131719f89432ab8b14e`
- Minimal: `699596da7ec2dbb2d5f515d9559148a55a3f3b2febff5463aac27407562efc53`
- Deep: `b0f6f68b9364c55800b502f4107f8f97d11c57509290ee157aa9f797fe6c004e`

Generated-report checks:

```yaml
selected_profiles:
  - contract-schema-repository
workflow_parse_status: parsed
parsed_triggers:
  - pull_request
  - push
  - workflow_dispatch
parsed_jobs: 1
parsed_commands: 13
command_evidence_records: 38
tests_run_on_pull_requests: operational
minimal_phase_1_items: 0
deep_phase_1_items: 0
implementation_package_actions: 0
```

No schedule identity or budget diagnostics were emitted for the repository's valid workflow.

## Preserved boundaries

Existing five-field cron grammar and cadence checks, event and dispatch/call validation, YAML 1.2 and merge-key handling, root/job/step/nested gates, condition/runnable/no-op/working-directory/test-target checks, path/symlink containment, byte-preserving history, profile authority, exact-head checkout, pinned Actions, `persist-credentials: false`, report schemas, artifact hashing, and non-mutating defaults remain unchanged.

No target-repository command execution, merge, approval, close, comment, auto-merge, deployment, secret access, package publication, repository-setting change, or write to `main` occurred.

## Remaining verification

- This documentation-only resulting head requires its own complete exact-source-head CI run; that final run is reported outside this file to avoid recursively changing the validated head.
- A fresh PR Inspector `v1.9.0` rereview remains mandatory on the resulting exact head.
- The current authorization explicitly prohibits PR comments. No PR Inspector tool is available in this runtime, so rereview request execution is `REQUIRES_EXTERNAL_TOOL`; no GitHub comment or PR metadata write was used as a substitute.
- Independent security/domain-specialist review remains pending.
- Repository-governance verification remains pending.
- Cross-platform execution outside the Ubuntu GitHub-hosted runner was not performed.

```yaml
technical_implementation: completed
implementation_exact_head_ci: passed
PRF-009: implemented_pending_rereview
PRF-010: implemented_pending_rereview
fresh_pr_inspector_review: requires_external_tool
security_or_domain_specialist_review: pending
repository_governance_verification: pending
technical_acceptance: pending
merge_readiness: not_established
merge_performed: false
approval_performed: false
comment_performed: false
deployment_performed: false
```