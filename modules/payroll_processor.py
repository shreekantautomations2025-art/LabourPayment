"""End-to-end monthly payroll processing orchestration."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

from modules.company_manager import CompanyManager
from modules.employee_manager import EmployeeManager, get_manager
from modules.excel_generator import (
    generate_advance_register,
    generate_bank_payment_excel,
    generate_department_salary_summary,
    generate_esic_summary,
    generate_nach_upload_csv,
    generate_pf_ecr_file,
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

_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_DEFAULT_IFSC = "SBIN0000001"
_DEFAULT_ACCOUNT = "000000000"
_EMP_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,39}$")


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


def _normalize_preview_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {c: str(c).strip().lower().replace(" ", "_") for c in df.columns}
    return df.rename(columns=renamed)


def _bool_approved(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    text = str(value).strip().lower()
    return text in {"y", "yes", "true", "1", "approved"}


def _calculate_totals(wages: list[dict]) -> dict:
    return {
        "gross_salary": round(sum(float(r["gross_salary"]) for r in wages), 2),
        "deductions": round(sum(float(r["total_deductions"]) for r in wages), 2),
        "net_payable": round(sum(float(r["net_payable"]) for r in wages), 2),
    }


def _persist_period_data(period_data_dir: Path, parsed_df: pd.DataFrame, wages: list[dict]) -> None:
    (period_data_dir / "parsed_muster.csv").write_text(parsed_df.to_csv(index=False), encoding="utf-8")
    (period_data_dir / "wage_details.json").write_text(json.dumps(wages, indent=2, default=str), encoding="utf-8")


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
        if math.isnan(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _normalize_bank_account(value: object) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if 9 <= len(digits) <= 18:
        return digits
    if len(digits) > 18:
        return digits[:18]
    return _DEFAULT_ACCOUNT


def _normalize_ifsc(value: object) -> str:
    text = str(value or "").strip().upper()
    return text if _IFSC_RE.match(text) else _DEFAULT_IFSC


def _normalize_designation(value: object) -> str:
    text = _clean_text(value).lower()
    if "supervisor" in text:
        return "Supervisor"
    if "semi" in text:
        return "Semi-Skilled"
    return "Labour"


def _is_valid_emp_code(value: object) -> bool:
    code = _clean_text(value)
    return bool(code and _EMP_CODE_RE.match(code) and " " not in code)


def _build_auto_employee_payload(record: dict, company_id: int | None) -> dict:
    emp_code = _clean_text(record.get("emp_code"))
    return {
        "emp_code": emp_code,
        "emp_name": _clean_text(record.get("emp_name")) or "Unknown Employee",
        "father_husband_name": _clean_text(record.get("father_husband_name")) or "Unknown",
        "dob": _clean_text(record.get("dob")) or "1990-01-01",
        "gender": _clean_text(record.get("gender")) or "Male",
        "designation": _normalize_designation(record.get("designation") or record.get("grade")),
        "doj": _clean_text(record.get("doj")) or datetime.now().date().isoformat(),
        "bank_account_no": _normalize_bank_account(record.get("bank_account_no")),
        "ifsc_code": _normalize_ifsc(record.get("ifsc_code")),
        "bank_name": _clean_text(record.get("bank_name")) or "UNKNOWN BANK",
        "pan_no": _clean_text(record.get("pan_no")),
        "aadhaar_no": _clean_text(record.get("aadhaar_no")),
        "uan_no": _clean_text(record.get("uan_no")),
        "esic_no": _clean_text(record.get("esic_no")),
        "department": _clean_text(record.get("department")),
        "company_id": company_id,
    }


def _reactivate_employee(manager: EmployeeManager, emp_code: str, company_id: int | None) -> None:
    with manager._connect() as conn:  # pylint: disable=protected-access
        if company_id is None:
            conn.execute(
                "UPDATE employees SET is_active = 1, updated_date = ? WHERE emp_code = ?",
                (datetime.now().isoformat(timespec="seconds"), emp_code),
            )
        else:
            conn.execute(
                "UPDATE employees SET is_active = 1, updated_date = ? WHERE emp_code = ? AND company_id = ?",
                (datetime.now().isoformat(timespec="seconds"), emp_code, int(company_id)),
            )
        conn.commit()


def _ensure_employee_in_master(
    manager: EmployeeManager,
    record: dict,
    company_id: int | None,
    allow_auto_employee_creation: bool,
) -> dict | None:
    emp_code = _clean_text(record.get("emp_code"))
    if not emp_code:
        return None
    if not _is_valid_emp_code(emp_code):
        return None
    emp_name = _clean_text(record.get("emp_name")).lower()

    def _sync_company(employee: dict | None) -> dict | None:
        if employee is None:
            return None
        canonical_emp_code = _clean_text(employee.get("emp_code")) or emp_code
        if company_id is None:
            return employee
        current_company = employee.get("company_id")
        if current_company is None or int(current_company) != int(company_id):
            manager.update_employee(canonical_emp_code, {"company_id": int(company_id)})
            return manager.get_employee(canonical_emp_code, include_inactive=True)
        return employee

    active = manager.get_employee(emp_code, include_inactive=False, company_id=company_id)
    if active:
        return _sync_company(active)

    any_status = manager.get_employee(emp_code, include_inactive=True, company_id=company_id)
    if any_status:
        _reactivate_employee(manager, emp_code, company_id)
        return _sync_company(manager.get_employee(emp_code, include_inactive=False, company_id=company_id))

    # Cross-company fallback for globally unique employee codes.
    any_company_active = manager.get_employee(emp_code, include_inactive=False, company_id=None)
    if any_company_active:
        return _sync_company(any_company_active)

    any_company_inactive = manager.get_employee(emp_code, include_inactive=True, company_id=None)
    if any_company_inactive:
        _reactivate_employee(manager, emp_code, None)
        return _sync_company(manager.get_employee(emp_code, include_inactive=False, company_id=None))

    if emp_name:
        filters = {"company_id": int(company_id)} if company_id is not None else None
        for candidate in manager.get_all_employees(filters=filters, active_only=False):
            if _clean_text(candidate.get("emp_name")).lower() != emp_name:
                continue
            canonical_emp_code = _clean_text(candidate.get("emp_code"))
            if not canonical_emp_code:
                continue
            if not bool(candidate.get("is_active", False)):
                _reactivate_employee(manager, canonical_emp_code, company_id)
                matched = manager.get_employee(canonical_emp_code, include_inactive=False, company_id=company_id)
                return _sync_company(matched)
            return _sync_company(candidate)

    if not allow_auto_employee_creation:
        return None

    payload = _build_auto_employee_payload(record, company_id)
    manager.add_employee(payload, raise_on_error=True)
    return manager.get_employee(emp_code, include_inactive=False, company_id=company_id)


def _auto_onboard_missing_employees(
    manager: EmployeeManager,
    records: list[dict],
    company_id: int | None,
    allow_auto_employee_creation: bool,
) -> None:
    if not allow_auto_employee_creation:
        return
    failures: list[str] = []
    for record in records:
        emp_code = _clean_text(record.get("emp_code"))
        if not emp_code:
            continue
        try:
            _ensure_employee_in_master(manager, record, company_id, allow_auto_employee_creation=True)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{emp_code}: {exc}")
    if failures:
        raise ValueError("Failed to auto-create missing employees: " + "; ".join(failures))


def _company_output_dir(base_output_dir: Path, company_id: int | None) -> Path:
    if company_id is None:
        return base_output_dir
    return base_output_dir / f"company_{int(company_id)}"


def _company_data_dir(base_data_dir: Path, company_id: int | None) -> Path:
    if company_id is None:
        return base_data_dir
    return base_data_dir / f"company_{int(company_id)}"


def _get_company_context(company_id: int | None, db_path: str | Path | None = None) -> dict | None:
    if company_id is None:
        return None
    company_manager = CompanyManager(db_path) if db_path is not None else CompanyManager()
    return company_manager.get_company_configuration(int(company_id))


def _resolve_company_from_preview(df: pd.DataFrame, company_id: int | None) -> int | None:
    if company_id is not None:
        return int(company_id)
    if "company_id" not in df.columns:
        return None
    series = df["company_id"].dropna()
    if series.empty:
        return None
    try:
        return int(series.iloc[0])
    except (TypeError, ValueError):
        return None


def _get_master_maps(manager: EmployeeManager, company_id: int | None = None) -> tuple[set[str], dict]:
    filters = {"company_id": int(company_id)} if company_id is not None else None
    master_rows = manager.get_all_employees(active_only=True, filters=filters)
    codes = {r["emp_code"] for r in master_rows}
    designations = {r["emp_code"]: r["designation"] for r in master_rows}
    return codes, designations


def _generate_outputs(
    *,
    wages: list[dict],
    month: int,
    year: int,
    period_data_dir: Path,
    period_output_dir: Path,
    company_config: dict | None = None,
) -> dict:
    dept_summary = build_department_summary(wages)
    output_paths = {
        "department_summary_excel": str(generate_department_salary_summary(wages, month, year, period_output_dir)),
        "md_invoice_pdf": str(generate_md_invoice(month, year, dept_summary, period_output_dir, company_config=company_config)),
        "ot_invoice_pdf": str(generate_ot_invoice(month, year, dept_summary, period_output_dir, company_config=company_config)),
        "bank_payment_excel": str(generate_bank_payment_excel(wages, month, year, period_output_dir)),
        "nach_upload_csv": str(generate_nach_upload_csv(wages, month, year, period_output_dir)),
        "pf_summary_excel": str(generate_pf_summary(wages, month, year, period_output_dir)),
        "pf_ecr_csv": str(generate_pf_ecr_file(wages, month, year, period_output_dir)),
        "esic_summary_excel": str(generate_esic_summary(wages, month, year, period_output_dir)),
        "pt_summary_excel": str(generate_pt_summary(wages, month, year, period_output_dir, company_settings=company_config)),
        "wages_register_excel": str(generate_wages_register_excel(wages, month, year, period_output_dir)),
        "wages_register_pdf": str(generate_wages_register_pdf(wages, month, year, period_output_dir, company_config=company_config)),
        "ot_register_pdf": str(generate_ot_register_pdf(wages, month, year, period_output_dir, company_config=company_config)),
    }

    advances_rows = _load_advances_for_period(period_data_dir)
    output_paths["advance_register_excel"] = str(generate_advance_register(advances_rows, month, year, period_output_dir))
    payment_summary = build_payment_summary(wages)
    output_paths["payment_instructions_pdf"] = str(
        generate_payment_instructions(payment_summary, month, year, period_output_dir, company_config=company_config)
    )
    return output_paths


def create_payroll_preview(
    *,
    muster_file: str | Path,
    month: int,
    year: int,
    employee_manager: EmployeeManager | None = None,
    company_id: int | None = None,
    adjustments_file: str | Path | None = None,
    output_dir: Path | None = None,
    allow_auto_employee_creation: bool = True,
) -> Dict[str, object]:
    """Create editable preview workbook before final payroll generation."""
    manager = employee_manager or get_manager()
    company_config = _get_company_context(company_id, db_path=manager.db_path)
    period_dirs = get_period_directories(month, year)
    period_data_dir = _company_data_dir(period_dirs["data_period"], company_id)
    if output_dir is None:
        period_output_dir = _company_output_dir(period_dirs["output_period"], company_id)
    else:
        period_output_dir = Path(output_dir)
    period_data_dir.mkdir(parents=True, exist_ok=True)
    period_output_dir.mkdir(parents=True, exist_ok=True)

    archived_muster = copy_original_muster(Path(muster_file), period_dirs["original_muster"])
    parsed_df = parse_muster_roll(
        muster_file,
        employee_manager=manager,
        company_id=company_id,
        allow_unknown_emp_codes=allow_auto_employee_creation,
    )
    _auto_onboard_missing_employees(
        manager,
        parsed_df.to_dict(orient="records"),
        company_id=company_id,
        allow_auto_employee_creation=allow_auto_employee_creation,
    )
    master_codes, master_designations = _get_master_maps(manager, company_id=company_id)
    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)
    if not is_valid:
        raise ValueError("Muster validation failed: " + "; ".join(errors))

    advances_map, other_deductions_map = _load_adjustments(adjustments_file)
    preview_df = parsed_df.copy()
    if "serial_no" not in preview_df.columns:
        preview_df.insert(0, "serial_no", range(1, len(preview_df) + 1))
    else:
        preview_df["serial_no"] = range(1, len(preview_df) + 1)
    preview_df["advance"] = preview_df["emp_code"].map(advances_map).fillna(0.0)
    preview_df["other_deduction"] = preview_df["emp_code"].map(other_deductions_map).fillna(0.0)
    preview_df["approved"] = "Y"
    preview_df["reviewer_remarks"] = ""
    preview_df["company_id"] = int(company_id) if company_id is not None else ""

    columns = [
        "serial_no",
        "emp_code",
        "emp_name",
        "father_husband_name",
        "department",
        "designation",
        "present_days",
        "ot_hours",
        "advance",
        "other_deduction",
        "approved",
        "reviewer_remarks",
        "company_id",
    ]
    preview_df = preview_df[columns]

    preview_path = period_output_dir / f"Payroll_Preview_{year}_{month:02d}.xlsx"
    instruction_df = pd.DataFrame(
        [
            {"Instruction": "Edit present_days/ot_hours/advance/other_deduction if required."},
            {"Instruction": "Set approved = Y for rows to include in final payroll."},
            {"Instruction": "Set approved = N to exclude a row from current month payout."},
            {"Instruction": "Do not change emp_code values."},
            {"Instruction": "serial_no is auto-normalized to sequential order."},
        ]
    )
    with pd.ExcelWriter(preview_path, engine="openpyxl") as writer:
        preview_df.to_excel(writer, sheet_name="Editable_Preview", index=False)
        instruction_df.to_excel(writer, sheet_name="Instructions", index=False)

    context = {
        "month": month,
        "year": year,
        "source_muster_file": str(muster_file),
        "archived_muster": str(archived_muster),
        "preview_file": str(preview_path),
        "row_count": int(len(preview_df)),
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
    }
    (period_data_dir / "preview_context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")
    log_audit("payroll_preview_created", context)

    return {
        "preview_file": str(preview_path),
        "archived_muster": str(archived_muster),
        "validation": {"is_valid": is_valid, "errors": errors, "warnings": warnings},
        "row_count": int(len(preview_df)),
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
    }


def create_payroll_preview_from_records(
    *,
    records: list[dict],
    month: int,
    year: int,
    employee_manager: EmployeeManager | None = None,
    company_id: int | None = None,
    output_dir: Path | None = None,
    allow_auto_employee_creation: bool = True,
) -> Dict[str, object]:
    """Create editable preview directly from manual/csv/json/txt records (no muster excel required)."""
    manager = employee_manager or get_manager()
    company_config = _get_company_context(company_id, db_path=manager.db_path)
    period_dirs = get_period_directories(month, year)
    period_data_dir = _company_data_dir(period_dirs["data_period"], company_id)
    if output_dir is None:
        period_output_dir = _company_output_dir(period_dirs["output_period"], company_id)
    else:
        period_output_dir = Path(output_dir)
    period_data_dir.mkdir(parents=True, exist_ok=True)
    period_output_dir.mkdir(parents=True, exist_ok=True)

    if not records:
        raise ValueError("No manual attendance records provided")

    df = pd.DataFrame(records)
    normalized = {c: str(c).strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=normalized)
    required = {"emp_code", "present_days", "ot_hours"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for manual preview: {', '.join(sorted(missing))}")

    if "emp_name" not in df.columns:
        df["emp_name"] = ""
    if "father_husband_name" not in df.columns:
        df["father_husband_name"] = ""
    if "designation" not in df.columns:
        df["designation"] = "Labour"
    if "department" not in df.columns:
        df["department"] = ""
    if "advance" not in df.columns:
        df["advance"] = 0.0
    if "other_deduction" not in df.columns:
        df["other_deduction"] = 0.0

    df["emp_code"] = df["emp_code"].astype(str).str.strip()
    df["present_days"] = df["present_days"].apply(lambda x: _safe_float(x, 0.0))
    df["ot_hours"] = df["ot_hours"].apply(lambda x: _safe_float(x, 0.0))
    df["advance"] = df["advance"].apply(lambda x: _safe_float(x, 0.0))
    df["other_deduction"] = df["other_deduction"].apply(lambda x: _safe_float(x, 0.0))
    df = df[df["emp_code"] != ""].copy()
    if df.empty:
        raise ValueError("No valid employee codes found in manual records")

    parsed_df = pd.DataFrame(
        {
            "emp_code": df["emp_code"],
            "emp_name": df["emp_name"].astype(str),
            "father_husband_name": df["father_husband_name"].astype(str),
            "designation": df["designation"].astype(str),
            "grade": df["designation"].astype(str),
            "department": df["department"].astype(str),
            "present_days": df["present_days"],
            "ot_hours": df["ot_hours"],
            "bank_account_no": "",
            "ifsc_code": "",
            "bank_name": "",
            "uan_no": "",
            "esic_no": "",
            "dob": "",
            "doj": "",
            "gender": "",
            "company_id": company_id,
        }
    )

    _auto_onboard_missing_employees(
        manager,
        parsed_df.to_dict(orient="records"),
        company_id=company_id,
        allow_auto_employee_creation=allow_auto_employee_creation,
    )

    master_codes, master_designations = _get_master_maps(manager, company_id=company_id)
    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)
    if not is_valid:
        raise ValueError("Manual input validation failed: " + "; ".join(errors))

    preview_df = parsed_df.copy()
    if "serial_no" not in preview_df.columns:
        preview_df.insert(0, "serial_no", range(1, len(preview_df) + 1))
    else:
        preview_df["serial_no"] = range(1, len(preview_df) + 1)
    preview_df["advance"] = df["advance"].values
    preview_df["other_deduction"] = df["other_deduction"].values
    preview_df["approved"] = "Y"
    preview_df["reviewer_remarks"] = ""
    preview_df["company_id"] = int(company_id) if company_id is not None else ""

    columns = [
        "serial_no",
        "emp_code",
        "emp_name",
        "father_husband_name",
        "department",
        "designation",
        "present_days",
        "ot_hours",
        "advance",
        "other_deduction",
        "approved",
        "reviewer_remarks",
        "company_id",
    ]
    preview_df = preview_df[columns]

    preview_path = period_output_dir / f"Payroll_Preview_{year}_{month:02d}.xlsx"
    instruction_df = pd.DataFrame(
        [
            {"Instruction": "Manual mode: records entered via UI/CSV/JSON/TXT (no muster excel needed)."},
            {"Instruction": "Set approved = Y for rows to include in final payroll."},
            {"Instruction": "Set approved = N to exclude a row from current month payout."},
            {"Instruction": "Do not change emp_code values."},
            {"Instruction": "serial_no is auto-normalized to sequential order."},
        ]
    )
    with pd.ExcelWriter(preview_path, engine="openpyxl") as writer:
        preview_df.to_excel(writer, sheet_name="Editable_Preview", index=False)
        instruction_df.to_excel(writer, sheet_name="Instructions", index=False)

    context = {
        "month": month,
        "year": year,
        "source_type": "manual_records",
        "preview_file": str(preview_path),
        "row_count": int(len(preview_df)),
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
    }
    (period_data_dir / "preview_context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")
    log_audit("payroll_preview_created_manual_mode", context)

    return {
        "preview_file": str(preview_path),
        "archived_muster": "",
        "validation": {"is_valid": is_valid, "errors": errors, "warnings": warnings},
        "row_count": int(len(preview_df)),
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
        "source_type": "manual_records",
    }


def finalize_payroll_from_preview(
    *,
    preview_file: str | Path,
    month: int,
    year: int,
    employee_manager: EmployeeManager | None = None,
    company_id: int | None = None,
    output_dir: Path | None = None,
    require_approved_rows: bool = True,
    allow_auto_employee_creation: bool = True,
) -> Dict[str, object]:
    """Finalize payroll from an edited preview workbook."""
    manager = employee_manager or get_manager()
    preview_path = Path(preview_file)
    if not preview_path.exists():
        raise FileNotFoundError(f"Preview file not found: {preview_path}")

    df = pd.read_excel(preview_path, sheet_name="Editable_Preview")
    df = _normalize_preview_columns(df)
    company_id = _resolve_company_from_preview(df, company_id)
    company_config = _get_company_context(company_id, db_path=manager.db_path)

    period_dirs = get_period_directories(month, year)
    period_data_dir = _company_data_dir(period_dirs["data_period"], company_id)
    if output_dir is None:
        period_output_dir = _company_output_dir(period_dirs["output_period"], company_id)
    else:
        period_output_dir = Path(output_dir)
    period_data_dir.mkdir(parents=True, exist_ok=True)
    period_output_dir.mkdir(parents=True, exist_ok=True)

    required_cols = {"emp_code", "present_days", "ot_hours"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Preview file missing required columns: {', '.join(sorted(missing))}")

    if "approved" not in df.columns:
        df["approved"] = "Y"
    if "advance" not in df.columns:
        df["advance"] = 0.0
    if "other_deduction" not in df.columns:
        df["other_deduction"] = 0.0

    selected_rows = []
    for _, row in df.iterrows():
        if require_approved_rows and not _bool_approved(row.get("approved", "")):
            continue
        emp_code = str(row.get("emp_code", "")).strip()
        if not emp_code:
            continue
        row_dict = row.to_dict()
        master = _ensure_employee_in_master(
            manager,
            row_dict,
            company_id=company_id,
            allow_auto_employee_creation=allow_auto_employee_creation,
        )
        if not master:
            if allow_auto_employee_creation and not _is_valid_emp_code(emp_code):
                continue
            raise ValueError(f"Employee code not found/active in master data: {emp_code}")
        canonical_emp_code = _clean_text(master.get("emp_code")) or emp_code
        selected_rows.append(
            {
                "emp_code": canonical_emp_code,
                "emp_name": _clean_text(row_dict.get("emp_name")) or _clean_text(master.get("emp_name")),
                "father_husband_name": _clean_text(row_dict.get("father_husband_name"))
                or _clean_text(master.get("father_husband_name")),
                "designation": _clean_text(row_dict.get("designation")) or _clean_text(master.get("designation")),
                "grade": _clean_text(row_dict.get("designation")) or _clean_text(master.get("designation")),
                "department": _clean_text(row_dict.get("department")) or _clean_text(master.get("department")),
                "present_days": _safe_float(row_dict.get("present_days"), 0.0),
                "ot_hours": _safe_float(row_dict.get("ot_hours"), 0.0),
                "advance": _safe_float(row_dict.get("advance"), 0.0),
                "other_deduction": _safe_float(row_dict.get("other_deduction"), 0.0),
                "bank_account_no": master.get("bank_account_no", ""),
                "ifsc_code": master.get("ifsc_code", ""),
                "bank_name": master.get("bank_name", ""),
                "uan_no": master.get("uan_no", ""),
                "esic_no": master.get("esic_no", ""),
                "dob": master.get("dob", ""),
                "doj": master.get("doj", ""),
                "company_id": company_id,
            }
        )

    if not selected_rows:
        raise ValueError("No approved rows found in preview file for final payroll processing")

    parsed_df = pd.DataFrame(selected_rows)
    master_codes, master_designations = _get_master_maps(manager, company_id=company_id)
    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)
    if not is_valid:
        raise ValueError("Preview validation failed: " + "; ".join(errors))

    wages = calculate_batch_wages(
        parsed_df.to_dict(orient="records"),
        month=month,
        company_settings=company_config,
    )
    _persist_period_data(period_data_dir, parsed_df, wages)
    output_paths = _generate_outputs(
        wages=wages,
        month=month,
        year=year,
        period_data_dir=period_data_dir,
        period_output_dir=period_output_dir,
        company_config=company_config,
    )

    response = {
        "source_type": "preview",
        "source_preview_file": str(preview_path),
        "validation": {"is_valid": is_valid, "errors": errors, "warnings": warnings},
        "employee_count": len(wages),
        "totals": _calculate_totals(wages),
        "output_paths": output_paths,
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
    }
    (period_data_dir / "processing_summary.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
    log_audit(
        "monthly_payroll_finalized_from_preview",
        {
            "month": month,
            "year": year,
            "preview_file": str(preview_path),
            "employee_count": len(wages),
            "company_id": company_id,
        },
    )
    return response


def process_monthly_payroll(
    *,
    muster_file: str | Path,
    month: int,
    year: int,
    employee_manager: EmployeeManager | None = None,
    company_id: int | None = None,
    adjustments_file: str | Path | None = None,
    output_dir: Path | None = None,
    require_clean_validation: bool = True,
    allow_auto_employee_creation: bool = True,
) -> Dict[str, object]:
    """Process one payroll month directly from muster and generate all documents."""
    manager = employee_manager or get_manager()
    company_config = _get_company_context(company_id, db_path=manager.db_path)
    period_dirs = get_period_directories(month, year)
    period_data_dir = _company_data_dir(period_dirs["data_period"], company_id)
    if output_dir is None:
        period_output_dir = _company_output_dir(period_dirs["output_period"], company_id)
    else:
        period_output_dir = Path(output_dir)
    period_data_dir.mkdir(parents=True, exist_ok=True)
    period_output_dir.mkdir(parents=True, exist_ok=True)

    archived_muster = copy_original_muster(Path(muster_file), period_dirs["original_muster"])
    parsed_df = parse_muster_roll(
        muster_file,
        employee_manager=manager,
        company_id=company_id,
        allow_unknown_emp_codes=allow_auto_employee_creation,
    )
    _auto_onboard_missing_employees(
        manager,
        parsed_df.to_dict(orient="records"),
        company_id=company_id,
        allow_auto_employee_creation=allow_auto_employee_creation,
    )

    master_codes, master_designations = _get_master_maps(manager, company_id=company_id)
    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)
    if require_clean_validation and not is_valid:
        raise ValueError("Muster validation failed: " + "; ".join(errors))

    advances_map, other_deductions_map = _load_adjustments(adjustments_file)
    wages = calculate_batch_wages(
        parsed_df.to_dict(orient="records"),
        month=month,
        advances_map=advances_map,
        deductions_map=other_deductions_map,
        company_settings=company_config,
    )

    _persist_period_data(period_data_dir, parsed_df, wages)
    output_paths = _generate_outputs(
        wages=wages,
        month=month,
        year=year,
        period_data_dir=period_data_dir,
        period_output_dir=period_output_dir,
        company_config=company_config,
    )

    response = {
        "source_type": "muster",
        "archived_muster": str(archived_muster),
        "validation": {"is_valid": is_valid, "errors": errors, "warnings": warnings},
        "employee_count": len(wages),
        "totals": _calculate_totals(wages),
        "output_paths": output_paths,
        "company_id": company_id,
        "company_name": (company_config or {}).get("company_name"),
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
            "company_id": company_id,
        },
    )
    return response

