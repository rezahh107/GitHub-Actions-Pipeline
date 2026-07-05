import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "scope_claim_audit.py"


class ScopeClaimAuditToolTests(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_tool_check_succeeds_for_valid_examples(self):
        for name in [
            "scope_claim_audit.example.json",
            "scope_claim_audit.true-negative.example.json",
            "scope_claim_audit.ambiguous.example.json",
        ]:
            with self.subTest(name=name):
                result = self.run_tool("--check", f"examples/{name}")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Scope Claim Audit package OK", result.stdout)
                self.assertIn("enforcement_mode=advisory", result.stdout)

    def test_tool_writes_markdown_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "summary.md"
            result = self.run_tool(
                "--input",
                "examples/scope_claim_audit.example.json",
                "--out",
                str(out),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Scope Claim Audit advisory summary", text)
            self.assertIn("scope_underreported", text)
            self.assertIn("Enforcement mode: `advisory`", text)

    def test_tool_exits_non_zero_for_malformed_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.json"
            bad.write_text('{"schema_version":"0.1"}', encoding="utf-8")
            result = self.run_tool("--check", str(bad))
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing required fields", result.stderr)

    def test_tool_does_not_fail_merely_because_result_is_mismatch(self):
        source = json.loads((ROOT / "examples" / "scope_claim_audit.example.json").read_text(encoding="utf-8"))
        source["scope_claim_result"] = "mismatch"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "mismatch.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            result = self.run_tool("--check", str(path))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("result=mismatch", result.stdout)

    def test_tool_rejects_short_reviewed_head_sha(self):
        source = json.loads((ROOT / "examples" / "scope_claim_audit.example.json").read_text(encoding="utf-8"))
        source["reviewed_head_sha"] = "1234567"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "short-sha.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            result = self.run_tool("--check", str(path))
            self.assertNotEqual(0, result.returncode)
            self.assertIn("40-character lowercase hexadecimal SHA", result.stderr)

    def test_tool_allows_blocking_true_only_with_wired_enforcement_gate(self):
        source = json.loads((ROOT / "examples" / "scope_claim_audit.example.json").read_text(encoding="utf-8"))
        source["enforcement_mode"] = "enforced"
        source["blocking"] = True
        source["wired_enforcement_gate"] = {
            "target_repository": "rezahh107/example-contract-repo",
            "gate_name": "Scope Claim Audit enforcement",
            "workflow_path": ".github/workflows/scope-claim-audit.yml",
            "check_name": "scope-claim-audit / enforce",
            "enforcement_evidence": "required status check is configured for this workflow",
            "policy_reference": "repository branch protection policy",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "enforced.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            result = self.run_tool("--check", str(path))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("enforcement_mode=enforced", result.stdout)

    def test_tool_rejects_blocking_true_without_enforcement_metadata(self):
        source = json.loads((ROOT / "examples" / "scope_claim_audit.example.json").read_text(encoding="utf-8"))
        source["blocking"] = True
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad-blocking.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            result = self.run_tool("--check", str(path))
            self.assertNotEqual(0, result.returncode)
            self.assertIn("blocking=true requires enforcement_mode=enforced", result.stderr)
