# GitHub Actions Pipeline

A personal, AI-assisted pipeline for designing meaningful GitHub Actions CI for repositories.

This repository is not a generic CI template collection.
It is a decision pipeline that helps a language model inspect a target repository, collect evidence, identify real failure modes, design high-signal CI gates, and then implement the smallest useful GitHub Actions patch after owner approval.

## Core Purpose

The purpose of this repository is to help a language model answer one practical question for any target repository:

> What can actually break in this repository, and which small machine-checkable GitHub Actions gates should be added to catch those failures with the least friction?

The pipeline is optimized for personal, solo-maintainer repositories.

Primary priorities:

1. Correctness
2. Determinism
3. Low-friction automation
4. Fast and actionable feedback
5. Small number of meaningful gates
6. Maximum useful autonomy from the language model

External attacker hardening and enterprise-grade security are not default priorities.
Low-cost safety guardrails are still kept to prevent accidental self-inflicted damage.

## Mental Model

Bad CI is like a guard who asks the same generic question at every door.

Good CI is like a smart checkpoint that knows what kind of building it protects.

A small personal script repository does not need airport-level security.
A schema/contract repository needs gates that prevent version drift, invalid schema, fixture regression, and broken generated outputs.
A browser extension repository needs gates that protect manifest integrity, build output, package contents, and runtime-sensitive files.

The pipeline therefore starts with evidence, not YAML.

```text
Evidence first → failure modes → meaningful gates → owner permission → branch patch → validation evidence
```

## Operating Assumptions

This project assumes the owner is not expected to make technical CI/CD decisions.

The language model has full technical authority to:

- inspect the repository;
- search current official documentation when needed;
- choose the best technical approach;
- reject generic best practices that do not fit the repository;
- design the CI gate map;
- implement the smallest useful patch after owner approval;
- report evidence honestly.

The model must not delegate technical decisions back to the owner.

Owner approval means:

```text
permission to make changes on a separate branch
```

Owner approval does not mean:

```text
choosing between technical CI options
```

## GitHub Connector-First Model

This repository is designed for a workflow where the language model interacts with GitHub through a GitHub Connector.

The model does not assume it can directly run local shell commands.

The model uses GitHub Connector/API-style operations to:

- inspect repository files;
- create or update files;
- create branches;
- open or update pull requests;
- trigger or inspect GitHub Actions runs when available;
- read workflow status and evidence.

Deterministic evidence mining should run inside GitHub Actions runners, not inside the model.

The long-term architecture is:

```text
Language model with GitHub Connector
        ↓
Orchestrates repository inspection and changes
        ↓
GitHub Actions runner executes deterministic evidence tools
        ↓
Artifacts + step summary + workflow evidence
        ↓
Model reads evidence and makes CI decisions
        ↓
Owner grants permission to modify branch
        ↓
Model applies patch and verifies results
```

## Pipeline Phases

### 0. Pipeline Load

The model reads this repository and understands the operating rules.

Expected model response:

```text
Pipeline loaded. I am ready. Send the target repository.
```

### 1. Target Repository Intake

The model receives the target repository URL and identifies:

- repository full name;
- default branch;
- repository purpose, if available;
- whether it is standalone or part of a multi-repository ecosystem;
- connector access limitations;
- whether workflows can be read or changed.

The model should not ask the owner to choose technical options.

### 2. Static Repository Inventory

The model inspects the current repository structure and identifies:

- languages;
- package managers;
- lockfiles;
- test runners;
- build scripts;
- schemas;
- validators;
- fixtures;
- release/version files;
- existing workflows;
- generated outputs;
- important documentation;
- deployment or packaging artifacts.

### 2.5. Bilingual Historical Failure Mining

The evidence layer must support English and Persian technical history.

English signal keywords:

```text
fix, bug, revert, regression, hotfix, broken, fail, failure, repair, patch
```

Persian signal keywords:

```text
رفع، اصلاح، باگ، خرابی، خراب، شکست، ناموفق، بازگشت، برگشت، رگرسیون، تعمیر، پچ
```

If evidence is collected through remote GitHub search, Persian search must be marked as best-effort until calibrated.

The model must not claim Persian evidence is complete unless the evidence source supports that claim.

### 2.6. Change Hotspot Detection

The pipeline should identify files that change frequently and may deserve stronger gates.

Examples:

- workflow files;
- schemas;
- validators;
- package metadata;
- version files;
- adapters;
- generated outputs;
- manifests.

### 2.7. CI Failure Telemetry

When available, the model or runner should inspect GitHub Actions run history and identify:

- failing workflows;
- repeated failures;
- flaky or noisy checks;
- slow workflows;
- failure-prone jobs;
- head SHA evidence for validation.

### 2.8. Cross-Repo Evidence Ingestion

If the target repository is part of a multi-repository ecosystem, the pipeline should check whether sibling repository evidence is available.

Examples of useful cross-repo evidence:

- audit documents;
- contract watch specifications;
- drift reports;
- shared contract changelogs;
- adapter or producer/consumer reports;
- issues or PRs mentioning the target repository.

If access to sibling repositories is unavailable, the model must state that cross-repo evidence is incomplete.

### 2.9. Deterministic Evidence Report

The long-term tool for evidence collection is expected to be `ci_detective.py`.

This tool should produce:

