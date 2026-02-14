"""Streamlit UI for end-to-end payroll automation workflows."""

from __future__ import annotations

import time
from datetime import date, datetime
import io
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
from modules.company_manager import CompanyManager
from modules.employee_manager import EmployeeManager
from modules.payroll_processor import (
    create_payroll_preview,
    create_payroll_preview_from_records,
    finalize_payroll_from_preview,
    process_monthly_payroll,
)
from ui_components.company_settings import render_company_settings
from ui_components.design_system import (
    create_stat_card,
    file_upload_zone,
    load_custom_css,
    page_header,
    show_alert,
    show_loading,
    show_progress,
    toggle_dark_mode,
)
from utils.currency_utils import format_inr
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


@st.cache_resource
def _bootstrap_company_manager() -> CompanyManager:
    ensure_base_directories()
    setup_logging()
    return CompanyManager()


def _inject_custom_css() -> None:
    load_custom_css()


def _render_hero(title: str, subtitle: str, pills: list[str] | None = None, icon: str = "💼") -> None:
    page_header(title=title, subtitle=subtitle, icon=icon)
    if pills:
        st.caption(" | ".join(pills))


def _render_metric_cards(metrics: list[tuple[str, str]]) -> None:
    if not metrics:
        return
    icon_map = ["📊", "👥", "🏢", "💰", "📄", "✅", "📅"]
    color_map = ["primary", "success", "info", "warning", "danger"]
    cols = st.columns(len(metrics))
    for idx, (col, (title, value)) in enumerate(zip(cols, metrics)):
        with col:
            create_stat_card(
                title=title,
                value=value,
                icon=icon_map[idx % len(icon_map)],
                color=color_map[idx % len(color_map)],
            )


def _run_with_animation(label: str, operation: Callable[[], Any], steps: list[str] | None = None) -> Any:
    flow = steps or ["Validating input", "Processing backend workflow", "Preparing outputs"]
    loading_slot = st.empty()
    progress_slot = st.empty()
    with loading_slot.container():
        show_loading(f"{label}...")
    with st.status(label, expanded=True) as status:
        for idx, step in enumerate(flow):
            pct = int(((idx + 1) / len(flow)) * 100)
            with progress_slot.container():
                show_progress(pct, step)
            status.write(f"⏳ {step}...")
            if idx < len(flow) - 1:
                time.sleep(0.2)
        result = operation()
        with progress_slot.container():
            show_progress(100, "Completed")
        status.write("✅ Completed successfully.")
        status.update(label=f"{label} complete", state="complete", expanded=False)
    loading_slot.empty()
    progress_slot.empty()
    return result


def _render_output_downloads(output_paths: dict) -> None:
    if not output_paths:
        return
    st.subheader("Generated Files")
    for key, file_path in output_paths.items():
        path = Path(file_path)
        if not path.exists():
            show_alert(f"{key}: file missing -> {path}", "warning")
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
            ("Gross Salary", format_inr(float(totals.get("gross_salary", 0)))),
            ("Total Deductions", format_inr(float(totals.get("deductions", 0)))),
            ("Net Payable", format_inr(float(totals.get("net_payable", 0)))),
        ]
    )

    validation = result.get("validation", {})
    warnings = validation.get("warnings", [])
    errors = validation.get("errors", [])
    if warnings:
        with st.expander("Validation Warnings"):
            for warning in warnings:
                show_alert(warning, "warning")
    if errors:
        with st.expander("Validation Errors"):
            for error in errors:
                show_alert(error, "error")
    _render_output_downloads(result.get("output_paths", {}))


def _to_date(value: str) -> date:
    if not value:
        return date(1990, 1, 1)
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return date(1990, 1, 1)


def _load_manual_records_file(uploaded_file) -> pd.DataFrame:
    name = str(getattr(uploaded_file, "name", "")).lower()
    payload = uploaded_file.getvalue()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(payload))
    if name.endswith(".json"):
        return pd.read_json(io.BytesIO(payload))
    if name.endswith(".txt"):
        text = payload.decode("utf-8", errors="ignore")
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        if "|" in first and first.count("|") >= 2:
            return pd.read_csv(io.StringIO(text), sep="|")
        if "\t" in first and first.count("\t") >= 2:
            return pd.read_csv(io.StringIO(text), sep="\t")
        return pd.read_csv(io.StringIO(text), sep=None, engine="python")
    raise ValueError("Unsupported manual records file. Use csv/json/txt.")


