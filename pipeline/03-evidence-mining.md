# 03 — Evidence Mining

## Purpose

Collect evidence before the model reasons about CI gates.

Evidence should come from repository files, workflow history, artifacts, summaries, commit or PR history when available, and deterministic tooling.

## Bilingual Historical Signals

The evidence layer must support both English and Persian technical history.

English keywords: fix, bug, revert, regression, hotfix, broken, fail, failure, repair, patch.

Persian keywords: رفع، اصلاح، باگ، خرابی، خراب، شکست، ناموفق، بازگشت، برگشت، رگرسیون، تعمیر، پچ.

Remote Persian search is best-effort until calibrated. Do not claim full Persian coverage without proof.

## Workflow Telemetry

When accessible, collect:

- workflow names;
- run events;
- run conclusion;
- head SHA;
- branch;
- created and updated timestamps;
- repeated failures;
- slow or noisy checks.

## Cross-Repo Evidence

For ecosystem repositories, check whether related repositories are accessible. Useful evidence may include audit documents, contract notes, drift reports, changelogs, and PRs that mention the target repository.

If related repositories are not accessible, report the limitation.

## Persistence Rules

Raw generated evidence should not be committed by default.

Preferred outputs:

- raw JSON as workflow artifact;
- readable Markdown as GitHub step summary;
- final decision summary in PR body or PR comment;
- optional latest report only as rolling overwrite.

## Rule

The model may reason from evidence, but must not invent evidence.
