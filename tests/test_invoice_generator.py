"""Unit tests for invoice total and GST behavior."""

from modules.invoice_generator import _invoice_tax_totals


def test_invoice_totals_force_gst_for_invoices():
    totals = _invoice_tax_totals(1000.0, company_config={"gst_applicable": 0, "gst_rate": 0.18})
    assert totals["gst_applicable"] is True
    assert totals["gst_rate"] == 0.18
    assert totals["gst_amount"] == 180.0
    assert totals["total"] == 1180.0


def test_invoice_totals_fallback_to_default_rate_when_invalid():
    totals = _invoice_tax_totals(2000.0, company_config={"gst_applicable": 0, "gst_rate": 0})
    assert totals["gst_applicable"] is True
    assert totals["gst_rate"] > 0
    assert totals["gst_amount"] == 360.0
    assert totals["total"] == 2360.0

