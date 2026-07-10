# GitHub Actions Pipeline

Current version: `0.2.0`.

## Quick Start

Start trigger: `شروع`

Canonical response: `آماده‌ام. آدرس ریپو را برای بررسی بفرست.`

Next input: target repository URL or `owner/repository`.

## Operating modes

- `minimal-safe-ci`: preserves the original conservative, low-noise gate design.
- `deep-repository-upgrade`: builds a component-aware repository model, audits capabilities and blind spots, ranks high-leverage improvements, and produces a staged upgrade plan.

Local executable entry:

```bash
python tools/repository_upgrade.py \
  --repo-root /path/to/target \
  --mode deep-repository-upgrade \
  --out /tmp/repository-upgrade.json \
  --summary-out /tmp/repository-upgrade.fa.md
```

The deep mode does not treat file presence as proof that a capability is operational. It separates observed failures, structural invariants, and baseline capabilities, and reports unavailable evidence explicitly.

## References

- Start entry: `START.md`
- Start contract: `protocol/start.yaml`
- Start schema: `schemas/start.schema.json`
- Full original project reference: `docs/project-reference.md`
- Deep upgrade protocol: `pipeline/09-repository-capability-audit.md`
- Deep upgrade status: `docs/DEEP_REPOSITORY_UPGRADE_STATUS.md`
- Upgrade report schema: `schemas/repository_upgrade_report.schema.json`