def _gender_index(value: str) -> int:
    options = ["Male", "Female", "Other"]
    normalized = str(value or "").strip().lower()
    for idx, option in enumerate(options):
        if option.lower() == normalized:
            return idx
    return 0


def page_dashboard(selected_company: dict | None = None) -> None:
    _render_hero(
        "Payroll Dashboard",
        "Indian Labour Contractor Payroll Automation System",
        ["Employee Master", "Payroll Engine", "Compliance Reports", "Payment Guidance"],
        icon="📊",
    )

    periods = discover_output_periods()
    contractor_name = (selected_company or {}).get("contractor_name", CONTRACTOR_NAME)
    client_name = (selected_company or {}).get("client_name", CLIENT_NAME)
    latest_period = periods[0] if periods else "-"
    cols = st.columns(4)
    with cols[0]:
        create_stat_card("Output Periods", str(len(periods)), "📁", "primary")
    with cols[1]:
        create_stat_card("Contractor", contractor_name, "🏢", "info")
    with cols[2]:
        create_stat_card("Client", client_name, "🤝", "success")
    with cols[3]:
        create_stat_card("Latest Period", latest_period, "📅", "warning")

    if periods:
        latest = periods[0]
        show_alert(f"Latest period detected: {latest}", "info")
        files = list_output_files(latest)
        st.write(f"Files generated in {latest}: {len(files)}")
        for file in files[:10]:
            st.write(f"- {file.name}")
    else:
        show_alert("No payroll output periods available yet. Process payroll to generate reports.", "warning")


def page_employee_management(manager: EmployeeManager, company_id: int | None) -> None:
    _render_hero(
        "Employee Management",
        "Add, edit, delete, filter, and bulk upload employee master records.",
        ["CRUD", "Bulk Upload", "Encrypted Fields"],
        icon="👥",
    )
    if company_id is None:
        show_alert("Select a company from sidebar first.", "warning")
        return
    tabs = st.tabs(["👀 View Employees", "➕ Add Employee", "✏️ Edit Employee", "🗑️ Delete Employee", "📤 Bulk Upload"])

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
        filters["company_id"] = company_id
        rows = manager.get_all_employees(filters=filters, active_only=active_only)
        if not rows:
            show_alert("No employees found.", "info")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Total rows: {len(df)}")
            stat_cols = st.columns(3)
            with stat_cols[0]:
                create_stat_card("Employees", str(len(df)), "👥", "primary")
            with stat_cols[1]:
                active_count = int(df.get("is_active", pd.Series(dtype=int)).sum()) if "is_active" in df.columns else len(df)
                create_stat_card("Active", str(active_count), "✅", "success")
            with stat_cols[2]:
                create_stat_card("Departments", str(df.get("department", pd.Series(dtype=str)).nunique()), "🏬", "info")

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
                "company_id": company_id,
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
                    show_alert(f"Employee {payload['emp_code']} added successfully.", "success")
                except Exception as exc:  # noqa: BLE001
                    show_alert(f"Failed to add employee: {exc}", "error")

    with tabs[2]:
        st.subheader("Edit Employee")
        all_rows = manager.get_all_employees(filters={"company_id": company_id}, active_only=False)
        if not all_rows:
            show_alert("No employees available for editing.", "info")
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
                    "company_id": company_id,
                }
                submitted = st.form_submit_button("Save Changes", use_container_width=True)
                if submitted:
                    try:
                        _run_with_animation(
                            "Updating employee",
                            lambda: manager.update_employee(emp_code, payload, raise_on_error=True),
                            steps=["Validating updated fields", "Applying update in database", "Writing audit log"],
                        )
                        show_alert(f"Employee {emp_code} updated successfully.", "success")
                    except Exception as exc:  # noqa: BLE001
                        show_alert(f"Failed to update employee: {exc}", "error")

    with tabs[3]:
        st.subheader("Delete Employee")
        all_rows = manager.get_all_employees(filters={"company_id": company_id}, active_only=False)
        if not all_rows:
            show_alert("No employees available for deletion.", "info")
        else:
            option_map = {f"{r['emp_code']} - {r['emp_name']}": r["emp_code"] for r in all_rows}
            selected_label = st.selectbox("Select Employee to Delete", options=list(option_map.keys()))
            emp_code = option_map[selected_label]
            soft_delete = st.checkbox("Soft delete (mark inactive)", value=True)
            confirm_text = st.text_input("Type employee code to confirm delete")
            if st.button("Delete Employee", type="primary", use_container_width=True):
                if confirm_text.strip() != emp_code:
                    show_alert("Confirmation code mismatch. Employee not deleted.", "error")
                else:
                    ok = _run_with_animation(
                        "Deleting employee",
                        lambda: manager.delete_employee(emp_code, soft_delete=soft_delete),
                        steps=["Checking employee record", "Applying delete operation", "Updating audit trail"],
                    )
                    if ok:
                        mode = "soft deleted" if soft_delete else "hard deleted"
                        show_alert(f"Employee {emp_code} {mode}.", "success")
                    else:
                        show_alert("Employee not found.", "error")

    with tabs[4]:
        st.subheader("Bulk Upload Employees")
        st.caption("Upload employee master in xlsx/xls/csv/json/txt/pdf format.")
        uploaded = file_upload_zone(
            "Upload employee master file",
            ["xlsx", "xls", "csv", "json", "txt", "pdf"],
            key="emp_bulk_upload",
        )
        if uploaded and st.button("Process Bulk Upload", use_container_width=True):
            try:
                file_path = save_uploaded_file(uploaded, INPUT_DIR / "ui_uploads", prefix="employee_bulk")
                result = _run_with_animation(
                    "Processing bulk upload",
                    lambda: manager.bulk_upload_employees(file_path, company_id=company_id),
                    steps=["Saving uploaded file", "Validating and upserting records", "Creating summary response"],
                )
                show_alert("Bulk upload processed.", "success")
                st.json(result)
            except Exception as exc:  # noqa: BLE001
                show_alert(f"Bulk upload failed: {exc}", "error")


