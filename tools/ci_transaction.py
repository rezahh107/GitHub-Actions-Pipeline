"""Recoverable repository-mutation plus evidence-persistence transaction."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Callable

from tools.ci_implementation_engine import apply_implementation_package, rollback_implementation_result
from tools.ci_models import canonical_json_bytes, serialize_report
from tools.ci_upgrade_models import UpgradeContractError

JOURNAL_VERSION = "1.0.0"
FailureInjector = Callable[[str], None]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _parent_has_symlink(path: Path) -> bool:
    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    return False


def _prepare_external_path(path: Path, root: Path, *, label: str) -> None:
    if _inside(path, root):
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_INSIDE_REPOSITORY", f"{label} must be outside the target repository: {path}")
    if path.exists() or path.is_symlink():
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_EXISTS", f"Refusing to overwrite existing {label}: {path}")
    if _parent_has_symlink(path.parent):
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_SYMLINK_PARENT", f"Refusing {label} under a symlinked parent: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, probe = tempfile.mkstemp(prefix=".preflight-", dir=path.parent)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_PREFLIGHT_FAILED", f"Cannot create {label} in {path.parent}: {exc}") from exc


def _atomic_create(path: Path, text: str) -> str:
    encoded = text.encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    linked = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        os.unlink(temporary)
    except Exception:
        if linked:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return hashlib.sha256(encoded).hexdigest()


def _atomic_replace(path: Path, text: str) -> None:
    encoded = text.encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _journal_text(journal: dict[str, object]) -> str:
    return json.dumps(journal, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _append_event(journal_path: Path, journal: dict[str, object], event: str, **fields: object) -> None:
    updated = deepcopy(journal)
    events = list(updated["events"])
    record: dict[str, object] = {"sequence": len(events), "event": event}
    record.update(fields)
    events.append(record)
    updated["events"] = events
    updated["status"] = event
    _atomic_replace(journal_path, _journal_text(updated))
    journal.clear()
    journal.update(updated)


def _remove_output(path: Path, expected_sha: str) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_file():
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_ROLLBACK_UNSAFE", f"Output rollback target is not a regular file: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise UpgradeContractError("IMPLEMENTATION_OUTPUT_ROLLBACK_CHANGED", f"Output changed after transaction write: {path}")
    path.unlink()


def execute_recoverable_implementation(repo_root: Path, report: dict[str, object], package: dict[str, object], *, allowed_recipe_ids: set[str], expected_head_sha: str, report_out: Path, package_out: Path, result_out: Path, journal_out: Path, failure_injector: FailureInjector | None = None) -> dict[str, object]:
    """Apply and persist as one recoverable operation.

    A durable pre-mutation plan is written outside the repository. Any later
    failure rolls back created repository files and transaction-created outputs.
    If rollback itself fails, the journal remains ``recovery_required`` with
    deterministic paths and hashes.
    """
    root = repo_root.resolve()
    outputs = {"report": report_out.resolve(), "package": package_out.resolve(), "result": result_out.resolve()}
    journal_path = journal_out.resolve()
    for label, path in [*outputs.items(), ("recovery journal", journal_path)]:
        _prepare_external_path(path, root, label=label)

    report_text = serialize_report(report)
    package_text = serialize_report(package)
    action_plan = [{"action_id": item.get("action_id"), "path": item.get("path"), "content_sha256": item.get("content_sha256")} for item in package.get("actions", []) if isinstance(item, dict) and item.get("status") == "applicable" and item.get("recipe_id") in allowed_recipe_ids]
    plan = {
        "expected_head_sha": expected_head_sha,
        "repository_root": str(root),
        "package_sha256": hashlib.sha256(package_text.encode("utf-8")).hexdigest(),
        "allowed_recipe_ids": sorted(allowed_recipe_ids),
        "actions": action_plan,
        "outputs": {label: str(path) for label, path in outputs.items()},
    }
    transaction_id = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()
    journal: dict[str, object] = {"journal_contract_version": JOURNAL_VERSION, "transaction_id": transaction_id, "status": "planned", "plan": plan, "events": [{"sequence": 0, "event": "planned"}]}
    _atomic_create(journal_path, _journal_text(journal))

    result: dict[str, object] | None = None
    written: dict[str, str] = {}
    try:
        if failure_injector:
            failure_injector("before_mutation")
        _append_event(journal_path, journal, "mutating")
        result = apply_implementation_package(root, package, allowed_recipe_ids=allowed_recipe_ids, expected_head_sha=expected_head_sha, failure_injector=failure_injector)
        result.update({"transaction_id": transaction_id, "transaction_status": "committed", "recovery_journal": str(journal_path)})
        result_text = serialize_report(result)
        _append_event(journal_path, journal, "mutated", applied_count=sum(1 for item in result["results"] if item.get("status") == "applied"))

        payloads = {"report": report_text, "package": package_text, "result": result_text}
        for label in ("report", "package", "result"):
            if failure_injector:
                failure_injector(f"during_{label}_write")
            digest = _atomic_create(outputs[label], payloads[label])
            written[label] = digest
            _append_event(journal_path, journal, "persisting", output_label=label, path=str(outputs[label]), sha256=digest)
        _append_event(journal_path, journal, "committed", output_digests=written)
        return result
    except Exception as exc:
        try:
            _append_event(journal_path, journal, "failed", error_code=getattr(exc, "code", type(exc).__name__), message=str(exc))
        except OSError:
            pass
        rollback_errors: list[str] = []
        try:
            for label, digest in reversed(list(written.items())):
                _remove_output(outputs[label], digest)
            if result is not None:
                rollback_implementation_result(root, result, failure_injector=failure_injector)
        except Exception as rollback_exc:
            rollback_errors.append(f"{getattr(rollback_exc, 'code', type(rollback_exc).__name__)}: {rollback_exc}")
        if rollback_errors:
            try:
                _append_event(journal_path, journal, "recovery_required", rollback_errors=rollback_errors)
            except OSError:
                pass
            raise UpgradeContractError("IMPLEMENTATION_TRANSACTION_RECOVERY_REQUIRED", f"Mutation or persistence failed and rollback was incomplete. Recovery journal: {journal_path}. {'; '.join(rollback_errors)}") from exc
        try:
            _append_event(journal_path, journal, "rolled_back", rolled_back_outputs=sorted(written))
        except OSError:
            pass
        raise UpgradeContractError("IMPLEMENTATION_TRANSACTION_ROLLED_BACK", f"Mutation or persistence failed; repository and transaction outputs were rolled back. Recovery journal: {journal_path}. Cause: {getattr(exc, 'code', type(exc).__name__)}: {exc}") from exc
