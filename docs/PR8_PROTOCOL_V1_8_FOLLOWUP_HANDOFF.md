# PR #8 Protocol v1.8 Follow-up Repair Handoff

Action kind: `repair_and_verify`  
Canonical review package: `ebfaadfdc6e4175e4f0d274243d82715f4b384e505e66d58b67cdab281769ba9`  
Reviewed source head: `d68416e87faafa6700dd58d3386cd3c4684208df`  
Finding disposition after implementation: `implemented_pending_rereview`

This is an implementer handoff, not an independent inspection, approval, merge authorization, deployment record, or final finding closure.

## Invariant extraction

| Finding | Surface symptom | Underlying invariant | Failure boundary | Affected components | Assumptions |
|---|---|---|---|---|---|
| `PRF-005` | Commands in `if: false`, dynamic-condition, or invalid `run`+`uses` paths can look operational | Command evidence may promote capability only when the job and step are structurally valid and unconditionally eligible under the bounded model | Workflow YAML parsing before semantic graph and capability promotion | `tools/ci_repository_collectors.py`, repository model consumers, generated reports | Full GitHub expression evaluation and called reusable-workflow bodies remain unsupported |
| `PRF-006` | Shared human-readable Git helper strips leading/trailing whitespace from NUL-framed filenames | Record transport must preserve exact bytes until individual NUL fields are decoded and validated | Git subprocess output before structural-history parsing | `tools/ci_models.py`, `tools/ci_history_analysis.py`, Deep Mode reports | Canonical repository filenames are decoded as strict UTF-8; undecodable fields fail closed |

## Repair architecture

### Workflow execution eligibility

The bounded execution-eligibility contract is versioned as `1.0.0` internally.

- Missing `if`, boolean `true`, string `true`, and `${{ true }}` are eligible.
- Boolean/string/expression literal `false` is deterministically disabled and cannot establish command families.
- Other expression strings are retained as unresolved conditional evidence rather than unconditional proof.
- Malformed condition types fail closed.
- A step containing both `run` and `uses` is structurally invalid for command evidence.
- Gated resolved records become `inert` for literal disablement or `unsupported` for unresolved/invalid execution; capability families are cleared.
- Diagnostics identify the exact job or step scope.

No full expression engine, target command execution, reusable-workflow body resolution, or shell emulation was added.

### Byte-preserving Git history

- Existing `run_git` remains the normalized helper for human-readable output.
- New `run_git_bytes` returns successful stdout without text decoding, `.strip()`, newline handling, or replacement decoding.
- NUL-framed commit/path collectors use only `run_git_bytes`.
- Commit SHA fields decode as strict ASCII and are validated as lowercase 40-character identities.
- Commit subjects and filenames decode individually as strict UTF-8 after NUL splitting.
- Leading/trailing spaces, tabs, newlines, Unicode, and `@@@` prefixes remain part of filename identity.
- Malformed, truncated, empty, or undecodable records become bounded unavailable diagnostics.

Commit/path/result bounds and the non-causation framing of co-change history remain unchanged.

## Adversarial coverage

Added fixtures for:

- job-level literal `if: false`;
- step-level literal `if: false`;
- steps containing both `run` and `uses`;
- unresolved dynamic job and step conditions;
- absent, literal-true, and `${{ true }}` positive controls;
- direct exact whitespace round-trip through the NUL parser;
- invalid UTF-8 path records;
- actual Git filenames with leading/trailing spaces, leading tab, leading newline, Unicode, spaces, and `@@@` prefix;
- deterministic repeated structural-history output.

## Adjacent impact audit

- Schemas: public Repository Upgrade Report remains `1.1.0`; no serialized object field was added.
- Validators: existing Draft 7 validation remains authoritative for both report modes.
- Semantic graph: consumes the gated command records already produced by the workflow collector.
- Capability model: only `status=resolved` records with retained families can promote execution.
- CLI: unchanged.
- Configuration: `minimal-safe-ci` remains default; Deep Mode remains opt-in.
- CI: exact-source-head checkout and structured identity workflow remain unchanged.
- Compatibility: `ci_detective@0.1.1`, legacy report `1.0.0`, and current report `1.1.0` remain unchanged.
- Mutation/rollback: unchanged by this follow-up slice.

## Development validation

Before repository writes, the reconstructed focused suite executed:

```text
python -m py_compile <changed modules and focused tests>
exit 0

python -m unittest /tmp/pr8v180/test_targeted.py -v
Ran 7 tests
OK
```

This is development evidence only. Full suite, both report modes, schema validation, run identity, and artifact hashes must be taken from GitHub Actions on the resulting exact source head.

## Safety and remaining verification

```yaml
action_kind: repair_and_verify
PRF-005: implemented_pending_rereview
PRF-006: implemented_pending_rereview
merge_performed: false
approval_performed: false
deployment_performed: false
fresh_pr_inspector_review: pending
security_or_domain_specialist_review: pending
```

Remaining intentionally unsupported or unexecuted areas:

- dynamic GitHub Actions expression semantics;
- called reusable-workflow body resolution;
- cross-platform filesystem behavior outside the Ubuntu GitHub-hosted runner;
- OS-level sandboxing, cryptographic containment, and concurrent filesystem replacement/TOCTOU resistance.

PR Inspector must be rerun on the final exact head before merge.
