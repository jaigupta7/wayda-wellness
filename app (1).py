import streamlit as st
import json
import os
import tempfile

import db
import extract
import rules_engine
import report_generator

st.set_page_config(page_title="Wayda Wellness Report Builder", layout="wide")
db.init_db()

st.title("Wayda Wellness Report Builder")

REQUIRED_KEYWORDS = ["guna", "nidan", "aarogya", "swasthya", "wms"]

page = st.sidebar.radio("Navigate", ["New Report", "History"])

# ---------------------------------------------------------------------------
if page == "New Report":
    if "extracted" not in st.session_state:
        st.session_state.extracted = None
    if "record_id" not in st.session_state:
        st.session_state.record_id = None

    st.header("Step 1 — Upload the 5 source PDFs")
    st.caption("Upload all 5 assessment PDFs together. Filenames just need to contain "
               "one of: guna, nidan, aarogya, swasthya, wms — order doesn't matter.")

    uploaded_files = st.file_uploader("Drop the 5 PDFs here", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        names_lower = [f.name.lower() for f in uploaded_files]
        matched = {kw: any(kw in n for n in names_lower) for kw in REQUIRED_KEYWORDS}
        missing = [kw for kw, ok in matched.items() if not ok]
        if missing:
            st.warning(f"Could not identify files for: {', '.join(missing)}. "
                       f"Make sure filenames contain these keywords.")

        if st.button("Extract Data", type="primary", disabled=bool(missing)):
            with st.spinner("Extracting data from PDFs (this includes OCR for image-based files, may take a moment)..."):
                tmp_dir = tempfile.mkdtemp()
                results = {}
                client_name_guess = "Unknown Client"
                for f in uploaded_files:
                    path = os.path.join(tmp_dir, f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    key, data = extract.detect_and_parse(path)
                    if key:
                        results[key] = data
                        for nk in ("customer_name", "patient_name", "client_name"):
                            if data.get(nk) and "NEEDS MANUAL" not in str(data.get(nk)):
                                client_name_guess = data[nk]
                st.session_state.extracted = results
                st.session_state.record_id = db.save_extraction(client_name_guess, results)
            st.success("Extraction complete. Review the data below.")

    if st.session_state.extracted:
        st.header("Step 2 — Review & confirm extracted data")
        st.caption("Yellow-flagged values come from chart/gauge images in the source PDFs and "
                   "could not be auto-extracted — please fill those in manually.")

        total_incomplete = sum(extract.count_incomplete_fields(f) for f in st.session_state.extracted.values())
        if total_incomplete:
            st.warning(f"⚠️ {total_incomplete} field(s) across all reports still need manual entry.")
        else:
            st.success("✅ All fields extracted automatically — nothing left to fill in by hand.")

        edited_sources = {}
        for source_key, fields in st.session_state.extracted.items():
            incomplete = extract.count_incomplete_fields(fields)
            badge = f" — ⚠️ {incomplete} field(s) need review" if incomplete else " — ✅ all fields extracted"
            with st.expander(f"📄 {source_key.upper()} report{badge}", expanded=False):
                edited_sources[source_key] = {}
                for field, value in fields.items():
                    if field.startswith("_"):
                        continue
                    needs_manual = isinstance(value, str) and "NEEDS MANUAL ENTRY" in value
                    display_default = "" if needs_manual else str(value) if not isinstance(value, list) else ""
                    label = f"⚠️ {field}" if needs_manual else field
                    new_val = st.text_input(label, value=display_default, key=f"{source_key}_{field}")
                    edited_sources[source_key][field] = new_val
        flat_confirmed = rules_engine.flatten_sources(edited_sources)

        if st.button("Confirm & Generate Final Report", type="primary"):
            db.update_confirmed(st.session_state.record_id, flat_confirmed)
            narrative = rules_engine.generate_narrative(flat_confirmed)

            template_path = os.path.join(os.path.dirname(__file__), "template.pdf")
            if not os.path.exists(template_path):
                st.error("template.pdf is missing from the app folder. Add it next to app.py and redeploy.")
            else:
                out_dir = tempfile.mkdtemp()
                out_path = os.path.join(out_dir, "final_report.pdf")
                with st.spinner("Generating final PDF..."):
                    report_generator.generate_final_report(flat_confirmed, narrative, template_path, out_path)
                db.mark_report_generated(st.session_state.record_id, out_path)
                with open(out_path, "rb") as f:
                    st.download_button("⬇️ Download Final Report PDF", f, file_name="wellness_report.pdf",
                                        mime="application/pdf")
                st.success("Report generated!")

# ---------------------------------------------------------------------------
elif page == "History":
    st.header("Past Reports")
    records = db.list_records()
    if not records:
        st.info("No reports generated yet.")
    for r in records:
        cols = st.columns([3, 2, 2, 2, 1])
        cols[0].write(r["client_name"])
        cols[1].write(r["created_at"][:19])
        cols[2].write(r["status"])
        cols[3].write(r["report_filename"] or "—")
        if cols[4].button("🗑️", key=f"del_{r['id']}"):
            db.delete_record(r["id"])
            st.rerun()
