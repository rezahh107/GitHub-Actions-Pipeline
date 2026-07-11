"""Deterministic IANA identifier validation from one pinned tzdata release."""
from __future__ import annotations

from functools import lru_cache
import hashlib
from importlib import metadata
from pathlib import Path
import re

from tools.ci_schedule_semantics import ScheduleSemanticError

PINNED_TZDATA_VERSION = "2026.3"
PINNED_IANA_VERSION = "2026c"
PINNED_ZONE_COUNT = 598
PINNED_ZONES_SHA256 = "5027e610a10d1983d286e21fa1fb718f0d34704446cb37f707e81707bb3c1244"
PINNED_INIT_SHA256 = "e2bfe056345bcf835f032f930539fb7f113b4d6e94c16e596ed30f09ee48e09a"

_SPECIAL = frozenset({
    "localtime", "posixrules", "leapseconds", "tzdata.zi", "zone.tab",
    "zone1970.tab", "iso3166.tab", "+VERSION",
})
_SPECIAL_PREFIXES = ("posix/", "right/", "SystemV/")
_KEY = re.compile(r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$")
_IANA = re.compile(rb'^IANA_VERSION = "([0-9]{4}[a-z])"$', re.MULTILINE)


def _safe_file(dist: metadata.Distribution, relative: str) -> Path:
    base = Path(dist.locate_file("")).resolve(strict=True)
    candidate = Path(dist.locate_file(relative))
    if candidate.is_symlink():
        raise OSError(f"{relative!r} is a symlink")
    resolved = candidate.resolve(strict=True)
    resolved.relative_to(base)
    if not resolved.is_file():
        raise OSError(f"{relative!r} is not a regular file")
    return resolved


@lru_cache(maxsize=1)
def pinned_identifier_state() -> tuple[frozenset[str] | None, str | None]:
    try:
        dist = metadata.distribution("tzdata")
        if dist.version != PINNED_TZDATA_VERSION:
            return None, f"expected tzdata=={PINNED_TZDATA_VERSION}, observed {dist.version!r}"
        zones = _safe_file(dist, "tzdata/zones").read_bytes()
        init = _safe_file(dist, "tzdata/__init__.py").read_bytes()
    except (metadata.PackageNotFoundError, OSError, ValueError) as exc:
        return None, f"pinned timezone data could not be verified: {exc}"

    if hashlib.sha256(zones).hexdigest() != PINNED_ZONES_SHA256:
        return None, "pinned timezone identifier manifest hash mismatch"
    if hashlib.sha256(init).hexdigest() != PINNED_INIT_SHA256:
        return None, "pinned timezone package identity hash mismatch"
    match = _IANA.search(init)
    if not match or match.group(1).decode("ascii") != PINNED_IANA_VERSION:
        return None, "pinned timezone package IANA version mismatch"
    try:
        names = zones.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        return None, f"timezone identifier manifest is not strict UTF-8: {exc}"
    if len(names) != PINNED_ZONE_COUNT or len(set(names)) != len(names):
        return None, "timezone identifier manifest count or uniqueness mismatch"
    if any(
        not name or name != name.strip() or not _KEY.fullmatch(name)
        or name in _SPECIAL or name.startswith(_SPECIAL_PREFIXES)
        for name in names
    ):
        return None, "timezone identifier manifest contains an invalid or host-special key"
    identifiers = frozenset(names)
    if not {"Etc/UTC", "UTC", "America/New_York", "Asia/Baku"} <= identifiers:
        return None, "timezone identifier manifest is missing required controls"
    return identifiers, None


def validate_pinned_timezone(value: object) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            "timezone must be a normalized non-empty IANA identifier string.",
        )
    if len(value) > 255 or value in _SPECIAL or value.startswith(_SPECIAL_PREFIXES):
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            f"timezone {value!r} is host-special or outside the pinned identifier contract.",
        )
    identifiers, error = pinned_identifier_state()
    if identifiers is None:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE",
            error or "pinned timezone identifier set is unavailable",
        )
    if value not in identifiers:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            f"timezone {value!r} is not in tzdata {PINNED_TZDATA_VERSION} / IANA {PINNED_IANA_VERSION}.",
        )
