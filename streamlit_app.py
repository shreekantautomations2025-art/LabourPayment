"""Streamlit UI for end-to-end payroll automation workflows."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    CLIENT_NAME,
    CONTRACTOR_NAME,
    ESIC_EMPLOYER_CODE,
    INPUT_DIR,
    OUTPUT_DIR,
    PF_ESTABLISHMENT_CODE,
    PT_REGISTRATION_NO,
)
from modules.employee_manager import EmployeeManager
from modules.payroll_processor import create_payroll_preview, finalize_payroll_from_preview, process_monthly_payroll
from utils.helpers import ensure_base_directories, setup_logging
from utils.ui_utils import (
    build_ui_temp_preview_path,
    dataframe_to_excel_bytes,
    discover_output_periods,
    guess_mime,
    list_output_files,
    read_binary_file,
    save_uploaded_file,
)


@st.cache_resource
def _bootstrap() -> EmployeeManager:
    ensure_base_directories()
    setup_logging()
    return EmployeeManager()


def _render_output_downloads(output_paths: dict) -> None:
    if not output_paths:
        return
    st.subheader("Generated Files")
    for key, file_path in output_paths.items():
        path = Path(file_path)
        if not path.exists():
            st.warning(f"{key}: file missing -> {path}")
            continue
        st.download_button(
            label=f"Download {key} ({path.name})",
            data=read_binary_file(path),
            file_name=path.name,
            mime=guess_mime(path),
            key=f"download_{key}_{path.name}_{path.stat().st_mtime_ns}",
            use_container_width=True,
        )


def _render_processing_summary(result: dict) -> None:
    totals = result.get("totals", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Employees", int(result.get("employee_count", 0)))
    c2.metric("Gross Salary", f"₹{float(totals.get('gross_salary', 0)):,.2f}")
    c3.metric("Total Deductions", f"₹{float(totals.get('deductions', 0)):,.2f}")
    c4.metric("Net Payable", f"₹{float(totals.get('net_payable', 0)):,.2f}")

    validation = result.get("validation", {})
    warnings = validation.get("warnings", [])
    errors = validation.get("errors", [])
    if warnings:
        with st.expander("Validation Warnings"):
            for warning in warnings:
                st.warning(warning)
    if errors:
        with st.expander("Validation Errors"):
            for error in errors:
                st.error(error)
    _render_output_downloads(result.get("output_paths", {}))


def _to_date(value: str) -> date:
    if not value:
        return date(1990, 1, 1)
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return date(1990, 1, 1)


def _gender_index(value: str) -> int:
    options = ["Male", "Female", "Other"]
    normalized = str(value or "").strip().lower()
    for idx, option in enumerate(options):
        if option.lower() == normalized:
            return idx
    return 0


def page_dashboard() -> None:
    st.header("Payroll Dashboard")
    st.caption("Indian Labour Contractor Payroll Automation System")

    periods = discover_output_periods()
    c1, c2, c3 = st.columns(3)
    c1.metric("Output Periods", len(periods))
    c2.metric("Contractor", CONTRACTOR_NAME)
    c3.metric("Client", CLIENT_NAME)

    if periods:
        latest = periods[0]
        st.info(f"Latest period detected: {latest}")
        files = list_output_files(latest)
        st.write(f"Files generated in {latest}: {len(files)}")
        for file in files[:10]:
            st.write(f"- {file.name}")
    else:
        st.warning("No payroll output periods available yet. Process payroll to generate reports.")


def page_employee_management(manager: EmployeeManager) -> None:
    st.header("Employee Management")
    tabs = st.tabs(["View Employees", "Add Employee", "Edit Employee", "Delete Employee", "Bulk Upload"])

    with tabs[0]:
        st.subheader("View All Employees")
        col1, col2, col3, col4 = st.columns(4)
        search = col1.text_input("Search by code/name", "")
        designation = col2.text_input("Designation filter", "")
        department = col3.text_input("Department filter", "")
        active_only = col4.checkbox("Active only", value=True)
        filters = {
            "search": search.strip() or None,
            "designation": designation.strip() or None,
            "department": department.strip() or None,
        }
        rows = manager.get_all_employees(filters=filters, active_only=active_only)
        if not rows:
            st.info("No employees found.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Total rows: {len(df)}")

    with tabs[1]:
        st.subheader("Add New Employee")
        with st.form("add_employee_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            payload = {
                "emp_code": c1.text_input("Employee Code *"),
                "emp_name": c2.text_input("Employee Name *"),
                "father_husband_name": c1.text_input("Father/Husband Name *"),
                "dob": c2.date_input("Date of Birth *", value=date(1995, 1, 1)),
                "gender": c1.selectbox("Gender *", ["Male", "Female", "Other"]),
                "designation": c2.selectbox("Designation *", ["Labour", "Supervisor", "Semi-Skilled"]),
                "doj": c1.date_input("Date of Joining *", value=date.today()),
                "bank_account_no": c2.text_input("Bank Account No *"),
                "ifsc_code": c1.text_input("IFSC Code *").upper(),
                "bank_name": c2.text_input("Bank Name *"),
                "pan_no": c1.text_input("PAN No"),
                "aadhaar_no": c2.text_input("Aadhaar No"),
                "uan_no": c1.text_input("UAN No"),
                "esic_no": c2.text_input("ESIC No"),
                "department": c1.text_input("Department"),
            }
            submitted = st.form_submit_button("Add Employee", use_container_width=True)
            if submitted:
                try:
                    manager.add_employee(payload, raise_on_error=True)
                    st.success(f"Employee {payload['emp_code']} added successfully.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to add employee: {exc}")

    with tabs[2]:
        st.subheader("Edit Employee")
        all_rows = manager.get_all_employees(active_only=False)
        if not all_rows:
            st.info("No employees available for editing.")
        else:
            option_map = {f"{r['emp_code']} - {r['emp_name']}": r["emp_code"] for r in all_rows}
            selected_label = st.selectbox("Select Employee", options=list(option_map.keys()))
            emp_code = option_map[selected_label]
            current = manager.get_employee(emp_code, include_inactive=True) or {}
            with st.form("edit_employee_form", clear_on_submit=False):
                c1, c2 = st.columns(2)
                payload = {
                    "emp_name": c1.text_input("Employee Name", value=str(current.get("emp_name", ""))),
                    "father_husband_name": c2.text_input(
                        "Father/Husband Name", value=str(current.get("father_husband_name", ""))
                    ),
                    "dob": c1.date_input("Date of Birth", value=_to_date(str(current.get("dob", "")))),
                    "gender": c2.selectbox(
                        "Gender",
                        ["Male", "Female", "Other"],
                        index=_gender_index(str(current.get("gender", "Male"))),
                    ),
                    "designation": c1.text_input("Designation", value=str(current.get("designation", ""))),
                    "doj": c2.date_input("Date of Joining", value=_to_date(str(current.get("doj", "")))),
                    "bank_account_no": c1.text_input("Bank Account No", value=str(current.get("bank_account_no", ""))),
                    "ifsc_code": c2.text_input("IFSC Code", value=str(current.get("ifsc_code", ""))).upper(),
                    "bank_name": c1.text_input("Bank Name", value=str(current.get("bank_name", ""))),
                    "pan_no": c2.text_input("PAN No", value=str(current.get("pan_no", ""))),
                    "aadhaar_no": c1.text_input("Aadhaar No", value=str(current.get("aadhaar_no", ""))),
                    "uan_no": c2.text_input("UAN No", value=str(current.get("uan_no", ""))),
                    "esic_no": c1.text_input("ESIC No", value=str(current.get("esic_no", ""))),
                    "department": c2.text_input("Department", value=str(current.get("department", ""))),
                }
                submitted = st.form_submit_button("Save Changes", use_container_width=True)
                if submitted:
                    try:
                        manager.update_employee(emp_code, payload, raise_on_error=True)
                        st.success(f"Employee {emp_code} updated successfully.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Failed to update employee: {exc}")

    with tabs[3]:
        st.subheader("Delete Employee")
        all_rows = manager.get_all_employees(active_only=False)
        if not all_rows:
            st.info("No employees available for deletion.")
        else:
            option_map = {f"{r['emp_code']} - {r['emp_name']}": r["emp_code"] for r in all_rows}
            selected_label = st.selectbox("Select Employee to Delete", options=list(option_map.keys()))
            emp_code = option_map[selected_label]
            soft_delete = st.checkbox("Soft delete (mark inactive)", value=True)
            confirm_text = st.text_input("Type employee code to confirm delete")
            if st.button("Delete Employee", type="primary", use_container_width=True):
                if confirm_text.strip() != emp_code:
                    st.error("Confirmation code mismatch. Employee not deleted.")
                else:
                    ok = manager.delete_employee(emp_code, soft_delete=soft_delete)
                    if ok:
                        mode = "soft deleted" if soft_delete else "hard deleted"
                        st.success(f"Employee {emp_code} {mode}.")
                    else:
                        st.error("Employee not found.")

    with tabs[4]:
        st.subheader("Bulk Upload Employees")
        st.caption("Upload .xlsx file with employee master columns.")
        uploaded = st.file_uploader("Upload employee master file", type=["xlsx"], key="emp_bulk_upload")
        if uploaded and st.button("Process Bulk Upload", use_container_width=True):
            try:
                file_path = save_uploaded_file(uploaded, INPUT_DIR / "ui_uploads", prefix="employee_bulk")
                result = manager.bulk_upload_employees(file_path)
                st.success("Bulk upload processed.")
                st.json(result)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Bulk upload failed: {exc}")


def page_payroll_processing(manager: EmployeeManager) -> None:
    st.header("Monthly Payroll Processing")
    preview_tab, direct_tab = st.tabs(["Preview -> Approve -> Finalize", "Direct Processing"])

    with preview_tab:
        st.subheader("Create Editable Preview")
        c1, c2 = st.columns(2)
        month = c1.number_input("Month", min_value=1, max_value=12, value=datetime.now().month, step=1)
        year = c2.number_input("Year", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        muster_upload = st.file_uploader("Upload Muster Roll (.xlsx)", type=["xlsx"], key="preview_muster_upload")
        adjustments_upload = st.file_uploader(
            "Upload Adjustments (optional .xlsx/.csv)",
            type=["xlsx", "csv"],
            key="preview_adjustments_upload",
        )

        if st.button("Create Preview Workbook", use_container_width=True):
            if not muster_upload:
                st.error("Please upload muster roll file.")
            else:
                try:
                    muster_path = save_uploaded_file(muster_upload, INPUT_DIR / "muster_rolls", prefix="muster_ui_preview")
                    adjustments_path = None
                    if adjustments_upload:
                        adjustments_path = save_uploaded_file(
                            adjustments_upload, INPUT_DIR / "ui_uploads", prefix="adjustments_ui_preview"
                        )

                    result = create_payroll_preview(
                        muster_file=muster_path,
                        month=int(month),
                        year=int(year),
                        employee_manager=manager,
                        adjustments_file=adjustments_path,
                    )
                    st.session_state["ui_preview_result"] = result
                    st.session_state["ui_preview_month"] = int(month)
                    st.session_state["ui_preview_year"] = int(year)
                    st.success("Preview workbook generated successfully.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Preview generation failed: {exc}")

        preview_result = st.session_state.get("ui_preview_result")
        if preview_result:
            st.markdown("#### Preview Result")
            st.json(preview_result)
            preview_path = Path(preview_result["preview_file"])
            if preview_path.exists():
                preview_df = pd.read_excel(preview_path, sheet_name="Editable_Preview")
                st.markdown("#### Edit Preview Rows Before Finalize")
                edited_df = st.data_editor(preview_df, use_container_width=True, num_rows="fixed", key="preview_editor")
                edited_preview_bytes = dataframe_to_excel_bytes(
                    edited_df,
                    instructions=[
                        "Set approved=Y for records to include.",
                        "You may edit present_days, ot_hours, advance, and other_deduction.",
                        "Do not change employee codes.",
                    ],
                )
                st.download_button(
                    "Download Edited Preview",
                    edited_preview_bytes,
                    file_name=(
                        f"Edited_Preview_{int(st.session_state.get('ui_preview_year', year))}_"
                        f"{int(st.session_state.get('ui_preview_month', month)):02d}.xlsx"
                    ),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                if st.button("Finalize Using Edited Table Above", type="primary", use_container_width=True):
                    try:
                        temp_preview_path = build_ui_temp_preview_path(
                            int(st.session_state["ui_preview_month"]),
                            int(st.session_state["ui_preview_year"]),
                        )
                        temp_preview_path.write_bytes(edited_preview_bytes)
                        final = finalize_payroll_from_preview(
                            preview_file=temp_preview_path,
                            month=int(st.session_state["ui_preview_month"]),
                            year=int(st.session_state["ui_preview_year"]),
                            employee_manager=manager,
                            require_approved_rows=True,
                        )
                        st.session_state["ui_final_result"] = final
                        st.success("Payroll finalized from edited table.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Finalize failed: {exc}")

                st.markdown("#### Or Upload External Edited Preview File")
                edited_file_upload = st.file_uploader(
                    "Upload edited preview workbook",
                    type=["xlsx"],
                    key="preview_external_finalize_upload",
                )
                if edited_file_upload and st.button("Finalize From Uploaded Preview", use_container_width=True):
                    try:
                        ext_preview_path = save_uploaded_file(
                            edited_file_upload, INPUT_DIR / "ui_uploads", prefix="external_edited_preview"
                        )
                        final = finalize_payroll_from_preview(
                            preview_file=ext_preview_path,
                            month=int(st.session_state["ui_preview_month"]),
                            year=int(st.session_state["ui_preview_year"]),
                            employee_manager=manager,
                            require_approved_rows=True,
                        )
                        st.session_state["ui_final_result"] = final
                        st.success("Payroll finalized from uploaded preview.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Finalize from upload failed: {exc}")

    with direct_tab:
        st.subheader("Direct Process (no preview)")
        c1, c2 = st.columns(2)
        month_direct = c1.number_input("Month ", min_value=1, max_value=12, value=datetime.now().month, step=1)
        year_direct = c2.number_input("Year ", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        muster_upload_direct = st.file_uploader("Upload Muster Roll (.xlsx) ", type=["xlsx"], key="direct_muster_upload")
        adjustments_upload_direct = st.file_uploader(
            "Upload Adjustments (optional .xlsx/.csv) ",
            type=["xlsx", "csv"],
            key="direct_adjustments_upload",
        )
        if st.button("Run Direct Payroll Processing", use_container_width=True):
            if not muster_upload_direct:
                st.error("Please upload muster roll file.")
            else:
                try:
                    muster_path = save_uploaded_file(
                        muster_upload_direct,
                        INPUT_DIR / "muster_rolls",
                        prefix="muster_ui_direct",
                    )
                    adjustments_path = None
                    if adjustments_upload_direct:
                        adjustments_path = save_uploaded_file(
                            adjustments_upload_direct,
                            INPUT_DIR / "ui_uploads",
                            prefix="adjustments_ui_direct",
                        )
                    result = process_monthly_payroll(
                        muster_file=muster_path,
                        month=int(month_direct),
                        year=int(year_direct),
                        employee_manager=manager,
                        adjustments_file=adjustments_path,
                        require_clean_validation=True,
                    )
                    st.session_state["ui_final_result"] = result
                    st.success("Direct payroll processing completed.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Direct payroll processing failed: {exc}")

    final_result = st.session_state.get("ui_final_result")
    if final_result:
        st.markdown("---")
        st.subheader("Finalized Payroll Summary")
        _render_processing_summary(final_result)


def page_reports() -> None:
    st.header("Reports & Documents")
    periods = discover_output_periods()
    if not periods:
        st.info("No output folders found. Process payroll first.")
        return

    selected = st.selectbox("Select output period (YYYY_MM)", periods)
    files = list_output_files(selected, extensions=[".xlsx", ".pdf", ".csv"])
    if not files:
        st.warning("No files in selected period.")
        return

    st.caption(f"Found {len(files)} files in output/{selected}")
    for file in files:
        cols = st.columns([5, 2, 2])
        cols[0].write(file.name)
        cols[1].write(file.suffix.upper())
        cols[2].download_button(
            "Download",
            data=read_binary_file(file),
            file_name=file.name,
            mime=guess_mime(file),
            key=f"report_download_{selected}_{file.name}",
            use_container_width=True,
        )


def page_payment_guidance() -> None:
    st.header("Payment Guidance")
    st.info("This system does not auto-pay challans. It only provides guidance and reports.")

    st.markdown(
        f"""
