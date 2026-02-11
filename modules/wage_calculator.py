"""Wage calculation logic for employee payroll."""

from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd

from config import LABOUR_DAILY_RATE, LABOUR_OT_RATE, SUPERVISOR_DAILY_RATE, SUPERVISOR_OT_RATE
from modules.statutory_calculator import calculate_esic, calculate_pf, calculate_pt


def _money(value: float) -> float:
    return round(float(value), 2)


def get_rates(designation: str) -> Dict[str, float]:
    """Determine daily and OT rates based on designation/grade."""
    value = str(designation or "").lower()
    if "semi" in value or "supervisor" in value:
        return {"daily_rate": SUPERVISOR_DAILY_RATE, "ot_rate": SUPERVISOR_OT_RATE, "role_type": "Supervisor"}
    return {"daily_rate": LABOUR_DAILY_RATE, "ot_rate": LABOUR_OT_RATE, "role_type": "Labour"}


def calculate_wages(emp_record: Dict[str, object], month: int, default_other_deduction: float = 0.0) -> Dict[str, object]:
    """Calculate complete wage structure for one employee."""
    designation = str(emp_record.get("designation") or emp_record.get("grade") or "")
    present_days = float(emp_record.get("present_days", 0) or 0)
    ot_hours = float(emp_record.get("ot_hours", 0) or 0)
    advance = float(emp_record.get("advance", 0) or 0)
    other = float(emp_record.get("other_deduction", default_other_deduction) or 0)

    rates = get_rates(designation)
    daily_rate = float(rates["daily_rate"])
    ot_rate = float(rates["ot_rate"])

    basic_wages = present_days * daily_rate
    ot_amount = ot_hours * ot_rate
    gross_salary = basic_wages + ot_amount

    pf_employee, pf_employer = calculate_pf(basic_wages)
    esic_employee, esic_employer, esic_applicable = calculate_esic(gross_salary)
    pt = calculate_pt(gross_salary, int(month))

    total_deductions = pf_employee + esic_employee + pt + advance + other
    net_payable = gross_salary - total_deductions

    return {
        "emp_code": str(emp_record.get("emp_code", "")).strip(),
        "emp_name": str(emp_record.get("emp_name", "")).strip(),
        "father_husband_name": str(emp_record.get("father_husband_name", "")).strip(),
        "department": str(emp_record.get("department", "")).strip(),
        "designation": designation,
        "grade": str(emp_record.get("grade", "")).strip() or designation,
        "bank_account_no": str(emp_record.get("bank_account_no", "")).strip(),
        "ifsc_code": str(emp_record.get("ifsc_code", "")).strip(),
        "bank_name": str(emp_record.get("bank_name", "")).strip(),
        "uan_no": str(emp_record.get("uan_no", "")).strip(),
        "esic_no": str(emp_record.get("esic_no", "")).strip(),
        "dob": str(emp_record.get("dob", "")).strip(),
        "doj": str(emp_record.get("doj", "")).strip(),
        "present_days": _money(present_days),
        "ot_hours": _money(ot_hours),
        "daily_rate": _money(daily_rate),
        "ot_rate": _money(ot_rate),
        "basic_wages": _money(basic_wages),
        "ot_amount": _money(ot_amount),
        "gross_salary": _money(gross_salary),
        "pf_basic": _money(basic_wages),
        "pf_employee": _money(pf_employee),
        "pf_employer": _money(pf_employer),
        "esic_employee": _money(esic_employee),
        "esic_employer": _money(esic_employer),
        "pt": _money(pt),
        "advance": _money(advance),
        "other_deduction": _money(other),
        "total_deductions": _money(total_deductions),
        "net_payable": _money(net_payable),
        "esic_applicable": bool(esic_applicable),
        "esic_remarks": "Applicable" if esic_applicable else "Not Applicable",
    }


def calculate_batch_wages(
    employee_records: Iterable[Dict[str, object]],
    month: int,
    advances_map: Dict[str, float] | None = None,
    deductions_map: Dict[str, float] | None = None,
) -> List[Dict[str, object]]:
    """Calculate payroll for multiple employees."""
    advances_map = advances_map or {}
    deductions_map = deductions_map or {}
    result: List[Dict[str, object]] = []
    for record in employee_records:
        emp_code = str(record.get("emp_code", "")).strip()
        payload = dict(record)
        payload["advance"] = advances_map.get(emp_code, float(payload.get("advance", 0) or 0))
        payload["other_deduction"] = deductions_map.get(emp_code, float(payload.get("other_deduction", 0) or 0))
        result.append(calculate_wages(payload, month=month))
    return result


def build_department_summary(employee_wages: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Build department-wise summary dataframe for reports and invoices."""
    df = pd.DataFrame(list(employee_wages))
    if df.empty:
        return pd.DataFrame(
            columns=[
                "department",
                "total_employees",
                "total_days",
                "total_ot_hrs",
                "total_basic_wages",
                "total_ot_amount",
                "total_gross",
                "total_deductions",
                "total_net_payable",
            ]
        )

    grouped = (
        df.groupby("department", dropna=False)
        .agg(
            total_employees=("emp_code", "count"),
            total_days=("present_days", "sum"),
            total_ot_hrs=("ot_hours", "sum"),
            total_basic_wages=("basic_wages", "sum"),
            total_ot_amount=("ot_amount", "sum"),
            total_gross=("gross_salary", "sum"),
            total_deductions=("total_deductions", "sum"),
            total_net_payable=("net_payable", "sum"),
        )
        .reset_index()
    )

    for col in grouped.columns:
        if col != "department":
            grouped[col] = grouped[col].round(2)
    grouped = grouped.sort_values("department", ignore_index=True)
    return grouped

