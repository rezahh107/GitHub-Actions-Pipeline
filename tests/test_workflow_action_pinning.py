import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>[^#\n]+?)\s*(?:#.*)?$")
FULL_LENGTH_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


def workflow_files():
    return sorted(
        path
        for suffix in ("*.yml", "*.yaml")
        for path in WORKFLOW_DIR.glob(suffix)
    )


def normalize_uses_ref(raw_ref: str) -> str:
    return raw_ref.strip().strip('"\'')


def find_unpinned_external_uses(text: str, source: str):
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = USES_RE.match(line)
        if not match:
            continue

        uses_ref = normalize_uses_ref(match.group("ref"))
        if uses_ref.startswith("./"):
            continue
        if uses_ref.startswith("docker://"):
            continue
        if "@" not in uses_ref:
            yield f"{source}:{line_number}: {uses_ref} has no @ref"
            continue

        action_name, ref = uses_ref.rsplit("@", 1)
        if not action_name or not FULL_LENGTH_SHA_RE.fullmatch(ref):
            yield (
                f"{source}:{line_number}: {uses_ref} is not pinned to a "
                "full-length 40-character commit SHA"
            )


class WorkflowActionPinningTests(unittest.TestCase):
    def test_external_github_actions_are_pinned_to_full_length_shas(self):
        failures = []
        for workflow in workflow_files():
            relative = workflow.relative_to(ROOT).as_posix()
            failures.extend(find_unpinned_external_uses(workflow.read_text(encoding="utf-8"), relative))

        self.assertEqual([], failures, "\n".join(failures))

    def test_static_check_catches_tag_ref_drift(self):
        workflow_text = """
name: Drift Example
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
      - uses: ./local-action
      - uses: docker://alpine:3.20
"""

        failures = list(find_unpinned_external_uses(workflow_text, "example.yml"))

        self.assertEqual(1, len(failures))
        self.assertIn("actions/checkout@v4", failures[0])