- raw JSON evidence as a workflow artifact;
- short human-readable Markdown in `GITHUB_STEP_SUMMARY`;
- evidence completeness flags;
- cache metadata;
- connector scope information;
- limitations.

Raw evidence should not be committed to the repository by default.

### 3. Evidence-Based Failure Mode Discovery

The model identifies failure modes only after reading evidence.

Failure modes must be classified as:

```text
historical      = previously occurred in commits, PRs, issues, or CI failures
structural      = implied by repository structure and file relationships
domain_pattern  = known risk for this project type
cross_repo      = found through sibling repositories or shared contracts
hypothetical    = plausible but weakly evidenced
```

The model must not label a risk as real without evidence.

### 3.5. Domain Risk Pattern Match

The model activates project-type-specific risk patterns.

Expected future risk pattern libraries:

- Python package;
- Python desktop app;
- browser extension MV3;
- WordPress plugin;
- contract/schema repository;
- docs-only repository;
- multi-repo adapter;
- LLM-assisted workflow repository.

### 3.6. Risk Scoring

Each failure mode should be scored using a lightweight personal-project scale:

```yaml
risk_score:
  evidence_count: 0
  likelihood: low|medium|high
  impact: low|medium|high
  estimated_added_seconds: 0
  maintenance_cost: low|medium|high
  priority: critical|high|medium|low|reject
```

For personal repositories, gate cost matters.
A gate that adds friction without strong signal should be rejected.

### 4. Gate Meaningfulness Test

Before adding any CI gate, the model must answer:

1. What exact real or structural failure does this gate catch?
2. What repository evidence justifies it?
3. Is there already a script, validator, or test that should be wired into CI?
4. If it fails, will the maintainer immediately know what to fix?
5. Should it run on PR, push, release, manual trigger, or scheduled run?
6. Is runtime cost proportional to signal value?
7. Could it be noisy or flaky?
8. Does it actually enforce something, or only document it?

If the answer is unclear, the gate should not be added.

### 5. Autonomous CI Decision

The model chooses the best technical path itself.

When multiple technically valid options exist, choose the option with the best balance of:

1. correctness;
2. determinism;
3. low friction;
4. maintainability;
5. clear failure messages;
6. solo-maintainer fit.

Do not ask the owner to choose between technical options.

### 6. Short Persian Owner Briefing

Before implementation, the model gives a short Persian report:

- what it found;
- what it decided;
- what it will change;
- what it intentionally will not add;
- why the plan is meaningful and low-friction.

The report must use simple language and mental imagery.

### 7. Owner Permission Gate

The model asks only for permission to make changes:

```text
آیا اجازه می‌دهی روی branch جدا این تغییرات را پیاده‌سازی کنم؟
```

The model must not ask the owner to select technical options.

### 8. GitHub Connector Implementation

After approval, the model uses GitHub Connector to:

- create a dedicated branch;
- apply the smallest useful patch;
- commit only related files;
- open or update a PR;
- avoid modifying `main` directly;
- verify GitHub Actions results on the exact head SHA.

### 9. Validation

The model must verify results using available evidence.

It must not claim local or CI execution succeeded without direct evidence.

### 10. Final Persian Evidence Report

The final report must include:

1. very short summary;
2. final CI Gate Map;
3. exact changed files;
4. what each new gate catches;
5. intentionally rejected gates and why;
6. validation evidence;
7. remaining risks;
8. recommendation: ready for review, draft, or needs more work.

## Personal Repository CI Policy

This pipeline is optimized for personal repositories.

Do not apply enterprise-grade security hardening by default.

Avoid by default:

- OpenSSF Scorecard;
- CodeQL;
- dependency review gates;
- secret scanning workflows;
- vulnerability gates;
- full-length SHA pinning for every action;
- heavyweight matrix builds;
- noisy scheduled scans.

Keep low-friction safety guardrails:

- do not use workflow-level `write-all` permissions;
- use the minimum permissions that a workflow or job needs;
- do not print secrets or sensitive values to logs;
- avoid `pull_request_target` unless there is a clear documented reason;
- keep workflow and job names stable if used as required checks;
- prefer simple readable workflows over clever generalized workflows.

## Report Persistence Policy

Raw evidence JSON should not be committed by default.

Preferred persistence:

```text
raw JSON evidence      → workflow artifact
human-readable summary → GITHUB_STEP_SUMMARY
final decision summary → PR body or PR comment
optional latest.json   → rolling overwrite only, never timestamp spam
```

## Success Criteria

This pipeline is successful when:

- CI gates are tied to real repository failure modes;
- the number of required checks stays small;
- failures are actionable;
- the model makes technical decisions autonomously;
- the owner only approves repository modification, not technical choices;
- implementation happens on a separate branch;
- no check is claimed as enforced unless it is wired into GitHub Actions;
- validation evidence is tied to the exact commit or head SHA.

## Current Repository Status

This repository is currently in bootstrap stage.

Planned next files:

```text
AGENTS.md
pipeline/00-overview.md
pipeline/01-target-intake.md
pipeline/02-static-inventory.md
pipeline/06-implementation-protocol.md
schemas/ci_detective_report.schema.json
schemas/ci_gate_map.schema.json
tools/ci_detective.py
prompts/00-start.md
examples/ci_gate_map.example.yaml
```
