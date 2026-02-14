"""Employee master CRUD and bulk upload operations."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from config import EMPLOYEE_DB_PATH
from modules.company_manager import CompanyManager
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
                    company_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_date TEXT NOT NULL,
                    updated_date TEXT NOT NULL
                )
                """
            )
            cursor = conn.execute("PRAGMA table_info(employees)")
            columns = {row["name"] for row in cursor.fetchall()}
            if "company_id" not in columns:
                conn.execute("ALTER TABLE employees ADD COLUMN company_id INTEGER")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(emp_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_employees_active ON employees(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_employees_company ON employees(company_id)")
            conn.commit()

    @staticmethod
    def _normalize_emp_code(value: object) -> str:
        code = str(value or "").strip()
        if not code:
            return ""
        compact = code.replace(" ", "")
        if re.fullmatch(r"\d+\.0+", compact):
            return str(int(float(compact)))
        return compact

    @staticmethod
    def _emp_code_aliases(emp_code: str) -> set[str]:
        code = EmployeeManager._normalize_emp_code(emp_code)
        if not code:
            return set()
        aliases = {code, code.upper()}
        if code.isdigit():
            number = str(int(code))
            aliases.update({number, number.upper()})
            for width in (4, 5, 6, 7, 8):
                aliases.add(number.zfill(width))
        return aliases

    @staticmethod
    def _sanitize_input(emp_data: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(emp_data)
        clean["emp_code"] = EmployeeManager._normalize_emp_code(clean.get("emp_code", ""))
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
        company_id = clean.get("company_id")
        try:
            clean["company_id"] = int(company_id) if company_id not in (None, "", "nan") else None
        except (TypeError, ValueError):
            clean["company_id"] = None
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

    def _resolve_existing_emp_code(self, emp_code: str) -> str | None:
        """Return existing canonical employee code using case-insensitive match."""
        code = self._normalize_emp_code(emp_code)
        if not code:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT emp_code FROM employees WHERE UPPER(emp_code) = UPPER(?) LIMIT 1",
                (code,),
            ).fetchone()
            if row:
                return str(row["emp_code"]).strip()

            aliases = self._emp_code_aliases(code)
            rows = conn.execute("SELECT emp_code FROM employees").fetchall()
            for item in rows:
                candidate = str(item["emp_code"]).strip()
                if self._normalize_emp_code(candidate) in aliases or candidate in aliases:
                    return candidate
        return None

    def get_employee_codes(self, active_only: bool = False) -> List[str]:
        query = "SELECT emp_code FROM employees"
        params: tuple = ()
        if active_only:
            query += " WHERE is_active = 1"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [str(r["emp_code"]) for r in rows]

    def get_employee(self, emp_code: str, include_inactive: bool = True, company_id: int | None = None) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM employees WHERE emp_code = ?"
        params: tuple[Any, ...] = (emp_code,)
        if not include_inactive:
            query += " AND is_active = 1"
        if company_id is not None:
            query += " AND company_id = ?"
            params += (int(company_id),)
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        if not row:
            return None
        return self._decrypt_sensitive(dict(row))

    def add_employee(self, emp_data: Dict[str, Any], raise_on_error: bool = False) -> bool:
        """Add employee to master table."""
        clean = self._sanitize_input(emp_data)
        existing_code_alias = self._resolve_existing_emp_code(clean.get("emp_code", ""))
        if existing_code_alias and str(existing_code_alias).strip().upper() != str(clean.get("emp_code", "")).strip().upper():
            if raise_on_error:
                raise ValueError(
                    f"emp_code '{clean.get('emp_code')}' maps to existing employee code '{existing_code_alias}'."
                )
            return False
        if clean.get("company_id") is None:
            clean["company_id"] = CompanyManager(self.db_path).get_default_company_id()
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
                    uan_no, esic_no, department, is_active, created_date, updated_date, company_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    clean_enc["company_id"],
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
        if clean.get("company_id") is None:
            clean["company_id"] = current.get("company_id") or CompanyManager(self.db_path).get_default_company_id()

        existing_codes = {
            code
            for code in self.get_employee_codes(active_only=False)
            if str(code).strip().upper() != str(emp_code).strip().upper()
        }
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
                    uan_no=?, esic_no=?, department=?, company_id=?, is_active=?, updated_date=?
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
                    clean_enc["company_id"],
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
        if filters.get("company_id") is not None:
            query += " AND company_id = ?"
            params.append(int(filters["company_id"]))

        query += " ORDER BY emp_name ASC"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._decrypt_sensitive(dict(row)) for row in rows]

    @staticmethod
    def _normalize_bulk_columns(df: pd.DataFrame) -> pd.DataFrame:
        mapping = {
            "emp code": "emp_code",
            "empcode": "emp_code",
            "employee code": "emp_code",
            "name": "emp_name",
            "empname": "emp_name",
            "employee name": "emp_name",
            "father/husband name": "father_husband_name",
            "fatherhusbandname": "father_husband_name",
            "father name": "father_husband_name",
            "dob": "dob",
            "gender": "gender",
            "designation": "designation",
            "doj": "doj",
            "bank account": "bank_account_no",
            "bankaccount": "bank_account_no",
            "bank account no": "bank_account_no",
            "ifsc": "ifsc_code",
            "ifsc code": "ifsc_code",
            "ifsccode": "ifsc_code",
            "bank name": "bank_name",
            "pan": "pan_no",
            "aadhaar": "aadhaar_no",
            "uan": "uan_no",
            "esic no": "esic_no",
            "esic number": "esic_no",
            "esicno": "esic_no",
            "department": "department",
            "company id": "company_id",
            "companyid": "company_id",
            "sl no": "serial_no",
            "sl.no": "serial_no",
            "slno": "serial_no",
            "serial no": "serial_no",
            "serial number": "serial_no",
            "sr no": "serial_no",
            "sr.no": "serial_no",
            "srno": "serial_no",
            "s no": "serial_no",
            "s.no": "serial_no",
            "sno": "serial_no",
        }

        normalized_cols = {}
        for col in df.columns:
            key = str(col).strip().lower().replace("_", " ")
            normalized_cols[col] = mapping.get(key, key.replace(" ", "_"))
        return df.rename(columns=normalized_cols)

    @staticmethod
    def _parse_text_table(text: str) -> pd.DataFrame:
        lines = [ln.strip() for ln in text.splitlines() if ln and ln.strip()]
        if not lines:
            raise ValueError("No readable text found in file")

        header_idx = 0
        for idx, line in enumerate(lines):
            low = line.lower()
            if "emp" in low and ("code" in low or "name" in low):
                header_idx = idx
                break

        header_line = lines[header_idx]
        delimiters = ["|", "\t", ",", ";"]
        for delim in delimiters:
            if header_line.count(delim) < 2:
                continue
            headers = [h.strip() for h in header_line.split(delim)]
            rows = []
            for line in lines[header_idx + 1 :]:
                if delim not in line:
                    continue
                parts = [p.strip() for p in line.split(delim)]
                if len(parts) < len(headers):
                    parts.extend([""] * (len(headers) - len(parts)))
                rows.append(parts[: len(headers)])
            if rows:
                return pd.DataFrame(rows, columns=headers)

        # Fallback: split by repeated spaces
        header_parts = [p.strip() for p in re.split(r"\s{2,}", header_line) if p.strip()]
        if len(header_parts) >= 3:
            rows = []
            for line in lines[header_idx + 1 :]:
                parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
                if not parts:
                    continue
                if len(parts) < len(header_parts):
                    parts.extend([""] * (len(header_parts) - len(parts)))
                rows.append(parts[: len(header_parts)])
            if rows:
                return pd.DataFrame(rows, columns=header_parts)

        raise ValueError("Unable to parse tabular employee data from file")

    def _load_bulk_dataframe(self, file_path: Path) -> pd.DataFrame:
        suffix = file_path.suffix.lower()

        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path)

        if suffix in {".csv"}:
            return pd.read_csv(file_path)

        if suffix in {".txt"}:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
            first_line = next((ln for ln in raw_text.splitlines() if ln.strip()), "")
            if "|" in first_line and first_line.count("|") >= 2:
                return pd.read_csv(file_path, sep="|")
            if "\t" in first_line and first_line.count("\t") >= 2:
                return pd.read_csv(file_path, sep="\t")
            try:
                return pd.read_csv(file_path, sep=None, engine="python")
            except Exception:
                return self._parse_text_table(raw_text)

        if suffix in {".json"}:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return pd.DataFrame(raw)
            if isinstance(raw, dict):
                if isinstance(raw.get("employees"), list):
                    return pd.DataFrame(raw["employees"])
                return pd.DataFrame([raw])
            raise ValueError("Unsupported JSON structure for bulk employee upload")

        if suffix in {".pdf"}:
            try:
                from pypdf import PdfReader
            except Exception as exc:  # noqa: BLE001
                raise ValueError("PDF upload requires 'pypdf' dependency") from exc
            reader = PdfReader(str(file_path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            if not text.strip():
                raise ValueError("No extractable text found in PDF")
            return self._parse_text_table(text)

        # Best-effort fallback for any other extension.
        try:
            return pd.read_csv(file_path, sep=None, engine="python")
        except Exception:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return self._parse_text_table(text)

    @staticmethod
    def _normalize_bulk_serial_numbers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Normalize serial numbers to a contiguous 1..N sequence when present."""
        serial_candidates = ["serial_no", "sl_no", "slno", "s_no", "sr_no", "serial", "sno"]
        serial_col = next((col for col in serial_candidates if col in df.columns), None)
        if not serial_col:
            return df, []

        out = df.copy()
        warnings: list[str] = []
        parsed = pd.to_numeric(out[serial_col], errors="coerce")
        expected = pd.Series(range(1, len(out) + 1), dtype="float64")
        actual = parsed.reset_index(drop=True)
        if actual.isna().any() or not actual.equals(expected):
            out[serial_col] = range(1, len(out) + 1)
            warnings.append(
                "Serial numbers were non-sequential/invalid in uploaded file and have been normalized to 1..N."
            )
        return out, warnings

    @staticmethod
    def _dedupe_bulk_records(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Drop duplicate employee codes from upload payload (case-insensitive)."""
        if "emp_code" not in df.columns:
            return df, []

        seen: set[str] = set()
        keep_rows: list[int] = []
        duplicate_codes: set[str] = set()
        for idx, value in enumerate(df["emp_code"].tolist()):
            code = str(value or "").strip()
            if not code:
                keep_rows.append(idx)
                continue
            key = code.upper()
            if key in seen:
                duplicate_codes.add(code)
                continue
            seen.add(key)
            keep_rows.append(idx)

        if len(keep_rows) == len(df):
            return df, []

        out = df.iloc[keep_rows].reset_index(drop=True)
        warnings = [
            "Duplicate employee codes found in upload and skipped: "
            + ", ".join(sorted({str(code).strip() for code in duplicate_codes}))
        ]
        return out, warnings

    def bulk_upload_employees(self, excel_file: str | Path, company_id: int | None = None) -> Dict[str, Any]:
        """Bulk upload employee records from xlsx/xls/csv/json/txt/pdf."""
        file_path = Path(excel_file)
        if not file_path.exists():
            return {"success": 0, "failed": 0, "errors": [f"File not found: {file_path}"]}

        backup_file(self.db_path, self.db_path.parent / "backups")
        try:
            df = self._load_bulk_dataframe(file_path)
        except Exception as exc:  # noqa: BLE001
            return {"success": 0, "failed": 0, "errors": [f"Unable to parse file '{file_path.name}': {exc}"]}

        df = self._normalize_bulk_columns(df)
        df, serial_warnings = self._normalize_bulk_serial_numbers(df)
        df, dedupe_warnings = self._dedupe_bulk_records(df)
        records = df.to_dict(orient="records")

        result = {"success": 0, "failed": 0, "skipped": 0, "errors": [], "warnings": []}
        result["warnings"].extend(serial_warnings)
        result["warnings"].extend(dedupe_warnings)
        seen_upload_codes: set[str] = set()
        for idx, record in enumerate(records, start=2):
            payload = {k: ("" if pd.isna(v) else v) for k, v in record.items()}
            if company_id is not None:
                payload["company_id"] = int(company_id)
            emp_code = str(payload.get("emp_code", "")).strip()
            if not emp_code:
                result["failed"] += 1
                result["errors"].append(f"Row {idx}: Missing emp_code")
                continue
            upload_key = emp_code.upper()
            if upload_key in seen_upload_codes:
                result["skipped"] += 1
                result["warnings"].append(f"Row {idx}: Duplicate emp_code '{emp_code}' skipped in upload file.")
                continue
            seen_upload_codes.add(upload_key)
            try:
                existing_code = self._resolve_existing_emp_code(emp_code)
                if existing_code:
                    ok = self.update_employee(existing_code, payload)
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
            {
                "file": str(file_path),
                "success": result["success"],
                "failed": result["failed"],
                "skipped": result["skipped"],
            },
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


def bulk_upload_employees(excel_file: str, company_id: int | None = None) -> Dict[str, Any]:
    return get_manager().bulk_upload_employees(excel_file, company_id=company_id)

