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


def _create_muster_with_normal_md(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "Sl.No",
            "EmployeeCode",
            "EmployeeName",
            "Department",
            "Grade",
            "1",
            "2",
            "P",
            "Normal MD",
            "OT Hrs",
            "OT Amount",
            "Final Days",
        ],
        [1, "E9004", "Normal MD Worker", "COLD DRAW", "Labour", "P", "A", 31, 20, 15, 99999, 31],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_duplicate_employee_rows(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, "E9005", "Duplicate Worker", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
        [2, "E9005", "Duplicate Worker", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_serial_as_emp_code(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, 1, "Bad Row", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
        [2, "E9006", "Valid Worker", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_short_numeric_unknown_code(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, 62, "Noise", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
        [2, "E9007", "Valid Worker 2", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_name_match_code_mismatch(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, "1009", "Valid Worker 3", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def _create_muster_with_unknown_long_code(file_path: Path) -> Path:
    rows = [
        ["Company", "", "", "", "", "", "", "", "", ""],
        ["Period", "Nov 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, "1009", "Unknown Noise", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
        [2, "E9008", "Valid Worker 4", "COLD DRAW", "Labour", "P", "P", 26, 10, 26],
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


def test_normal_md_and_ot_hours_are_taken_from_muster_columns(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_4.db")
    manager.add_employee(
        {
            "emp_code": "E9004",
            "emp_name": "Normal MD Worker",
            "father_husband_name": "Parent Four",
            "dob": "01-01-1993",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2023",
            "bank_account_no": "123456789017",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234J",
            "aadhaar_no": "123412341238",
            "uan_no": "123456789017",
            "esic_no": "ESIC9004",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_normal_md(tmp_path / "muster_with_normal_md.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    # Should prioritize "Normal MD" over generic "P"/"Final Days".
    assert float(parsed.iloc[0]["present_days"]) == 20.0
    # Should use OT hours column, not OT amount.
    assert float(parsed.iloc[0]["ot_hours"]) == 15.0


def test_duplicate_employee_rows_are_collapsed(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_5.db")
    manager.add_employee(
        {
            "emp_code": "E9005",
            "emp_name": "Duplicate Worker",
            "father_husband_name": "Parent Five",
            "dob": "01-01-1994",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2024",
            "bank_account_no": "123456789018",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234K",
            "aadhaar_no": "123412341239",
            "uan_no": "123456789018",
            "esic_no": "ESIC9005",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_duplicate_employee_rows(tmp_path / "muster_duplicates.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9005"


def test_serial_number_not_used_as_employee_code(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_6.db")
    manager.add_employee(
        {
            "emp_code": "E9006",
            "emp_name": "Valid Worker",
            "father_husband_name": "Parent Six",
            "dob": "01-01-1995",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2025",
            "bank_account_no": "123456789019",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234L",
            "aadhaar_no": "123412341240",
            "uan_no": "123456789019",
            "esic_no": "ESIC9006",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_serial_as_emp_code(tmp_path / "muster_serial_as_code.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9006"


def test_short_numeric_unknown_emp_code_is_skipped(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_7.db")
    manager.add_employee(
        {
            "emp_code": "E9007",
            "emp_name": "Valid Worker 2",
            "father_husband_name": "Parent Seven",
            "dob": "01-01-1995",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2025",
            "bank_account_no": "123456789020",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234M",
            "aadhaar_no": "123412341241",
            "uan_no": "123456789020",
            "esic_no": "ESIC9007",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_short_numeric_unknown_code(tmp_path / "muster_short_numeric_code.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9007"


def test_name_match_keeps_excel_emp_code(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_8.db")
    manager.add_employee(
        {
            "emp_code": "E9008",
            "emp_name": "Valid Worker 3",
            "father_husband_name": "Parent Eight",
            "dob": "01-01-1995",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2025",
            "bank_account_no": "123456789021",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234N",
            "aadhaar_no": "123412341242",
            "uan_no": "123456789021",
            "esic_no": "ESIC9008",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_name_match_code_mismatch(tmp_path / "muster_name_match.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "1009"


def test_unknown_long_code_skipped_in_strict_mode(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_9.db")
    manager.add_employee(
        {
            "emp_code": "E9008",
            "emp_name": "Valid Worker 4",
            "father_husband_name": "Parent Nine",
            "dob": "01-01-1995",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2025",
            "bank_account_no": "123456789022",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234O",
            "aadhaar_no": "123412341243",
            "uan_no": "123456789022",
            "esic_no": "ESIC9009",
            "department": "COLD DRAW",
        }
    )

    muster_file = _create_muster_with_unknown_long_code(tmp_path / "muster_unknown_long_code.xlsx")
    parsed = parse_muster_roll(muster_file, employee_manager=manager)

    assert len(parsed) == 1
    assert parsed.iloc[0]["emp_code"] == "E9008"
