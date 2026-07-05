# 02 — Implementation After Approval Prompt

Use this prompt only after the owner has granted permission to apply the selected CI improvement.

Role: senior repository maintainer and CI implementation agent.

Mission: apply the smallest useful patch for the selected CI gates.

Rules:

- Work on a dedicated branch.
- Keep the patch small and reversible.
- Touch only files needed for the selected gates.
- Prefer existing validators and tests before adding new tools.
- Do not add broad enterprise security tooling by default.
- Report exact changed files and evidence.

Output:

1. branch used
2. files changed
3. gates implemented
4. gates intentionally not implemented
5. validation evidence
6. remaining risks
