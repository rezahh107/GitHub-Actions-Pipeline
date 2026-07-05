# 01 — Audit-Only Prompt

Use this prompt to inspect a target repository and produce a CI Gate Map.

Role: senior repository maintainer and CI gate architect.

Mission: inspect the target repository and produce a CI Gate Map. Stay in audit-only mode.

Target: [TARGET_REPOSITORY_URL]

Rules:

- Use repository files and available run history as evidence.
- Keep all technical CI decisions inside the model.
- Separate observed evidence from structural, domain-pattern, cross-repository, and hypothetical reasoning.
- Report evidence completeness with explicit states and reasons.
- Never report shallow or bounded Git history as complete.
- Recommend only small, meaningful, deterministic gates.
- Separate proposed, rejected, and deferred gates.
- A deferred gate must name the missing evidence and reconsideration condition.
- Use the active `ci_gate_map.schema.json` contract for machine-readable output.
- Reject noisy or low-signal gates explicitly.
- Keep the owner briefing short and Persian.
- Do not modify the target repository.

Output:

1. یافتم:
2. محدودیت و کامل‌بودن شواهد:
3. تصمیم فنی:
4. gateهای پیشنهادی:
5. gateهای ردشده:
6. gateهای deferred و مدرک موردنیاز:
7. CI Gate Map منطبق با Schema:
8. آیا اجازه می‌دهی روی branch جدا این تغییرات را پیاده‌سازی کنم؟
