"""Employee master CRUD and bulk upload operations."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from config import EMPLOYEE_DB_PATH
from modules.validators import normalize_designation, normalize_gender, validate_employee_data
from utils.date_utils import parse_flexible_date
from utils.helpers import backup_file, log_audit
from utils.security import decrypt_text, encrypt_text

SENSITIVE_FIELDS = {"bank_account_no", "pan_no", "aadhaar_no"}


class EmployeeManager:
    """SQLite backed employee master management."""

    def __init__(self, db_path: Path | str = EMPLOYEE_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize employee master schema."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    emp_code TEXT PRIMARY KEY,
                    emp_name TEXT NOT NULL,
                    father_husband_name TEXT NOT NULL,
                    dob TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    designation TEXT NOT NULL,
                    doj TEXT NOT NULL,
                    bank_account_no TEXT NOT NULL,
                    ifsc_code TEXT NOT NULL,
                    bank_name TEXT NOT NULL,
                    pan_no TEXT,
                    aadhaar_no TEXT,
                    uan_no TEXT,
                    esic_no TEXT,
                    department TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_date TEXT NOT NULL,
                    updated_date TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(emp_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_employees_active ON employees(is_active)")
            conn.commit()

    @staticmethod
    def _sanitize_input(emp_data: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(emp_data)
        clean["emp_code"] = str(clean.get("emp_code", "")).strip()
        clean["emp_name"] = str(clean.get("emp_name", "")).strip()
        clean["father_husband_name"] = str(clean.get("father_husband_name", "")).strip()
        clean["dob"] = parse_flexible_date(clean.get("dob"))
        clean["gender"] = normalize_gender(str(clean.get("gender", "")).strip())
        clean["designation"] = normalize_designation(str(clean.get("designation", "")).strip())
        clean["doj"] = parse_flexible_date(clean.get("doj"))
        clean["bank_account_no"] = str(clean.get("bank_account_no", "")).strip()
        clean["ifsc_code"] = str(clean.get("ifsc_code", "")).strip().upper()
        clean["bank_name"] = str(clean.get("bank_name", "")).strip()
        clean["pan_no"] = str(clean.get("pan_no", "")).strip().upper()
        clean["aadhaar_no"] = str(clean.get("aadhaar_no", "")).strip()
        clean["uan_no"] = str(clean.get("uan_no", "")).strip()
        clean["esic_no"] = str(clean.get("esic_no", "")).strip()
        clean["department"] = str(clean.get("department", "")).strip()
        return clean

    @staticmethod
    def _encrypt_sensitive(emp_data: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(emp_data)
        for field in SENSITIVE_FIELDS:
            record[field] = encrypt_text(record.get(field, ""))
        return record

    @staticmethod
    def _decrypt_sensitive(row: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(row)
        for field in SENSITIVE_FIELDS:
            record[field] = decrypt_text(record.get(field, ""))
        record["is_active"] = bool(record.get("is_active", 0))
        return record

    def employee_exists(self, emp_code: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM employees WHERE emp_code = ?", (emp_code,)).fetchone()
            return row is not None

    def get_employee_codes(self, active_only: bool = False) -> List[str]:
        query = "SELECT emp_code FROM employees"
        params: tuple = ()
        if active_only:
            query += " WHERE is_active = 1"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [str(r["emp_code"]) for r in rows]

    def get_employee(self, emp_code: str, include_inactive: bool = True) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM employees WHERE emp_code = ?"
        params: tuple[Any, ...] = (emp_code,)
        if not include_inactive:
            query += " AND is_active = 1"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return self._decrypt_sensitive(dict(row))

    def add_employee(self, emp_data: Dict[str, Any], raise_on_error: bool = False) -> bool:
        """Add employee to master table."""
        clean = self._sanitize_input(emp_data)
        valid, errors = validate_employee_data(clean, existing_codes=self.get_employee_codes(active_only=False))
        if not valid:
            if raise_on_error:
                raise ValueError("; ".join(errors))
            return False

        now = datetime.now().isoformat(timespec="seconds")
        clean["created_date"] = now
        clean["updated_date"] = now
        clean["is_active"] = 1
        clean_enc = self._encrypt_sensitive(clean)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO employees (
                    emp_code, emp_name, father_husband_name, dob, gender, designation,
                    doj, bank_account_no, ifsc_code, bank_name, pan_no, aadhaar_no,
                    uan_no, esic_no, department, is_active, created_date, updated_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_enc["emp_code"],
                    clean_enc["emp_name"],
                    clean_enc["father_husband_name"],
                    clean_enc["dob"],
                    clean_enc["gender"],
                    clean_enc["designation"],
                    clean_enc["doj"],
                    clean_enc["bank_account_no"],
                    clean_enc["ifsc_code"],
                    clean_enc["bank_name"],
                    clean_enc["pan_no"],
                    clean_enc["aadhaar_no"],
                    clean_enc["uan_no"],
                    clean_enc["esic_no"],
                    clean_enc["department"],
                    clean_enc["is_active"],
                    clean_enc["created_date"],
                    clean_enc["updated_date"],
                ),
            )
            conn.commit()

        log_audit("employee_added", {"emp_code": clean["emp_code"]})
        return True

    def update_employee(self, emp_code: str, updated_data: Dict[str, Any], raise_on_error: bool = False) -> bool:
        """Update an existing employee."""
        current = self.get_employee(emp_code, include_inactive=True)
        if not current:
            return False

        merged = {**current, **updated_data}
        merged["emp_code"] = emp_code
        clean = self._sanitize_input(merged)

        existing_codes = set(self.get_employee_codes(active_only=False))
        existing_codes.discard(emp_code)
        valid, errors = validate_employee_data(clean, existing_codes=existing_codes)
        if not valid:
            if raise_on_error:
                raise ValueError("; ".join(errors))
            return False

        clean["updated_date"] = datetime.now().isoformat(timespec="seconds")
        clean["created_date"] = current.get("created_date", clean["updated_date"])
        clean["is_active"] = 1 if current.get("is_active", True) else 0
        clean_enc = self._encrypt_sensitive(clean)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE employees
                SET emp_name=?, father_husband_name=?, dob=?, gender=?, designation=?,
                    doj=?, bank_account_no=?, ifsc_code=?, bank_name=?, pan_no=?, aadhaar_no=?,
                    uan_no=?, esic_no=?, department=?, is_active=?, updated_date=?
                WHERE emp_code=?
                """,
                (
                    clean_enc["emp_name"],
                    clean_enc["father_husband_name"],
                    clean_enc["dob"],
                    clean_enc["gender"],
                    clean_enc["designation"],
                    clean_enc["doj"],
                    clean_enc["bank_account_no"],
                    clean_enc["ifsc_code"],
                    clean_enc["bank_name"],
                    clean_enc["pan_no"],
                    clean_enc["aadhaar_no"],
                    clean_enc["uan_no"],
                    clean_enc["esic_no"],
                    clean_enc["department"],
                    clean_enc["is_active"],
                    clean_enc["updated_date"],
                    emp_code,
                ),
            )
            conn.commit()

        log_audit("employee_updated", {"emp_code": emp_code, "fields": sorted(updated_data.keys())})
        return True

    def delete_employee(self, emp_code: str, soft_delete: bool = True) -> bool:
        """Delete employee using soft or hard mode."""
        if not self.employee_exists(emp_code):
            return False
        with self._connect() as conn:
            if soft_delete:
                conn.execute(
                    "UPDATE employees SET is_active = 0, updated_date = ? WHERE emp_code = ?",
                    (datetime.now().isoformat(timespec="seconds"), emp_code),
                )
                action = "employee_soft_deleted"
            else:
                conn.execute("DELETE FROM employees WHERE emp_code = ?", (emp_code,))
                action = "employee_hard_deleted"
            conn.commit()
        log_audit(action, {"emp_code": emp_code})
        return True

    def get_all_employees(self, filters: dict | None = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Fetch employees with optional filters."""
        filters = filters or {}
        query = "SELECT * FROM employees WHERE 1=1"
        params: List[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if filters.get("search"):
            query += " AND (emp_code LIKE ? OR emp_name LIKE ?)"
            token = f"%{filters['search']}%"
            params.extend([token, token])
        if filters.get("designation"):
            query += " AND lower(designation) = ?"
            params.append(str(filters["designation"]).strip().lower())
        if filters.get("department"):
            query += " AND lower(department) = ?"
            params.append(str(filters["department"]).strip().lower())
        if filters.get("ifsc_code"):
            query += " AND ifsc_code = ?"
            params.append(str(filters["ifsc_code"]).strip().upper())

        query += " ORDER BY emp_name ASC"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._decrypt_sensitive(dict(row)) for row in rows]

    @staticmethod
    def _normalize_bulk_columns(df: pd.DataFrame) -> pd.DataFrame:
        mapping = {
            "emp code": "emp_code",
            "employee code": "emp_code",
            "name": "emp_name",
            "employee name": "emp_name",
            "father/husband name": "father_husband_name",
            "father name": "father_husband_name",
            "dob": "dob",
            "gender": "gender",
            "designation": "designation",
            "doj": "doj",
            "bank account": "bank_account_no",
            "bank account no": "bank_account_no",
            "ifsc": "ifsc_code",
            "ifsc code": "ifsc_code",
            "bank name": "bank_name",
            "pan": "pan_no",
            "aadhaar": "aadhaar_no",
            "uan": "uan_no",
            "esic no": "esic_no",
            "esic number": "esic_no",
            "department": "department",
        }

        normalized_cols = {}
        for col in df.columns:
            key = str(col).strip().lower().replace("_", " ")
            normalized_cols[col] = mapping.get(key, key.replace(" ", "_"))
        return df.rename(columns=normalized_cols)

    def bulk_upload_employees(self, excel_file: str | Path) -> Dict[str, Any]:
        """Bulk upload employee records from excel file."""
        file_path = Path(excel_file)
        if not file_path.exists():
            return {"success": 0, "failed": 0, "errors": [f"File not found: {file_path}"]}

        backup_file(self.db_path, self.db_path.parent / "backups")
        df = pd.read_excel(file_path)
        df = self._normalize_bulk_columns(df)
        records = df.to_dict(orient="records")

        result = {"success": 0, "failed": 0, "errors": []}
        for idx, record in enumerate(records, start=2):
            payload = {k: ("" if pd.isna(v) else v) for k, v in record.items()}
            emp_code = str(payload.get("emp_code", "")).strip()
            if not emp_code:
                result["failed"] += 1
                result["errors"].append(f"Row {idx}: Missing emp_code")
                continue
            try:
                if self.employee_exists(emp_code):
                    ok = self.update_employee(emp_code, payload)
                else:
                    ok = self.add_employee(payload)
                if ok:
                    result["success"] += 1
                else:
                    result["failed"] += 1
                    result["errors"].append(f"Row {idx}: Validation failed for employee {emp_code}")
            except Exception as exc:  # noqa: BLE001
                result["failed"] += 1
                result["errors"].append(f"Row {idx}: {exc}")

        log_audit(
            "employee_bulk_upload",
            {"file": str(file_path), "success": result["success"], "failed": result["failed"]},
        )
        return result

    def export_employees_to_excel(self, output_file: str | Path, active_only: bool = True) -> Path:
        """Export employee list to excel."""
        rows = self.get_all_employees(active_only=active_only)
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_excel(out_path, index=False)
        return out_path


_DEFAULT_MANAGER: Optional[EmployeeManager] = None


def get_manager() -> EmployeeManager:
    global _DEFAULT_MANAGER
    if _DEFAULT_MANAGER is None:
        _DEFAULT_MANAGER = EmployeeManager()
    return _DEFAULT_MANAGER


def init_db() -> None:
    get_manager().init_db()


def add_employee(emp_data: dict) -> bool:
    return get_manager().add_employee(emp_data)


def update_employee(emp_code: str, updated_data: dict) -> bool:
    return get_manager().update_employee(emp_code, updated_data)


def delete_employee(emp_code: str, soft_delete: bool = True) -> bool:
    return get_manager().delete_employee(emp_code, soft_delete=soft_delete)


def get_all_employees(filters: dict | None = None, active_only: bool = True) -> List[Dict[str, Any]]:
    return get_manager().get_all_employees(filters=filters, active_only=active_only)


def bulk_upload_employees(excel_file: str) -> Dict[str, Any]:
    return get_manager().bulk_upload_employees(excel_file)

