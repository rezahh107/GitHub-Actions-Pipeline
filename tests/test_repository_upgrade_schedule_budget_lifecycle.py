from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ci_schedule_resource_patch as resource
from tools.ci_repository_model import build_repository_model


def write_workflow(path: Path, days: range) -> None:
    schedule = "".join(
        f"    - cron: '0,59 0,23 {day} 1 *'\n"
        for day in days
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: lifecycle fixture\non:\n  schedule:\n"
        + schedule
        + "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: python -m unittest discover -s tests\n",
        encoding="utf-8",
    )


class RepositoryScheduleBudgetLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        resource._STATE.set(None)

    def test_separate_model_builds_on_same_root_receive_fresh_repository_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "tests" / "test_x.py"
            tests.parent.mkdir(parents=True)
            tests.write_text("import unittest\n", encoding="utf-8")

            first = root / ".github" / "workflows" / "a.yml"
            write_workflow(first, range(1, 10, 2))
            with patch.object(resource, "REPOSITORY_LIMIT", 350):
                first_model = build_repository_model(root)
                self.assertEqual(first_model["workflows"][0]["parse_status"], "parsed")

                first.unlink()
                second = root / ".github" / "workflows" / "z.yml"
                write_workflow(second, range(1, 10, 2))
                second_model = build_repository_model(root)

        self.assertEqual(second_model["workflows"][0]["parse_status"], "parsed")
        self.assertNotIn(
            "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            {item["code"] for item in second_model["unresolved_evidence"]},
        )


if __name__ == "__main__":
    unittest.main()
