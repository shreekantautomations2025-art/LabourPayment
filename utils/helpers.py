"""General helper functions and system bootstrap utilities."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict

from config import DATA_DIR, INPUT_DIR, LOG_DIR, OUTPUT_DIR, TEMPLATE_DIR
from utils.date_utils import get_period_key


def ensure_base_directories() -> None:
    """Create all required base directories."""
    for path in (
        DATA_DIR,
        DATA_DIR / "monthly_data",
        DATA_DIR / "advances",
        INPUT_DIR,
        INPUT_DIR / "muster_rolls",
        OUTPUT_DIR,
        TEMPLATE_DIR,
        LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def get_period_directories(month: int, year: int) -> Dict[str, Path]:
    """Get monthly data and output folders."""
    key = get_period_key(month, year)
    data_period = DATA_DIR / "monthly_data" / key
    output_period = OUTPUT_DIR / key
    original_muster = data_period / "original_muster"

    data_period.mkdir(parents=True, exist_ok=True)
    output_period.mkdir(parents=True, exist_ok=True)
    original_muster.mkdir(parents=True, exist_ok=True)

    return {"data_period": data_period, "output_period": output_period, "original_muster": original_muster}


def backup_file(file_path: Path, backup_dir: Path | None = None) -> Path | None:
    """Create timestamped backup if file exists."""
    if not file_path.exists():
        return None
    target_dir = backup_dir or (file_path.parent / "backups")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"{file_path.stem}_{stamp}{file_path.suffix}"
    shutil.copy2(file_path, target)
    return target


def copy_original_muster(source: Path, target_dir: Path) -> Path:
    """Copy uploaded muster file into monthly archive."""
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"{source.stem}_{stamp}{source.suffix}"
    shutil.copy2(source, target)
    return target


def setup_logging() -> None:
    """Initialize logging handlers."""
    ensure_base_directories()
    error_log = LOG_DIR / "payroll_errors.log"
    audit_log = LOG_DIR / "payroll_audit.log"

    logging.getLogger().handlers.clear()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(error_log),
            logging.StreamHandler(),
        ],
    )

    audit_logger = logging.getLogger("audit")
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "").endswith("payroll_audit.log")
               for h in audit_logger.handlers):
        audit_handler = logging.FileHandler(audit_log)
        audit_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(logging.INFO)


def log_audit(action: str, metadata: dict | None = None) -> None:
    """Write action to audit log."""
    payload = {"action": action, "metadata": metadata or {}}
    logging.getLogger("audit").info(json.dumps(payload, default=str))

