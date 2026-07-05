# 03 — Evidence Mining

## Purpose

Collect evidence before the model reasons about CI gates.

Evidence should come from repository files, workflow history, artifacts, summaries, commit or PR history when available, and deterministic tooling.

## Evidence States

Every evidence channel must report a status and a reason.

Allowed completeness states:

```text
complete
bounded
partial
unavailable
unknown
not_applicable
```

`complete` is allowed only relative to an explicitly stated scope. A shallow clone must never be reported as complete Git history.

## Local Git Evidence

The local collector records:

- whether the repository is shallow;
- available commit count;
- configured signal-match limit;
- configured hotspot commit limit;
- whether signal results were truncated;
- deterministic hotspot ordering.

English and Persian commit searches are separate evidence channels. Search results must include the exact commit SHA and summary.

English keywords: fix, bug, revert, regression, hotfix, broken, fail, failure, repair, patch.

Persian keywords: رفع، اصلاح، باگ، خرابی، خراب، شکست، ناموفق، بازگشت، برگشت، رگرسیون، تعمیر، پچ.

Do not expand keyword registries without corpus evidence. Remote Persian search remains best-effort until calibrated.

## Workflow Run Context

When running in GitHub Actions, record these values separately:

```text
event_name
tested_sha
source_head_sha
base_sha
ref
tested_ref_kind
run_id
run_attempt
```

For a pull request, `tested_sha` may be GitHub's synthetic merge commit while `source_head_sha` is the contributor branch head. Never conflate them.

## Workflow Telemetry

When accessible through a connector, collect:

- workflow names;
- run events;
- run conclusion;
- head SHA;
- branch;
- created and updated timestamps;
- repeated failures;
- slow or noisy checks.

The local Python collector does not call GitHub APIs and must mark workflow telemetry unavailable.

## Cross-Repo Evidence

For ecosystem repositories, check whether related repositories are accessible. Useful evidence may include audit documents, contract notes, drift reports, changelogs, and PRs that mention the target repository.

If connector scope is not supplied, report cross-repository evidence as `unknown`, not `not_applicable`.

## Canonical Evidence Hash

The report includes:

```text
canonicalization_version: 1
hash_algorithm: SHA-256
evidence_sha256: hash of canonical evidence content
```

The evidence hash excludes generation time and run context. Canonical JSON uses UTF-8, stable key order, compact separators for hashing, and rejects NaN and infinities.

## Persistence Rules

Raw generated evidence should not be committed by default.

Preferred outputs:

- raw JSON as workflow artifact;
- readable Markdown as GitHub step summary;
- final decision summary in PR body or PR comment;
- optional latest report only as rolling overwrite.

## Rule

The model may reason from evidence, but must not invent evidence or silently promote bounded evidence to complete evidence.
