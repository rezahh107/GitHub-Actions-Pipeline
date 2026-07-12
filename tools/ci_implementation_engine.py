"""Opt-in, recipe-bound implementation planning and recoverable file creation.

Report generation is read-only. Mutation requires an explicit recipe allowlist, a
clean Git worktree, a canonical lowercase exact HEAD SHA, and non-overwriting
paths. Repository commands are never executed because checked-out code is
untrusted input.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

from tools.ci_models import run_git
from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

DEFAULT_RECIPES = Path(__file__).resolve().parents[1] / "profiles" / "implementation-recipes.v1.json"
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
FailureInjector = Callable[[str], None]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_recipes(path: Path | None = None) -> dict[str, object]:
    source = path or DEFAULT_RECIPES
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpgradeContractError("IMPLEMENTATION_RECIPES_UNAVAILABLE", f"Could not read implementation recipes {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpgradeContractError("IMPLEMENTATION_RECIPES_INVALID_JSON", f"Implementation recipes {source} are invalid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("implementation_recipe_version") != "1.0.0" or not isinstance(data.get("recipes"), list):
        raise UpgradeContractError("IMPLEMENTATION_RECIPES_INVALID_SHAPE", "Implementation recipe registry must use version 1.0.0 and contain recipes.")
    return data


def _cap_state(model: dict[str, object], capability_id: str) -> str:
    for item in model.get("capabilities", []):
        if isinstance(item, dict) and item.get("capability_id") == capability_id:
            return str(item.get("state"))
    return "unknown"


def _unique_candidate(model: dict[str, object], category: str, prefix: str) -> tuple[str | None, list[dict[str, object]]]:
    candidates = [item for item in model.get("command_candidates", {}).get(category, []) if isinstance(item, dict) and isinstance(item.get("command"), str) and str(item["command"]).startswith(prefix)]
    unique = {str(item["command"]): item for item in candidates}
    return (next(iter(unique)) if len(unique) == 1 else None), sorted(unique.values(), key=lambda item: str(item["command"]))


def _python_workflow(install_command: str, test_command: str) -> str:
    return f'''name: Repository Upgrade Tests

on:
  pull_request:

permissions:
  contents: read

concurrency:
  group: repository-upgrade-tests-${{{{ github.event.pull_request.number || github.ref }}}}
  cancel-in-progress: true

jobs:
  tests:
    name: repository-upgrade-tests
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - name: Checkout
        uses: actions/checkout@{CHECKOUT_SHA}
        with:
          fetch-depth: 1
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@{SETUP_PYTHON_SHA}
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: {install_command}
      - name: Run tests
        run: {test_command}
'''


def build_implementation_package(report: dict[str, object], repo_root: Path, recipe_catalog: dict[str, object] | None = None) -> dict[str, object]:
    catalog = recipe_catalog or load_recipes()
    model = report["repository_model"]
    root = repo_root.resolve()
    phase_1 = report.get("staged_upgrade", {}).get("phase_1", [])
    recommendations = {str(item.get("recommendation_id")): item for item in phase_1 if isinstance(item, dict)}
    actions: list[dict[str, object]] = []
    for recipe in sorted(catalog["recipes"], key=lambda item: str(item.get("recipe_id"))):
        matched = next((recommendation_id for recommendation_id in recipe.get("recommendation_ids", []) if recommendation_id in recommendations), None)
        if not matched:
            continue
        recipe_id = str(recipe["recipe_id"])
        target = str(recipe["target_path"])
        preconditions: list[dict[str, object]] = []
        capability = str(recipe["affected_capability"])
        state = _cap_state(model, capability)
        preconditions.append({"precondition_id": "capability_not_operational", "status": "pass" if state not in {"operational", "not_applicable"} else "fail", "evidence": [capability, state]})
        preconditions.append({"precondition_id": "supported_language", "status": "pass" if recipe.get("supported_language") in model.get("languages", []) else "fail", "evidence": [str(recipe.get("supported_language"))]})
        install, install_evidence = _unique_candidate(model, "install", "python ")
        test, test_evidence = _unique_candidate(model, "test", "python ")
        preconditions.append({"precondition_id": "unique_install_command", "status": "pass" if install else "fail", "evidence": [str(item.get("basis")) for item in install_evidence]})
        preconditions.append({"precondition_id": "unique_test_command", "status": "pass" if test else "fail", "evidence": [str(item.get("basis")) for item in test_evidence]})
        destination = root / target
        preconditions.append({"precondition_id": "target_absent", "status": "pass" if not destination.exists() and not destination.is_symlink() else "fail", "evidence": [target]})
        content = _python_workflow(install, test) if install and test else None
        status = "applicable" if content and all(item["status"] == "pass" for item in preconditions) else "blocked"
        diagnostics: list[dict[str, object]] = []
        if status == "blocked":
            diagnostics.append(diagnostic("IMPLEMENTATION_RECIPE_BLOCKED", f"Recipe {recipe_id} cannot be applied because one or more deterministic preconditions failed.", affected_area=target, evidence_references=[str(value) for precondition in preconditions for value in precondition["evidence"]], repair_hint="Resolve ambiguous commands, unsupported language, existing target path, or operational capability before applying."))
        actions.append({
            "action_id": f"action:{recipe_id}:{matched}",
            "recipe_id": recipe_id,
            "recommendation_id": matched,
            "status": status,
            "operation": "create_file",
            "path": target,
            "content_sha256": _sha(content) if content else None,
            "proposed_content": content,
            "preconditions": preconditions,
            "validation_commands": list(recipe.get("validation_commands", [])),
            "diagnostics": diagnostics,
            "evidence": evidence("derived", [matched, *[str(item.get("basis")) for item in install_evidence + test_evidence]], "Action was produced only from a versioned recipe and deterministic command-resolution preconditions.", confidence="high" if status == "applicable" else "medium"),
        })
    counts = {state: sum(1 for item in actions if item["status"] == state) for state in ("applicable", "blocked", "unsupported")}
    return {"implementation_contract_version": "1.0.0", "mutation_default": "dry_run", "repository": report.get("repository"), "analysis_basis_sha256": report.get("analysis_basis_sha256"), "actions": actions, "summary": counts, "security_boundary": "No repository command is executed. Applying requires canonical exact HEAD, clean worktree, explicit recipe allowlist, path containment, non-overwriting writes, and an external recovery journal."}


def _git_head_and_clean(root: Path) -> tuple[str, str]:
    ok, head = run_git(root, ["rev-parse", "HEAD"])
    if not ok:
        raise UpgradeContractError("IMPLEMENTATION_GIT_HEAD_UNAVAILABLE", f"Could not resolve Git HEAD: {head}")
    ok, status = run_git(root, ["status", "--porcelain"])
    if not ok:
        raise UpgradeContractError("IMPLEMENTATION_GIT_STATUS_UNAVAILABLE", f"Could not inspect Git status: {status}")
    return head, status


def _lexical_destination(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise UpgradeContractError("IMPLEMENTATION_PATH_INVALID", f"Action path must be a normalized relative path without traversal: {relative}")
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise UpgradeContractError("IMPLEMENTATION_SYMLINK_PATH", f"Refusing a target path that traverses a symlink: {relative}")
    destination = root.joinpath(*candidate.parts)
    try:
        destination.resolve().relative_to(root)
    except ValueError as exc:
        raise UpgradeContractError("IMPLEMENTATION_PATH_ESCAPE", f"Action path escapes repository root: {relative}") from exc
    return destination


def apply_implementation_package(repo_root: Path, package: dict[str, object], *, allowed_recipe_ids: set[str], expected_head_sha: str, failure_injector: FailureInjector | None = None) -> dict[str, object]:
    if not GIT_SHA.fullmatch(expected_head_sha):
        raise UpgradeContractError("IMPLEMENTATION_EXPECTED_HEAD_INVALID", "expected_head_sha must be exactly 40 lowercase hexadecimal characters.")
    root = repo_root.resolve()
    head, status = _git_head_and_clean(root)
    if head != expected_head_sha:
        raise UpgradeContractError("IMPLEMENTATION_HEAD_MISMATCH", f"Expected HEAD {expected_head_sha}, found {head}.")
    if status.strip():
        raise UpgradeContractError("IMPLEMENTATION_WORKTREE_DIRTY", "Refusing implementation because the Git worktree is not clean.")
    if not allowed_recipe_ids:
        raise UpgradeContractError("IMPLEMENTATION_RECIPE_ALLOWLIST_REQUIRED", "At least one --allow-recipe value is required.")

    results: list[dict[str, object]] = []
    created: list[Path] = []
    created_directories: list[Path] = []
    try:
        for action in package.get("actions", []):
            if not isinstance(action, dict):
                raise UpgradeContractError("IMPLEMENTATION_ACTION_INVALID", "Every implementation action must be an object.")
            recipe = str(action.get("recipe_id"))
            path = str(action.get("path"))
            content = action.get("proposed_content")
            if recipe not in allowed_recipe_ids:
                results.append({"action_id": action.get("action_id"), "status": "skipped", "reason": "recipe_not_allowlisted"})
                continue
            if action.get("status") != "applicable" or action.get("operation") != "create_file" or not isinstance(content, str):
                results.append({"action_id": action.get("action_id"), "status": "skipped", "reason": "action_not_applicable"})
                continue
            destination = _lexical_destination(root, path)
            if destination.exists() or destination.is_symlink():
                raise UpgradeContractError("IMPLEMENTATION_TARGET_EXISTS", f"Refusing to overwrite or follow existing target: {path}")
            if _sha(content) != action.get("content_sha256"):
                raise UpgradeContractError("IMPLEMENTATION_CONTENT_HASH_MISMATCH", f"Proposed content hash mismatch for {path}.")
            if failure_injector:
                failure_injector("before_target_creation")
            missing_parents: list[Path] = []
            parent = destination.parent
            while parent != root and not parent.exists():
                missing_parents.append(parent)
                parent = parent.parent
            destination.parent.mkdir(parents=True, exist_ok=True)
            for created_parent in reversed(missing_parents):
                if created_parent not in created_directories:
                    created_directories.append(created_parent)
            fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, 0o644)
                os.link(temporary, destination)
                os.unlink(temporary)
                created.append(destination)
                if failure_injector:
                    failure_injector("after_target_creation")
            except Exception:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
            results.append({"action_id": action.get("action_id"), "status": "applied", "path": path, "content_sha256": _sha(content), "created_directories": [directory.relative_to(root).as_posix() for directory in missing_parents], "validation_commands": action.get("validation_commands", []), "validation_status": "not_executed_untrusted_repository_boundary"})
    except Exception:
        rollback_errors = []
        for destination in reversed(created):
            try:
                destination.unlink(missing_ok=True)
            except OSError as exc:
                rollback_errors.append(f"{destination}: {exc}")
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except FileNotFoundError:
                pass
            except OSError as exc:
                rollback_errors.append(f"{directory}: {exc}")
        if rollback_errors:
            raise UpgradeContractError("IMPLEMENTATION_APPLY_ROLLBACK_FAILED", "; ".join(rollback_errors))
        raise
    return {"implementation_contract_version": "1.0.0", "expected_head_sha": expected_head_sha, "observed_head_sha": head, "results": results, "repository_commands_executed": False, "transactional_create_rollback": True, "next_step": "Persist report, package, and result through the external recovery transaction before considering the operation complete."}


def rollback_implementation_result(repo_root: Path, result: dict[str, object], *, failure_injector: FailureInjector | None = None) -> list[str]:
    """Idempotently remove only files created by a matching implementation result."""
    root = repo_root.resolve()
    removed: list[str] = []
    for item in reversed(result.get("results", [])):
        if not isinstance(item, dict) or item.get("status") != "applied":
            continue
        relative = str(item.get("path"))
        destination = _lexical_destination(root, relative)
        if not destination.exists() and not destination.is_symlink():
            continue
        if destination.is_symlink() or not destination.is_file():
            raise UpgradeContractError("IMPLEMENTATION_ROLLBACK_PATH_UNSAFE", f"Rollback target is not a regular file: {relative}")
        current_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if current_hash != item.get("content_sha256"):
            raise UpgradeContractError("IMPLEMENTATION_ROLLBACK_CONTENT_CHANGED", f"Rollback target content changed after apply: {relative}")
        if failure_injector:
            failure_injector("during_rollback")
        destination.unlink()
        removed.append(relative)
        for directory_relative in item.get("created_directories", []):
            directory = _lexical_destination(root, str(directory_relative))
            try:
                directory.rmdir()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise UpgradeContractError("IMPLEMENTATION_ROLLBACK_DIRECTORY_NOT_EMPTY", f"Could not remove transaction-created directory {directory_relative}: {exc}") from exc
    return removed
