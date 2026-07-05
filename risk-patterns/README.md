# Domain Risk Patterns

This directory is the domain-specific risk-pattern library for the audit pipeline.

The library makes `domain_pattern` evidence concrete: during Static Repository Inventory, the agent checks `detection_signals` from every `risk-patterns/*.yaml` file against the actual target repository structure. Any matching `project_type` contributes its `risk_patterns` to the Failure Mode Discovery candidate list.

Domain patterns are candidate risks, not automatic CI gates. A pattern becomes a proposed gate only after the Gate Meaningfulness Test confirms repository evidence, practical machine-checkability, acceptable runtime/noise, and clear maintainer actionability.

## Matching rules

- More than one project type can match one repository.
- Matches are additive, not mutually exclusive.
- Example: a Python package inside a multi-repo ecosystem can activate both `python-package` and `multi-repo-adapter`.
- If no project type matches, report: `no domain risk pattern matched — falling back to generic checklist only`.

## Required YAML shape

Each pattern file validates against `schemas/risk_pattern.schema.json` and uses this shape:

```yaml
project_type: python-package
detection_signals:
  - signal: pyproject.toml at repository root
risk_patterns:
  - id: version-drift
    description: Package runtime version diverges from pyproject.toml metadata.
    typical_trigger: Release bump updates one source but not the other.
    detectability: easy
    suggested_gate: Static test parses both version sources and asserts they agree.
notes: Optional free text.
```

## Adding a new project type

1. Add one new `risk-patterns/<project-type>.yaml` file.
2. Keep `project_type` stable, lowercase, and hyphenated.
3. Write detection signals as static file, directory, manifest, dependency, or structure facts the audit can observe without running project code.
4. Add concrete risk patterns that describe domain-specific failure modes.
5. Prefer deterministic, machine-checkable `suggested_gate` text when realistic.
6. Use `manual_review_only` only when static or deterministic automation is not reasonable.
7. Run the repository validation tests.

## Limitation

The per-file schema validates file shape, required fields, strict object keys, and allowed detectability values. It does not enforce cross-file uniqueness of `project_type` or risk pattern ids. If this becomes important, add a repository-level validation test.
