# Repository Upgrade Architecture

Current report contract: `1.1.0`  
Repository version: `0.3.0`

## Architecture

```text
files + manifests + workflows + bounded source semantics
                         ↓
               RepositoryModel v1.1
                         ↓
 evidence-rich profile detection + conflict-aware composition
                         ↓
 structural history     optional read-only telemetry
              ↘          ↓          ↙
 observed failures / structural invariants / baseline capabilities
                         ↓
       ranking-policy.v1 + factor-level rationale
                         ↓
 minimal plan OR staged deep upgrade + dry-run recipe package
                         ↓
 explicit exact-HEAD allowlisted application, when requested
```

Validated outcomes feed a separate review-only profile-evolution process. They never mutate runtime behavior automatically.

## Module boundaries

| Module | Responsibility |
|---|---|
| `tools/ci_repository_model.py` | bounded inventory, manifests, workspaces, workflows, command candidates, capability states |
| `tools/ci_semantic_analysis.py` | Python AST and package/workflow script resolution |
| `tools/ci_profiles.py` | evidence-rich profile detection and conflict-aware composition |
| `tools/ci_ranking.py` | versioned ranking-policy loading and factor derivation |
| `tools/ci_recommendations.py` | independent recommendation channels and decisions |
| `tools/ci_implementation_engine.py` | dry-run packages and exact-HEAD allowlisted atomic file creation |
| `tools/ci_outcome_registry.py` | deterministic review-only profile evolution proposals |
| `tools/ci_upgrade_engine.py` | orchestration and mode-specific report assembly |
| `tools/repository_upgrade.py` | analysis and explicit application CLI |
| `tools/profile_evolution.py` | outcome aggregation CLI |

## Semantic evidence boundary

The v1.1 semantic analyzer supports:

- Python import edges parsed with `ast`;
- test-to-source resolution when test code imports a local module;
- literal FastAPI/Flask-style route decorators;
- `if __name__ == "__main__"` entry signals;
- `module:function` entry-point resolution against parsed callables;
- package scripts and workflow commands that invoke them.

It does not claim dynamic imports, runtime dependency injection, reflection, generated code, JavaScript call graphs, or network behavior. Unsupported semantics remain explicit limitations.

## Component boundaries

Boundary authority is:

1. explicit workspace membership;
2. nearest manifest root;
3. repository root fallback.

A manifest-derived boundary is not presented as semantic ownership. Each component records `boundary_basis` and evidence.

## Profile composition

Profile matches record the exact satisfied criteria and references. Confidence is based on independent and authoritative signals.

Expected and excluded capability contributions are preserved separately. A conflict is emitted as `PROFILE_CAPABILITY_CONFLICT`; the capability is not silently promoted into baseline recommendations until the conflict is resolved by a versioned rule.

## Ranking v1.1

`profiles/ranking-policy.v1.json` maps capability classes to bounded ordinal risk and cost characteristics. Recommendation ranking records:

- source channel;
- current capability state;
- evidence confidence and reference count;
- implementation-step count;
- all factor values;
- factor-level rationale;
- policy version.

The result is an ordering aid, not probability, expected loss, or calibrated quantitative risk.

## Implementation engine

The engine is real but deliberately narrow.

Report generation produces a dry-run `implementation_package`. A recipe is applicable only when all versioned preconditions pass. Application additionally requires:

- exact Git HEAD match;
- clean worktree;
- explicit recipe allowlist;
- non-existing non-symlink target;
- content hash match;
- path containment under repository root.

Writes are atomic and non-overwriting. Repository commands are not executed. The first recipe supports creation of a Python pull-request test workflow only when one install command and one test command are unambiguously resolved.

Unsupported recommendations remain staged recommendations, not fake implementation actions.

## Profile evolution

`repository_outcomes.v1` records privacy-preserving repository fingerprints, profile IDs, capability transitions, implementation outcome, exact head SHA, and workflow conclusion.

A proposal requires evidence from multiple distinct repositories and exact-head successful outcomes. Output status is `proposed_for_human_review`. Updating a profile or recipe still requires a separate versioned change, fixtures, schema validation, and review.

## Migration

- Legacy upgrade report `1.0.0` remains valid against `schemas/repository_upgrade_report.v1.schema.json`.
- New reports use `report_version: 1.1.0` and `schemas/repository_upgrade_report.v1.1.schema.json`.
- `ci_detective` remains `0.1.1`.
- No silent conversion is performed.
