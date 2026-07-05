# AGENTS.md

This file defines operating instructions for AI agents working in this repository.

The repository owner is a non-technical owner. The agent is expected to make technical CI/CD decisions autonomously, based on repository evidence, current official documentation when needed, and the policies in this repository.

## Repository Mission

This repository, `GitHub-Actions-Pipeline`, defines a personal AI-assisted pipeline for designing and implementing meaningful GitHub Actions CI gates in target repositories.

The goal is not to create generic workflows.
The goal is to help an AI agent inspect a target repository, detect real failure modes, decide the best low-friction CI gates, and implement only the smallest useful patch after owner approval.

## Operating Mode

This project is GitHub Connector-first.

Assume the agent interacts with GitHub through connector/API operations unless a later task explicitly provides a local execution environment.

The agent may use GitHub Connector to:

- inspect files;
- create or update files;
- create branches;
- open or update pull requests;
- inspect workflow runs when accessible;
- inspect artifacts or summaries when accessible;
- apply changes after owner approval.

The agent must not assume it can directly run local shell commands such as `git log`, `git grep`, `python`, `pytest`, or `bash` unless a runner/tool execution environment is explicitly available.

Deterministic evidence mining should run inside GitHub Actions runners or through explicitly available tools, not through model imagination.

## Owner Interaction Rules

The owner is not expected to make technical CI/CD decisions.

Do not ask the owner to choose between technical options such as:

- whether to use pytest or unittest;
- whether to use a matrix;
- whether to add cache;
- whether to split workflows;
- whether to add CodeQL, Scorecard, dependency review, or other tools;
- which GitHub Actions syntax or architecture to use.

The agent must decide technical matters itself.

Only ask the owner for:

1. the target repository URL, if missing;
2. permission to modify a repository on a dedicated branch;
3. access expansion when connector scope is insufficient;
4. clarification of non-technical preferences when absolutely necessary;
5. approval for destructive, irreversible, or unusually risky actions.

Owner approval means permission to perform repository changes.
It does not mean the owner is selecting technical options.

The standard approval question is:

```text
آیا اجازه می‌دهی روی branch جدا این تغییرات را پیاده‌سازی کنم؟
```

## Decision Authority

When multiple technically valid options exist, choose the option with the best balance of:

1. correctness;
2. determinism;
3. low friction;
4. maintainability;
5. clear failure messages;
6. small number of gates;
7. personal solo-maintainer fit.

If evidence is insufficient, gather more evidence where possible.
If evidence remains incomplete, choose the safest reversible low-friction option and clearly label the uncertainty.

If a technical challenge appears, the agent must:

1. inspect repository evidence;
2. search current official or primary documentation if needed;
3. choose the best approach itself;
4. document the decision briefly in Persian;
5. continue without asking the owner to make the technical choice.

## Core CI Philosophy

A CI gate is allowed only if it catches a real, plausible, repository-specific failure with low noise and acceptable runtime cost.

Do not add CI theater.

Avoid:

- generic checks without repository evidence;
- heavy security scanners by default;
- broad matrix builds without compatibility risk;
- slow workflows without signal;
- duplicated validator logic inside workflow YAML;
- many fragile path allowlists;
- documentation-only enforcement that is not wired into CI;
- claims of success without evidence.

Prefer:

- wiring existing validators into CI;
- small deterministic tests;
- clear failure messages;
- stable job names;
- fast structural checks before slower behavioral checks;
- simple workflow files;
- branch-based reversible implementation.

## Scope Claim Audit Rule

Scope Claim Audit separates deterministic diff facts from interpretive claim classification. A mismatch or under-reported signal is advisory by default and should feed review attention or future CI Gate Map design, not automatic rejection.

Do not treat a Scope Claim Audit result as enforced unless the target repository has a real wired enforcement gate and the audit package declares `enforcement_mode: enforced` with non-null `wired_enforcement_gate` metadata.

## Evidence Rules

The agent must separate:

- confirmed evidence;
- structural inference;
- domain-pattern inference;
- cross-repo evidence;
- hypothetical risk;
- rejected gates.

Do not call a risk `real` without evidence.

Use these evidence levels:

```text
historical      = observed in commits, PRs, issues, or CI failures
structural      = implied by repository structure and file relationships
domain_pattern  = known risk for this project type
cross_repo      = found through sibling repositories or shared contracts
hypothetical    = plausible but weakly evidenced
```

When evidence is unavailable, say so.
Silence is not proof.

## Personal Repository Security Policy

The target repositories are usually personal, solo-maintainer repositories.
External attacker hardening is not a default priority.

Do not add enterprise-grade security controls unless repository evidence justifies them or the owner explicitly requests them.

Do not add by default:

