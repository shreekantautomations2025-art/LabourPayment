"""Tests for muster parser edge cases."""

from pathlib import Path

import pandas as pd

from modules.employee_manager import EmployeeManager
from modules.muster_parser import parse_muster_roll


def _create_muster_with_summary(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, "E9001", "Valid Employee", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
        ["", "", "", "", "", "08:00", "08:01", "", "", ""],
        ["PayDays Summary", "PayDays Summary", "PayDays Summary", "", "", "", "", 1702, 4500, 1702],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def test_summary_rows_are_skipped(tmp_path):
    manager = EmployeeManager(tmp_path / "employees.db")
    manager.add_employee(
        {
            "emp_code": "E9001",
            "emp_name": "Valid Employee",
            "father_husband_name": "Parent Name",
            "dob": "01-01-1990",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2020",
            "bank_account_no": "123456789012",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234F",
            "aadhaar_no": "123412341234",
            "uan_no": "123456789012",
            "esic_no": "ESIC9001",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_summary(tmp_path / "muster_with_summary.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9001"
    assert float(parsed.iloc[0]["present_days"]) == 26.0
