"""Tests for employee master CRUD."""

from pathlib import Path

import pandas as pd

from modules.employee_manager import EmployeeManager


def _employee_payload(code: str = "E001") -> dict:
    return {
        "emp_code": code,
        "emp_name": "Ravi Patil",
        "father_husband_name": "Suresh Patil",
        "dob": "01-01-1995",
        "gender": "Male",
        "designation": "Labour",
        "doj": "01-01-2020",
        "bank_account_no": "123456789012",
        "ifsc_code": "SBIN0001234",
        "bank_name": "State Bank of India",
        "pan_no": "ABCDE1234F",
        "aadhaar_no": "123412341234",
        "uan_no": "123456789012",
        "esic_no": "9876543210",
        "department": "COLD DRAW",
    }


def test_employee_crud(tmp_path):
    manager = EmployeeManager(tmp_path / "employees.db")
    payload = _employee_payload()

    assert manager.add_employee(payload) is True
    fetched = manager.get_employee("E001")
    assert fetched is not None
    assert fetched["emp_name"] == "Ravi Patil"

    assert manager.update_employee("E001", {"emp_name": "Ravi S. Patil"}) is True
    updated = manager.get_employee("E001")
    assert updated["emp_name"] == "Ravi S. Patil"

    assert manager.delete_employee("E001", soft_delete=True) is True
    inactive = manager.get_employee("E001", include_inactive=True)
    assert inactive is not None
    assert inactive["is_active"] is False


def test_duplicate_employee_code_rejected(tmp_path):
    manager = EmployeeManager(tmp_path / "employees.db")
    payload = _employee_payload("E002")
    assert manager.add_employee(payload) is True
    assert manager.add_employee(payload) is False


def test_duplicate_employee_code_case_insensitive_rejected(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_case.db")
    assert manager.add_employee(_employee_payload("E003")) is True
    assert manager.add_employee(_employee_payload("e003")) is False


def test_bulk_upload_skips_duplicate_codes_and_normalizes_serial(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_bulk.db")
    upload = pd.DataFrame(
        [
            {
                "Sl.No": 1,
                "Emp Code": "B001",
                "Employee Name": "Bulk One",
                "Father/Husband Name": "Parent One",
                "DOB": "01-01-1990",
                "Gender": "Male",
                "Designation": "Labour",
                "DOJ": "01-01-2020",
                "Bank Account No": "123456789011",
                "IFSC Code": "SBIN0001234",
                "Bank Name": "State Bank of India",
            },
            {
                "Sl.No": 2,
                "Emp Code": "B001",  # duplicate code in same upload
                "Employee Name": "Bulk One Duplicate",
                "Father/Husband Name": "Parent One",
                "DOB": "01-01-1990",
                "Gender": "Male",
                "Designation": "Labour",
                "DOJ": "01-01-2020",
                "Bank Account No": "123456789011",
                "IFSC Code": "SBIN0001234",
                "Bank Name": "State Bank of India",
            },
            {
                "Sl.No": 6,  # non-sequential serial to normalize
                "Emp Code": "B002",
                "Employee Name": "Bulk Two",
                "Father/Husband Name": "Parent Two",
                "DOB": "01-01-1991",
                "Gender": "Male",
                "Designation": "Labour",
                "DOJ": "01-01-2021",
                "Bank Account No": "123456789012",
                "IFSC Code": "SBIN0001234",
                "Bank Name": "State Bank of India",
            },
        ]
    )
    path = Path(tmp_path) / "bulk_employees.xlsx"
    upload.to_excel(path, index=False)

    result = manager.bulk_upload_employees(path)
    assert result["success"] == 2
    assert result["failed"] == 0
    assert manager.get_employee("B001", include_inactive=False) is not None
    assert manager.get_employee("B002", include_inactive=False) is not None

