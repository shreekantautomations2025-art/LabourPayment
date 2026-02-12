"""Validation functions for employee and muster data."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, List, Tuple

import pandas as pd

ALLOWED_GENDERS = {"m", "f", "male", "female", "other"}
ALLOWED_DESIGNATIONS = {"labour", "unskilled", "semi-skilled", "semiskilled", "supervisor", "semi skilled"}

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
AADHAAR_RE = re.compile(r"^\d{12}$")
EMP_CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
NAME_RE = re.compile(r"^[A-Za-z .'-]+$")


def _normalize_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = _normalize_text(value)
    if not text:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(text, dayfirst=True).date()
    except Exception:
        return None


def normalize_gender(gender: str) -> str:
    raw = _normalize_text(gender).lower()
    if raw in {"m", "male"}:
        return "Male"
    if raw in {"f", "female"}:
        return "Female"
    if raw == "other":
        return "Other"
    return gender


def normalize_designation(designation: str) -> str:
    raw = _normalize_text(designation).lower()
    if raw in {"semi skilled", "semiskilled"}:
        return "Semi-Skilled"
    if raw in {"semi-skilled"}:
        return "Semi-Skilled"
    if raw == "supervisor":
        return "Supervisor"
    if raw in {"unskilled", "labour"}:
        return "Labour"
    return designation


def validate_employee_data(emp_data: dict, existing_codes: Iterable[str] | None = None) -> Tuple[bool, List[str]]:
    """Validate employee data before save."""
    errors: List[str] = []
    existing_codes = set(existing_codes or [])

    mandatory_fields = [
        "emp_code",
        "emp_name",
        "father_husband_name",
        "dob",
        "gender",
        "designation",
        "doj",
        "bank_account_no",
        "ifsc_code",
        "bank_name",
    ]
    for field in mandatory_fields:
        if not _normalize_text(emp_data.get(field)):
            errors.append(f"{field} is required")

    emp_code = _normalize_text(emp_data.get("emp_code"))
    if emp_code and not EMP_CODE_RE.match(emp_code):
        errors.append("emp_code must be alphanumeric and may include _ or -")
    if emp_code and emp_code in existing_codes:
        errors.append(f"emp_code '{emp_code}' already exists")

    emp_name = _normalize_text(emp_data.get("emp_name"))
    if emp_name and not NAME_RE.match(emp_name):
        errors.append("emp_name contains invalid characters")

    father_name = _normalize_text(emp_data.get("father_husband_name"))
    if father_name and not NAME_RE.match(father_name):
        errors.append("father_husband_name contains invalid characters")

    dob = _parse_date(emp_data.get("dob"))
    if dob is None:
        errors.append("dob is invalid")
    else:
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18 or age > 65:
            errors.append("employee age must be between 18 and 65")

    doj = _parse_date(emp_data.get("doj"))
    if doj is None:
        errors.append("doj is invalid")

    gender = _normalize_text(emp_data.get("gender")).lower()
    if gender and gender not in ALLOWED_GENDERS:
        errors.append("gender must be one of M/F/Male/Female/Other")

    designation = _normalize_text(emp_data.get("designation")).lower()
    if designation and designation not in ALLOWED_DESIGNATIONS:
        errors.append("designation must be Labour/Unskilled/Semi-Skilled/Supervisor")

    bank_account = re.sub(r"\s+", "", _normalize_text(emp_data.get("bank_account_no")))
    if bank_account and (not bank_account.isdigit() or not (9 <= len(bank_account) <= 18)):
        errors.append("bank_account_no must be numeric and 9-18 digits")

    ifsc = _normalize_text(emp_data.get("ifsc_code")).upper()
    if ifsc and not IFSC_RE.match(ifsc):
        errors.append("ifsc_code is invalid (expected format: SBIN0001234)")

    pan = _normalize_text(emp_data.get("pan_no")).upper()
    if pan and not PAN_RE.match(pan):
        errors.append("pan_no is invalid")

    aadhaar = re.sub(r"\s+", "", _normalize_text(emp_data.get("aadhaar_no")))
    if aadhaar and not AADHAAR_RE.match(aadhaar):
        errors.append("aadhaar_no must be exactly 12 digits")

    uan = re.sub(r"\s+", "", _normalize_text(emp_data.get("uan_no")))
    if uan and (not uan.isdigit() or len(uan) != 12):
        errors.append("uan_no must be exactly 12 digits if provided")

    return len(errors) == 0, errors


def validate_muster_roll(
    df: pd.DataFrame,
    master_emp_codes: Iterable[str] | None = None,
    master_designation_map: dict | None = None,
) -> Tuple[bool, List[str], List[str]]:
    """Validate parsed muster roll dataframe."""
    errors: List[str] = []
    warnings: List[str] = []
    master_emp_codes = set(master_emp_codes or [])
    master_designation_map = master_designation_map or {}

    required_columns = {"emp_code", "emp_name", "designation", "present_days", "ot_hours"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(sorted(missing_columns))}")
        return False, errors, warnings

    if df.empty:
        errors.append("Muster data is empty")
        return False, errors, warnings

    duplicate_codes = df[df["emp_code"].astype(str).str.strip().duplicated(keep=False)]["emp_code"].tolist()
    if duplicate_codes:
        errors.append(f"Duplicate employee codes in muster roll: {sorted(set(duplicate_codes))}")

    for _, row in df.iterrows():
        emp_code = str(row.get("emp_code", "")).strip()
        if not emp_code:
            errors.append("Found blank employee code")
            continue

        if master_emp_codes and emp_code not in master_emp_codes:
            errors.append(f"Employee code not found in master data: {emp_code}")

        try:
            present_days = float(row.get("present_days", 0))
            if present_days < 0 or present_days > 31:
                errors.append(f"Invalid present_days ({present_days}) for {emp_code}")
        except (TypeError, ValueError):
            errors.append(f"present_days is not numeric for {emp_code}")

        try:
            ot_hours = float(row.get("ot_hours", 0))
            if ot_hours < 0 or ot_hours > 300:
                errors.append(f"Invalid ot_hours ({ot_hours}) for {emp_code}")
        except (TypeError, ValueError):
            errors.append(f"ot_hours is not numeric for {emp_code}")

        master_designation = master_designation_map.get(emp_code)
        muster_designation = str(row.get("designation", "")).strip()
        if master_designation and muster_designation and master_designation.lower() != muster_designation.lower():
            warnings.append(
                f"Designation mismatch for {emp_code}: master='{master_designation}', muster='{muster_designation}'"
            )

    return len(errors) == 0, errors, warnings

