"""End-to-end monthly payroll processing orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

from modules.employee_manager import EmployeeManager, get_manager
from modules.excel_generator import (
    generate_advance_register,
    generate_bank_payment_excel,
    generate_department_salary_summary,
    generate_esic_summary,
    generate_pf_summary,
    generate_pt_summary,
    generate_wages_register_excel,
)
from modules.invoice_generator import generate_md_invoice, generate_ot_invoice
from modules.muster_parser import parse_muster_roll
from modules.payment_instructions import build_payment_summary, generate_payment_instructions
from modules.pdf_generator import generate_ot_register_pdf, generate_wages_register_pdf
from modules.validators import validate_muster_roll
from modules.wage_calculator import build_department_summary, calculate_batch_wages
from utils.helpers import copy_original_muster, get_period_directories, log_audit


def _load_adjustments(adjustments_file: str | Path | None) -> tuple[dict, dict]:
    if not adjustments_file:
        return {}, {}
    path = Path(adjustments_file)
    if not path.exists():
        raise FileNotFoundError(f"Adjustments file not found: {path}")
    df = pd.read_excel(path) if path.suffix.lower() in {".xls", ".xlsx"} else pd.read_csv(path)
    normalized = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
    code_col = normalized.get("emp_code") or normalized.get("employee_code")
    if not code_col:
        raise ValueError("Adjustments file requires emp_code column")
    adv_col = normalized.get("advance")
    other_col = normalized.get("other_deduction") or normalized.get("other_ded")

    advances, others = {}, {}
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip()
        if not code:
            continue
        if adv_col:
            advances[code] = float(row.get(adv_col, 0) or 0)
        if other_col:
            others[code] = float(row.get(other_col, 0) or 0)
    return advances, others


def _load_advances_for_period(data_period: Path) -> list[dict]:
    file_path = data_period / "advances.json"
    if not file_path.exists():
        return []
    return json.loads(file_path.read_text(encoding="utf-8"))


def process_monthly_payroll(
    *,
    muster_file: str | Path,
    month: int,
    year: int,
    employee_manager: EmployeeManager | None = None,
    adjustments_file: str | Path | None = None,
    output_dir: Path | None = None,
    require_clean_validation: bool = True,
) -> Dict[str, object]:
    """Process one payroll month and generate all documents."""
    manager = employee_manager or get_manager()
    period_dirs = get_period_directories(month, year)
    period_data_dir = period_dirs["data_period"]
    period_output_dir = output_dir or period_dirs["output_period"]

    archived_muster = copy_original_muster(Path(muster_file), period_dirs["original_muster"])
    parsed_df = parse_muster_roll(muster_file, employee_manager=manager)

    master_rows = manager.get_all_employees(active_only=True)
    master_codes = {r["emp_code"] for r in master_rows}
    master_designations = {r["emp_code"]: r["designation"] for r in master_rows}

    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)
    if require_clean_validation and not is_valid:
        raise ValueError("Muster validation failed: " + "; ".join(errors))

    advances_map, other_deductions_map = _load_adjustments(adjustments_file)
    wages = calculate_batch_wages(
        parsed_df.to_dict(orient="records"),
        month=month,
        advances_map=advances_map,
        deductions_map=other_deductions_map,
    )
    dept_summary = build_department_summary(wages)

    (period_data_dir / "parsed_muster.csv").write_text(parsed_df.to_csv(index=False), encoding="utf-8")
    (period_data_dir / "wage_details.json").write_text(json.dumps(wages, indent=2, default=str), encoding="utf-8")

    output_paths = {
        "department_summary_excel": str(generate_department_salary_summary(wages, month, year, period_output_dir)),
        "md_invoice_pdf": str(generate_md_invoice(month, year, dept_summary, period_output_dir)),
        "ot_invoice_pdf": str(generate_ot_invoice(month, year, dept_summary, period_output_dir)),
        "bank_payment_excel": str(generate_bank_payment_excel(wages, month, year, period_output_dir)),
        "pf_summary_excel": str(generate_pf_summary(wages, month, year, period_output_dir)),
        "esic_summary_excel": str(generate_esic_summary(wages, month, year, period_output_dir)),
        "pt_summary_excel": str(generate_pt_summary(wages, month, year, period_output_dir)),
        "wages_register_excel": str(generate_wages_register_excel(wages, month, year, period_output_dir)),
        "wages_register_pdf": str(generate_wages_register_pdf(wages, month, year, period_output_dir)),
        "ot_register_pdf": str(generate_ot_register_pdf(wages, month, year, period_output_dir)),
    }

    advances_rows = _load_advances_for_period(period_data_dir)
    output_paths["advance_register_excel"] = str(generate_advance_register(advances_rows, month, year, period_output_dir))
    payment_summary = build_payment_summary(wages)
    output_paths["payment_instructions_pdf"] = str(
        generate_payment_instructions(payment_summary, month, year, period_output_dir)
    )

    response = {
        "archived_muster": str(archived_muster),
        "validation": {"is_valid": is_valid, "errors": errors, "warnings": warnings},
        "employee_count": len(wages),
        "totals": {
            "gross_salary": round(sum(float(r["gross_salary"]) for r in wages), 2),
            "deductions": round(sum(float(r["total_deductions"]) for r in wages), 2),
            "net_payable": round(sum(float(r["net_payable"]) for r in wages), 2),
        },
        "output_paths": output_paths,
    }
    (period_data_dir / "processing_summary.json").write_text(json.dumps(response, indent=2), encoding="utf-8")

    log_audit(
        "monthly_payroll_processed",
        {
            "month": month,
            "year": year,
            "muster_file": str(muster_file),
            "employee_count": len(wages),
            "net_payable": response["totals"]["net_payable"],
        },
    )
    return response

