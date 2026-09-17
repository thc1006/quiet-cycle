"""Civil dates and explicit-offset instants; never use the host clock or timezone."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
INSTANT_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
MIN_DATE = date(1900, 1, 1)
MAX_DATE = date(2200, 12, 31)


def civil(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(DATE_PATTERN, value):
        raise ValueError("invalid_civil_date")
    parsed = date.fromisoformat(value)
    if not MIN_DATE <= parsed <= MAX_DATE:
        raise ValueError("date_outside_domain")
    return value


def instant(value: str) -> str:
    """Normalize RFC3339 instants to UTC milliseconds. Reject lossy precision."""
    if not isinstance(value, str) or not re.fullmatch(INSTANT_PATTERN, value):
        raise ValueError("invalid_instant")
    civil(value[:10])
    if value.endswith("-00:00"):
        raise ValueError("unknown_offset")
    if not value.endswith("Z"):
        hh, mm = int(value[-5:-3]), int(value[-2:])
        if hh > 14 or mm > 59 or (hh == 14 and mm != 0):
            raise ValueError("offset_outside_domain")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    civil(dt.date().isoformat())
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def local_day(value: str, offset: int) -> str:
    if type(offset) is not int or not -840 <= offset <= 840:
        raise ValueError("invalid_offset")
    dt = datetime.fromisoformat(instant(value).replace("Z", "+00:00"))
    return civil((dt + timedelta(minutes=offset)).date().isoformat())


def add_days(value: str, n: int) -> str:
    if type(n) is not int:
        raise ValueError("integer_days_required")
    return civil((date.fromisoformat(civil(value)) + timedelta(days=n)).isoformat())


def day_difference(end: str, start: str) -> int:
    return (date.fromisoformat(civil(end)) - date.fromisoformat(civil(start))).days
