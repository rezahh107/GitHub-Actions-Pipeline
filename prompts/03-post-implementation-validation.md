# 03 — Post-Implementation Validation Prompt

Use this prompt after a CI implementation patch exists.

Role: senior CI validation reviewer.

Mission: verify whether the patch actually enforces the intended gates.

Check:

- PR branch;
- source head SHA;
- tested SHA and tested ref kind;
- base SHA when available;
- changed files;
- workflow status when accessible;
- artifact schema validity and evidence hash;
- whether each gate catches the intended failure mode;
- whether any added check is noisy or unnecessary;
- whether rejected and deferred gates remain correctly classified.

Rules:

- Do not conflate a synthetic PR merge SHA with the PR source head SHA.
- Do not report shallow or bounded history as complete.
- Do not claim success without evidence.
- Do not create extra changes unless a real defect is found.
- Keep the final report short and Persian.

Output:

1. خلاصه خیلی کوتاه
2. source head SHA
3. tested SHA و نوع ref
4. فایل‌های تغییر یافته
5. وضعیت workflowها
6. اعتبار artifact و evidence SHA-256
7. gateهای معتبر
8. gateهای رد یا deferred
9. ریسک‌های باقی‌مانده
10. توصیه نهایی
