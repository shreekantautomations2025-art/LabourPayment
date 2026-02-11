"""PDF generation for statutory register style outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import CLIENT_NAME, CONTRACTOR_NAME, OUTPUT_DIR
from utils.date_utils import month_name, month_short_name


def _output_dir(month: int, year: int, output_dir: Path | None = None) -> Path:
    base = output_dir or (OUTPUT_DIR / f"{year}_{month:02d}")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _chunk(rows: list[list], size: int) -> list[list[list]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def generate_wages_register_pdf(
    employee_wages: Iterable[dict],
    month: int,
    year: int,
    output_dir: Path | None = None,
    company_config: dict | None = None,
) -> Path:
    """Generate wages register PDF (Form II style tabular summary)."""
    rows = list(employee_wages)
    out_file = _output_dir(month, year, output_dir) / f"Wages_Register_{month_short_name(month)}_{year}.pdf"

    doc = SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=8 * mm, rightMargin=8 * mm)
    styles = getSampleStyleSheet()
    contractor_name = (company_config or {}).get("contractor_name", CONTRACTOR_NAME)
    client_name = (company_config or {}).get("client_name", CLIENT_NAME)
    story = [
        Paragraph("FORM II (See Rule 27(1))", styles["Heading3"]),
        Paragraph(f"Register of Wages - {month_name(month)} {year}", styles["Title"]),
        Paragraph(f"Contractor: {contractor_name} | Principal Employer: {client_name}", styles["Normal"]),
        Spacer(1, 4),
    ]

    header = [
        "S.No",
        "Emp Code",
        "Employee Name",
        "Father/Husband",
        "Department",
        "Days Worked",
        "WO/PH",
        "OT Hrs",
        "Basic",
        "OT",
        "Gross",
        "PF",
        "ESIC",
        "PT",
        "Advance",
        "Other",
        "Total Ded",
        "Net Paid",
        "Date Paid",
        "Signature",
    ]
    body = []
    total_days = 0.0
    total_ot = 0.0
    total_gross = 0.0
    total_ded = 0.0
    total_net = 0.0
    for idx, row in enumerate(rows, start=1):
        days = float(row.get("present_days", 0) or 0)
        ot_hrs = float(row.get("ot_hours", 0) or 0)
        gross = float(row.get("gross_salary", 0) or 0)
        deductions = float(row.get("total_deductions", 0) or 0)
        net = float(row.get("net_payable", 0) or 0)
        total_days += days
        total_ot += ot_hrs
        total_gross += gross
        total_ded += deductions
        total_net += net
        body.append(
            [
                idx,
                row.get("emp_code", ""),
                row.get("emp_name", ""),
                row.get("father_husband_name", ""),
                row.get("department", ""),
                f"{days:.2f}",
                "0.00",
                f"{ot_hrs:.2f}",
                f"{float(row.get('basic_wages', 0) or 0):.2f}",
                f"{float(row.get('ot_amount', 0) or 0):.2f}",
                f"{gross:.2f}",
                f"{float(row.get('pf_employee', 0) or 0):.2f}",
                f"{float(row.get('esic_employee', 0) or 0):.2f}",
                f"{float(row.get('pt', 0) or 0):.2f}",
                f"{float(row.get('advance', 0) or 0):.2f}",
                f"{float(row.get('other_deduction', 0) or 0):.2f}",
                f"{deductions:.2f}",
                f"{net:.2f}",
                "",
                "",
            ]
        )
    body.append(
        [
            "",
            "",
            "TOTAL",
            "",
            "",
            f"{total_days:.2f}",
            "0.00",
            f"{total_ot:.2f}",
            "",
            "",
            f"{total_gross:.2f}",
            "",
            "",
            "",
            "",
            "",
            f"{total_ded:.2f}",
            f"{total_net:.2f}",
            "",
            "",
        ]
    )

    chunks = _chunk(body, 28) or [[]]
    for c_idx, chunk in enumerate(chunks):
        table = Table([header] + chunk, repeatRows=1)
        style_rows = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (5, 1), (-2, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if c_idx == len(chunks) - 1:
            style_rows.extend(
                [
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E9EEF5")),
                ]
            )
        table.setStyle(TableStyle(style_rows))
        story.append(table)
        if c_idx < len(chunks) - 1:
            story.append(PageBreak())

    doc.build(story)
    return out_file


def generate_ot_register_pdf(
    employee_wages: Iterable[dict],
    month: int,
    year: int,
    output_dir: Path | None = None,
    company_config: dict | None = None,
) -> Path:
    """Generate OT register PDF (Form XIX style concise table)."""
    rows = list(employee_wages)
    out_file = _output_dir(month, year, output_dir) / f"OT_Register_{month_short_name(month)}_{year}.pdf"
    doc = SimpleDocTemplate(str(out_file), pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm)
    styles = getSampleStyleSheet()
    contractor_name = (company_config or {}).get("contractor_name", CONTRACTOR_NAME)
    client_name = (company_config or {}).get("client_name", CLIENT_NAME)
    story = [
        Paragraph("FORM XIX (See Rule 25(2))", styles["Heading3"]),
        Paragraph(f"Register of Overtime - {month_name(month)} {year}", styles["Title"]),
        Paragraph(f"Contractor: {contractor_name} | Principal Employer: {client_name}", styles["Normal"]),
        Spacer(1, 6),
    ]

    header = [
        "S.No",
        "Emp Code",
        "Employee Name",
        "Department",
        "OT Hours",
        "Rate/Hour",
        "OT Amount",
        "Date",
        "Signature",
    ]
    body = []
    total_ot = 0.0
    total_amount = 0.0
    for idx, row in enumerate(rows, start=1):
        ot_hrs = float(row.get("ot_hours", 0) or 0)
        ot_amt = float(row.get("ot_amount", 0) or 0)
        total_ot += ot_hrs
        total_amount += ot_amt
        body.append(
            [
                idx,
                row.get("emp_code", ""),
                row.get("emp_name", ""),
                row.get("department", ""),
                f"{ot_hrs:.2f}",
                f"{float(row.get('ot_rate', 0) or 0):.2f}",
                f"{ot_amt:.2f}",
                "",
                "",
            ]
        )
    body.append(["", "", "TOTAL", "", f"{total_ot:.2f}", "", f"{total_amount:.2f}", "", ""])

    table = Table([header] + body, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (4, 1), (7, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E9EEF5")),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return out_file

