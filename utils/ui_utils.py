"""Utility helpers used by the Streamlit UI layer."""

from __future__ import annotations

import io
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Iterable

from config import DATA_DIR, INPUT_DIR, OUTPUT_DIR


def ensure_ui_directories() -> None:
    """Create UI specific upload folders if missing."""
    (INPUT_DIR / "ui_uploads").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "ui_temp").mkdir(parents=True, exist_ok=True)


def _extract_upload_bytes(uploaded_file: object) -> bytes:
    if uploaded_file is None:
        raise ValueError("uploaded_file cannot be None")

    if hasattr(uploaded_file, "getbuffer"):
        return bytes(uploaded_file.getbuffer())
    if hasattr(uploaded_file, "getvalue"):
        return bytes(uploaded_file.getvalue())
    if hasattr(uploaded_file, "read"):
        payload = uploaded_file.read()
        if isinstance(payload, bytes):
            return payload
        return bytes(payload)
    raise ValueError("Unsupported uploaded file object")


def save_uploaded_file(
    uploaded_file: object,
    destination_dir: Path,
    *,
    prefix: str = "",
    keep_original_name: bool = True,
    fallback_suffix: str = ".bin",
) -> Path:
    """Persist uploaded file-like object and return absolute path."""
    ensure_ui_directories()
    destination_dir.mkdir(parents=True, exist_ok=True)

    name = getattr(uploaded_file, "name", "") if keep_original_name else ""
    name = str(name or "").strip()
    suffix = Path(name).suffix if name else fallback_suffix
    stem = Path(name).stem if name else "upload"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix_part = f"{prefix}_" if prefix else ""
    safe_name = f"{prefix_part}{stem}_{stamp}{suffix}"
    output_path = destination_dir / safe_name
    output_path.write_bytes(_extract_upload_bytes(uploaded_file))
    return output_path


def discover_output_periods() -> list[str]:
    """Return available output period keys sorted by latest first."""
    if not OUTPUT_DIR.exists():
        return []
    periods = [p.name for p in OUTPUT_DIR.iterdir() if p.is_dir() and len(p.name) == 7 and p.name[4] == "_"]
    return sorted(periods, reverse=True)


def list_output_files(period_key: str, extensions: Iterable[str] | None = None) -> list[Path]:
    """List generated files for a period key (YYYY_MM)."""
    target_dir = OUTPUT_DIR / period_key
    if not target_dir.exists():
        return []

    exts = {e.lower() for e in (extensions or [])}
    files = [p for p in target_dir.iterdir() if p.is_file()]
    if exts:
        files = [p for p in files if p.suffix.lower() in exts]
    return sorted(files, key=lambda p: p.name.lower())


def read_binary_file(path: str | Path) -> bytes:
    """Read file as bytes for download buttons."""
    return Path(path).read_bytes()


def guess_mime(path: str | Path) -> str:
    """Guess mime type for streamlit download button."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def build_ui_temp_preview_path(month: int, year: int) -> Path:
    """Return path for UI-generated edited preview workbook."""
    ensure_ui_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DATA_DIR / "ui_temp" / f"edited_preview_{year}_{month:02d}_{stamp}.xlsx"


def dataframe_to_excel_bytes(df, *, instructions: list[str] | None = None) -> bytes:
    """Serialize dataframe to xlsx bytes with optional instruction sheet."""
    stream = io.BytesIO()
    import pandas as pd

    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Editable_Preview", index=False)
        if instructions:
            pd.DataFrame({"Instruction": instructions}).to_excel(writer, sheet_name="Instructions", index=False)
    stream.seek(0)
    return stream.read()

