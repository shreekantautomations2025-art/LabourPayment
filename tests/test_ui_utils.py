"""Tests for Streamlit UI helper utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import ui_utils


class DummyUpload:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def test_save_uploaded_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_utils, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(ui_utils, "DATA_DIR", tmp_path / "data")

    upload = DummyUpload("sample.xlsx", b"hello-world")
    target_dir = tmp_path / "uploads"
    written = ui_utils.save_uploaded_file(upload, target_dir, prefix="test")

    assert written.exists()
    assert written.suffix == ".xlsx"
    assert written.read_bytes() == b"hello-world"


def test_discover_periods_and_list_files(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    (output_dir / "2025_07").mkdir(parents=True)
    (output_dir / "2025_08").mkdir(parents=True)
    (output_dir / "2025_08" / "Bank_Payment_Aug_2025.xlsx").write_bytes(b"x")
    (output_dir / "2025_08" / "OT_Invoice_Aug_2025.pdf").write_bytes(b"y")

    monkeypatch.setattr(ui_utils, "OUTPUT_DIR", output_dir)

    periods = ui_utils.discover_output_periods()
    assert periods == ["2025_08", "2025_07"]

    files = ui_utils.list_output_files("2025_08", extensions=[".xlsx"])
    assert len(files) == 1
    assert files[0].name.endswith(".xlsx")


def test_dataframe_to_excel_bytes_has_expected_sheet():
    df = pd.DataFrame([{"emp_code": "E001", "present_days": 26, "ot_hours": 10}])
    payload = ui_utils.dataframe_to_excel_bytes(df, instructions=["line1", "line2"])

    assert isinstance(payload, bytes)
    assert len(payload) > 100

    # Smoke parse resulting workbook.
    from io import BytesIO

    parsed = pd.read_excel(BytesIO(payload), sheet_name="Editable_Preview")
    assert parsed.loc[0, "emp_code"] == "E001"

