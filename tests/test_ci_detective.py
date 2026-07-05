import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cmd(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


class CIDetectiveHistoryTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is not available in this test environment")

    def init_repo(self, root: Path):
        run_cmd(["git", "init"], cwd=root)
        run_cmd(["git", "config", "user.email", "ci@example.test"], cwd=root)
        run_cmd(["git", "config", "user.name", "CI Test"], cwd=root)

    def commit_file(self, root: Path, filename: str, message: str):
        path = root / filename
        path.write_text(message + "\n", encoding="utf-8")
        run_cmd(["git", "add", filename], cwd=root)
        run_cmd(["git", "commit", "-m", message], cwd=root)

    def run_detective(self, root: Path):
        output = root / "report.json"
        run_cmd([sys.executable, str(ROOT / "tools" / "ci_detective.py"), "--repo-root", str(root), "--out", str(output)], cwd=ROOT)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_detects_english_and_persian_history_signals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo)
            self.commit_file(repo, "a.txt", "fix validator")
            self.commit_file(repo, "b.txt", "bug in schema")
            self.commit_file(repo, "c.txt", "رفع گزارش")
            self.commit_file(repo, "d.txt", "اصلاح schema")

            report = self.run_detective(repo)

            english = "\n".join(item["summary"] for item in report["historical_signals"])
            persian = "\n".join(item["summary"] for item in report["persian_historical_signals"])

            self.assertIn("fix validator", english)
            self.assertIn("bug in schema", english)
            self.assertIn("رفع گزارش", persian)
            self.assertIn("اصلاح schema", persian)

    def test_no_invented_signals_when_history_has_no_keyword_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo)
            self.commit_file(repo, "a.txt", "initial commit")

            report = self.run_detective(repo)

            self.assertEqual(report["historical_signals"], [])
            self.assertEqual(report["persian_historical_signals"], [])