### PF Payment
- Portal: https://unifiedportal-mem.epfindia.gov.in
- Upload ECR generated by system
- Due Date: 15th of next month
- Establishment Code: **{PF_ESTABLISHMENT_CODE}**

### ESIC Payment
- Portal: https://portal.esic.in
- Enter monthly contribution and pay online
- Due Date: 15th of next month
- Employer Code: **{ESIC_EMPLOYER_CODE}**

### Professional Tax (Maharashtra)
- Portal: Maharashtra State Tax Portal
- Monthly return + challan payment
- Due Date: 21st of next month
- Registration No: **{PT_REGISTRATION_NO or 'N/A'}**

### Bank Salary Payment
- Use `Bank_Payment_*.xlsx` (NEFT / NACH sheets)
- Use `NACH_Upload_*.csv` where required by bank
"""
    )

    periods = discover_output_periods()
    if periods:
        selected = st.selectbox("Download Payment Instructions PDF for period", periods, key="guidance_period")
        candidate = OUTPUT_DIR / selected
        files = [p for p in candidate.iterdir() if p.is_file() and "Payment_Instructions" in p.name]
        if files:
            latest = sorted(files)[-1]
            st.download_button(
                f"Download {latest.name}",
                data=read_binary_file(latest),
                file_name=latest.name,
                mime=guess_mime(latest),
                key=f"payment_instruction_download_{selected}",
                use_container_width=True,
            )


def page_configuration() -> None:
    st.header("Configuration Snapshot")
    st.caption("Read-only configuration currently loaded by system.")
    config_payload = {
        "contractor_name": CONTRACTOR_NAME,
        "client_name": CLIENT_NAME,
        "pf_establishment_code": PF_ESTABLISHMENT_CODE,
        "esic_employer_code": ESIC_EMPLOYER_CODE,
        "pt_registration_no": PT_REGISTRATION_NO or "",
    }
    st.json(config_payload)


def run_app() -> None:
    st.set_page_config(page_title="Indian Labour Payroll Automation", layout="wide")
    manager = _bootstrap()

    st.sidebar.title("Payroll Automation")
    page = st.sidebar.radio(
        "Navigate",
        [
            "Dashboard",
            "Employee Management",
            "Payroll Processing",
            "Reports & Documents",
            "Payment Guidance",
            "Configuration",
        ],
    )

    if page == "Dashboard":
        page_dashboard()
    elif page == "Employee Management":
        page_employee_management(manager)
    elif page == "Payroll Processing":
        page_payroll_processing(manager)
    elif page == "Reports & Documents":
        page_reports()
    elif page == "Payment Guidance":
        page_payment_guidance()
    else:
        page_configuration()

    st.sidebar.markdown("---")
    st.sidebar.caption("For CLI usage: python3 main.py --help")


if __name__ == "__main__":
    run_app()

