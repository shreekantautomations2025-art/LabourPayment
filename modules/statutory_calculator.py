"""Statutory deduction and contribution calculations."""

from __future__ import annotations

from typing import Dict, Tuple

from config import (
    ESIC_EMPLOYEE_RATE,
    ESIC_EMPLOYER_RATE,
    ESIC_WAGE_CEILING,
    PF_EMPLOYEE_RATE,
    PF_EMPLOYER_RATE,
    PF_EPF_RATE,
    PF_EPS_RATE,
    PT_FEB_ADDITIONAL,
    PT_SLABS,
)


def _money(value: float) -> float:
    return round(float(value), 2)


def calculate_pf(
    basic_wages: float,
    employee_rate: float = PF_EMPLOYEE_RATE,
    employer_rate: float = PF_EMPLOYER_RATE,
) -> Tuple[float, float]:
    """Return (employee_pf, employer_pf) on basic wages."""
    basic = max(float(basic_wages), 0.0)
    employee_pf = basic * float(employee_rate)
    employer_pf = basic * float(employer_rate)
    return _money(employee_pf), _money(employer_pf)


def split_employer_pf(
    basic_wages: float,
    epf_rate: float = PF_EPF_RATE,
    eps_rate: float = PF_EPS_RATE,
) -> Tuple[float, float]:
    """Return (employer_epf_3_67, employer_eps_8_33) split on basic wages."""
    basic = max(float(basic_wages), 0.0)
    employer_epf = basic * float(epf_rate)
    employer_eps = basic * float(eps_rate)
    return _money(employer_epf), _money(employer_eps)


def calculate_esic(
    gross_salary: float,
    employee_rate: float = ESIC_EMPLOYEE_RATE,
    employer_rate: float = ESIC_EMPLOYER_RATE,
    wage_ceiling: float = ESIC_WAGE_CEILING,
) -> Tuple[float, float, bool]:
    """Return (employee_esic, employer_esic, applicable)."""
    gross = max(float(gross_salary), 0.0)
    if gross <= float(wage_ceiling):
        employee_esic = gross * float(employee_rate)
        employer_esic = gross * float(employer_rate)
        return _money(employee_esic), _money(employer_esic), True
    return 0.0, 0.0, False


def calculate_pt(
    gross_salary: float,
    month: int,
    pt_slabs: list[dict] | None = None,
    feb_additional: float = PT_FEB_ADDITIONAL,
) -> float:
    """Calculate Maharashtra professional tax for month."""
    gross = max(float(gross_salary), 0.0)
    slabs = pt_slabs or PT_SLABS
    pt = 0.0
    for slab in slabs:
        if slab["min"] <= gross <= slab["max"]:
            pt = float(slab["amount"])
            break
    if int(month) == 2:
        pt += float(feb_additional)
    return _money(pt)


def get_pt_slab_label(gross_salary: float, pt_slabs: list[dict] | None = None) -> str:
    """Return PT slab label for report readability."""
    gross = max(float(gross_salary), 0.0)
    slabs = pt_slabs or PT_SLABS
    for slab in slabs:
        if slab["min"] <= gross <= slab["max"]:
            return f"₹{int(slab['min']):,} - ₹{int(slab['max']):,}"
    return "N/A"


def build_statutory_summary(employee_rows: list[dict]) -> Dict[str, float]:
    """Aggregate key statutory totals."""
    summary = {
        "employee_pf_total": 0.0,
        "employer_pf_total": 0.0,
        "employee_esic_total": 0.0,
        "employer_esic_total": 0.0,
        "pt_total": 0.0,
    }
    for row in employee_rows:
        summary["employee_pf_total"] += float(row.get("pf_employee", 0) or 0)
        summary["employer_pf_total"] += float(row.get("pf_employer", 0) or 0)
        summary["employee_esic_total"] += float(row.get("esic_employee", 0) or 0)
        summary["employer_esic_total"] += float(row.get("esic_employer", 0) or 0)
        summary["pt_total"] += float(row.get("pt", 0) or 0)
    return {key: _money(value) for key, value in summary.items()}

