# 01 — Audit-Only Prompt

Use this prompt to inspect a target repository and produce a CI Gate Map.

Role: senior repository maintainer and CI gate architect.

Mission: inspect the target repository and produce a CI Gate Map. Stay in audit-only mode.

Target: [TARGET_REPOSITORY_URL]

Rules:

- Use repository files as evidence.
- Keep all technical CI decisions inside the model.
- Separate confirmed evidence from inference.
- Recommend only small, meaningful, deterministic gates.
- Reject noisy or low-signal gates explicitly.
- Keep the owner briefing short and Persian.

Output:

1. یافتم:
2. تصمیم فنی:
3. gateهای پیشنهادی:
4. gateهای رد شده:
5. محدودیت شواهد:
6. آیا اجازه می‌دهی روی branch جدا این تغییرات را پیاده‌سازی کنم؟
