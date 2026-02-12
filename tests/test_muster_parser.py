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


def _create_muster_with_contractor_text(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        ["", "Shankar Manik Patil (Beldar)", "", "", "", "", "", "", "", ""],
        [1, "E9002", "Worker Two", "PQF MILL", "Labour", "P", "P", 24, 8, 24],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_numeric_emp_code(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, 281, "Employee Numeric Code", "COLD DRAW", "Labour", "P", "P", 26, 12, 26],
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


def test_non_employee_text_in_emp_code_column_is_skipped(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_2.db")
    manager.add_employee(
        {
            "emp_code": "E9002",
            "emp_name": "Worker Two",
            "father_husband_name": "Parent Two",
            "dob": "01-01-1991",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2021",
            "bank_account_no": "123456789015",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234H",
            "aadhaar_no": "123412341236",
            "uan_no": "123456789015",
            "esic_no": "ESIC9002",
            "department": "PQF MILL",
        }
    )

    muster_file = _create_muster_with_contractor_text(tmp_path / "muster_with_contractor_text.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9002"


def test_numeric_emp_code_matches_zero_padded_master_code(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_3.db")
    manager.add_employee(
        {
            "emp_code": "000281",
            "emp_name": "Employee Numeric Code",
            "father_husband_name": "Parent Three",
            "dob": "01-01-1992",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2022",
            "bank_account_no": "123456789016",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234I",
            "aadhaar_no": "123412341237",
            "uan_no": "123456789016",
            "esic_no": "ESIC9003",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_numeric_emp_code(tmp_path / "muster_numeric_emp_code.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "000281"
