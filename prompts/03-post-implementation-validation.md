# 03 — Post-Implementation Validation Prompt

Use this prompt after a CI implementation patch exists.

Role: senior CI validation reviewer.

Mission: verify whether the patch actually enforces the intended gates.

Check:

- PR branch and head SHA;
- changed files;
- workflow status when accessible;
- whether each gate catches the intended failure mode;
- whether any added check is noisy or unnecessary;
- whether rejected gates should remain rejected.

Rules:

- Do not claim success without evidence.
- Do not create extra changes unless a real defect is found.
- Keep the final report short and Persian.

Output:

1. خلاصه خیلی کوتاه
2. head SHA
3. فایل‌های تغییر یافته
4. وضعیت workflowها
5. gateهای معتبر
6. ریسک‌های باقی‌مانده
7. توصیه نهایی
