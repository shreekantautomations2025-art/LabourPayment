"""Durability tests for auto-onboarding and flexible bulk upload."""

from pathlib import Path

import pandas as pd

from modules.employee_manager import EmployeeManager
from modules.payroll_processor import finalize_payroll_from_preview


def _create_preview_file(path: Path, emp_code: str) -> Path:
    df = pd.DataFrame(
        [
            {
                "emp_code": emp_code,
                "emp_name": "Auto Added Worker",
                "father_husband_name": "Unknown",
                "designation": "Labour",
                "department": "COLD DRAW",
                "present_days": 10,
                "ot_hours": 5,
                "advance": 0,
                "other_deduction": 0,
                "approved": "Y",
                "reviewer_remarks": "",
            }
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Editable_Preview", index=False)
        pd.DataFrame([{"Instruction": "test"}]).to_excel(writer, sheet_name="Instructions", index=False)
    return path


def test_finalize_auto_creates_missing_employee(tmp_path):
    manager = EmployeeManager(tmp_path / "employees.db")
    preview = _create_preview_file(tmp_path / "preview_missing_emp.xlsx", "AUTO001")

    result = finalize_payroll_from_preview(
        preview_file=preview,
        month=9,
        year=2025,
        employee_manager=manager,
        output_dir=tmp_path / "output",
        require_approved_rows=True,
        allow_auto_employee_creation=True,
    )
    assert result["employee_count"] == 1
    created = manager.get_employee("AUTO001", include_inactive=False)
    assert created is not None
    assert created["emp_name"] == "Auto Added Worker"


def test_bulk_upload_accepts_json_and_txt(tmp_path):
    manager = EmployeeManager(tmp_path / "employees_bulk.db")

    json_file = tmp_path / "employees.json"
    pd.DataFrame(
        [
            {
                "emp_code": "J001",
                "emp_name": "Json User",
                "father_husband_name": "Json Parent",
                "dob": "01-01-1990",
                "gender": "Male",
                "designation": "Labour",
                "doj": "01-01-2020",
                "bank_account_no": "123456789012",
                "ifsc_code": "SBIN0001234",
                "bank_name": "SBI",
                "pan_no": "ABCDE1234F",
                "aadhaar_no": "123412341234",
                "uan_no": "123456789012",
                "esic_no": "ESICJ001",
                "department": "COLD DRAW",
            }
        ]
    ).to_json(json_file, orient="records")

    txt_file = tmp_path / "employees.txt"
    txt_file.write_text(
        "emp_code|emp_name|father_husband_name|dob|gender|designation|doj|bank_account_no|ifsc_code|bank_name|pan_no|aadhaar_no|uan_no|esic_no|department\n"
        "T001|Txt User|Txt Parent|01-01-1992|Male|Labour|01-01-2021|123456789013|SBIN0001234|SBI|ABCDE1234G|123412341235|123456789013|ESICT001|PQF MILL\n",
        encoding="utf-8",
    )

    json_result = manager.bulk_upload_employees(json_file)
    txt_result = manager.bulk_upload_employees(txt_file)

    assert json_result["success"] == 1
    assert txt_result["success"] == 1
    assert manager.get_employee("J001", include_inactive=False) is not None
    assert manager.get_employee("T001", include_inactive=False) is not None
