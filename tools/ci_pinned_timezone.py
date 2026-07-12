"""Deterministic IANA identifier and fixed-offset validation from one pinned tzdata release."""
from __future__ import annotations

from functools import lru_cache
import hashlib
from importlib import metadata
from pathlib import Path
import re
import struct

from tools.ci_schedule_semantics import ScheduleSemanticError

PINNED_TZDATA_VERSION = "2026.3"
PINNED_IANA_VERSION = "2026c"
PINNED_ZONE_COUNT = 598
PINNED_ZONES_SHA256 = "5027e610a10d1983d286e21fa1fb718f0d34704446cb37f707e81707bb3c1244"
PINNED_INIT_SHA256 = "e2bfe056345bcf835f032f930539fb7f113b4d6e94c16e596ed30f09ee48e09a"

# Multi-entry schedule aggregation is intentionally limited to timezone files whose
# exact bytes are pinned here and whose TZif payload independently proves one
# non-DST type with no transitions or future transition rule. The name is never
# accepted as proof by itself.
PINNED_FIXED_OFFSET_TZIF_SHA256 = {
    "UTC": "fddce1e648a1732ac29afd9a16151b2973cdf082e7ec0c690f7e42be6b598b93",
    "Etc/UTC": "fddce1e648a1732ac29afd9a16151b2973cdf082e7ec0c690f7e42be6b598b93",
    "Etc/GMT": "dc4a07571b10884e4f4f3450c9d1a1cbf4c03ef53d06ed2e4ea152d9eba5d5d7",
    "Etc/GMT+5": "4d9e6a6a810b96ccd6fd9e4576a00430a93c63fc6ee5785904d654728e794ab3",
}

_SPECIAL = frozenset({
    "localtime", "posixrules", "leapseconds", "tzdata.zi", "zone.tab",
    "zone1970.tab", "iso3166.tab", "+VERSION",
})
_SPECIAL_PREFIXES = ("posix/", "right/", "SystemV/")
_KEY = re.compile(r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$")
_IANA = re.compile(rb'^IANA_VERSION = "([0-9]{4}[a-z])"$', re.MULTILINE)
_FIXED_POSIX_TAIL = re.compile(
    rb"(?:[A-Za-z]{3,}|<[^>\n]{1,32}>)[+-]?(?:[0-9]|1[0-9]|2[0-4])"
    rb"(?::[0-5][0-9](?::[0-5][0-9])?)?"
)
_TZIF_HEADER_SIZE = 44
_TZIF_COUNT_STRUCT = struct.Struct(">6I")
_TZIF_TYPE_STRUCT = struct.Struct(">lBB")


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


def _tzif_block(data: bytes, offset: int, time_size: int) -> tuple[bytes, tuple[int, ...], int, int]:
    if len(data) < offset + _TZIF_HEADER_SIZE or data[offset:offset + 4] != b"TZif":
        raise ValueError("timezone transition file has no complete TZif header")
    version = data[offset + 4:offset + 5]
    counts = _TZIF_COUNT_STRUCT.unpack(data[offset + 20:offset + 44])
    isutccnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
    data_start = offset + _TZIF_HEADER_SIZE
    end = data_start + (
        timecnt * time_size
        + timecnt
        + typecnt * 6
        + charcnt
        + leapcnt * (time_size + 4)
        + isstdcnt
        + isutccnt
    )
    if end > len(data):
        raise ValueError("timezone transition file contains a truncated TZif block")
    return version, counts, data_start, end


def _tzif_proves_fixed_offset(data: bytes) -> bool:
    version, counts, data_start, block_end = _tzif_block(data, 0, 4)
    time_size = 4
    if version in {b"2", b"3", b"4"}:
        version, counts, data_start, block_end = _tzif_block(data, block_end, 8)
        time_size = 8
        if data[block_end:block_end + 1] != b"\n" or not data.endswith(b"\n"):
            raise ValueError("timezone transition file has no bounded POSIX tail")
        posix_tail = data[block_end + 1:-1]
    else:
        raise ValueError("timezone transition file does not expose a 64-bit TZif contract")

    isutccnt, isstdcnt, leapcnt, timecnt, typecnt, _charcnt = counts
    if timecnt != 0 or typecnt != 1 or leapcnt != 0:
        return False
    if isutccnt not in {0, 1} or isstdcnt not in {0, 1}:
        return False
    type_offset = data_start + timecnt * time_size + timecnt
    _gmtoff, isdst, _abbr_index = _TZIF_TYPE_STRUCT.unpack(
        data[type_offset:type_offset + _TZIF_TYPE_STRUCT.size]
    )
    return isdst == 0 and _FIXED_POSIX_TAIL.fullmatch(posix_tail) is not None


@lru_cache(maxsize=64)
def pinned_fixed_offset_state(value: str) -> tuple[bool | None, str | None]:
    """Return fixed-offset proof state from exact pinned TZif bytes.

    ``True`` means the exact file hash is pinned and its TZif payload contains no
    transition, DST type, leap table, or future transition rule. ``False`` means
    the identifier is valid but outside this intentionally bounded proof set.
    ``None`` means a pinned proof entry exists but its bytes cannot be verified.
    """
    expected_sha256 = PINNED_FIXED_OFFSET_TZIF_SHA256.get(value)
    if expected_sha256 is None:
        return False, None
    try:
        dist = metadata.distribution("tzdata")
        if dist.version != PINNED_TZDATA_VERSION:
            return None, f"expected tzdata=={PINNED_TZDATA_VERSION}, observed {dist.version!r}"
        data = _safe_file(dist, f"tzdata/zoneinfo/{value}").read_bytes()
    except (metadata.PackageNotFoundError, OSError, ValueError) as exc:
        return None, f"pinned timezone transition data could not be verified: {exc}"
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        return None, f"timezone transition identity mismatch for {value!r}"
    try:
        fixed = _tzif_proves_fixed_offset(data)
    except (ValueError, struct.error) as exc:
        return None, f"timezone transition data for {value!r} is malformed: {exc}"
    if not fixed:
        return None, f"pinned fixed-offset proof for {value!r} no longer matches its TZif semantics"
    return True, None


def validate_fixed_offset_timezone(value: object) -> None:
    """Require an exact pinned no-transition proof for multi-entry aggregation."""
    validate_pinned_timezone(value)
    assert isinstance(value, str)
    fixed, error = pinned_fixed_offset_state(value)
    if fixed is None:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITION_UNVERIFIABLE",
            error or "pinned timezone transition data is unavailable or mismatched.",
        )
    if not fixed:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED",
            f"multi-entry schedules in timezone {value!r} are unsupported because "
            "the pinned fixed-offset proof registry does not establish transition-free semantics.",
        )
