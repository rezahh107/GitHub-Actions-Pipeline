import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA_RE = re.compile(r"^[^/@]+/[^/@]+@[0-9a-fA-F]{40}$")


class WorkflowPinningTests(unittest.TestCase):
    def test_external_actions_are_pinned_to_full_sha(self):
        workflow_files = list((ROOT / ".github" / "workflows").glob("*.yml")) + list((ROOT / ".github" / "workflows").glob("*.yaml"))
        self.assertTrue(workflow_files, "expected at least one workflow file")

        offenders = []
        for path in workflow_files:
            text = path.read_text(encoding="utf-8")
            for match in USES_RE.finditer(text):
                ref = match.group(1).strip()
                if ref.startswith("./"):
                    continue
                if not FULL_SHA_RE.match(ref):
                    offenders.append(f"{path.relative_to(ROOT)}: {ref}")

        self.assertEqual(offenders, [], "external actions must be pinned to 40-character SHAs")
