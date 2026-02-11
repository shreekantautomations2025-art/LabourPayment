"""Muster roll parser for monthly attendance and OT extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from modules.employee_manager import EmployeeManager, get_manager

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


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


def parse_muster_roll(excel_file: str | Path, employee_manager: EmployeeManager | None = None) -> pd.DataFrame:
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
    col_p = _resolve_column(columns, ("P", "Present"))
    col_ot_hrs = _resolve_column(columns, ("OT Hrs", "OTHrs", "OTHours", "OT"))
    col_payable_days = _resolve_column(columns, ("PayableDays", "Final Days", "FinalDays"))

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
    master_rows = manager.get_all_employees(filters=None, active_only=False)
    master_by_code = {str(row["emp_code"]).strip(): row for row in master_rows}

    parsed_rows: List[Dict[str, object]] = []
    for _, row in data.iterrows():
        if _is_time_row(row, day_columns):
            continue

        emp_code = str(row.get(col_emp_code, "")).strip()
        if not emp_code or emp_code.lower() == "nan":
            continue
        if col_sl_no:
            slno_val = str(row.get(col_sl_no, "")).strip()
            if _TIME_RE.match(slno_val):
                continue

        master = master_by_code.get(emp_code, {})

        present_days = _to_float(row.get(col_p)) if col_p else 0.0
        if present_days <= 0:
            present_days = sum(_attendance_value(row.get(day)) for day in day_columns)
        if present_days <= 0 and col_payable_days:
            present_days = _to_float(row.get(col_payable_days))

        ot_hours = _to_float(row.get(col_ot_hrs)) if col_ot_hrs else 0.0
        designation = str(master.get("designation") or row.get(col_grade, "")).strip()
        department = str(master.get("department") or row.get(col_department, "")).strip()

        parsed_rows.append(
            {
                "emp_code": emp_code,
                "emp_name": str(master.get("emp_name") or row.get(col_emp_name, "")).strip(),
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
            }
        )

    if not parsed_rows:
        raise ValueError("No employee attendance rows detected in muster roll")

    return pd.DataFrame(parsed_rows)

