# 07 — Validation and Reporting

## Purpose

Define how results are checked and reported after an approved CI change.

## Evidence Rule

Report only evidence that is directly available.

Useful evidence includes:

- workflow status;
- exact head SHA;
- changed file list;
- artifact or step summary content;
- PR status;
- output from an available runner or tool.

Do not claim success without evidence.

## Head SHA Rule

When using GitHub Actions evidence, connect the result to the exact branch or PR head SHA.

## Persistence Rule

Raw generated evidence normally belongs in artifacts or step summaries.

Keep long-term repository history for durable decisions, not repeated generated reports.

## Final Persian Report

Include:

- خلاصه خیلی کوتاه؛
- فایل‌های تغییر یافته؛
- ساختار pipeline؛
- schemaها و promptها؛
- ابزار یا workflow اضافه‌شده؛
- اینکه validation چه چیزی را کنترل می‌کند؛
- چیزهایی که عمداً اضافه نشد؛
- evidence موجود؛
- PR link؛
- head SHA؛
- ریسک‌های باقی‌مانده؛
- توصیه نهایی.

## Recommendation Values

Use one of: ready for review, draft, needs more work.
