"""Muster roll parser for monthly attendance and OT extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from modules.employee_manager import EmployeeManager, get_manager

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_SUMMARY_RE = re.compile(r"(summary|grand\s*total|total|paydays?)", re.IGNORECASE)
_EMP_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,39}$")


def _normalize_header(text: object) -> str:
    return str(text).strip().lower().replace(" ", "").replace(".", "")


def _unique_headers(headers: List[object]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for item in headers:
        base = str(item).strip() if str(item).strip() else "unnamed"
        if base not in seen:
            seen[base] = 0
            result.append(base)
        else:
            seen[base] += 1
            result.append(f"{base}_{seen[base]}")
    return result


def _is_time_row(row: pd.Series, day_columns: Iterable[str]) -> bool:
    values = [str(row.get(col, "")).strip() for col in day_columns]
    values = [v for v in values if v]
    if not values:
        return False
    time_hits = sum(bool(_TIME_RE.match(v)) for v in values)
    return (time_hits / max(len(values), 1)) >= 0.5


def _find_header_row(raw_df: pd.DataFrame) -> int:
    for idx, row in raw_df.iterrows():
        norm_values = {_normalize_header(cell) for cell in row.tolist()}
        if "slno" in norm_values and (
            "employeecode" in norm_values
            or "employeename" in norm_values
            or "employeecode_1" in norm_values
        ):
            return idx
    raise ValueError("Unable to locate muster roll header row containing 'Sl.No' and employee columns")


def _resolve_column(columns: List[str], candidates: Iterable[str]) -> str | None:
    normalized_map = {_normalize_header(col): col for col in columns}
    for candidate in candidates:
        hit = normalized_map.get(_normalize_header(candidate))
        if hit:
            return hit
    for col in columns:
        col_norm = _normalize_header(col)
        if any(_normalize_header(candidate) in col_norm for candidate in candidates):
            return col
    return None


def _resolve_column_safe(columns: List[str], candidates: Iterable[str]) -> str | None:
    """Resolve header match while avoiding fuzzy matches for short tokens.

    Tokens like ``P`` and ``OT`` are very short and can accidentally match
    unrelated columns (for example, ``EmployeeCode`` or ``Total``). This helper
    keeps short candidates exact-match only, while still allowing partial match
    for descriptive headers like ``Normal MD`` or ``OT Hrs``.
    """
    normalized_map = {_normalize_header(col): col for col in columns}
    candidate_norms = [_normalize_header(candidate) for candidate in candidates]

    # Exact header match first.
    for candidate_norm in candidate_norms:
        hit = normalized_map.get(candidate_norm)
        if hit:
            return hit

    # Fuzzy match only for sufficiently descriptive candidates.
    for col in columns:
        col_norm = _normalize_header(col)
        for candidate_norm in candidate_norms:
            if len(candidate_norm) <= 2:
                continue
            if candidate_norm and candidate_norm in col_norm:
                return col
    return None


def _attendance_value(cell: object) -> float:
    code = str(cell).strip().upper().replace(" ", "")
    if not code:
        return 0.0
    half_codes = {"HD", "1/2", "HALF", "½", "½PLD", "HALFDAY", "HPL", "0.5"}
    present_codes = {"P", "PR", "PRESENT"}
    if code in present_codes:
        return 1.0
    if code in half_codes or "1/2" in code or "HALF" in code or "½" in code:
        return 0.5
    return 0.0


def _to_float(value: object) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _has_value(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text and text.lower() != "nan")


def _is_number_like(value: object) -> bool:
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def _is_summary_row(emp_code: str, emp_name: str, department: str, slno: str) -> bool:
    blob = " ".join([emp_code, emp_name, department, slno]).strip()
    return bool(blob and _SUMMARY_RE.search(blob))


def _normalize_name_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _emp_code_candidates(value: object) -> list[str]:
    raw = str(value or "").strip()
    if not raw or raw.lower() == "nan":
        return []

    candidates: list[str] = [raw]
    compact = raw.replace(" ", "")
    if compact not in candidates:
        candidates.append(compact)

    # Excel numeric coercion can convert '000281' -> 281 or 281.0
    numeric_text = compact
    if re.fullmatch(r"\d+(\.0+)?", numeric_text):
        number = str(int(float(numeric_text)))
        if number not in candidates:
            candidates.append(number)
        if number.lstrip("0") and number.lstrip("0") not in candidates:
            candidates.append(number.lstrip("0"))
        # Common employee code widths in labour payroll sheets.
        for width in (4, 5, 6, 7, 8):
            padded = number.zfill(width)
            if padded not in candidates:
                candidates.append(padded)
    return candidates


def _resolve_emp_code(value: object, master_by_code: dict[str, dict]) -> str:
    candidates = _emp_code_candidates(value)
    if not candidates:
        return ""
    for candidate in candidates:
        if candidate in master_by_code:
            canonical = str(master_by_code[candidate].get("emp_code", "")).strip()
            return canonical or candidate
    return candidates[0]


def _looks_like_employee_code(emp_code: str) -> bool:
    code = str(emp_code or "").strip()
    if not code:
        return False
    if not _EMP_CODE_RE.match(code):
        return False
    # Reject obvious descriptive strings with no digits.
    if " " in code:
        return False
    return True


def _is_suspicious_unknown_code(emp_code: str, slno_val: str) -> bool:
    """Heuristic guard for non-employee numeric tokens leaking as emp codes."""
    code = str(emp_code or "").strip()
    if not code:
        return True
    digits_only = code.isdigit()
    if digits_only and len(code.lstrip("0") or "0") <= 3:
        return True
    if digits_only and slno_val and _is_number_like(slno_val):
        try:
            if int(float(code)) == int(float(slno_val)):
                return True
        except Exception:  # noqa: BLE001
            return False
    return False


def parse_muster_roll(
    excel_file: str | Path,
    employee_manager: EmployeeManager | None = None,
    company_id: int | None = None,
    allow_unknown_emp_codes: bool = False,
) -> pd.DataFrame:
    """Parse uploaded muster roll excel and return employee-wise attendance dataset."""
    file_path = Path(excel_file)
    if not file_path.exists():
        raise FileNotFoundError(f"Muster roll not found: {excel_file}")

    raw = pd.read_excel(file_path, header=None)
    header_idx = _find_header_row(raw)
    headers = _unique_headers(raw.iloc[header_idx].tolist())
    data = raw.iloc[header_idx + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all")

    columns = list(data.columns)
    col_sl_no = _resolve_column(columns, ("Sl.No", "SlNo", "SerialNo"))
    col_emp_code = _resolve_column(columns, ("EmployeeCode", "EmpCode", "Employee Code"))
    col_emp_name = _resolve_column(columns, ("EmployeeName", "Emp Name", "Name"))
    col_department = _resolve_column(columns, ("Department",))
    col_grade = _resolve_column(columns, ("Grade", "Designation", "NatureofWork", "Nature of Work"))
    col_normal_md = _resolve_column_safe(
        columns,
        (
            "Normal MD",
            "Normal M.D.",
            "NormalMD",
            "Normal Man Days",
            "Normal Days",
            "Man Days",
            "Mandays",
            "MD",
        ),
    )
    col_p = _resolve_column_safe(columns, ("P", "Present"))
    col_ot_hrs = _resolve_column_safe(
        columns,
        (
            "OT Hrs",
            "OT Hours",
            "OTHrs",
            "OTHours",
            "Normal OT Hrs",
            "Normal OT Hours",
            "Overtime Hrs",
            "Overtime Hours",
            "OT",
        ),
    )
    col_payable_days = _resolve_column_safe(
        columns,
        ("PayableDays", "Payable Days", "Final Days", "FinalDays", "Pay Days", "PayDays"),
    )

    if not col_emp_code:
        raise ValueError("Could not map EmployeeCode column in muster file")

    day_columns = [c for c in columns if str(c).strip().isdigit() and 1 <= int(str(c).strip()) <= 31]
    if not day_columns:
        day_columns = [
            c
            for c in columns
            if re.fullmatch(r"day\s*\d{1,2}", str(c).strip(), re.IGNORECASE)
            or re.fullmatch(r"d\d{1,2}", str(c).strip(), re.IGNORECASE)
        ]

    manager = employee_manager or get_manager()
    master_filters = {"company_id": int(company_id)} if company_id is not None else None
    master_rows = manager.get_all_employees(filters=master_filters, active_only=False)
    master_by_code: Dict[str, dict] = {}
    master_by_name: Dict[str, dict] = {}
    for row in master_rows:
        code = str(row["emp_code"]).strip()
        if not code:
            continue
        master_by_code[code] = row
        for alt in _emp_code_candidates(code):
            master_by_code.setdefault(alt, row)
        name_key = _normalize_name_key(row.get("emp_name"))
        if name_key:
            # Keep first mapping to avoid arbitrary reassignment in ambiguous names.
            master_by_name.setdefault(name_key, row)

    parsed_rows: List[Dict[str, object]] = []
    row_sequence = 0
    for _, row in data.iterrows():
        if _is_time_row(row, day_columns):
            continue

        slno_val = str(row.get(col_sl_no, "")).strip() if col_sl_no else ""
        if col_sl_no:
            if not slno_val:
                # Employee rows should carry serial numbers when column exists.
                continue
            if _TIME_RE.match(slno_val):
                continue
            # Most muster serial rows are numeric; non-numeric serial entries
            # are typically summary/footer rows and should not be treated as employees.
            if not _is_number_like(slno_val):
                continue

        emp_code = _resolve_emp_code(row.get(col_emp_code, ""), master_by_code)
        if not emp_code or emp_code.lower() == "nan":
            continue
        emp_name_raw = str(row.get(col_emp_name, "")).strip() if col_emp_name else ""
        dept_raw = str(row.get(col_department, "")).strip() if col_department else ""
        if emp_code not in master_by_code and emp_name_raw:
            by_name = master_by_name.get(_normalize_name_key(emp_name_raw))
            if by_name:
                emp_code = str(by_name.get("emp_code", "")).strip() or emp_code
        if _is_summary_row(emp_code, emp_name_raw, dept_raw, slno_val):
            continue
        if emp_code not in master_by_code and not _looks_like_employee_code(emp_code):
            # Ignore non-employee text rows leaking into employee code column.
            continue
        if emp_code not in master_by_code and _is_suspicious_unknown_code(emp_code, slno_val):
            continue
        if emp_code not in master_by_code and not emp_name_raw:
            # Unknown employee code without name is almost always noise.
            continue
        if master_by_code and emp_code not in master_by_code and not allow_unknown_emp_codes:
            # For strict processing, skip unknown master codes to prevent inflated rows.
            continue
        if (
            emp_code not in master_by_code
            and col_sl_no
            and _is_number_like(slno_val)
            and _is_number_like(emp_code)
            and int(float(slno_val)) == int(float(emp_code))
        ):
            # Guardrail: avoid interpreting serial numbers as employee codes.
            continue

        master = master_by_code.get(emp_code, {})

        # Prefer explicit "Normal MD" from uploaded muster if available.
        present_days = 0.0
        normal_md_cell = row.get(col_normal_md) if col_normal_md else None
        used_normal_md = col_normal_md is not None and _has_value(normal_md_cell)
        if used_normal_md:
            present_days = _to_float(normal_md_cell)
        elif col_p:
            present_days = _to_float(row.get(col_p))

        if present_days <= 0 and not used_normal_md:
            present_days = sum(_attendance_value(row.get(day)) for day in day_columns)
        if present_days <= 0 and not used_normal_md and col_payable_days:
            present_days = _to_float(row.get(col_payable_days))

        ot_hours = _to_float(row.get(col_ot_hrs)) if col_ot_hrs else 0.0
        designation = str(master.get("designation") or row.get(col_grade, "")).strip()
        department = str(master.get("department") or row.get(col_department, "")).strip()
        row_sequence += 1

        parsed_rows.append(
            {
                "_row_sequence": row_sequence,
                "emp_code": emp_code,
                "emp_name": str(master.get("emp_name") or emp_name_raw).strip(),
                "father_husband_name": str(master.get("father_husband_name", "")).strip(),
                "designation": designation,
                "grade": str(row.get(col_grade, "")).strip(),
                "department": department,
                "present_days": round(present_days, 2),
                "ot_hours": round(ot_hours, 2),
                "bank_account_no": str(master.get("bank_account_no", "")).strip(),
                "ifsc_code": str(master.get("ifsc_code", "")).strip(),
                "bank_name": str(master.get("bank_name", "")).strip(),
                "uan_no": str(master.get("uan_no", "")).strip(),
                "esic_no": str(master.get("esic_no", "")).strip(),
                "dob": str(master.get("dob", "")).strip(),
                "doj": str(master.get("doj", "")).strip(),
                "gender": str(master.get("gender", "")).strip(),
                "company_id": master.get("company_id"),
            }
        )

    if not parsed_rows:
        raise ValueError("No employee attendance rows detected in muster roll")

    # Guardrail: keep one row per employee code to avoid double counting
    # when source muster accidentally repeats employee blocks/pages.
    deduped_by_code: Dict[str, Dict[str, object]] = {}
    order: list[str] = []
    for row in parsed_rows:
        key = str(row.get("emp_code", "")).strip().upper()
        if key not in deduped_by_code:
            deduped_by_code[key] = dict(row)
            order.append(key)
            continue

        existing = deduped_by_code[key]
        existing["present_days"] = round(max(float(existing.get("present_days", 0) or 0), float(row.get("present_days", 0) or 0)), 2)
        existing["ot_hours"] = round(max(float(existing.get("ot_hours", 0) or 0), float(row.get("ot_hours", 0) or 0)), 2)
        for text_field in ("emp_name", "father_husband_name", "designation", "grade", "department"):
            if not str(existing.get(text_field, "")).strip() and str(row.get(text_field, "")).strip():
                existing[text_field] = row.get(text_field, "")

    final_rows = [deduped_by_code[key] for key in order]
    for idx, item in enumerate(final_rows, start=1):
        item["serial_no"] = idx
        item.pop("_row_sequence", None)

    return pd.DataFrame(final_rows)