def page_payroll_processing(manager: EmployeeManager, company_id: int | None) -> None:
    _render_hero(
        "Monthly Payroll Processing",
        "Run direct payroll or use preview -> approve -> finalize flow.",
        ["Validation", "Preview Mode", "Automated Reports", "ECR + NACH"],
        icon="💸",
    )
    preview_tab, direct_tab = st.tabs(["📄 Preview -> Approve -> Finalize", "⚡ Direct Processing"])
    if company_id is None:
        show_alert("Select a company from sidebar first.", "warning")
        return
    strict_master = st.checkbox(
        "Strict master validation (disable auto-create missing employees)",
        value=True,
        help="When unchecked, payroll auto-creates missing employees from muster/preview data.",
    )
    if strict_master:
        show_alert("Strict mode enabled: missing employees must already exist in master.", "warning")
    else:
        show_alert("Smart mode enabled: missing employees can be auto-created during processing.", "info")

    with preview_tab:
        st.subheader("Create Editable Preview")
        c1, c2 = st.columns(2)
        month = c1.number_input("Month", min_value=1, max_value=12, value=datetime.now().month, step=1)
        year = c2.number_input("Year", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        muster_upload = file_upload_zone("Upload Muster Roll (.xlsx)", ["xlsx"], key="preview_muster_upload")
        adjustments_upload = file_upload_zone(
            "Upload Adjustments (optional .xlsx/.csv)",
            ["xlsx", "csv"],
            key="preview_adjustments_upload",
        )

        if st.button("Create Preview Workbook", use_container_width=True):
            if not muster_upload:
                show_alert("Please upload muster roll file.", "error")
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
                            company_id=company_id,
                            adjustments_file=adjustments_path,
                            allow_auto_employee_creation=not strict_master,
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
                    st.session_state["ui_preview_company_id"] = int(company_id)
                    show_alert("Preview workbook generated successfully.", "success")
                except Exception as exc:  # noqa: BLE001
                    show_alert(f"Preview generation failed: {exc}", "error")

        st.markdown("#### No Excel? Use Manual/CSV/JSON/TXT input")
        st.caption("Enter attendance manually or upload simple records with columns: emp_code, present_days, ot_hours.")
        manual_file = file_upload_zone(
            "Upload manual records (.csv/.json/.txt)",
            ["csv", "json", "txt"],
            key="manual_records_upload",
        )
        if "manual_records_df" not in st.session_state:
            st.session_state["manual_records_df"] = pd.DataFrame(
                [
                    {
                        "emp_code": "",
                        "emp_name": "",
                        "department": "",
                        "designation": "Labour",
                        "present_days": 0,
                        "ot_hours": 0,
                        "advance": 0,
                        "other_deduction": 0,
                    }
                ]
            )

        if manual_file is not None:
            try:
                st.session_state["manual_records_df"] = _load_manual_records_file(manual_file)
            except Exception as exc:  # noqa: BLE001
                show_alert(f"Manual file parse failed: {exc}", "error")

        manual_df = st.data_editor(
            st.session_state["manual_records_df"],
            num_rows="dynamic",
            use_container_width=True,
            key="manual_records_editor",
        )
        st.session_state["manual_records_df"] = manual_df

        if st.button("Create Preview From Manual Records", use_container_width=True):
            try:
                records = manual_df.to_dict(orient="records")
                result = _run_with_animation(
                    "Creating preview from manual records",
                    lambda: create_payroll_preview_from_records(
                        records=records,
                        month=int(month),
                        year=int(year),
                        employee_manager=manager,
                        company_id=company_id,
                        allow_auto_employee_creation=not strict_master,
                    ),
                    steps=[
                        "Reading manual records",
                        "Auto-onboarding missing employees",
                        "Generating editable preview workbook",
                    ],
                )
                st.session_state["ui_preview_result"] = result
                st.session_state["ui_preview_month"] = int(month)
                st.session_state["ui_preview_year"] = int(year)
                st.session_state["ui_preview_company_id"] = int(company_id)
                show_alert("Preview workbook generated from manual records.", "success")
            except Exception as exc:  # noqa: BLE001
                show_alert(f"Manual preview generation failed: {exc}", "error")

        preview_result = st.session_state.get("ui_preview_result")
        if preview_result:
            st.markdown("#### Preview Result")
            show_alert("Review preview rows and approve before finalization.", "info")
            muster_summary = preview_result.get("muster_summary", {}) if isinstance(preview_result, dict) else {}
            if muster_summary:
                summary_cols = st.columns(3)
                with summary_cols[0]:
                    create_stat_card("Employees Found", str(muster_summary.get("employee_count", 0)), "👥", "primary")
                with summary_cols[1]:
                    create_stat_card("Source Sl.No Range", str(muster_summary.get("source_slno_range", 0)), "🔢", "info")
                with summary_cols[2]:
                    create_stat_card("Sl.No Gaps Handled", str(muster_summary.get("slno_gaps_detected", 0)), "🛠️", "warning")
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
                                company_id=int(st.session_state.get("ui_preview_company_id", company_id)),
                                require_approved_rows=True,
                                allow_auto_employee_creation=not strict_master,
                            ),
                            steps=[
                                "Validating approved rows",
                                "Running payroll calculation engine",
                                "Generating Excel/PDF/CSV outputs",
                            ],
                        )
                        st.session_state["ui_final_result"] = final
                        st.balloons()
                        show_alert("Payroll finalized from edited table.", "success")
                    except Exception as exc:  # noqa: BLE001
                        show_alert(f"Finalize failed: {exc}", "error")

                st.markdown("#### Or Upload External Edited Preview File")
                edited_file_upload = file_upload_zone(
                    "Upload edited preview workbook",
                    ["xlsx"],
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
                                company_id=int(st.session_state.get("ui_preview_company_id", company_id)),
                                require_approved_rows=True,
                                allow_auto_employee_creation=not strict_master,
                            ),
                            steps=[
                                "Reading uploaded preview workbook",
                                "Validating approved payroll records",
                                "Generating all statutory outputs",
                            ],
                        )
                        st.session_state["ui_final_result"] = final
                        st.balloons()
                        show_alert("Payroll finalized from uploaded preview.", "success")
                    except Exception as exc:  # noqa: BLE001
                        show_alert(f"Finalize from upload failed: {exc}", "error")
            else:
                show_alert("Preview file could not be found on disk. Please regenerate preview.", "warning")

    with direct_tab:
        st.subheader("Direct Process (no preview)")
        c1, c2 = st.columns(2)
        month_direct = c1.number_input("Month ", min_value=1, max_value=12, value=datetime.now().month, step=1)
        year_direct = c2.number_input("Year ", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        muster_upload_direct = file_upload_zone(
            "Upload Muster Roll (.xlsx)",
            ["xlsx"],
            key="direct_muster_upload",
        )
        adjustments_upload_direct = file_upload_zone(
            "Upload Adjustments (optional .xlsx/.csv)",
            ["xlsx", "csv"],
            key="direct_adjustments_upload",
        )
        if st.button("Run Direct Payroll Processing", use_container_width=True):
            if not muster_upload_direct:
                show_alert("Please upload muster roll file.", "error")
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
                            company_id=company_id,
                            adjustments_file=adjustments_path,
                            require_clean_validation=True,
                            allow_auto_employee_creation=not strict_master,
                        ),
                        steps=[
                            "Archiving source muster file",
                            "Calculating wages and deductions",
                            "Generating all reports and registers",
                        ],
                    )
                    st.session_state["ui_final_result"] = result
                    st.balloons()
                    show_alert("Direct payroll processing completed.", "success")
                except Exception as exc:  # noqa: BLE001
                    show_alert(f"Direct payroll processing failed: {exc}", "error")

    final_result = st.session_state.get("ui_final_result")
    if final_result:
        st.markdown("---")
        st.subheader("Finalized Payroll Summary")
        _render_processing_summary(final_result)


