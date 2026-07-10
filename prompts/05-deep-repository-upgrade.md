# Deep Repository Upgrade Prompt

Use this prompt only with operating mode `deep-repository-upgrade`.

## Required evidence questions

Return concise evidence and decision rationale for:

1. executable architecture, components, and critical paths;
2. principal behavioral and structural contracts;
3. failures that are silent or detected too late;
4. high-risk areas without a machine-checkable oracle;
5. unprotected invariants;
6. nominal versus operational capabilities;
7. failures current CI cannot detect;
8. testability gaps;
9. the highest realistic risk-reduction improvement;
10. whether testability, validation, or observability must improve before another gate;
11. immediate, staged, rejected, and intentionally uncovered recommendations.

## Rules

- Do not expose private chain-of-thought.
- Do not treat file presence as operational capability.
- Keep observed failure, structural invariant, and baseline capability channels independent.
- Treat cold-start as limited evidence, not proof that controls are unnecessary.
- Use the bounded ordinal ranking contract.
- Emit `status: unavailable` when telemetry or semantic evidence is missing.
- Preserve the existing `ci_detective` contract.
- Produce an executable Phase 1 package, not only prose.
- Never claim validation without exact command results and exit codes.
