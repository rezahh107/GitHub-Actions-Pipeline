# 04 — Scope Claim Audit Prompt

Use this prompt to run an advisory Scope Claim Audit on one target PR.

```text
You are working with `rezahh107/GitHub-Actions-Pipeline`.

Load README.md, AGENTS.md, pipeline/08-scope-claim-audit.md, schemas/scope_claim_audit.schema.json, and this prompt.

Target input: PR URL, or owner/name plus PR number. If a PR URL is given, derive owner/name and PR number from it.

Preferred GitHub tools when available:
GitHub.get_repo
GitHub.get_pr_info
GitHub.fetch_pr
GitHub.get_pr_diff
GitHub.fetch_pr_patch
GitHub.fetch_pr_file_patch
GitHub.list_pr_changed_filenames
GitHub.compare_commits
GitHub.fetch_commit_workflow_runs
GitHub.fetch_workflow_run_jobs
GitHub.fetch_workflow_job_steps
GitHub.fetch_workflow_job_logs
GitHub.fetch_workflow_run_artifacts
GitHub.download_workflow_artifact

If a named tool is unavailable, use the closest supported connector/API equivalent and report that limitation.

Procedure:
1. Collect PR metadata: title, body, draft state, full lowercase 40-character head SHA, base SHA, and author if available.
2. Collect claim sources: title, body, handoff, implementation summary, commit messages, review comments, or unknown.
3. Collect deterministic diff facts: files changed, additions, deletions, changed paths, file statuses, patch availability, source method, and limitations.
4. Classify sensitive surfaces: protocol, schema, validator, workflow, release_lock, package_metadata, tests_fixtures, generated_output, docs, scripts, other.
5. Classify claim text separately from the diff with confidence, rationale, and uncertainty reason.
6. Choose one result: congruent, scope_expanded_but_declared, scope_underreported, mismatch, not_assessable.
7. Default output is advisory: enforcement_mode=advisory, wired_enforcement_gate=null, blocking=false.
8. Use blocking=true only when a real wired gate is verified and the JSON includes enforcement_mode=enforced plus wired_enforcement_gate.

Output A: concise Persian owner report.
Output B: one JSON object matching schemas/scope_claim_audit.schema.json.

Do not invent files, comments, patches, workflow runs, artifacts, settings, or enforcement. Do not treat LLM classification as deterministic truth.
```
