# PR #8 Root-Cause Repair Evidence

Status: implementation complete on branch; final exact-head CI evidence must be recorded after the final documentation commit.

## Defect-to-repair map

| Finding | Violated invariant | Repair boundary | Executable evidence |
|---|---|---|---|
| `PRF-001` false command evidence | Textual resemblance must not establish execution | `tools/ci_command_evidence.py`, workflow collector, semantic graph | Comment, inert, inline-comment, redirection, control-flow, substitution, package-script, and real invocation tests |
| `PRF-002` permission modeling | Classification must reflect every job's effective permission | workflow parser and repository capability model | Missing, empty, read-only, `read-all`, `write-all`, narrowing, broadening, mixed-job, malformed tests |
| `PRF-003` open report contract | Canonical contract-bearing objects must be closed | `schemas/repository_upgrade_report.v1.1.schema.json` | Positive generated reports plus unknown-field, missing-field, enum, SHA, duplicate, mode, semantic, telemetry, recommendation, and action mutations |
| `PRF-004` invalid exact-head outcomes | Invalid evidence must be rejected before aggregation | `tools/ci_outcome_registry.py`, `schemas/repository_outcomes.v1.schema.json` | Null, short, non-hex, uppercase, duplicate, conflict, head mismatch, threshold, and deterministic proposal tests |
| `PRF-005` correlation promoted to Phase 1 | Phase 1 requires a concrete missing oracle | `tools/ci_recommendations.py` | Generic subsystem suppression, operational duplicate suppression, correlation deferral, behavior-specific eligibility tests |
| `PRF-006` non-recoverable mutation | Repository mutation and authoritative persistence must be recoverable as one operation | `tools/ci_transaction.py`, implementation engine, CLI, recovery schema | Failure injection before mutation, during creation, and during each output write; idempotent rollback; recovery-required test |
| `PRF-007` unsafe summary rendering | Exact identities must be rendered literally and verifiably | `tools/render_workflow_summary.sh`, workflow | Executed shell test checks both SHAs, literal backticks, clean stderr, missing-input failure, and run-identity JSON |

## Command-evidence boundary

The parser deliberately supports only deterministic standalone argv invocations. It does not emulate Bash, PowerShell, or another shell. These constructs cannot establish operational capability:

- comments and blank lines;
- assignments without an executable;
- shell builtins and inert output;
- command substitution and process substitution;
- heredocs and here-strings;
- pipes and compound operators;
- control-flow blocks;
- nested shell interpreters such as `bash -c`.

Unsupported constructs remain visible as unresolved evidence. Extending support requires a versioned parser change and adversarial fixtures.

## Permission model

For each workflow and job, the model stores:

- declaration presence: `missing` or `explicit`;
- declaration form: `empty`, `map`, `read-all`, `write-all`, or `malformed`;
- normalized values and source location;
- effective source scope: `job`, `workflow`, or `platform_default`;
- effective access: `read_or_none`, `write`, or `unknown`.

A job declaration overrides the workflow declaration. Missing platform defaults and malformed shapes remain `unknown`. Any effective write job makes least privilege `operational_but_weak`; no permission is broadened by this repair.

## Closed contract architecture

The `1.1.0` report schema is independent of the legacy `1.0.0` schema. Reusable definitions close mode policy, repository model, workflow evidence, permissions, semantic nodes/edges/signals/relationships, profiles, history, telemetry, recommendations, ranking rationale, staged output, diagnostics, and implementation actions. Mode conditionals reject Deep fields in Minimal Mode and require Deep-only fields in Deep Mode.

Implementation actions are recipe-bound create-file records. Arbitrary operations, paths, recipe identifiers, executable payload shapes, and undeclared fields are rejected.

## Outcome trust boundary

The complete registry is validated before grouping. Canonical Git identity is exactly 40 lowercase hexadecimal characters. Outcome identity and exact-head evidence identity are deterministic and unique. A successful outcome contributes only when `exact_head_sha == workflow_head_sha`, workflow conclusion is `success`, implementation is `applied`, and post-state is operational. Invalid evidence produces actionable contract diagnostics rather than silent skipping.

## Phase 1 eligibility

Each recommendation now carries an `oracle_gap` answering:

1. the exact failure mode or invariant;
2. affected paths or contracts;
3. why existing controls do not detect it;
4. the smallest missing assertion or oracle;
5. the validation plan.

Historical correlation, generic subsystem names, or operational duplicate controls cannot independently satisfy eligibility. Ranking remains bounded ordinal ordering and not probability or causal proof.

## Recoverable mutation transaction

Mutation requires Deep Mode, a canonical exact expected HEAD, clean worktree, explicit recipe allowlist, contained non-symlink absent targets, and external non-existing output paths. Before repository mutation, an immutable recovery plan is persisted outside the target repository.

The transaction then:

1. applies allowlisted create-file recipes without executing repository commands;
2. records created paths, directories, and SHA-256 hashes;
3. atomically creates report, package, and result outputs;
4. marks the external journal `committed` only after all outputs exist.

On failure, transaction-created outputs and repository files are removed only when hashes match. Rollback is idempotent. If rollback cannot safely finish, the journal becomes `recovery_required` and retains deterministic continuation data.

## Compatibility retained

- `minimal-safe-ci` remains the default.
- Deep Mode remains explicit opt-in.
- `ci_detective` remains `0.1.1`.
- legacy Repository Upgrade Report remains `1.0.0`.
- current report remains independently versioned as `1.1.0`.
- no automatic registry mutation or hidden online learning exists.
- no target-repository command execution or arbitrary patch synthesis was introduced.
- exact expected HEAD and clean worktree remain mandatory.
- authoritative outputs remain outside the target repository during mutation.

## Intentionally unsupported

- full shell execution semantics;
- dynamic imports, reflection, generated runtime graphs, and dependency-injection resolution;
- JavaScript/TypeScript AST semantics until a versioned analyzer exists;
- deriving GitHub platform defaults when permissions are missing;
- causal inference from commit-subject or subsystem correlation;
- arbitrary patches or commands in implementation packages;
- automatic profile or recipe promotion.

## Required final validation

The final exact PR head must execute:

```bash
python -m py_compile tools/*.py
python -m unittest discover -s tests
```

The workflow must also generate and schema-validate both report modes, preserve deterministic fixed-timestamp output and hashes, exercise dry-run implementation packaging, and upload `run-identity.json` containing the tested SHA and PR source head SHA. A successful run on an older head is not final evidence.