def page_reports(company_id: int | None) -> None:
    _render_hero(
        "Reports & Documents",
        "Browse monthly generated files and download reports instantly.",
        ["Excel", "PDF", "CSV"],
        icon="📁",
    )
    periods = discover_output_periods()
    if not periods:
        show_alert("No output folders found. Process payroll first.", "info")
        return

    selected = st.selectbox("Select output period (YYYY_MM)", periods)
    files = list_output_files(selected, extensions=[".xlsx", ".pdf", ".csv"])
    if company_id is not None:
        files = [f for f in files if f"company_{company_id}" in str(f)]
    if not files:
        show_alert("No files in selected period.", "warning")
        return

    cards = st.columns(3)
    with cards[0]:
        create_stat_card("Period", selected, "📅", "primary")
    with cards[1]:
        create_stat_card("Files Found", str(len(files)), "📄", "success")
    with cards[2]:
        create_stat_card("Company Filter", str(company_id or "All"), "🏢", "info")

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


def page_payment_guidance(selected_company: dict | None) -> None:
    _render_hero(
        "Payment Guidance",
        "Step-by-step statutory and bank payment instructions (guidance only).",
        ["PF", "ESIC", "PT", "Bank Upload"],
        icon="🏦",
    )
    show_alert("This system does not auto-pay challans. It only provides guidance and reports.", "info")

    pf_code = (selected_company or {}).get("pf_establishment_code", PF_ESTABLISHMENT_CODE)
    esic_code = (selected_company or {}).get("esic_employer_code", ESIC_EMPLOYER_CODE)
    pt_code = (selected_company or {}).get("pt_registration_no", PT_REGISTRATION_NO)
    metrics = st.columns(3)
    with metrics[0]:
        create_stat_card("PF Code", pf_code or "N/A", "🧾", "primary")
    with metrics[1]:
        create_stat_card("ESIC Code", esic_code or "N/A", "🏥", "success")
    with metrics[2]:
        create_stat_card("PT No.", pt_code or "N/A", "📌", "warning")
    st.markdown(
        f"""
### PF Payment
- Portal: https://unifiedportal-mem.epfindia.gov.in
- Upload ECR generated by system
- Due Date: 15th of next month
- Establishment Code: **{pf_code}**

### ESIC Payment
- Portal: https://portal.esic.in
- Enter monthly contribution and pay online
- Due Date: 15th of next month
- Employer Code: **{esic_code}**

### Professional Tax (Maharashtra)
- Portal: Maharashtra State Tax Portal
- Monthly return + challan payment
- Due Date: 21st of next month
- Registration No: **{pt_code or 'N/A'}**

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
        else:
            show_alert("No payment instruction file found for selected period.", "warning")


def page_configuration(selected_company: dict | None) -> None:
    _render_hero(
        "Configuration Snapshot",
        "Read-only values loaded from current configuration.",
        ["Contractor", "Client", "Statutory Codes"],
        icon="⚙️",
    )
    st.caption("Read-only configuration currently loaded by system.")
    config_payload = {
        "company_id": (selected_company or {}).get("company_id"),
        "company_name": (selected_company or {}).get("company_name", CONTRACTOR_NAME),
        "contractor_name": (selected_company or {}).get("contractor_name", CONTRACTOR_NAME),
        "client_name": (selected_company or {}).get("client_name", CLIENT_NAME),
        "pf_establishment_code": (selected_company or {}).get("pf_establishment_code", PF_ESTABLISHMENT_CODE),
        "esic_employer_code": (selected_company or {}).get("esic_employer_code", ESIC_EMPLOYER_CODE),
        "pt_registration_no": (selected_company or {}).get("pt_registration_no", PT_REGISTRATION_NO) or "",
        "labour_daily_rate": (selected_company or {}).get("labour_daily_rate"),
        "supervisor_daily_rate": (selected_company or {}).get("supervisor_daily_rate"),
        "labour_ot_rate": (selected_company or {}).get("labour_ot_rate"),
        "supervisor_ot_rate": (selected_company or {}).get("supervisor_ot_rate"),
    }
    cards = st.columns(3)
    with cards[0]:
        create_stat_card("Company", config_payload["company_name"], "🏢", "primary")
    with cards[1]:
        create_stat_card("Contractor", config_payload["contractor_name"], "👤", "info")
    with cards[2]:
        create_stat_card("Client", config_payload["client_name"], "🤝", "success")
    st.json(config_payload)


def run_app() -> None:
    st.set_page_config(page_title="Indian Labour Payroll Automation", layout="wide")
    _inject_custom_css()
    manager = _bootstrap()
    company_manager = _bootstrap_company_manager()

    st.sidebar.title("Payroll Automation")
    toggle_dark_mode()
    companies = company_manager.get_all_companies(active_only=True)
    selected_company_id: int | None = st.session_state.get("active_company_id")

    if companies:
        options = {f"{c['company_id']} | {c['company_name']}": int(c["company_id"]) for c in companies}
        labels = list(options.keys())
        default_index = 0
        if selected_company_id is not None:
            for idx, label in enumerate(labels):
                if options[label] == int(selected_company_id):
                    default_index = idx
                    break
        selected_label = st.sidebar.selectbox("Active Company", labels, index=default_index)
        selected_company_id = options[selected_label]
        st.session_state["active_company_id"] = selected_company_id
        selected_company = company_manager.get_company(selected_company_id)
    else:
        selected_company = None
        st.sidebar.warning("No active company found. Create one in Company Settings.")

    page = st.sidebar.radio(
        "Navigate",
        [
            "Dashboard",
            "Employee Management",
            "Payroll Processing",
            "Reports & Documents",
            "Company Settings",
            "Payment Guidance",
            "Configuration",
        ],
    )

    if page == "Dashboard":
        page_dashboard(selected_company=selected_company)
    elif page == "Employee Management":
        page_employee_management(manager, selected_company_id)
    elif page == "Payroll Processing":
        page_payroll_processing(manager, selected_company_id)
    elif page == "Reports & Documents":
        page_reports(selected_company_id)
    elif page == "Company Settings":
        new_company_id = render_company_settings(company_manager, selected_company_id)
        if new_company_id is not None:
            st.session_state["active_company_id"] = int(new_company_id)
    elif page == "Payment Guidance":
        page_payment_guidance(selected_company)
    else:
        page_configuration(selected_company)

    st.sidebar.markdown("---")
    st.sidebar.caption("For CLI usage: python3 main.py --help")


if __name__ == "__main__":
    run_app()

