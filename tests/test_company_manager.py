"""Tests for multi-company configuration and company-specific payroll behavior."""

from pathlib import Path

import pandas as pd

from modules.company_manager import CompanyManager
from modules.employee_manager import EmployeeManager
from modules.payroll_processor import process_monthly_payroll


def _create_single_employee_muster(file_path: Path, emp_code: str, emp_name: str) -> Path:
    rows = [
        ["Test Muster", "", "", "", "", "", "", "", "", ""],
        ["Period", "Aug 2025", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Sl.No", "EmployeeCode", "EmployeeName", "Department", "Grade", "1", "2", "P", "OT Hrs", "Final Days"],
        [1, emp_code, emp_name, "COLD DRAW", "Labour", "P", "P", 10, 5, 10],
        ["", "", "", "", "", "08:00", "08:00", "", "", ""],
    ]
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)
    return file_path


def test_company_crud_and_configuration(tmp_path):
    db_path = tmp_path / "companies.db"
    manager = CompanyManager(db_path)

    # Default company should exist after initialization.
    all_companies = manager.get_all_companies(active_only=False)
    assert len(all_companies) >= 1

    new_id = manager.add_company(
        {
            "company_name": "Acme Contractor",
            "contractor_name": "Acme Contractor",
            "labour_daily_rate": 900.0,
            "supervisor_daily_rate": 850.0,
            "labour_ot_rate": 120.0,
            "supervisor_ot_rate": 130.0,
        }
    )
    company = manager.get_company(new_id)
    assert company is not None
    assert company["company_name"] == "Acme Contractor"

    assert manager.update_company(new_id, {"labour_daily_rate": 950.0}) is True
    updated = manager.get_company(new_id)
    assert updated is not None
    assert float(updated["labour_daily_rate"]) == 950.0

    config = manager.get_company_configuration(new_id)
    assert config["company_id"] == new_id
    assert len(config["pt_slabs"]) == 3


def test_company_specific_rates_used_in_payroll(tmp_path):
    db_path = tmp_path / "payroll_multi_company.db"
    company_manager = CompanyManager(db_path)
    employee_manager = EmployeeManager(db_path)

    company_id = company_manager.add_company(
        {
            "company_name": "Rate Test Co",
            "contractor_name": "Rate Test Co",
            "labour_daily_rate": 1000.0,
            "supervisor_daily_rate": 1100.0,
            "labour_ot_rate": 150.0,
            "supervisor_ot_rate": 170.0,
        }
    )

    employee_added = employee_manager.add_employee(
        {
            "emp_code": "RTC001",
            "emp_name": "Rahul Test",
            "father_husband_name": "Mohan Test",
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
            "esic_no": "ESIC12345",
            "department": "COLD DRAW",
            "company_id": company_id,
        }
    )
    assert employee_added is True

    muster_file = _create_single_employee_muster(tmp_path / "rate_test_muster.xlsx", "RTC001", "Rahul Test")
    result = process_monthly_payroll(
        muster_file=muster_file,
        month=8,
        year=2025,
        employee_manager=employee_manager,
        company_id=company_id,
        output_dir=tmp_path / "output",
    )

    # Gross = (10 * 1000) + (5 * 150) = 10,750
    assert abs(float(result["totals"]["gross_salary"]) - 10750.0) < 0.01
    assert Path(result["output_paths"]["pf_ecr_csv"]).exists()

