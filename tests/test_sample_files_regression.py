"""Regression checks for real-world sample files when available."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.employee_manager import EmployeeManager
from modules.muster_parser import parse_muster_roll


SAMPLE_MUSTER_CANDIDATES = [
    "input/muster_rolls/Shankar_Patil_MusterRoll_Nov_2025_updated_1.xlsx",
    "input/samples/Shankar_Patil_MusterRoll_Nov_2025_updated_1.xlsx",
    "Shankar_Patil_MusterRoll_Nov_2025_updated_1.xlsx",
]


def _first_existing(base: Path, paths: list[str]) -> Path | None:
    for rel in paths:
        candidate = base / rel
        if candidate.exists():
            return candidate
    return None


def test_parse_real_sample_muster_if_available(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    sample_file = _first_existing(repo_root, SAMPLE_MUSTER_CANDIDATES)
    if not sample_file:
        pytest.skip("Real sample muster file not found in repository; skipping regression test.")

    manager = EmployeeManager(tmp_path / "sample_employees.db")
    parsed = parse_muster_roll(sample_file, employee_manager=manager)

    assert not parsed.empty
    assert {"emp_code", "present_days", "ot_hours"}.issubset(set(parsed.columns))
