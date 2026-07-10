# PR #8 Protocol v1.8 Repair Handoff

Action kind: `repair_and_verify`  
Review package: `7f772bdeea83fb7199d22f8aab7df35cb63228d29c48a8a6f32816a0427af76e`  
Reviewed source head: `b45dea478b139546810db398d2669a5b54aed3dd`  
Finding disposition after implementation: `implemented_pending_rereview`

This document records implementation evidence. It does not close a PR Inspector finding, approve the pull request, or authorize merge.

## Invariant extraction

| Finding | Surface symptom | Underlying invariant | Failure boundary | Affected components | Assumptions |
|---|---|---|---|---|---|
| `PRF-001` | Symlink files/parents and escaping workspace globs can leave the target root | No repository-controlled path may be read or serialized until lexical containment, per-component `lstat`, non-symlink status, resolved containment, and type constraints are established | Repository inventory and workspace expansion | `ci_repository_collectors.py`, repository model, report generation | The process is not an OS sandbox; concurrent filesystem replacement remains outside the static analyzer contract |
| `PRF-002` | Help, collect-only, dry-run, no-run, zero-target, or non-runnable jobs can resemble execution | Operational capability requires a bounded behavioral invocation in a structurally runnable job; test capability additionally requires a discovered test target in the command working directory | Workflow parsing and capability promotion | `ci_command_evidence.py`, workflow collector, repository model, semantic command graph | Full shell and called reusable-workflow bodies remain unsupported |
| `PRF-003` | Path names alone select domain profiles | Path correlation is supporting evidence only; a domain profile requires independent language, manifest, framework, entry-point, archetype, or semantic authority | Profile detection and profile-driven recommendations | `ci_profiles.py`, upgrade report diagnostics | The profile catalog remains versioned; the engine applies an authority floor to legacy path-only rules |
| `PRF-004` | A filename beginning with `@@@` collides with history record framing | Untrusted filenames must not share a text delimiter with metadata records | Git history collection | `ci_history_analysis.py`, Deep Mode | Git object and tree readability are required; malformed/truncated output becomes unavailable evidence |

## Repair architecture

### Repository path containment

- Inventory uses `os.walk(..., followlinks=False)`.
- Each candidate is checked lexically beneath the canonical root.
- Every existing path component is inspected with `lstat`; any symlink component is rejected.
- Resolved containment and regular-file/directory type are required.
- Reads use `O_NOFOLLOW` where available and retain file-count/text-size bounds.
- Workspace patterns must be bounded normalized relative POSIX patterns without absolute roots, drives, backslashes, NUL, or `..` components.
- Rejected paths produce stable diagnostics and are never serialized as content evidence.

### Behavioral command and runnable-job evidence

The bounded command parser now excludes recognized non-behavioral modes, including help/version, pytest collection/listing, Cargo `--no-run`/listing, Go listing, Maven test skipping, Gradle dry-run, package-manager dry-run/optional execution, and artifact checks without operands.

A normal GitHub Actions job must have a supported `runs-on` shape and a `steps` array. A reusable job using `jobs.<job_id>.uses` is structurally recognized but contributes no local command evidence until the called workflow is modeled under a separate trust boundary. Invalid jobs convert any contained command records to unsupported evidence.

`tests_run_on_pull_requests` becomes operational only when:

1. the workflow has a pull-request trigger;
2. the job is structurally runnable;
3. the invocation is bounded and behavioral;
4. at least one concrete test target exists in the invocation working directory.

### Profile authority

Path tokens are filtered to code-bearing paths/manifests and remain supporting evidence. Legacy path-only Python rules receive an effective Python-language requirement. Other legacy path-only repository rules receive a manifest-authority requirement. Path-only suggestions that fail authority are emitted as `PROFILE_PATH_ONLY_CANDIDATE` diagnostics instead of selected profiles.

### Structural history framing

Commit metadata is collected as NUL-delimited `sha, subject` pairs. Changed paths are collected separately per validated commit identity using NUL-delimited `git diff-tree` output. Filenames containing `@@@`, tabs, spaces, or Unicode cannot become metadata. Truncated or malformed records return stable unavailable diagnostics rather than raising an uncaught parser exception.

### Exact source-head execution

The validation workflow explicitly checks out `${{ github.event.pull_request.head.sha || github.sha }}`, verifies `git rev-parse HEAD` equals that expected source identity, exports the verified identity through `GITHUB_ENV`, and enables exact mode in `render_workflow_summary.sh`. In exact mode, the summary writer fails unless `TESTED_SHA == SOURCE_HEAD_SHA` and writes structured `run-identity.json` containing the source, tested, event, and exact-verification fields.

## Adversarial validation added

- external symlinked manifest/source/test marker;
- symlinked parent directory;
- parent, absolute, and symlink-matching workspace patterns;
- pytest help/collection, unittest help, Cargo no-run/list, Go list, Maven skip, Gradle dry-run, npm help;
- zero-test repositories, missing/invalid `runs-on`, reusable jobs, malformed siblings, valid positive controls across Python, npm, Cargo, Go, Maven, and Gradle;
- docs-only `pipeline/` and filename-only adapter negatives;
- authoritative Python ETL and manifest-backed adapter positives;
- Git filenames beginning `@@@`, containing tabs/spaces, and Unicode;
- exact-mode identity equality and structured evidence.

## Adjacent impact audit

- Schemas: no public report object shape was expanded; matched profile signal output retains the existing public field set.
- Validators: both current report modes remain subject to the existing Draft 7 validator step.
- CLI: no new mutation or command-execution authority was added.
- Configuration: `minimal-safe-ci` remains the default and Deep Mode remains opt-in.
- CI: source checkout is exact and read-only; timeout, pinned actions, artifact retention, and full-history collection remain bounded.
- Compatibility: `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` remain unchanged.
- Rollback: implementation transaction code is unchanged by this review slice.

## Verification status

Local targeted validation before repository write:

```text
python -m py_compile <changed Python modules and tests>
exit 0

bash -n tools/render_workflow_summary.sh
exit 0

PYTHONPATH=/tmp/pr8repair python -m unittest tests/test_repository_upgrade_review_v180.py -v
Ran 10 tests
OK
```

These results are development evidence only. The complete repository suite, generated reports, schema validation, exact source-head run identity, and artifact hashes must be recorded from GitHub Actions on the resulting PR head.

## Remaining required external verification

- Fresh PR Inspector review on the resulting exact source head.
- Limited security/domain-specialist review of filesystem containment and evidence-trust boundaries.
- Cross-platform filesystem and rollback behavior outside the Ubuntu GitHub-hosted runner remains unexecuted unless separately observed.

## Safety record

```text
merge_performed: false
approval_performed: false
deployment_performed: false
```
