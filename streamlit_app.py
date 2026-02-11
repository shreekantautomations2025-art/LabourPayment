"""Streamlit UI for end-to-end payroll automation workflows."""

from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

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


def _inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --brand-1: #5d7cf9;
            --brand-2: #7d5bff;
            --brand-3: #21c7ff;
            --glass-bg: rgba(255, 255, 255, 0.08);
            --glass-border: rgba(255, 255, 255, 0.16);
        }

        [data-testid="stAppViewContainer"] {
            background: linear-gradient(120deg, #0f172a, #1e1b4b, #0b1022);
            background-size: 250% 250%;
            animation: gradientShift 16s ease infinite;
        }

        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .hero-card {
            border: 1px solid var(--glass-border);
            background: linear-gradient(145deg, rgba(255,255,255,0.12), rgba(255,255,255,0.05));
            border-radius: 16px;
            padding: 1.1rem 1.2rem;
            backdrop-filter: blur(8px);
            box-shadow: 0 8px 22px rgba(0,0,0,0.25);
            margin-bottom: 0.8rem;
        }

        .hero-title {
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: 0.2px;
            background: linear-gradient(90deg, #ffffff, #a5b4fc, #67e8f9);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            color: rgba(241, 245, 249, 0.9);
            font-size: 0.95rem;
            margin-top: 4px;
        }

        .metric-card {
            border: 1px solid rgba(165, 180, 252, 0.35);
            background: var(--glass-bg);
            border-radius: 14px;
            padding: 0.85rem 0.9rem;
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
            backdrop-filter: blur(6px);
            transform: translateY(0);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            animation: softPulse 3s ease-in-out infinite;
        }

        .metric-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 24px rgba(0,0,0,0.28);
        }

        @keyframes softPulse {
            0%, 100% { border-color: rgba(165, 180, 252, 0.30); }
            50% { border-color: rgba(103, 232, 249, 0.45); }
        }

        .metric-title {
            font-size: 0.82rem;
            color: rgba(241, 245, 249, 0.78);
            margin-bottom: 0.2rem;
        }
        .metric-value {
            font-size: 1.18rem;
            font-weight: 700;
            color: #f8fafc;
        }

        .tag-pill {
            display: inline-block;
            padding: 0.22rem 0.6rem;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.22);
            color: #e2e8f0;
            font-size: 0.75rem;
            margin-right: 0.35rem;
            margin-bottom: 0.25rem;
            background: rgba(255,255,255,0.06);
        }

        .section-anchor {
            display: block;
            padding-top: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero(title: str, subtitle: str, pills: list[str] | None = None) -> None:
    pills_html = "".join([f'<span class="tag-pill">{item}</span>' for item in (pills or [])])
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
            <div style="margin-top: 8px;">{pills_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_cards(metrics: list[tuple[str, str]]) -> None:
    cols = st.columns(len(metrics))
    for col, (title, value) in zip(cols, metrics):
        col.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">{title}</div>
                <div class="metric-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _run_with_animation(label: str, operation: Callable[[], Any], steps: list[str] | None = None) -> Any:
    flow = steps or ["Validating input", "Processing backend workflow", "Preparing outputs"]
    with st.status(label, expanded=True) as status:
        for idx, step in enumerate(flow):
            status.write(f"⏳ {step}...")
            if idx < len(flow) - 1:
                time.sleep(0.2)
        result = operation()
        status.write("✅ Completed successfully.")
        status.update(label=f"{label} complete", state="complete", expanded=False)
    return result


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
    _render_metric_cards(
        [
            ("Employees", f"{int(result.get('employee_count', 0))}"),
            ("Gross Salary", f"₹{float(totals.get('gross_salary', 0)):,.2f}"),
            ("Total Deductions", f"₹{float(totals.get('deductions', 0)):,.2f}"),
            ("Net Payable", f"₹{float(totals.get('net_payable', 0)):,.2f}"),
        ]
    )

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
    _render_hero(
        "Payroll Dashboard",
        "Indian Labour Contractor Payroll Automation System",
        ["Employee Master", "Payroll Engine", "Compliance Reports", "Payment Guidance"],
    )

    periods = discover_output_periods()
    _render_metric_cards(
        [
            ("Output Periods", str(len(periods))),
            ("Contractor", CONTRACTOR_NAME),
            ("Client", CLIENT_NAME),
        ]
    )

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
    _render_hero(
        "Employee Management",
        "Add, edit, delete, filter, and bulk upload employee master records.",
        ["CRUD", "Bulk Upload", "Encrypted Fields"],
    )
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
                    _run_with_animation(
                        "Adding employee",
                        lambda: manager.add_employee(payload, raise_on_error=True),
                        steps=["Validating employee fields", "Persisting to database", "Refreshing cache"],
                    )
                    st.balloons()
                    st.toast("Employee added", icon="✅")
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
                        _run_with_animation(
                            "Updating employee",
                            lambda: manager.update_employee(emp_code, payload, raise_on_error=True),
                            steps=["Validating updated fields", "Applying update in database", "Writing audit log"],
                        )
                        st.toast("Employee updated", icon="✅")
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
                    ok = _run_with_animation(
                        "Deleting employee",
                        lambda: manager.delete_employee(emp_code, soft_delete=soft_delete),
                        steps=["Checking employee record", "Applying delete operation", "Updating audit trail"],
                    )
                    if ok:
                        mode = "soft deleted" if soft_delete else "hard deleted"
                        st.toast("Employee deleted", icon="🗑️")
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
                result = _run_with_animation(
                    "Processing bulk upload",
                    lambda: manager.bulk_upload_employees(file_path),
                    steps=["Saving uploaded file", "Validating and upserting records", "Creating summary response"],
                )
                st.success("Bulk upload processed.")
                st.json(result)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Bulk upload failed: {exc}")


def page_payroll_processing(manager: EmployeeManager) -> None:
    _render_hero(
        "Monthly Payroll Processing",
        "Run direct payroll or use preview -> approve -> finalize flow.",
        ["Validation", "Preview Mode", "Automated Reports", "ECR + NACH"],
    )
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

                    result = _run_with_animation(
                        "Creating payroll preview",
                        lambda: create_payroll_preview(
                            muster_file=muster_path,
                            month=int(month),
                            year=int(year),
                            employee_manager=manager,
                            adjustments_file=adjustments_path,
                        ),
                        steps=[
                            "Uploading and archiving muster",
                            "Parsing attendance and OT",
                            "Generating editable preview workbook",
                        ],
                    )
                    st.session_state["ui_preview_result"] = result
                    st.session_state["ui_preview_month"] = int(month)
                    st.session_state["ui_preview_year"] = int(year)
                    st.toast("Preview workbook created", icon="📄")
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
                        final = _run_with_animation(
                            "Finalizing payroll from edited preview",
                            lambda: finalize_payroll_from_preview(
                                preview_file=temp_preview_path,
                                month=int(st.session_state["ui_preview_month"]),
                                year=int(st.session_state["ui_preview_year"]),
                                employee_manager=manager,
                                require_approved_rows=True,
                            ),
                            steps=[
                                "Validating approved rows",
                                "Running payroll calculation engine",
                                "Generating Excel/PDF/CSV outputs",
                            ],
                        )
                        st.session_state["ui_final_result"] = final
                        st.balloons()
                        st.toast("Payroll finalized", icon="✅")
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
                        final = _run_with_animation(
                            "Finalizing payroll from uploaded preview",
                            lambda: finalize_payroll_from_preview(
                                preview_file=ext_preview_path,
                                month=int(st.session_state["ui_preview_month"]),
                                year=int(st.session_state["ui_preview_year"]),
                                employee_manager=manager,
                                require_approved_rows=True,
                            ),
                            steps=[
                                "Reading uploaded preview workbook",
                                "Validating approved payroll records",
                                "Generating all statutory outputs",
                            ],
                        )
                        st.session_state["ui_final_result"] = final
                        st.balloons()
                        st.toast("Payroll finalized", icon="✅")
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
                    result = _run_with_animation(
                        "Running direct payroll",
                        lambda: process_monthly_payroll(
                            muster_file=muster_path,
                            month=int(month_direct),
                            year=int(year_direct),
                            employee_manager=manager,
                            adjustments_file=adjustments_path,
                            require_clean_validation=True,
                        ),
                        steps=[
                            "Archiving source muster file",
                            "Calculating wages and deductions",
                            "Generating all reports and registers",
                        ],
                    )
                    st.session_state["ui_final_result"] = result
                    st.balloons()
                    st.toast("Direct payroll run completed", icon="✅")
                    st.success("Direct payroll processing completed.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Direct payroll processing failed: {exc}")

    final_result = st.session_state.get("ui_final_result")
    if final_result:
        st.markdown("---")
        st.subheader("Finalized Payroll Summary")
        _render_processing_summary(final_result)


def page_reports() -> None:
    _render_hero(
        "Reports & Documents",
        "Browse monthly generated files and download reports instantly.",
        ["Excel", "PDF", "CSV"],
    )
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
    _render_hero(
        "Payment Guidance",
        "Step-by-step statutory and bank payment instructions (guidance only).",
        ["PF", "ESIC", "PT", "Bank Upload"],
    )
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
    _render_hero(
        "Configuration Snapshot",
        "Read-only values loaded from current configuration.",
        ["Contractor", "Client", "Statutory Codes"],
    )
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
    _inject_custom_css()
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

