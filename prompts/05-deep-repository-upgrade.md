# Deep Repository Upgrade Prompt

Use only with operating mode `deep-repository-upgrade`.

Return concise evidence and decision rationale for:

1. executable architecture, declared components, and bounded critical paths;
2. which relationships are resolved, inferred, partial, or unresolved;
3. principal behavioral and structural contracts;
4. failures that are silent or detected too late;
5. high-risk areas without a machine-checkable oracle;
6. nominal versus operational capabilities;
7. failures current CI cannot detect;
8. testability and observability gaps;
9. the highest realistic risk-reduction improvements;
10. whether validation/testability must improve before another gate;
11. immediate, staged, rejected, and intentionally uncovered recommendations;
12. applicable implementation recipes and failed preconditions.

Rules:

- Do not expose private chain-of-thought.
- Do not treat file presence as operational capability.
- Do not call manifest boundaries semantic ownership.
- Keep observed failure, structural invariant, and baseline capability channels independent.
- Treat cold-start as limited evidence, not proof that controls are unnecessary.
- Use the versioned ranking policy and include factor-level rationale.
- Preserve profile contribution conflicts rather than silently resolving them.
- Emit `unavailable` or `unresolved` when proof is missing.
- Produce a dry-run implementation package; never mutate unless explicit exact-HEAD recipe authorization exists.
- Never execute repository commands as part of generic mutation.
- Profile evolution is review-only and requires exact-head validated outcomes from distinct repositories.
- Never claim validation without exact command results and exit codes.
