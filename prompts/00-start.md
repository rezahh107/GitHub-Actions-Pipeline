# 00 — Start Prompt

Use this prompt at the beginning of a GitHub-connected model session.

When the user says `شروع`, `شروع کن`, `آغاز`, `start`, `begin`, or `load pipeline` without supplying a target repository, reply with exactly:

```text
آماده‌ام. آدرس ریپو را برای بررسی بفرست.
```

Do not add Markdown, explanation, status, or another question.
Stop immediately after that sentence.

The normative machine-readable contract is `protocol/bootstrap-contract.yaml`.
