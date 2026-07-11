# PR #8 Protocol v1.9 Timezone Identity and Schedule Budget Handoff

```yaml
action_kind: repair_and_verify
reviewed_head: f8e7e7a3a2e320174eae0d92bb81999a4dadab14
PRF-009: implemented_pending_rereview
PRF-010: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
```

This records bounded implementer evidence only. It does not close either finding or satisfy PR Inspector, security/domain-specialist, or repository-governance review.

## PRF-009

Validation is pinned to `tzdata==2026.3` / IANA `2026c`. The distribution version, `tzdata/zones` SHA-256, package identity SHA-256, IANA version, identifier count, uniqueness, and key grammar are verified before membership is accepted. Host-special identifiers including `posixrules`, `localtime`, `posix/`, `right/`, and `SystemV/` fail closed. An unavailable or unverifiable pinned source emits `WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE`.

## PRF-010

Repeated 146,097-day scans are replaced by one lazily built Gregorian-cycle bitset index. Parsed expressions and equivalent date predicates are memoized. Logical work is charged independently of cache warmth with explicit `4096`-unit per-workflow and `8192`-unit per-repository limits. Exceeding either emits `WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED` and invalidates the affected workflow before command evidence.

## Development evidence

- Pinned manifest: 598 identifiers.
- `tzdata/zones`: `5027e610a10d1983d286e21fa1fb718f0d34704446cb37f707e81707bb3c1244`.
- `tzdata/__init__.py`: `e2bfe056345bcf835f032f930539fb7f113b4d6e94c16e596ed30f09ee48e09a`.
- A `PYTHONTZPATH`-injected TZif key was loadable by `ZoneInfo` but rejected by the pinned contract.
- 256 repeats of `0,59 0,23 31 * *` reused one calendar predicate and remained below budget.
- Distinct worst-case predicates reached identical deterministic work counts on repeated trials.
- Bitset adjacency was compared with the former complete 400-year scan for randomized predicates.

## Implementation paths

- `docs/PR8_PROTOCOL_V1_9_IDENTITY_BUDGET_HANDOFF.md`
- `requirements-test.txt`
- `tests/test_repository_upgrade_schedule_identity_and_budget.py`
- `tests/test_repository_upgrade_workflow_schedule_semantics.py`
- `tools/__init__.py`
- `tools/ci_calendar_bitsets.py`
- `tools/ci_pinned_timezone.py`
- `tools/ci_schedule_resource_patch.py`

## Preserved boundaries

Existing cron grammar/cadence checks, event and dispatch/call validation, YAML 1.2 and merge-key handling, root/job/step/nested gates, condition/runnable/no-op/working-directory/test-target checks, path/symlink containment, history framing, exact-head checkout, report schemas, artifact hashing, and non-mutating defaults remain unchanged.

## Pending authoritative verification

Full unit suite, both report modes, schema validation, canonical hash recomputation, exact-head identity, artifact digests, fresh PR Inspector v1.9.0 rereview, independent specialist review, and repository-governance verification remain pending until observed on the resulting exact head.
