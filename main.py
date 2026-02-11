"""Main entry point for payroll automation system."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

from modules.employee_manager import EmployeeManager
from modules.muster_parser import parse_muster_roll
from modules.payroll_processor import process_monthly_payroll
from modules.validators import validate_muster_roll
from utils.date_utils import parse_month_year
from utils.helpers import ensure_base_directories, setup_logging

LOGGER = logging.getLogger(__name__)


def _build_employee_payload(args: argparse.Namespace, existing: dict | None = None) -> Dict[str, Any]:
    base = dict(existing or {})
    mapping = {
        "emp_code": args.emp_code,
        "emp_name": args.emp_name,
        "father_husband_name": args.father_husband_name,
        "dob": args.dob,
        "gender": args.gender,
        "designation": args.designation,
        "doj": args.doj,
        "bank_account_no": args.bank_account_no,
        "ifsc_code": args.ifsc_code,
        "bank_name": args.bank_name,
        "pan_no": args.pan_no,
        "aadhaar_no": args.aadhaar_no,
        "uan_no": args.uan_no,
        "esic_no": args.esic_no,
        "department": args.department,
    }
    for key, value in mapping.items():
        if value is not None:
            base[key] = value
    return base


def handle_employee_command(args: argparse.Namespace, manager: EmployeeManager) -> int:
    if args.employee_action == "add":
        payload = _build_employee_payload(args)
        ok = manager.add_employee(payload)
        print("Employee added successfully." if ok else "Failed to add employee. Check validation logs.")
        return 0 if ok else 1

    if args.employee_action == "update":
        existing = manager.get_employee(args.emp_code, include_inactive=True)
        if not existing:
            print(f"Employee not found: {args.emp_code}")
            return 1
        payload = _build_employee_payload(args, existing=existing)
        ok = manager.update_employee(args.emp_code, payload)
        print("Employee updated successfully." if ok else "Failed to update employee.")
        return 0 if ok else 1

    if args.employee_action == "delete":
        ok = manager.delete_employee(args.emp_code, soft_delete=not args.permanent)
        print("Employee deleted successfully." if ok else "Employee not found.")
        return 0 if ok else 1

    if args.employee_action == "list":
        filters = {"search": args.search, "designation": args.designation_filter, "department": args.department_filter}
        rows = manager.get_all_employees(filters=filters, active_only=not args.include_inactive)
        if not rows:
            print("No employees found.")
            return 0
        for idx, row in enumerate(rows, start=1):
            print(
                f"{idx:03d} | {row['emp_code']} | {row['emp_name']} | {row['designation']} | "
                f"{row.get('department', '')} | {'Active' if row['is_active'] else 'Inactive'}"
            )
        print(f"Total employees: {len(rows)}")
        return 0

    if args.employee_action == "bulk-upload":
        result = manager.bulk_upload_employees(args.file)
        print(json.dumps(result, indent=2))
        return 0 if result["failed"] == 0 else 1

    if args.employee_action == "export":
        out = manager.export_employees_to_excel(args.output, active_only=not args.include_inactive)
        print(f"Exported employees to: {out}")
        return 0

    print("Unsupported employee action.")
    return 1


def handle_payroll_process(args: argparse.Namespace, manager: EmployeeManager) -> int:
    month, year = parse_month_year(args.month, args.year)
    parsed_df = parse_muster_roll(args.muster_file, employee_manager=manager)
    master_rows = manager.get_all_employees(active_only=True)
    master_codes = {r["emp_code"] for r in master_rows}
    master_designations = {r["emp_code"]: r["designation"] for r in master_rows}
    is_valid, errors, warnings = validate_muster_roll(parsed_df, master_codes, master_designations)

    print("\nMuster Preview (first 10 rows):")
    print(parsed_df.head(10).to_string(index=False))
    print(f"\nParsed employee rows: {len(parsed_df)}")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"- {w}")
    if errors:
        print("Validation Errors:")
        for e in errors:
            print(f"- {e}")
        return 1

    if not args.yes:
        confirm = input("\nProceed with wage calculation and report generation? (y/n): ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Operation cancelled by user.")
            return 0

    response = process_monthly_payroll(
        muster_file=args.muster_file,
        month=month,
        year=year,
        employee_manager=manager,
        adjustments_file=args.adjustments_file,
        require_clean_validation=True,
    )
    print("\nProcessing complete.")
    print(json.dumps(response, indent=2))
    return 0


def run_interactive_menu(manager: EmployeeManager) -> int:
    while True:
        print(
            "\nINDIAN LABOUR CONTRACTOR PAYROLL SYSTEM\n"
            "=======================================\n"
            "1. View All Employees\n"
            "2. Bulk Upload Employees\n"
            "3. Process Monthly Payroll\n"
            "0. Exit\n"
        )
        choice = input("Select option: ").strip()
        if choice == "0":
            return 0
        if choice == "1":
            rows = manager.get_all_employees(active_only=False)
            if not rows:
                print("No employees found.")
            else:
                for row in rows:
                    print(
                        f"{row['emp_code']} | {row['emp_name']} | {row['designation']} | "
                        f"{row.get('department', '')} | {'Active' if row['is_active'] else 'Inactive'}"
                    )
        elif choice == "2":
            file_path = input("Enter employee master excel file path: ").strip()
            result = manager.bulk_upload_employees(file_path)
            print(json.dumps(result, indent=2))
        elif choice == "3":
            muster = input("Enter muster roll excel file path: ").strip()
            month = int(input("Enter month (1-12): ").strip())
            year = int(input("Enter year (e.g. 2025): ").strip())
            res = process_monthly_payroll(muster_file=muster, month=month, year=year, employee_manager=manager)
            print(json.dumps(res, indent=2))
        else:
            print("Invalid option.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Indian Labour Contractor Payroll Automation System")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize employee master database")

    emp = subparsers.add_parser("employee", help="Employee CRUD and bulk upload")
    emp_sub = emp.add_subparsers(dest="employee_action")

    common_fields = [
        ("--emp-code", dict(required=False)),
        ("--emp-name", dict(required=False)),
        ("--father-husband-name", dict(required=False)),
        ("--dob", dict(required=False)),
        ("--gender", dict(required=False)),
        ("--designation", dict(required=False)),
        ("--doj", dict(required=False)),
        ("--bank-account-no", dict(required=False)),
        ("--ifsc-code", dict(required=False)),
        ("--bank-name", dict(required=False)),
        ("--pan-no", dict(required=False)),
        ("--aadhaar-no", dict(required=False)),
        ("--uan-no", dict(required=False)),
        ("--esic-no", dict(required=False)),
        ("--department", dict(required=False)),
    ]

    add = emp_sub.add_parser("add", help="Add a new employee")
    for arg, kwargs in common_fields:
        add.add_argument(arg, **kwargs)
    add.add_argument("--emp-code", required=True)
    add.add_argument("--emp-name", required=True)
    add.add_argument("--father-husband-name", required=True)
    add.add_argument("--dob", required=True)
    add.add_argument("--gender", required=True)
    add.add_argument("--designation", required=True)
    add.add_argument("--doj", required=True)
    add.add_argument("--bank-account-no", required=True)
    add.add_argument("--ifsc-code", required=True)
    add.add_argument("--bank-name", required=True)

    upd = emp_sub.add_parser("update", help="Update employee details")
    upd.add_argument("--emp-code", required=True)
    for arg, kwargs in common_fields:
        if arg != "--emp-code":
            upd.add_argument(arg, **kwargs)

    delete = emp_sub.add_parser("delete", help="Delete employee")
    delete.add_argument("--emp-code", required=True)
    delete.add_argument("--permanent", action="store_true", help="Hard delete instead of soft delete")

    list_cmd = emp_sub.add_parser("list", help="List employees")
    list_cmd.add_argument("--search")
    list_cmd.add_argument("--designation-filter")
    list_cmd.add_argument("--department-filter")
    list_cmd.add_argument("--include-inactive", action="store_true")

    bulk = emp_sub.add_parser("bulk-upload", help="Bulk upload from excel")
    bulk.add_argument("--file", required=True)

    export = emp_sub.add_parser("export", help="Export employees to excel")
    export.add_argument("--output", required=True)
    export.add_argument("--include-inactive", action="store_true")

    payroll = subparsers.add_parser("process-payroll", help="Process monthly payroll")
    payroll.add_argument("--muster-file", required=True)
    payroll.add_argument("--month", required=True, type=int)
    payroll.add_argument("--year", required=True, type=int)
    payroll.add_argument("--adjustments-file")
    payroll.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    return parser


def main() -> int:
    ensure_base_directories()
    setup_logging()

    parser = build_parser()
    args = parser.parse_args()
    manager = EmployeeManager()

    try:
        if not args.command:
            return run_interactive_menu(manager)

        if args.command == "init-db":
            manager.init_db()
            print(f"Employee database initialized at: {manager.db_path}")
            return 0

        if args.command == "employee":
            return handle_employee_command(args, manager)

        if args.command == "process-payroll":
            return handle_payroll_process(args, manager)

        parser.print_help()
        return 1
    except FileNotFoundError as exc:
        LOGGER.exception("File not found error")
        print(f"Error: {exc}")
        return 1
    except ValueError as exc:
        LOGGER.exception("Validation error")
        print(f"Validation error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unhandled error")
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

