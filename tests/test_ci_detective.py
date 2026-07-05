import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-05T00:00:00Z"


def run_cmd(cmd, cwd, check=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


class CIDetectiveTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is not available in this test environment")

    def init_repo(self, root: Path):
        run_cmd(["git", "init"], cwd=root)
        run_cmd(["git", "config", "user.email", "ci@example.test"], cwd=root)
        run_cmd(["git", "config", "user.name", "CI Test"], cwd=root)

    def commit_file(self, root: Path, filename: str, message: str):
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(message + "\n", encoding="utf-8")
        run_cmd(["git", "add", filename], cwd=root)
        run_cmd(["git", "commit", "-m", message], cwd=root)

    def run_detective(self, root: Path, output: Path | None = None):
        output = output or (root / "report.json")
        result = run_cmd(
            [
                sys.executable,
                str(ROOT / "tools" / "ci_detective.py"),
                "--repo-root",
                str(root),
                "--out",
                str(output),
                "--generated-at",
                FIXED_TIME,
            ],
            cwd=ROOT,
        )
        return result, json.loads(output.read_text(encoding="utf-8"))

    def test_detects_english_and_persian_history_signals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo)
            self.commit_file(repo, "a.txt", "fix validator")
            self.commit_file(repo, "b.txt", "bug in schema")
            self.commit_file(repo, "c.txt", "رفع گزارش")
            self.commit_file(repo, "d.txt", "اصلاح schema")

            _, report = self.run_detective(repo)

            english = "\n".join(item["summary"] for item in report["historical_signals"])
            persian = "\n".join(
                item["summary"] for item in report["persian_historical_signals"]
            )
            self.assertIn("fix validator", english)
            self.assertIn("bug in schema", english)
            self.assertIn("رفع گزارش", persian)
            self.assertIn("اصلاح schema", persian)
            self.assertEqual(report["evidence_completeness"]["git_history"]["status"], "complete")
            self.assertFalse(report["evidence_completeness"]["git_history"]["is_shallow"])

    def test_no_invented_signals_when_history_has_no_keyword_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo)
            self.commit_file(repo, "a.txt", "initial commit")

            _, report = self.run_detective(repo)

            self.assertEqual(report["historical_signals"], [])
            self.assertEqual(report["persian_historical_signals"], [])

    def test_shallow_clone_is_never_reported_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = base / "source"
            shallow = base / "shallow"
            source.mkdir()
            self.init_repo(source)
            self.commit_file(source, "a.txt", "initial commit")
            self.commit_file(source, "b.txt", "fix first regression")
            self.commit_file(source, "c.txt", "fix second regression")

            run_cmd(
                ["git", "clone", "--depth", "1", source.as_uri(), str(shallow)],
                cwd=base,
            )
            _, report = self.run_detective(shallow, base / "shallow-report.json")

            completeness = report["evidence_completeness"]["git_history"]
            self.assertEqual(completeness["status"], "partial")
            self.assertTrue(completeness["is_shallow"])
            limitation_codes = {item["code"] for item in report["limitations"]}
            self.assertIn("GIT_HISTORY_SHALLOW", limitation_codes)

    def test_non_git_directory_reports_unavailable_without_signals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "README.md").write_text("example\n", encoding="utf-8")

            _, report = self.run_detective(root)

            self.assertEqual(
                report["evidence_completeness"]["git_history"]["status"],
                "unavailable",
            )
            self.assertEqual(report["historical_signals"], [])
            self.assertEqual(report["hotspots"], [])

    def test_output_is_byte_identical_with_fixed_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.init_repo(root)
            self.commit_file(root, "a.txt", "fix deterministic report")
            output = root / "report.json"

            self.run_detective(root, output)
            first_bytes = output.read_bytes()
            self.run_detective(root, output)
            second_bytes = output.read_bytes()

            self.assertEqual(first_bytes, second_bytes)

    def test_hotspot_ties_use_path_as_deterministic_tie_breaker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.init_repo(root)
            self.commit_file(root, "z.txt", "add z")
            self.commit_file(root, "a.txt", "add a")

            _, report = self.run_detective(root)
            tied_paths = [
                item["path"]
                for item in report["hotspots"]
                if item["change_count"] == 1
            ]
            self.assertEqual(tied_paths, sorted(tied_paths))

    def test_missing_root_returns_stable_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing"
            output = Path(tmpdir) / "report.json"
            result = run_cmd(
                [
                    sys.executable,
                    str(ROOT / "tools" / "ci_detective.py"),
                    "--repo-root",
                    str(missing),
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("CI_DETECTIVE_ROOT_NOT_FOUND", result.stderr)
            self.assertFalse(output.exists())
