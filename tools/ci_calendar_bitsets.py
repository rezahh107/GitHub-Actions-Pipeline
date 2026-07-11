"""One-cycle calendar bitsets replacing repeated date-by-date schedule scans."""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from tools import ci_schedule_semantics as _semantics

_CYCLE_DAYS = 146097
_ORIGINAL_PARSE = _semantics.parse_cron_expression


def _set(mask: bytearray, index: int) -> None:
    mask[index >> 3] |= 1 << (index & 7)


@lru_cache(maxsize=1)
def calendar_masks() -> tuple[int, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    size = (_CYCLE_DAYS + 7) // 8
    months = [bytearray(size) for _ in range(13)]
    month_days = [bytearray(size) for _ in range(32)]
    week_days = [bytearray(size) for _ in range(7)]
    current = date(2000, 1, 1)
    for index in range(_CYCLE_DAYS):
        _set(months[current.month], index)
        _set(month_days[current.day], index)
        _set(week_days[(current.weekday() + 1) % 7], index)
        current += timedelta(days=1)
    convert = lambda values: tuple(int.from_bytes(value, "little") for value in values)
    return (1 << _CYCLE_DAYS) - 1, convert(months), convert(month_days), convert(week_days)


def predicate_key(parsed: object) -> tuple[object, ...]:
    return (
        tuple(sorted(parsed.day_of_month.values)), parsed.day_of_month.unrestricted,
        tuple(sorted(parsed.month.values)),
        tuple(sorted(parsed.day_of_week.values)), parsed.day_of_week.unrestricted,
    )


def predicate_work_units(key: tuple[object, ...]) -> int:
    dom, _, months, weekdays, _ = key
    return 8 + len(dom) + len(months) + len(weekdays)


def _union(values: tuple[int, ...], masks: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result |= masks[value]
    return result


@lru_cache(maxsize=4096)
def consecutive_dates(key: tuple[object, ...]) -> bool:
    dom, dom_any, months, weekdays, weekday_any = key
    all_dates, month_masks, dom_masks, weekday_masks = calendar_masks()
    month_mask = _union(months, month_masks)
    dom_mask = _union(dom, dom_masks)
    weekday_mask = _union(weekdays, weekday_masks)
    if dom_any and weekday_any:
        day_mask = all_dates
    elif dom_any:
        day_mask = weekday_mask
    elif weekday_any:
        day_mask = dom_mask
    else:
        day_mask = dom_mask | weekday_mask
    matched = month_mask & day_mask
    return bool(matched & (matched >> 1)) or bool(
        (matched & 1) and (matched & (1 << (_CYCLE_DAYS - 1)))
    )


@lru_cache(maxsize=2048)
def _cached_parse(expression: str):
    return _ORIGINAL_PARSE(expression)


def cached_parse(expression: object):
    if not isinstance(expression, str):
        return _ORIGINAL_PARSE(expression)
    return _cached_parse(expression)


def install_calendar_bitsets() -> None:
    _semantics.parse_cron_expression = cached_parse
    _semantics._has_consecutive_matching_dates = lambda parsed: consecutive_dates(predicate_key(parsed))
