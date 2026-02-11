"""Configuration for Indian Labour Contractor Payroll Automation System."""

from __future__ import annotations

from pathlib import Path

# Root paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
TEMPLATE_DIR = BASE_DIR / "templates"

# Company Details
CONTRACTOR_NAME = "Shankar Manik Patil (Beldar)"
CONTRACTOR_ADDRESS = "MIDC, Baramati, Pune - 413133, Maharashtra"
CONTRACTOR_GSTIN = ""
CONTRACTOR_PAN = ""
CONTRACTOR_BANK_NAME = ""
CONTRACTOR_BANK_ACCOUNT = ""
CONTRACTOR_IFSC = ""

# Client Details
CLIENT_NAME = "Kirloskar Ferrous Industries Ltd"
CLIENT_ADDRESS = "Plant - Baramati, MIDC, Pune - 413133"
CLIENT_GSTIN = ""
CLIENT_LOCATION = "Baramati"

# Statutory Registration
PF_ESTABLISHMENT_CODE = "PUPUN0301449000"
ESIC_EMPLOYER_CODE = "33000577790001001"
PT_REGISTRATION_NO = ""

# Wage Rates
LABOUR_DAILY_RATE = 785.58
SUPERVISOR_DAILY_RATE = 740.76
LABOUR_OT_RATE = 92.13
SUPERVISOR_OT_RATE = 97.73

# Statutory Rates
PF_EMPLOYEE_RATE = 0.12
PF_EMPLOYER_RATE = 0.13
PF_EPS_RATE = 0.0833
PF_EPF_RATE = 0.0367

ESIC_EMPLOYEE_RATE = 0.0075
ESIC_EMPLOYER_RATE = 0.0325
ESIC_WAGE_CEILING = 21000

# Professional Tax Slabs (Maharashtra - Monthly)
PT_SLABS = [
    {"min": 0, "max": 10000, "amount": 0},
    {"min": 10001, "max": 25000, "amount": 175},
    {"min": 25001, "max": 999999999, "amount": 300},
]
PT_FEB_ADDITIONAL = 300

# Invoice Settings
GST_APPLICABLE = False
GST_RATE = 0.18
INVOICE_PREFIX_MD = "MD"
INVOICE_PREFIX_OT = "OT"
INVOICE_PAYMENT_TERMS = "Net 7 Days"

# Other Settings
DEFAULT_CURRENCY = "INR"
DATE_FORMAT = "%d-%b-%Y"
SUPPORTED_DESIGNATIONS = {"labour", "unskilled", "semi-skilled", "semiskilled", "supervisor"}

# Storage
EMPLOYEE_DB_PATH = DATA_DIR / "employees_master.db"
ADVANCES_PATH = DATA_DIR / "advances" / "advances.xlsx"
INVOICE_COUNTER_PATH = DATA_DIR / "monthly_data" / "invoice_counter.json"
SECRET_KEY_PATH = DATA_DIR / ".secret.key"

