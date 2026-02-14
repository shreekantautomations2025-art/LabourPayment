"""Validation tests for flexible employee-code matching."""

from __future__ import annotations

import pandas as pd

from modules.validators import validate_muster_roll


def test_validate_muster_roll_allows_leading_zero_alias_match():
    df = pd.DataFrame(
        [
            {
                "emp_code": "2390",
                "emp_name": "Worker One",
                "designation": "Labour",
                "present_days": 26,
                "ot_hours": 10,
            }
        ]
    )
    is_valid, errors, warnings = validate_muster_roll(
        df,
        master_emp_codes={"002390"},
        master_designation_map={"002390": "Labour"},
    )
    assert is_valid is True
    assert errors == []
    assert warnings == []


def test_validate_muster_roll_detects_duplicate_numeric_aliases():
    df = pd.DataFrame(
        [
            {
                "emp_code": "002390",
                "emp_name": "Worker One",
                "designation": "Labour",
                "present_days": 26,
                "ot_hours": 10,
            },
            {
                "emp_code": "2390.0",
                "emp_name": "Worker One Duplicate",
                "designation": "Labour",
                "present_days": 26,
                "ot_hours": 10,
            },
        ]
    )
    is_valid, errors, _ = validate_muster_roll(df, master_emp_codes={"002390"}, master_designation_map={"002390": "Labour"})
    assert is_valid is False
    assert any("Duplicate employee codes" in error for error in errors)

