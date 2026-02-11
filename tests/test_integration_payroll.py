"""Integration test: full payroll processing pipeline."""

from pathlib import Path

import pandas as pd

from modules.employee_manager import EmployeeManager
from modules.payroll_processor import process_monthly_payroll


def _add_test_employees(manager: EmployeeManager) -> None:
    rows = [
        {
            "emp_code": "E101",
            "emp_name": "Amit Kumar",
            "father_husband_name": "Suresh Kumar",
            "dob": "05-03-1992",
            "gender": "Male",
            "designation": "Labour",
            "doj": "01-01-2021",
            "bank_account_no": "111122223333",
            "ifsc_code": "SBIN0001234",
            "bank_name": "State Bank of India",
            "pan_no": "ABCDE1234F",
            "aadhaar_no": "111122223333",
            "uan_no": "123456789012",
            "esic_no": "ESIC001",
            "department": "COLD DRAW",
        },
        {
            "emp_code": "E102",
            "emp_name": "Sunil Patil",
            "father_husband_name": "Prakash Patil",
            "dob": "15-07-1990",
            "gender": "Male",
            "designation": "Supervisor",
            "doj": "10-06-2018",
            "bank_account_no": "444455556666",
            "ifsc_code": "HDFC0001234",
            "bank_name": "HDFC Bank",
            "pan_no": "PQRSX6789L",
            "aadhaar_no": "444455556666",
            "uan_no": "987654321012",
            "esic_no": "ESIC002",
            "department": "ADMIN",
        },
    ]
    for row in rows:
        assert manager.add_employee(row)


def _create_sample_muster(file_path: Path) -> Path:
    rows = [
        ["Shankar Patil Muster Roll", "", "", "", "", "", "", "", "", ""],
        ["Period", "July 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, "E101", "Amit Kumar", "COLD DRAW", "Labour", "P", "P", 26, 16, 26],
        ["", "", "", "", "", "08:00", "08:10", "", "", ""],
        [2, "E102", "Sunil Patil", "ADMIN", "Supervisor", "P", "A", 24, 20, 24],
        ["", "", "", "", "", "08:05", "08:15", "", "", ""],
    ]
    df = pd.DataFrame(rows)
    df.to_excel(file_path, header=False, index=False)
    return file_path


def test_full_monthly_processing(tmp_path):
    manager = EmployeeManager(tmp_path / "employees.db")
    _add_test_employees(manager)
    muster_file = _create_sample_muster(tmp_path / "muster.xlsx")

    result = process_monthly_payroll(
        muster_file=muster_file,
        month=7,
        year=2025,
        employee_manager=manager,
        output_dir=tmp_path / "output",
    )

    assert result["employee_count"] == 2
    assert result["totals"]["gross_salary"] > 0
    for _, file_path in result["output_paths"].items():
        assert Path(file_path).exists()

