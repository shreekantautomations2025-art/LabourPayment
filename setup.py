"""Setup utility commands."""

from __future__ import annotations

import argparse

from modules.employee_manager import EmployeeManager
from utils.helpers import ensure_base_directories, setup_logging


def init_db() -> None:
    ensure_base_directories()
    setup_logging()
    manager = EmployeeManager()
    manager.init_db()
    print(f"Database initialized at {manager.db_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup utilities for payroll automation")
    parser.add_argument("command", choices=["init_db"], help="Command to execute")
    args = parser.parse_args()
    if args.command == "init_db":
        init_db()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

