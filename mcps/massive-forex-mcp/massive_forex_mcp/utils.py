from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Literal

CurrencyCode = str
Timespan = Literal["second", "minute", "hour", "day", "week", "month", "quarter", "year"]
SortOrder = Literal["asc", "desc"]
RelativeWeek = Literal["last", "current"]


def clean_currency(code: str) -> str:
    value = code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError(f"Currency code must be three letters, got {code!r}.")
    return value


def clean_forex_ticker(ticker: str) -> str:
    """Normalize EURUSD, EUR/USD, EUR-USD, or C:EURUSD to C:EURUSD."""
    value = ticker.strip().upper()
    if value.startswith("C:"):
        pair = value[2:]
    else:
        pair = value.replace("/", "").replace("-", "").replace("_", "").replace(" ", "")
    if not re.fullmatch(r"[A-Z]{6}", pair):
        raise ValueError(
            "Forex ticker must be a 6-letter pair such as EURUSD, EUR/USD, EUR-USD, or C:EURUSD."
        )
    return f"C:{pair}"


def omit_none(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a YYYY-MM-DD date, got {value!r}.") from exc


def resolve_week_date_range(
    *,
    from_date: str | None,
    to_date: str | None,
    week_number: int | None,
    year: int | None,
    relative_week: RelativeWeek,
) -> tuple[date, date, str]:
    if from_date or to_date:
        if not from_date or not to_date:
            raise ValueError("from_date and to_date must be provided together.")
        start = parse_date(from_date, "from_date")
        end = parse_date(to_date, "to_date")
        if start > end:
            raise ValueError("from_date must be on or before to_date.")
        return start, end, "date_range"

    today = datetime.now().date()
    if week_number is not None:
        if not (1 <= week_number <= 53):
            raise ValueError("week_number must be between 1 and 53.")
        iso_year = year if year is not None else today.isocalendar().year
        try:
            start = date.fromisocalendar(iso_year, week_number, 1)
        except ValueError as exc:
            raise ValueError(f"Week {week_number} is not valid for ISO year {iso_year}.") from exc
        return start, start + timedelta(days=6), "iso_week"

    current_week_start = today - timedelta(days=today.isoweekday() - 1)
    if relative_week == "current":
        return current_week_start, today, "current_week"
    if relative_week == "last":
        start = current_week_start - timedelta(days=7)
        return start, start + timedelta(days=6), "last_week"
    raise ValueError("relative_week must be 'last' or 'current'.")


def date_from_millis(timestamp_ms: int | float | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000).date().isoformat()
