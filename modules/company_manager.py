"""Company/contractor configuration management for multi-company payroll."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    CLIENT_ADDRESS,
    CLIENT_GSTIN,
    CLIENT_LOCATION,
    CLIENT_NAME,
    CONTRACTOR_ADDRESS,
    CONTRACTOR_BANK_ACCOUNT,
    CONTRACTOR_BANK_NAME,
    CONTRACTOR_GSTIN,
    CONTRACTOR_IFSC,
    CONTRACTOR_NAME,
    CONTRACTOR_PAN,
    EMPLOYEE_DB_PATH,
    ESIC_EMPLOYEE_RATE,
    ESIC_EMPLOYER_CODE,
    ESIC_EMPLOYER_RATE,
    ESIC_WAGE_CEILING,
    GST_APPLICABLE,
    GST_RATE,
    INVOICE_PAYMENT_TERMS,
    INVOICE_PREFIX_MD,
    INVOICE_PREFIX_OT,
    LABOUR_DAILY_RATE,
    LABOUR_OT_RATE,
    PF_EMPLOYEE_RATE,
    PF_EMPLOYER_RATE,
    PF_ESTABLISHMENT_CODE,
    PT_FEB_ADDITIONAL,
    PT_REGISTRATION_NO,
    PT_SLABS,
    SUPERVISOR_DAILY_RATE,
    SUPERVISOR_OT_RATE,
)
from utils.helpers import log_audit


class CompanyManager:
    """CRUD and configuration operations for contractor companies."""

    def __init__(self, db_path: str | Path = EMPLOYEE_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self) -> None:
        """Create companies table and employee company mapping if needed."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    contractor_name TEXT NOT NULL,
                    contractor_address TEXT,
                    contractor_gstin TEXT,
                    contractor_pan TEXT,
                    contractor_bank_name TEXT,
                    contractor_bank_account TEXT,
                    contractor_ifsc TEXT,

                    client_name TEXT,
                    client_address TEXT,
                    client_gstin TEXT,
                    client_location TEXT,

                    pf_establishment_code TEXT,
                    esic_employer_code TEXT,
                    pt_registration_no TEXT,

                    labour_daily_rate REAL DEFAULT 785.58,
                    supervisor_daily_rate REAL DEFAULT 740.76,
                    labour_ot_rate REAL DEFAULT 92.13,
                    supervisor_ot_rate REAL DEFAULT 97.73,

                    pf_employee_rate REAL DEFAULT 0.12,
                    pf_employer_rate REAL DEFAULT 0.13,
                    esic_employee_rate REAL DEFAULT 0.0075,
                    esic_employer_rate REAL DEFAULT 0.0325,
                    esic_wage_ceiling REAL DEFAULT 21000,

                    pt_state TEXT DEFAULT 'Maharashtra',
                    pt_slab_1_min REAL DEFAULT 0,
                    pt_slab_1_max REAL DEFAULT 10000,
                    pt_slab_1_amount REAL DEFAULT 0,
                    pt_slab_2_min REAL DEFAULT 10001,
                    pt_slab_2_max REAL DEFAULT 25000,
                    pt_slab_2_amount REAL DEFAULT 175,
                    pt_slab_3_min REAL DEFAULT 25001,
                    pt_slab_3_max REAL DEFAULT 999999999,
                    pt_slab_3_amount REAL DEFAULT 300,
                    pt_feb_additional REAL DEFAULT 300,

                    gst_applicable BOOLEAN DEFAULT 0,
                    gst_rate REAL DEFAULT 0.18,
                    invoice_prefix_md TEXT DEFAULT 'MD',
                    invoice_prefix_ot TEXT DEFAULT 'OT',
                    payment_terms TEXT DEFAULT 'Net 7 Days',

                    currency TEXT DEFAULT 'INR',
                    date_format TEXT DEFAULT '%d-%b-%Y'
                )
                """
            )

            cursor.execute("PRAGMA table_info(employees)")
            columns = {row["name"] for row in cursor.fetchall()}
            if columns and "company_id" not in columns:
                cursor.execute("ALTER TABLE employees ADD COLUMN company_id INTEGER REFERENCES companies(company_id)")
            conn.commit()

        self._ensure_default_company()
        self._assign_default_company_to_unmapped_employees()

    @staticmethod
    def _default_company_payload() -> Dict[str, Any]:
        return {
            "company_name": CONTRACTOR_NAME,
            "contractor_name": CONTRACTOR_NAME,
            "contractor_address": CONTRACTOR_ADDRESS,
            "contractor_gstin": CONTRACTOR_GSTIN,
            "contractor_pan": CONTRACTOR_PAN,
            "contractor_bank_name": CONTRACTOR_BANK_NAME,
            "contractor_bank_account": CONTRACTOR_BANK_ACCOUNT,
            "contractor_ifsc": CONTRACTOR_IFSC,
            "client_name": CLIENT_NAME,
            "client_address": CLIENT_ADDRESS,
            "client_gstin": CLIENT_GSTIN,
            "client_location": CLIENT_LOCATION,
            "pf_establishment_code": PF_ESTABLISHMENT_CODE,
            "esic_employer_code": ESIC_EMPLOYER_CODE,
            "pt_registration_no": PT_REGISTRATION_NO,
            "labour_daily_rate": LABOUR_DAILY_RATE,
            "supervisor_daily_rate": SUPERVISOR_DAILY_RATE,
            "labour_ot_rate": LABOUR_OT_RATE,
            "supervisor_ot_rate": SUPERVISOR_OT_RATE,
            "pf_employee_rate": PF_EMPLOYEE_RATE,
            "pf_employer_rate": PF_EMPLOYER_RATE,
            "esic_employee_rate": ESIC_EMPLOYEE_RATE,
            "esic_employer_rate": ESIC_EMPLOYER_RATE,
            "esic_wage_ceiling": ESIC_WAGE_CEILING,
            "pt_state": "Maharashtra",
            "pt_slab_1_min": PT_SLABS[0]["min"],
            "pt_slab_1_max": PT_SLABS[0]["max"],
            "pt_slab_1_amount": PT_SLABS[0]["amount"],
            "pt_slab_2_min": PT_SLABS[1]["min"],
            "pt_slab_2_max": PT_SLABS[1]["max"],
            "pt_slab_2_amount": PT_SLABS[1]["amount"],
            "pt_slab_3_min": PT_SLABS[2]["min"],
            "pt_slab_3_max": PT_SLABS[2]["max"],
            "pt_slab_3_amount": PT_SLABS[2]["amount"],
            "pt_feb_additional": PT_FEB_ADDITIONAL,
            "gst_applicable": 1 if GST_APPLICABLE else 0,
            "gst_rate": GST_RATE,
            "invoice_prefix_md": INVOICE_PREFIX_MD,
            "invoice_prefix_ot": INVOICE_PREFIX_OT,
            "payment_terms": INVOICE_PAYMENT_TERMS,
            "currency": "INR",
            "date_format": "%d-%b-%Y",
        }

    def _ensure_default_company(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT company_id FROM companies LIMIT 1").fetchone()
            if row:
                return
        self.add_company(self._default_company_payload())

    def _assign_default_company_to_unmapped_employees(self) -> None:
        default_company = self.get_default_company_id()
        if default_company is None:
            return
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(employees)")
            columns = {row["name"] for row in cursor.fetchall()}
            if "company_id" not in columns:
                return
            cursor.execute("UPDATE employees SET company_id = ? WHERE company_id IS NULL", (default_company,))
            conn.commit()

    def get_default_company_id(self) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute("SELECT company_id FROM companies WHERE is_active = 1 ORDER BY company_id LIMIT 1").fetchone()
            if row:
                return int(row["company_id"])
        return None

    def add_company(self, company_data: Dict[str, Any]) -> int:
        """Add a new company and return company_id."""
        payload = dict(company_data)
        payload.setdefault("is_active", 1)
        if not str(payload.get("company_name", "")).strip():
            raise ValueError("company_name is required")
        if not str(payload.get("contractor_name", "")).strip():
            raise ValueError("contractor_name is required")

        columns = ", ".join(payload.keys())
        placeholders = ", ".join("?" for _ in payload)
        values = list(payload.values())
        query = f"INSERT INTO companies ({columns}) VALUES ({placeholders})"

        with self._connect() as conn:
            try:
                cur = conn.execute(query, values)
                company_id = int(cur.lastrowid)
                conn.commit()
                log_audit("company_added", {"company_id": company_id, "company_name": payload.get("company_name")})
                return company_id
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Company '{payload.get('company_name')}' already exists") from exc

    def get_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,)).fetchone()
            return dict(row) if row else None

    def get_all_companies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM companies"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY company_name"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]

    def update_company(self, company_id: int, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values()) + [company_id]
        query = f"UPDATE companies SET {set_clause} WHERE company_id = ?"

        with self._connect() as conn:
            cur = conn.execute(query, values)
            conn.commit()
            success = cur.rowcount > 0
            if success:
                log_audit("company_updated", {"company_id": company_id, "fields": sorted(updates.keys())})
            return success

    def delete_company(self, company_id: int, soft_delete: bool = True) -> bool:
        with self._connect() as conn:
            cur = conn.cursor()
            if soft_delete:
                cur.execute("UPDATE companies SET is_active = 0 WHERE company_id = ?", (company_id,))
                conn.commit()
                success = cur.rowcount > 0
                if success:
                    log_audit("company_soft_deleted", {"company_id": company_id})
                return success

            emp_count = 0
            cur.execute("PRAGMA table_info(employees)")
            columns = {row["name"] for row in cur.fetchall()}
            if "company_id" in columns:
                cur.execute("SELECT COUNT(*) FROM employees WHERE company_id = ?", (company_id,))
                emp_count = int(cur.fetchone()[0])
            if emp_count > 0:
                raise ValueError(f"Cannot delete company with {emp_count} employees. Reassign/remove employees first.")
            cur.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))
            conn.commit()
            success = cur.rowcount > 0
            if success:
                log_audit("company_hard_deleted", {"company_id": company_id})
            return success

    def get_wage_rates(self, company_id: int) -> Dict[str, float]:
        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Company ID {company_id} not found")
        return {
            "labour_daily_rate": float(company["labour_daily_rate"]),
            "supervisor_daily_rate": float(company["supervisor_daily_rate"]),
            "labour_ot_rate": float(company["labour_ot_rate"]),
            "supervisor_ot_rate": float(company["supervisor_ot_rate"]),
        }

    def get_pt_slabs(self, company_id: int) -> List[Dict[str, float]]:
        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Company ID {company_id} not found")
        return [
            {"min": float(company["pt_slab_1_min"]), "max": float(company["pt_slab_1_max"]), "amount": float(company["pt_slab_1_amount"])},
            {"min": float(company["pt_slab_2_min"]), "max": float(company["pt_slab_2_max"]), "amount": float(company["pt_slab_2_amount"])},
            {"min": float(company["pt_slab_3_min"]), "max": float(company["pt_slab_3_max"]), "amount": float(company["pt_slab_3_amount"])},
        ]

    def get_company_configuration(self, company_id: int) -> Dict[str, Any]:
        """Return company configuration payload consumable by calculators/generators."""
        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Company ID {company_id} not found")
        config = dict(company)
        config["pt_slabs"] = self.get_pt_slabs(company_id)
        config["gst_applicable"] = bool(config.get("gst_applicable", 0))
        return config

    def export_config(self, company_id: int, file_path: str | Path) -> Path:
        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Company ID {company_id} not found")
        payload = dict(company)
        payload.pop("company_id", None)
        payload.pop("created_date", None)
        out_path = Path(file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return out_path

    def import_config(self, file_path: str | Path) -> int:
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return self.add_company(data)


_DEFAULT_COMPANY_MANAGER: CompanyManager | None = None


def get_company_manager() -> CompanyManager:
    global _DEFAULT_COMPANY_MANAGER
    if _DEFAULT_COMPANY_MANAGER is None:
        _DEFAULT_COMPANY_MANAGER = CompanyManager()
    return _DEFAULT_COMPANY_MANAGER

