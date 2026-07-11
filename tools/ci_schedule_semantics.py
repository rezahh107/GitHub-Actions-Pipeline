"""Bounded semantic validation for represented GitHub Actions schedules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError as _ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - exercised through patched capability tests
    _ZoneInfo = None

    class _ZoneInfoNotFoundError(KeyError):
        """Compatibility placeholder when zoneinfo is unavailable."""


SCHEDULE_SEMANTICS_CONTRACT_VERSION = "1.0.0"
MINIMUM_INTERVAL_MINUTES = 5
MAX_CRON_LENGTH = 256
MAX_FIELD_TERMS = 64
_GREGORIAN_CYCLE_DAYS = 146097

_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_DAY_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}


class ScheduleSemanticError(ValueError):
    """Stable fail-closed validation error for a represented schedule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _FieldSpec:
    minimum: int
    maximum: int
    names: dict[str, int] | None = None

    @property
    def span(self) -> int:
        return self.maximum - self.minimum + 1


@dataclass(frozen=True)
class _ParsedField:
    values: frozenset[int]
    unrestricted: bool


@dataclass(frozen=True)
class _ParsedCron:
    minute: _ParsedField
    hour: _ParsedField
    day_of_month: _ParsedField
    month: _ParsedField
    day_of_week: _ParsedField


_FIELD_SPECS = (
    _FieldSpec(0, 59),
    _FieldSpec(0, 23),
    _FieldSpec(1, 31),
    _FieldSpec(1, 12, _MONTH_NAMES),
    _FieldSpec(0, 6, _DAY_NAMES),
)


def _cron_error(message: str) -> ScheduleSemanticError:
    return ScheduleSemanticError("WORKFLOW_SCHEDULE_CRON_INVALID", message)


def _parse_value(token: str, spec: _FieldSpec) -> int:
    normalized = token.upper()
    if spec.names and normalized in spec.names:
        return spec.names[normalized]
    if not token.isascii() or not token.isdigit():
        raise _cron_error(f"Unsupported cron value {token!r}.")
    value = int(token, 10)
    if value < spec.minimum or value > spec.maximum:
        raise _cron_error(
            f"Cron value {token!r} is outside {spec.minimum}-{spec.maximum}."
        )
    return value


def _parse_term(term: str, spec: _FieldSpec) -> set[int]:
    if not term:
        raise _cron_error("Cron fields cannot contain empty list terms.")
    if term.count("/") > 1:
        raise _cron_error(f"Cron term {term!r} contains multiple step operators.")

    base, separator, step_text = term.partition("/")
    step = 1
    if separator:
        if not step_text.isascii() or not step_text.isdigit():
            raise _cron_error(f"Cron step {step_text!r} must be a positive integer.")
        step = int(step_text, 10)
        if step < 1 or step > spec.span:
            raise _cron_error(
                f"Cron step {step!r} is outside the bounded range 1-{spec.span}."
            )

    if base == "*":
        start, end = spec.minimum, spec.maximum
    elif base.count("-") == 1:
        start_text, end_text = base.split("-", 1)
        start, end = _parse_value(start_text, spec), _parse_value(end_text, spec)
        if start > end:
            raise _cron_error(f"Cron range {base!r} must be ascending.")
    elif "-" in base:
        raise _cron_error(f"Cron term {base!r} contains an unsupported range form.")
    else:
        start = _parse_value(base, spec)
        end = spec.maximum if separator else start

    return set(range(start, end + 1, step))


def _parse_field(expression: str, spec: _FieldSpec) -> _ParsedField:
    terms = expression.split(",")
    if len(terms) > MAX_FIELD_TERMS:
        raise _cron_error(
            f"Cron field has more than {MAX_FIELD_TERMS} list terms."
        )
    values: set[int] = set()
    for term in terms:
        values.update(_parse_term(term, spec))
    if not values:
        raise _cron_error("Cron field resolves to no values.")
    return _ParsedField(frozenset(values), expression == "*")


