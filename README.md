# Indian Labour Contractor Payroll Automation System

Production-grade Python payroll automation for Indian labour contractors with:

- Employee master management (CRUD + bulk upload)
- Muster roll parsing (two-row format: data row + time row)
- Wage/statutory calculations (PF/ESIC/PT + advances + other deductions)
- Multi-output document generation (Excel + PDF)
- Payment guidance documents (no auto-payment)
- Validation, monthly archive handling, backup, and audit logging

---

## Features

### Employee Master (SQLite)
- Add / update / soft-delete / hard-delete employees
- Bulk upload from Excel template
- Search and filter by code/name/designation/department
- Sensitive fields encrypted at rest (bank account, PAN, Aadhaar)

### Monthly Payroll Processing
- Parse uploaded muster roll Excel files
- Detect header row automatically (`Sl.No` + employee columns)
- Skip time rows in two-row attendance structure
- Extract present days and OT hours
- Validate employee codes against master data
- Generate preview before finalization (CLI flow)

### Wage & Compliance Calculations
- Designation-based daily and OT rate selection
- PF on basic wages only
- ESIC with wage ceiling logic
- Maharashtra PT slabs + February adjustment
- Net payable with advances and other deductions

### Generated Outputs
- Department salary summary (`.xlsx`)
- MD invoice (`.pdf`)
- OT invoice (`.pdf`)
- Bank payment sheet + NEFT + NACH sheets (`.xlsx`)
- NACH upload file (`.csv`)
- PF summary (`.xlsx`)
- PF ECR upload file (`.csv`)
- ESIC summary (`.xlsx`)
- PT summary (`.xlsx`)
- Advance register (`.xlsx`)
- Wages register (`.xlsx` + `.pdf`)
- OT register (`.pdf`)
- Payment instructions (`.pdf`)

---

## Project Structure

```text
.
├── config.py
├── main.py
├── streamlit_app.py
├── setup.py
├── requirements.txt
├── modules/
│   ├── employee_manager.py
│   ├── muster_parser.py
│   ├── validators.py
│   ├── statutory_calculator.py
│   ├── wage_calculator.py
│   ├── payroll_processor.py
│   ├── excel_generator.py
│   ├── invoice_generator.py
│   ├── pdf_generator.py
│   └── payment_instructions.py
├── utils/
│   ├── helpers.py
│   ├── security.py
│   ├── date_utils.py
│   ├── number_to_words.py
│   └── ui_utils.py
├── templates/
├── data/
├── input/
├── output/
├── logs/
└── tests/
    └── test_ui_utils.py
```

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py init_db
```

---

## Usage

### 0) Run Streamlit UI (recommended)
```bash
streamlit run streamlit_app.py
```

The UI provides:
- Employee CRUD + bulk upload
- Payroll preview -> approve -> finalize workflow
- Direct payroll processing option
- Report/document browser with download buttons
- Payment guidance view and payment instruction PDF download
- Animated gradient dashboard, live status loaders, and success effects

### 1) Initialize DB
```bash
python main.py init-db
```

### 2) Employee CRUD
Add employee:
```bash
python main.py employee add \
  --emp-code E001 \
  --emp-name "Ravi Patil" \
  --father-husband-name "Suresh Patil" \
  --dob "01-01-1995" \
  --gender Male \
  --designation Labour \
  --doj "01-01-2020" \
  --bank-account-no 123456789012 \
  --ifsc-code SBIN0001234 \
  --bank-name "State Bank of India"
```

Bulk upload:
```bash
python main.py employee bulk-upload --file input/employee_master.xlsx
```

List employees:
```bash
python main.py employee list --search Ravi
```

### 3) Process Monthly Payroll
```bash
python main.py process-payroll \
  --muster-file input/muster_rolls/Shankar_Patil_MusterRoll_Nov_2025_updated_1.xlsx \
  --month 11 \
  --year 2025
```

For non-interactive runs:
```bash
python main.py process-payroll --muster-file <file> --month 11 --year 2025 --yes
```

### 4) Preview -> Approve -> Finalize Flow (recommended)
Create editable preview:
```bash
python main.py process-payroll \
  --muster-file input/muster_rolls/Shankar_Patil_MusterRoll_Nov_2025_updated_1.xlsx \
  --month 11 \
  --year 2025 \
  --preview-only
```

Then edit `Payroll_Preview_YYYY_MM.xlsx` and set `approved` column (`Y` / `N`), adjust days/OT/deductions.

Finalize from edited preview:
```bash
python main.py finalize-payroll \
  --preview-file output/2025_11/Payroll_Preview_2025_11.xlsx \
  --month 11 \
  --year 2025 \
  --yes
```

### 5) Interactive Menu
```bash
python main.py
```

### 6) Streamlit Pages
- Dashboard
- Employee Management
- Payroll Processing
  - Preview -> Approve -> Finalize
  - Direct processing
- Reports & Documents
- Payment Guidance
- Configuration Snapshot

---

## Data and Archive Policy

- Original uploaded muster files are archived to:
  - `data/monthly_data/YYYY_MM/original_muster/`
- Processed outputs are saved in:
  - `output/YYYY_MM/`
- Monthly processing summaries are saved in:
  - `data/monthly_data/YYYY_MM/processing_summary.json`

---

## Logging

- Errors: `logs/payroll_errors.log`
- Audit actions: `logs/payroll_audit.log`

---

## Testing

```bash
pytest -q
```

Included tests:
- Wage/statutory unit tests
- Employee CRUD tests
- End-to-end monthly processing integration test
- Preview/finalize integration test
- Optional real sample muster regression test (auto-skips if sample file is absent)
- UI utility tests

---

## Important Compliance Note

This system **does not auto-pay statutory challans or bank salaries**.  
It generates calculations, reports, and payment instructions only.