- OpenSSF Scorecard;
- CodeQL;
- dependency review;
- secret scanning workflows;
- vulnerability gates;
- mandatory full-length SHA pinning for every action;
- heavy scheduled scans;
- enterprise-style policy enforcement.

Keep low-friction safety guardrails:

- do not use workflow-level `write-all` permissions;
- use only required permissions;
- avoid printing secrets or sensitive values to logs;
- avoid `pull_request_target` unless there is a clear documented reason;
- keep workflow/job names stable if they may become required checks;
- prefer trusted official/common actions unless repository evidence says otherwise.

## GitHub Connector Implementation Rules

Before owner approval:

- read-only analysis only;
- do not create branches;
- do not commit files;
- do not open PRs;
- do not modify workflows;
- do not claim enforcement.

After explicit owner approval:

- create a dedicated branch;
- apply the smallest useful patch;
- commit only related files;
- open or update a PR if appropriate;
- verify workflow results on the exact head SHA when possible;
- report evidence honestly.

Never modify `main` directly unless the owner explicitly asks for direct main edits and the repository is in bootstrap state.

For bootstrap of this repository itself, direct `main` updates are acceptable only when the owner explicitly asks to create foundational files in the empty repository.

## GitHub Actions Evidence Model

For future implementation, deterministic evidence should be produced by a workflow runner.

Preferred report channels:

```text
raw JSON evidence      → workflow artifact
human-readable summary → GITHUB_STEP_SUMMARY
final decision summary → PR body or PR comment
optional latest.json   → rolling overwrite only, never timestamp spam
```

Do not commit raw generated evidence reports by default.

## Bilingual Mining Policy

Historical evidence mining must support English and Persian keywords.

English keywords:

```text
fix, bug, revert, regression, hotfix, broken, fail, failure, repair, patch
```

Persian keywords:

```text
رفع، اصلاح، باگ، خرابی، خراب، شکست، ناموفق، بازگشت، برگشت، رگرسیون، تعمیر، پچ
```

Remote GitHub search in Persian is best-effort until calibrated.
Do not claim complete Persian historical coverage without evidence.

## Cross-Repo Evidence Policy

If a target repository appears to be part of a multi-repository ecosystem, the agent must check whether connector access includes sibling repositories.

Record access as:

```yaml
connector_scope:
  target_repo: read|write|unknown
  workflows: read|write|unknown
  actions_runs: read|unknown
  sibling_repos:
    - repo: owner/name
      access: read|write|unauthorized|unknown
```

If sibling repositories are not authorized, state that cross-repo evidence is incomplete and continue with available evidence unless access is necessary for correctness.

## Gate Meaningfulness Test

Before recommending or implementing a gate, answer:

1. What exact real or structural failure does this gate catch?
2. What evidence justifies it in this repository?
3. Is there already a script, validator, or test that should be wired into CI?
4. If it fails, will the maintainer immediately know what to fix?
5. Should it run on PR, push, release, manual trigger, or scheduled run?
6. Is runtime cost proportional to signal value?
7. Could it be noisy or flaky?
8. Does it actually enforce something, or only document it?

If the answer is unclear, reject the gate or mark it low-priority.

## Required Report Style

User-facing reports must be in Persian.

They must be:

- short;
- practical;
- non-technical where possible;
- clear about decisions made by the model;
- honest about missing evidence;
- supported by exact file paths, branch names, commit SHAs, or workflow run evidence when applicable.

Use mental imagery when helpful.

The owner should receive the conclusion, not the model's private reasoning.

## Final Report Requirements

After implementation, report:

1. خلاصه خیلی کوتاه؛
2. CI Gate Map نهایی؛
3. فایل‌های دقیق تغییر یافته؛
4. هر gate چه خرابی واقعی‌ای را می‌گیرد؛
5. چه چیزهایی عمداً اضافه نشد و چرا؛
6. شواهد اجرا و وضعیت GitHub Actions روی head SHA؛
7. ریسک‌های باقی‌مانده؛
8. توصیه نهایی: ready for review، draft، یا needs more work.

## Current Bootstrap Instructions

This repository is currently in bootstrap stage.

When adding foundational files, keep them clear and modular.

Preferred near-term structure:

```text
README.md
AGENTS.md
pipeline/
  00-overview.md
  01-target-intake.md
  02-static-inventory.md
  06-implementation-protocol.md
prompts/
  00-start.md
  01-audit-only.md
  02-implementation-after-approval.md
schemas/
  ci_detective_report.schema.json
  ci_gate_map.schema.json
tools/
  ci_detective.py
examples/
  ci_gate_map.example.yaml
```

Do not create complex tooling before the protocol and schemas are stable.

Recommended build order:

1. master README;
2. AGENTS.md;
3. pipeline protocol files;
4. schemas;
5. prompt files;
6. examples;
7. `ci_detective.py`;
8. reusable workflow;
9. composite action, if later justified.