def parse_cron_expression(expression: object) -> _ParsedCron:
    """Parse the bounded documented five-field POSIX cron subset."""
    if not isinstance(expression, str) or not expression.strip():
        raise _cron_error("cron must be a non-empty string.")
    if len(expression) > MAX_CRON_LENGTH:
        raise _cron_error(
            f"cron exceeds the bounded length of {MAX_CRON_LENGTH} characters."
        )
    if any(character.isspace() and character != " " for character in expression):
        raise _cron_error("cron fields must be separated by spaces only.")
    fields = expression.split()
    if len(fields) != 5:
        raise _cron_error("cron must contain exactly five fields.")
    parsed = tuple(
        _parse_field(field, spec)
        for field, spec in zip(fields, _FIELD_SPECS, strict=True)
    )
    return _ParsedCron(*parsed)


def _date_matches(parsed: _ParsedCron, candidate: date) -> bool:
    if candidate.month not in parsed.month.values:
        return False
    day_of_month_matches = candidate.day in parsed.day_of_month.values
    cron_day_of_week = (candidate.weekday() + 1) % 7
    day_of_week_matches = cron_day_of_week in parsed.day_of_week.values

    if parsed.day_of_month.unrestricted and parsed.day_of_week.unrestricted:
        return True
    if parsed.day_of_month.unrestricted:
        return day_of_week_matches
    if parsed.day_of_week.unrestricted:
        return day_of_month_matches
    return day_of_month_matches or day_of_week_matches


def _has_consecutive_matching_dates(parsed: _ParsedCron) -> bool:
    current = date(2000, 1, 1)
    first_matches = _date_matches(parsed, current)
    previous_matches = first_matches
    for _ in range(1, _GREGORIAN_CYCLE_DAYS):
        current += timedelta(days=1)
        current_matches = _date_matches(parsed, current)
        if previous_matches and current_matches:
            return True
        previous_matches = current_matches
    return previous_matches and first_matches


def _minimum_interval_minutes(parsed: _ParsedCron) -> int | None:
    times = sorted(
        hour * 60 + minute
        for hour in parsed.hour.values
        for minute in parsed.minute.values
    )
    if len(times) > 1:
        same_day = min(right - left for left, right in zip(times, times[1:]))
        if same_day < MINIMUM_INTERVAL_MINUTES:
            return same_day

    cross_day = 1440 - times[-1] + times[0]
    if (
        cross_day < MINIMUM_INTERVAL_MINUTES
        and _has_consecutive_matching_dates(parsed)
    ):
        return cross_day
    return None


def validate_cron_expression(expression: object) -> None:
    parsed = parse_cron_expression(expression)
    interval = _minimum_interval_minutes(parsed)
    if interval is not None:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT",
            f"cron can run {interval} minute(s) apart; the minimum supported interval is {MINIMUM_INTERVAL_MINUTES} minutes.",
        )


@lru_cache(maxsize=1)
def _timezone_database_available() -> bool:
    if _ZoneInfo is None:
        return False
    for key in ("Etc/UTC", "UTC"):
        try:
            _ZoneInfo(key)
        except (KeyError, ValueError, OSError):
            continue
        return True
    return False


def validate_timezone_name(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            "timezone must be a non-empty IANA timezone string.",
        )
    if len(value) > 255:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            "timezone exceeds the bounded length of 255 characters.",
        )
    if _ZoneInfo is None:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE",
            "The runtime does not provide zoneinfo and cannot verify the timezone.",
        )
    try:
        _ZoneInfo(value)
    except _ZoneInfoNotFoundError as exc:
        code = (
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID"
            if _timezone_database_available()
            else "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE"
        )
        message = (
            f"timezone {value!r} is not present in the available IANA timezone database."
            if code.endswith("INVALID")
            else "The runtime has no usable IANA timezone database and cannot verify the timezone."
        )
        raise ScheduleSemanticError(code, message) from exc
    except ValueError as exc:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            f"timezone {value!r} is not a normalized IANA timezone key.",
        ) from exc
    except OSError as exc:
        raise ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE",
            "The runtime could not read its IANA timezone database.",
        ) from exc
