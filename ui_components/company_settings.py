"""Streamlit UI component for multi-company configuration management."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

import streamlit as st

from modules.company_manager import CompanyManager
from utils.ui_utils import guess_mime, read_binary_file, save_uploaded_file


def _company_label(company: dict) -> str:
    active_tag = "Active" if int(company.get("is_active", 0)) == 1 else "Inactive"
    return f"{company['company_id']} | {company['company_name']} ({active_tag})"


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _active_company_option(manager: CompanyManager, selected_company_id: int | None) -> tuple[list[dict], int | None]:
    companies = manager.get_all_companies(active_only=False)
    if not companies:
        return [], None
    if selected_company_id is not None and any(int(c["company_id"]) == int(selected_company_id) for c in companies):
        return companies, int(selected_company_id)
    return companies, int(companies[0]["company_id"])


def _render_add_company_form(manager: CompanyManager) -> None:
    with st.expander("➕ Add New Company", expanded=st.session_state.get("show_add_company", False)):
        with st.form("add_company_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            company_name = c1.text_input("Company/Contractor Name *")
            contractor_name = c2.text_input("Contractor Legal Name *")

            c3, c4 = st.columns(2)
            labour_rate = c3.number_input("Labour Daily Rate (₹)", min_value=0.0, value=785.58, step=0.01, format="%.2f")
            supervisor_rate = c4.number_input(
                "Supervisor Daily Rate (₹)",
                min_value=0.0,
                value=740.76,
                step=0.01,
                format="%.2f",
            )

            c5, c6 = st.columns(2)
            labour_ot = c5.number_input("Labour OT Rate (₹)", min_value=0.0, value=92.13, step=0.01, format="%.2f")
            supervisor_ot = c6.number_input(
                "Supervisor OT Rate (₹)",
                min_value=0.0,
                value=97.73,
                step=0.01,
                format="%.2f",
            )

            submitted = st.form_submit_button("Create Company", use_container_width=True)
            if submitted:
                if not company_name.strip() or not contractor_name.strip():
                    st.error("Company name and contractor name are required.")
                else:
                    payload = {
                        "company_name": company_name.strip(),
                        "contractor_name": contractor_name.strip(),
                        "labour_daily_rate": labour_rate,
                        "supervisor_daily_rate": supervisor_rate,
                        "labour_ot_rate": labour_ot,
                        "supervisor_ot_rate": supervisor_ot,
                    }
                    try:
                        new_id = manager.add_company(payload)
                        st.session_state["active_company_id"] = new_id
                        st.success(f"Company created successfully. ID: {new_id}")
                        st.balloons()
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Failed to create company: {exc}")


def _render_company_details_tab(manager: CompanyManager, company: dict) -> None:
    with st.form("company_details_form"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Contractor Details**")
            contractor_name = st.text_input("Contractor Name *", value=company.get("contractor_name", ""))
            contractor_address = st.text_area("Contractor Address", value=company.get("contractor_address") or "")
            contractor_gstin = st.text_input("Contractor GSTIN", value=company.get("contractor_gstin") or "")
            contractor_pan = st.text_input("Contractor PAN", value=company.get("contractor_pan") or "")
            contractor_bank_name = st.text_input("Contractor Bank Name", value=company.get("contractor_bank_name") or "")
            contractor_bank_account = st.text_input(
                "Contractor Bank Account",
                value=company.get("contractor_bank_account") or "",
            )
            contractor_ifsc = st.text_input("Contractor IFSC", value=company.get("contractor_ifsc") or "").upper()

        with c2:
            st.markdown("**Client Details**")
            client_name = st.text_input("Client Name", value=company.get("client_name") or "")
            client_address = st.text_area("Client Address", value=company.get("client_address") or "")
            client_gstin = st.text_input("Client GSTIN", value=company.get("client_gstin") or "")
            client_location = st.text_input("Client Location", value=company.get("client_location") or "")

            st.markdown("**Statutory Registration**")
            pf_code = st.text_input("PF Establishment Code", value=company.get("pf_establishment_code") or "")
            esic_code = st.text_input("ESIC Employer Code", value=company.get("esic_employer_code") or "")
            pt_code = st.text_input("PT Registration Number", value=company.get("pt_registration_no") or "")
            is_active = st.checkbox("Company Active", value=bool(company.get("is_active", 1)))

        submitted = st.form_submit_button("Save Company Details", use_container_width=True)
        if submitted:
            updates = {
                "contractor_name": contractor_name,
                "contractor_address": contractor_address,
                "contractor_gstin": contractor_gstin,
                "contractor_pan": contractor_pan,
                "contractor_bank_name": contractor_bank_name,
                "contractor_bank_account": contractor_bank_account,
                "contractor_ifsc": contractor_ifsc,
                "client_name": client_name,
                "client_address": client_address,
                "client_gstin": client_gstin,
                "client_location": client_location,
                "pf_establishment_code": pf_code,
                "esic_employer_code": esic_code,
                "pt_registration_no": pt_code,
                "is_active": 1 if is_active else 0,
            }
            ok = manager.update_company(int(company["company_id"]), updates)
            if ok:
                st.success("Company details updated successfully.")
                st.rerun()
            else:
                st.error("Failed to update company details.")


def _render_wage_rates_tab(manager: CompanyManager, company: dict) -> None:
    st.info("Set company-specific rates. Payroll calculations for this company will use these values.")
    with st.form("wage_rates_form"):
        c1, c2 = st.columns(2)
        with c1:
            labour_daily = st.number_input(
                "Labour Daily Rate (₹)",
                min_value=0.0,
                value=_number(company.get("labour_daily_rate"), 785.58),
                step=0.01,
                format="%.2f",
            )
            labour_ot = st.number_input(
                "Labour OT Rate (₹)",
                min_value=0.0,
                value=_number(company.get("labour_ot_rate"), 92.13),
                step=0.01,
                format="%.2f",
            )
            st.caption(f"Suggested Labour OT (double time): ₹{(labour_daily / 8 * 2):.2f}")
        with c2:
            supervisor_daily = st.number_input(
                "Supervisor Daily Rate (₹)",
                min_value=0.0,
                value=_number(company.get("supervisor_daily_rate"), 740.76),
                step=0.01,
                format="%.2f",
            )
            supervisor_ot = st.number_input(
                "Supervisor OT Rate (₹)",
                min_value=0.0,
                value=_number(company.get("supervisor_ot_rate"), 97.73),
                step=0.01,
                format="%.2f",
            )
            st.caption(f"Suggested Supervisor OT (double time): ₹{(supervisor_daily / 8 * 2):.2f}")

        submitted = st.form_submit_button("Save Wage Rates", use_container_width=True)
        if submitted:
            updates = {
                "labour_daily_rate": labour_daily,
                "labour_ot_rate": labour_ot,
                "supervisor_daily_rate": supervisor_daily,
                "supervisor_ot_rate": supervisor_ot,
            }
            if manager.update_company(int(company["company_id"]), updates):
                st.success("Wage rates updated successfully.")
                st.rerun()
            else:
                st.error("Failed to update wage rates.")


def _render_statutory_tab(manager: CompanyManager, company: dict) -> None:
    pf_tab, esic_tab, pt_tab = st.tabs(["PF", "ESIC", "PT"])

    with pf_tab:
        with st.form("pf_settings_form"):
            pf_employee_rate = st.number_input(
                "Employee PF Rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=_number(company.get("pf_employee_rate"), 0.12) * 100,
                step=0.01,
                format="%.2f",
            )
            pf_employer_rate = st.number_input(
                "Employer PF Rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=_number(company.get("pf_employer_rate"), 0.13) * 100,
                step=0.01,
                format="%.2f",
            )
            submitted = st.form_submit_button("Save PF Settings")
            if submitted:
                updates = {
                    "pf_employee_rate": pf_employee_rate / 100,
                    "pf_employer_rate": pf_employer_rate / 100,
                }
                if manager.update_company(int(company["company_id"]), updates):
                    st.success("PF settings updated.")
                    st.rerun()
                else:
                    st.error("Failed to update PF settings.")

    with esic_tab:
        with st.form("esic_settings_form"):
            esic_employee_rate = st.number_input(
                "Employee ESIC Rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=_number(company.get("esic_employee_rate"), 0.0075) * 100,
                step=0.01,
                format="%.2f",
            )
            esic_employer_rate = st.number_input(
                "Employer ESIC Rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=_number(company.get("esic_employer_rate"), 0.0325) * 100,
                step=0.01,
                format="%.2f",
            )
            esic_wage_ceiling = st.number_input(
                "ESIC Wage Ceiling (₹)",
                min_value=0.0,
                value=_number(company.get("esic_wage_ceiling"), 21000),
                step=100.0,
            )
            submitted = st.form_submit_button("Save ESIC Settings")
            if submitted:
                updates = {
                    "esic_employee_rate": esic_employee_rate / 100,
                    "esic_employer_rate": esic_employer_rate / 100,
                    "esic_wage_ceiling": esic_wage_ceiling,
                }
                if manager.update_company(int(company["company_id"]), updates):
                    st.success("ESIC settings updated.")
                    st.rerun()
                else:
                    st.error("Failed to update ESIC settings.")

    with pt_tab:
        with st.form("pt_settings_form"):
            pt_state = st.text_input("PT State", value=company.get("pt_state") or "Maharashtra")
            st.markdown("**Slab 1**")
            s11, s12, s13 = st.columns(3)
            pt_1_min = s11.number_input("Min 1", value=_number(company.get("pt_slab_1_min"), 0.0), key="pt_1_min")
            pt_1_max = s12.number_input("Max 1", value=_number(company.get("pt_slab_1_max"), 10000.0), key="pt_1_max")
            pt_1_amt = s13.number_input(
                "Amount 1",
                value=_number(company.get("pt_slab_1_amount"), 0.0),
                key="pt_1_amt",
            )

            st.markdown("**Slab 2**")
            s21, s22, s23 = st.columns(3)
            pt_2_min = s21.number_input("Min 2", value=_number(company.get("pt_slab_2_min"), 10001.0), key="pt_2_min")
            pt_2_max = s22.number_input("Max 2", value=_number(company.get("pt_slab_2_max"), 25000.0), key="pt_2_max")
            pt_2_amt = s23.number_input(
                "Amount 2",
                value=_number(company.get("pt_slab_2_amount"), 175.0),
                key="pt_2_amt",
            )

            st.markdown("**Slab 3**")
            s31, s32, s33 = st.columns(3)
            pt_3_min = s31.number_input("Min 3", value=_number(company.get("pt_slab_3_min"), 25001.0), key="pt_3_min")
            pt_3_max = s32.number_input(
                "Max 3",
                value=_number(company.get("pt_slab_3_max"), 999999999.0),
                key="pt_3_max",
            )
            pt_3_amt = s33.number_input(
                "Amount 3",
                value=_number(company.get("pt_slab_3_amount"), 300.0),
                key="pt_3_amt",
            )

            pt_feb_additional = st.number_input(
                "February Additional PT (₹)",
                value=_number(company.get("pt_feb_additional"), 300.0),
            )
            submitted = st.form_submit_button("Save PT Settings")
            if submitted:
                updates = {
                    "pt_state": pt_state,
                    "pt_slab_1_min": pt_1_min,
                    "pt_slab_1_max": pt_1_max,
                    "pt_slab_1_amount": pt_1_amt,
                    "pt_slab_2_min": pt_2_min,
                    "pt_slab_2_max": pt_2_max,
                    "pt_slab_2_amount": pt_2_amt,
                    "pt_slab_3_min": pt_3_min,
                    "pt_slab_3_max": pt_3_max,
                    "pt_slab_3_amount": pt_3_amt,
                    "pt_feb_additional": pt_feb_additional,
                }
                if manager.update_company(int(company["company_id"]), updates):
                    st.success("PT settings updated.")
                    st.rerun()
                else:
                    st.error("Failed to update PT settings.")


def _render_invoice_tab(manager: CompanyManager, company: dict) -> None:
    with st.form("invoice_settings_form"):
        gst_applicable = st.checkbox("GST Applicable", value=bool(company.get("gst_applicable", 0)))
        gst_rate = st.number_input(
            "GST Rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=_number(company.get("gst_rate"), 0.18) * 100,
            step=0.01,
            format="%.2f",
        )
        c1, c2 = st.columns(2)
        invoice_prefix_md = c1.text_input("MD Invoice Prefix", value=company.get("invoice_prefix_md") or "MD")
        invoice_prefix_ot = c2.text_input("OT Invoice Prefix", value=company.get("invoice_prefix_ot") or "OT")
        payment_terms = st.text_input("Payment Terms", value=company.get("payment_terms") or "Net 7 Days")
        submitted = st.form_submit_button("Save Invoice Settings", use_container_width=True)
        if submitted:
            updates = {
                "gst_applicable": 1 if gst_applicable else 0,
                "gst_rate": (gst_rate / 100) if gst_applicable else 0.18,
                "invoice_prefix_md": invoice_prefix_md.strip() or "MD",
                "invoice_prefix_ot": invoice_prefix_ot.strip() or "OT",
                "payment_terms": payment_terms.strip() or "Net 7 Days",
            }
            if manager.update_company(int(company["company_id"]), updates):
                st.success("Invoice settings updated.")
                st.rerun()
            else:
                st.error("Failed to update invoice settings.")


def _render_import_export_tab(manager: CompanyManager, company: dict | None) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Export Current Company Config**")
        if company is None:
            st.info("Select a company to export.")
        elif st.button("Export Company JSON", use_container_width=True):
            export_dir = Path("data") / "ui_temp"
            export_dir.mkdir(parents=True, exist_ok=True)
            file_path = export_dir / f"company_{company['company_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            manager.export_config(int(company["company_id"]), file_path)
            st.download_button(
                "Download Exported JSON",
                data=read_binary_file(file_path),
                file_name=file_path.name,
                mime=guess_mime(file_path),
                use_container_width=True,
            )

    with col2:
        st.markdown("**Import Company Config**")
        upload = st.file_uploader("Upload JSON", type=["json"], key="company_config_import")
        if upload and st.button("Import Config", use_container_width=True):
            try:
                path = save_uploaded_file(upload, Path("data") / "ui_temp", prefix="company_import")
                new_id = manager.import_config(path)
                st.session_state["active_company_id"] = new_id
                st.success(f"Company config imported successfully. New company ID: {new_id}")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to import config: {exc}")


def _render_company_danger_zone(manager: CompanyManager, company: dict) -> None:
    with st.expander("Danger Zone", expanded=False):
        st.warning("Use carefully. Soft delete deactivates company. Hard delete is blocked if employees are linked.")
        soft_delete = st.checkbox("Soft delete (recommended)", value=True, key="company_soft_delete")
        confirmation = st.text_input("Type company name to confirm", key="company_delete_confirmation")
        if st.button("Delete Company", type="secondary", use_container_width=True):
            if confirmation.strip() != str(company.get("company_name", "")).strip():
                st.error("Confirmation text mismatch.")
                return
            try:
                ok = manager.delete_company(int(company["company_id"]), soft_delete=soft_delete)
                if ok:
                    st.success("Company deleted/deactivated successfully.")
                    st.session_state["active_company_id"] = None
                    st.rerun()
                else:
                    st.error("Failed to delete/deactivate company.")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))


def render_company_settings(manager: CompanyManager, selected_company_id: int | None = None) -> int | None:
    """Render multi-company settings page and return active company_id."""
    st.subheader("⚙️ Company Settings")
    st.caption("Manage contractor/client configuration, rates, and statutory settings per company.")

    companies, active_id = _active_company_option(manager, selected_company_id)
    if not companies:
        st.warning("No companies found. Create a company to proceed.")
        _render_add_company_form(manager)
        return None

    labels = [_company_label(c) for c in companies]
    label_to_id = {label: int(company["company_id"]) for label, company in zip(labels, companies)}
    default_label = next(label for label, cid in label_to_id.items() if cid == active_id)

    selected_label = st.selectbox("Select Company", options=labels, index=labels.index(default_label))
    selected_id = label_to_id[selected_label]
    company = manager.get_company(selected_id)
    if company is None:
        st.error("Selected company could not be loaded.")
        return None

    tabs = st.tabs(["Company Details", "Wage Rates", "Statutory", "Invoice", "Import/Export"])
    with tabs[0]:
        _render_company_details_tab(manager, company)
    with tabs[1]:
        _render_wage_rates_tab(manager, company)
    with tabs[2]:
        _render_statutory_tab(manager, company)
    with tabs[3]:
        _render_invoice_tab(manager, company)
    with tabs[4]:
        _render_import_export_tab(manager, company)

    _render_add_company_form(manager)
    _render_company_danger_zone(manager, company)

    return selected_id

