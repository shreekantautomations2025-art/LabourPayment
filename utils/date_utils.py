"""Date and period helpers."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Tuple


def month_name(month: int) -> str:
    """Return month label from month number."""
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    return calendar.month_name[month]


def month_short_name(month: int) -> str:
    """Return short month label from month number."""
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    return calendar.month_abbr[month]


def get_period_key(month: int, year: int) -> str:
    """Return YYYY_MM period key."""
    return f"{year}_{month:02d}"


def parse_month_year(month: int | str, year: int | str) -> Tuple[int, int]:
    """Parse and normalize month/year values."""
    month_num = int(month)
    year_num = int(year)
    if month_num < 1 or month_num > 12:
        raise ValueError("month must be between 1 and 12")
    if year_num < 1900 or year_num > 9999:
        raise ValueError("year must be between 1900 and 9999")
    return month_num, year_num


def next_month_due_date(day: int, month: int, year: int) -> date:
    """Return due date in next month at given day."""
    if month == 12:
        due_month = 1
        due_year = year + 1
    else:
        due_month = month + 1
        due_year = year
    last_day = calendar.monthrange(due_year, due_month)[1]
    return date(due_year, due_month, min(day, last_day))


def parse_flexible_date(value: object) -> str:
    """Return date string in ISO format if possible."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text

