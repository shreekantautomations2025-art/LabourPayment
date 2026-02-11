"""Tests for employee master CRUD."""

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

