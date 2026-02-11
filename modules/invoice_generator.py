"""MD and OT invoice PDF generation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import (
    CLIENT_ADDRESS,
    CLIENT_GSTIN,
    CLIENT_NAME,
    CONTRACTOR_ADDRESS,
    CONTRACTOR_BANK_ACCOUNT,
    CONTRACTOR_BANK_NAME,
    CONTRACTOR_GSTIN,
    CONTRACTOR_IFSC,
    CONTRACTOR_NAME,
    GST_APPLICABLE,
    GST_RATE,
    INVOICE_COUNTER_PATH,
    INVOICE_PAYMENT_TERMS,
    INVOICE_PREFIX_MD,
    INVOICE_PREFIX_OT,
    OUTPUT_DIR,
)
from utils.date_utils import month_name, month_short_name
from utils.number_to_words import amount_to_words_inr


def _money(value: float) -> float:
    return round(float(value), 2)


def _cfg(company_config: dict | None, key: str, default):
    if company_config is None:
        return default
    return company_config.get(key, default)


def _output_dir(month: int, year: int, output_dir: Path | None = None) -> Path:
    base = output_dir or (OUTPUT_DIR / f"{year}_{month:02d}")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_counter() -> dict:
    INVOICE_COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if INVOICE_COUNTER_PATH.exists():
        return json.loads(INVOICE_COUNTER_PATH.read_text(encoding="utf-8"))
    return {}


def _save_counter(counter: dict) -> None:
    INVOICE_COUNTER_PATH.write_text(json.dumps(counter, indent=2), encoding="utf-8")


def _next_invoice_no(prefix: str, year: int) -> str:
    counter = _load_counter()
    key = f"{prefix}_{year}"
    seq = int(counter.get(key, 0)) + 1
    counter[key] = seq
    _save_counter(counter)
    return f"{prefix}/{year}/{seq:03d}"


def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading",
            parent=styles["Heading2"],
            alignment=1,
            fontSize=16,
            spaceAfter=10,
        )
    )
    return styles


def _to_dataframe(data: pd.DataFrame | Iterable[dict]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame(list(data))


def _generate_invoice_pdf(
    *,
    out_file: Path,
    invoice_no: str,
    month: int,
    year: int,
    line_headers: list[str],
    line_rows: list[list[object]],
    subtotal: float,
    title: str,
    company_config: dict | None = None,
) -> Path:
    styles = _make_styles()
    doc = SimpleDocTemplate(str(out_file), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=12 * mm)
    story = []

    story.append(Paragraph("TAX INVOICE", styles["Heading"]))
    story.append(Spacer(1, 4))

    header_table = Table(
        [
            [
                Paragraph(
                    (
                        f"<b>FROM:</b><br/>{_cfg(company_config, 'contractor_name', CONTRACTOR_NAME)}"
                        f"<br/>{_cfg(company_config, 'contractor_address', CONTRACTOR_ADDRESS)}"
                        f"<br/>GSTIN: {_cfg(company_config, 'contractor_gstin', CONTRACTOR_GSTIN) or 'N/A'}"
                    ),
                    styles["Small"],
                ),
                Paragraph(
                    (
                        f"<b>TO:</b><br/>{_cfg(company_config, 'client_name', CLIENT_NAME)}"
                        f"<br/>{_cfg(company_config, 'client_address', CLIENT_ADDRESS)}"
                        f"<br/>GSTIN: {_cfg(company_config, 'client_gstin', CLIENT_GSTIN) or 'N/A'}"
                    ),
                    styles["Small"],
                ),
            ]
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 8))

    meta = Table(
        [
            [f"Invoice No: {invoice_no}", f"Date: {date.today().isoformat()}"],
            [f"Period: {month_name(month)} {year}", f"Payment Terms: {_cfg(company_config, 'payment_terms', INVOICE_PAYMENT_TERMS)}"],
            [f"Invoice Type: {title}", ""],
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    meta.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story.append(meta)
    story.append(Spacer(1, 8))

    table_data = [line_headers] + line_rows
    line_table = Table(table_data, colWidths=[15 * mm, 65 * mm, 30 * mm, 30 * mm, 40 * mm])
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(line_table)
    story.append(Spacer(1, 10))

    gst_applicable = bool(_cfg(company_config, "gst_applicable", GST_APPLICABLE))
    gst_rate = float(_cfg(company_config, "gst_rate", GST_RATE))
    gst_amount = _money(subtotal * gst_rate) if gst_applicable else 0.0
    total = _money(subtotal + gst_amount)
    summary = [
        ["Sub Total", f"₹{subtotal:,.2f}"],
        [f"GST @ {gst_rate * 100:.0f}%" if gst_applicable else "GST", f"₹{gst_amount:,.2f}"],
        ["TOTAL", f"₹{total:,.2f}"],
    ]
    summary_table = Table(summary, colWidths=[110 * mm, 40 * mm], hAlign="RIGHT")
    summary_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Amount in Words: {amount_to_words_inr(total)}", styles["Small"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            (
                "<b>Bank Details:</b><br/>"
                f"Account Name: {_cfg(company_config, 'contractor_name', CONTRACTOR_NAME)}<br/>"
                f"Bank: {_cfg(company_config, 'contractor_bank_name', CONTRACTOR_BANK_NAME) or 'N/A'}<br/>"
                f"Account No: {_cfg(company_config, 'contractor_bank_account', CONTRACTOR_BANK_ACCOUNT) or 'N/A'}<br/>"
                f"IFSC: {_cfg(company_config, 'contractor_ifsc', CONTRACTOR_IFSC) or 'N/A'}"
            ),
            styles["Small"],
        )
    )
    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            f"For {_cfg(company_config, 'contractor_name', CONTRACTOR_NAME)}<br/><br/>Authorized Signatory",
            styles["Small"],
        )
    )

    doc.build(story)
    return out_file


def generate_md_invoice(
    month: int,
    year: int,
    dept_summary: pd.DataFrame | Iterable[dict],
    output_dir: Path | None = None,
    invoice_no: str | None = None,
    company_config: dict | None = None,
) -> Path:
    """Generate MD (normal wages/man-days) invoice PDF."""
    df = _to_dataframe(dept_summary)
    if df.empty:
        raise ValueError("Department summary is empty, cannot generate MD invoice")

    rows = []
    subtotal = 0.0
    for idx, row in enumerate(df.itertuples(index=False), start=1):
        dept = getattr(row, "department", "")
        days = float(getattr(row, "total_days", 0) or 0)
        amount = float(getattr(row, "total_basic_wages", 0) or 0)
        rate = amount / days if days else 0.0
        subtotal += amount
        rows.append([idx, dept, f"{days:,.2f}", f"{rate:,.2f}", f"{amount:,.2f}"])

    invoice_prefix_md = str(_cfg(company_config, "invoice_prefix_md", INVOICE_PREFIX_MD))
    invoice_no = invoice_no or _next_invoice_no(invoice_prefix_md, year)
    out_file = _output_dir(month, year, output_dir) / f"MD_Invoice_{month_short_name(month)}_{year}_{invoice_no.replace('/', '_')}.pdf"
    return _generate_invoice_pdf(
        out_file=out_file,
        invoice_no=invoice_no,
        month=month,
        year=year,
        line_headers=["SR.", "DEPARTMENT", "MAN DAYS", "RATE/DAY", "AMOUNT (₹)"],
        line_rows=rows,
        subtotal=_money(subtotal),
        title="MD Invoice",
        company_config=company_config,
    )


def generate_ot_invoice(
    month: int,
    year: int,
    dept_summary: pd.DataFrame | Iterable[dict],
    output_dir: Path | None = None,
    invoice_no: str | None = None,
    company_config: dict | None = None,
) -> Path:
    """Generate OT (overtime) invoice PDF."""
    df = _to_dataframe(dept_summary)
    if df.empty:
        raise ValueError("Department summary is empty, cannot generate OT invoice")

    rows = []
    subtotal = 0.0
    for idx, row in enumerate(df.itertuples(index=False), start=1):
        dept = getattr(row, "department", "")
        hrs = float(getattr(row, "total_ot_hrs", 0) or 0)
        amount = float(getattr(row, "total_ot_amount", 0) or 0)
        rate = amount / hrs if hrs else 0.0
        subtotal += amount
        rows.append([idx, dept, f"{hrs:,.2f}", f"{rate:,.2f}", f"{amount:,.2f}"])

    invoice_prefix_ot = str(_cfg(company_config, "invoice_prefix_ot", INVOICE_PREFIX_OT))
    invoice_no = invoice_no or _next_invoice_no(invoice_prefix_ot, year)
    out_file = _output_dir(month, year, output_dir) / f"OT_Invoice_{month_short_name(month)}_{year}_{invoice_no.replace('/', '_')}.pdf"
    return _generate_invoice_pdf(
        out_file=out_file,
        invoice_no=invoice_no,
        month=month,
        year=year,
        line_headers=["SR.", "DEPARTMENT", "OT HOURS", "RATE/HR", "AMOUNT (₹)"],
        line_rows=rows,
        subtotal=_money(subtotal),
        title="OT Invoice",
        company_config=company_config,
    )

