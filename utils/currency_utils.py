"""Currency and number formatting helpers."""

from __future__ import annotations


def format_indian_number(value: float | int) -> str:
    """Format number in Indian grouping style (e.g., 15,47,321.03)."""
    negative = float(value) < 0
    abs_value = abs(float(value))

    integer_part = int(abs_value)
    decimal_part = int(round((abs_value - integer_part) * 100))
    if decimal_part == 100:
        integer_part += 1
        decimal_part = 0

    int_text = str(integer_part)
    if len(int_text) <= 3:
        grouped = int_text
    else:
        last_three = int_text[-3:]
        rest = int_text[:-3]
        pairs = []
        while len(rest) > 2:
            pairs.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            pairs.insert(0, rest)
        grouped = ",".join(pairs + [last_three])

    sign = "-" if negative else ""
    return f"{sign}{grouped}.{decimal_part:02d}"


def format_inr(value: float | int) -> str:
    """Format rupee amount with Indian numbering style."""
    return f"₹{format_indian_number(value)}"

