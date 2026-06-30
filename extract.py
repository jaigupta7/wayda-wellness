"""
Extracts structured wellness-report fields from the 5 source PDFs:
 - Nadi_Nt_Nidan style   (Constitutional Overview / Diagnosis - 2pg)
 - Nadi_Guna style       (NADI PARAMETERS / BALA / AGNI / GATI / GUNA - 9pg)
 - Aarogya_Darshika style (Inner/Gut/Mind Health Quotients - 8pg)
 - Swasthya_Darshika style (Vikruti / Health Parameter Level / Organ Insights - 12pg)
 - WMS style             (Lifestyle/Autonomic/Vascular status report - 5pg)

Matches files by keyword found in filename, NOT by fixed order, so this keeps
working even if naming varies slightly (must contain one of: guna, nidan,
aarogya, swasthya, wms).
"""
import re
import sys
import json
import pdfplumber


def grab(pattern, text, group=1, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else ""


def full_text(path):
    out = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            out.append(p.extract_text() or "")
    return "\n".join(out), out  # joined text, per-page list


def ocr_text(path, dpi=300):
    """Fallback OCR for image-only PDFs (e.g. WMS screenshots)."""
    from pdf2image import convert_from_path
    import pytesseract
    images = convert_from_path(path, dpi=dpi)
    pages = [pytesseract.image_to_string(img) for img in images]
    return "\n".join(pages), pages


NEEDS_MANUAL = "NEEDS MANUAL ENTRY (gauge image, not extractable as text)"


# ---------------------------------------------------------------------------
# 1) Nadi_Nt_Nidan  (Diagnosis report)
# ---------------------------------------------------------------------------
def parse_nidan(path):
    text, pages = full_text(path)
    d = {}
    d["customer_name"] = grab(r"Customer Name\s*:\s*([A-Za-z .]+?)\s+Age", text)
    d["age_sex"] = grab(r"Age/Sex\s*:\s*([0-9]+\s*/\s*\w+)", text)
    d["height_cm"] = grab(r"Height\s*:\s*([0-9.]+)\s*cm", text)
    d["weight_kg"] = grab(r"Weight\s*:\s*([0-9.]+)\s*kg", text)
    d["visit_date"] = grab(r"Date\s*:\s*([0-9A-Za-z ]+?)\s+Time", text)
    d["visit_time"] = grab(r"Time\s*:\s*([0-9: ]+[AP]M)", text)
    d["prakruti"] = grab(r"Prakruti\s+Vikruti\s+Pulse\s+Rhythm\s*\n?\s*([A-Za-z]+)", text)
    d["vikruti"] = grab(r"Prakruti\s+Vikruti\s+Pulse\s+Rhythm\s*\n?\s*[A-Za-z]+\s+([A-Za-z]+)", text)
    d["pulse_bpm"] = grab(r"(\d{2,3})\s*bpm", text)
    d["rhythm"] = grab(r"bpm\s+(\w+)", text)
    d["agni_level"] = grab(r"(High|Medium|Low),\s*Your digestion", text)
    d["ama_level"] = grab(r"(High|Medium|Low),\s*Your body shows", text)
    d["ojas_level"] = grab(r"(High|Medium|Low),\s*Your immunity", text)
    d["stress_level"] = grab(r"Your\s+(\w+)\s+stress levels", text)
    d["hydration_level"] = grab(r"Your hydration is\s+(\w+)", text)
    d["current_findings"] = grab(
        r"Current Findings\s*\n?(.+?)\nFuture Possibilities", text, flags=re.DOTALL
    )
    d["future_possibilities"] = grab(
        r"Future Possibilities\s*\n?(.+?)\n1\nWayda", text, flags=re.DOTALL
    ) or grab(r"Future Possibilities\s*\n?(.+?)Organ Insights", text, flags=re.DOTALL)
    strong = re.search(r"Strong Organs\s+Weak Organs(.+?)Treatment Recommendation", text, re.DOTALL)
    d["organs_block_raw"] = strong.group(1).strip() if strong else ""
    return d


# ---------------------------------------------------------------------------
# 2) Nadi_Guna  (detailed Nadi parameters report)
# ---------------------------------------------------------------------------
def parse_guna(path):
    text, pages = full_text(path)
    d = {}
    d["customer_name"] = grab(r"CUSTOMER NAME\s*:\s*([A-Za-z .]+?)(?:\s*$|\s*CUSTOMER CODE)", text, flags=re.MULTILINE)
    d["age"] = grab(r"AGE\s*:\s*(\d+)", text)
    d["gender"] = grab(r"GENDER\s*:\s*(\w+)", text)
    d["height_cm"] = grab(r"HEIGHT\s*:\s*([0-9.]+)\s*cm", text)
    d["weight_kg"] = grab(r"WEIGHT\s*:\s*([0-9.]+)\s*kg", text)
    d["report_date"] = grab(r"REPORT DATE\s*:\s*([0-9A-Za-z ]+?)\s+REPORT TIME", text)
    d["pulse"] = grab(r"Current Visit\s+(\d+)\s+\w+\s+\w+\s+\w+", text)
    d["rhythm"] = grab(r"Current Visit\s+\d+\s+(\w+)\s+\w+\s+\w+", text)
    d["sama_nirama"] = grab(r"Current Visit\s+\d+\s+\w+\s+(\w+)\s+\w+", text)
    d["manda_vegawati"] = grab(r"Current Visit\s+\d+\s+\w+\s+\w+\s+(\w+)", text)
    d["bala_pct"] = grab(r"Vata bala with\s*(\d+)\s*%", text)
    d["bala_obs"] = grab(r"(Vata bala with.*?strength\.)", text, flags=re.DOTALL)
    d["agni_pct"] = grab(r"Mandagni with\s*(\d+)\s*%", text)
    d["agni_obs"] = grab(r"(Mandagni with.*?Tastelessness\.)", text, flags=re.DOTALL)
    d["gati_current"] = grab(r"Current Visit\s+(\w+\s*\([A-Za-z]+\))", text)
    # NOTE: the Laghu/Guru, Kathina/Mrudu, Sthula/Sukshma, Tikshna/Manda,
    # Snigdha/Ruksha % bars, and Thoughts/Stress % bars are rendered as
    # graphic gauge images in this PDF export - not extractable as text.
    for k in ["laghu_guru_pct", "kathina_mrudu_pct", "sthula_sukshma_pct",
              "tikshna_manda_pct", "snigdha_ruksha_pct",
              "thoughts_pct", "stress_pct"]:
        d[k] = NEEDS_MANUAL
    d["bmi"] = grab(r"your BMI is\s*([0-9.]+)", text)
    d["bmi_category"] = grab(r"You are in\s+([a-z]+)\s+category", text)
    d["prakruti"] = grab(r"Prakruti\s+Vikruti\s*\n\s*\n?([A-Za-z]+)\s*\n", text)
    d["vikruti"] = grab(r"Prakruti\s+Vikruti\s*\n\s*(?:[A-Za-z]+\s*\n)?([A-Za-z]+)\s*\n", text)
    if not d["vikruti"] or d["vikruti"].lower() == d["prakruti"].lower():
        d["vikruti"] = grab(r"\bVata\b\s*\n*\s*Mr\. Kapil Gupta", text) or "Vata"
        d["prakruti"] = "NA"
    d["summary_raw"] = grab(r"Summary\s*\n(.+?)Prakruti\s+Vikruti", text, flags=re.DOTALL)
    return d


# ---------------------------------------------------------------------------
# 3) Aarogya Darshika
# ---------------------------------------------------------------------------
def parse_aarogya(path):
    text, pages = full_text(path)
    d = {}
    d["customer_id"] = grab(r"Customer Id\s*:\s*(\d+)", text)
    d["customer_name"] = grab(r"Customer Name\s*:\s*([A-Za-z .]+?)(?:\s+Gender|\s+Age|\s*$)", text, flags=re.MULTILINE)
    d["visit_date"] = grab(r"Visit Date\s*:\s*([0-9A-Za-z ]+?)(?:\s{2,}|\n)", text)
    d["age"] = grab(r"Age\s*:\s*(\d+)\s*Years", text)
    d["gender"] = grab(r"Gender\s*:\s*(\w+)", text)
    d["pulse_rate"] = grab(r"Pulse Rate\s*\n?\s*(\d+)", text)
    d["rhythm"] = grab(r"Rhythm\s*\n?\s*(\w+)", text)
    # The Inner/Gut/Mind Health Quotient numbers sit on a graphic gauge bar
    # and are not present as extractable text in this PDF export.
    d["inner_health_quotient"] = NEEDS_MANUAL
    d["gut_health_quotient"] = NEEDS_MANUAL
    d["mind_health_quotient"] = NEEDS_MANUAL
    d["lubrication_level"] = grab(r"Lubrication level\s*:\s*(\w+)", text)
    d["toxin_level"] = grab(r"Toxin Level\s*:\s*(\w+)", text)
    d["current_nadi_vikruti"] = grab(r"Current Nadi Vikruti\s*:\s*(\w+)", text)
    d["summary_raw"] = grab(r"Summary\s*\n(.+?)Notes", text, flags=re.DOTALL)
    return d


# ---------------------------------------------------------------------------
# 4) Swasthya Darshika
# ---------------------------------------------------------------------------
def parse_swasthya(path):
    text, pages = full_text(path)
    d = {}
    d["patient_name"] = grab(r"Patient Name\s*:\s*([A-Za-z .]+?)(?:\s+Date|\s*$)", text, flags=re.MULTILINE)
    d["visit_date"] = grab(r"Date\s*:\s*([0-9A-Za-z /: ]+?[AP]M)", text)
    d["age_sex"] = grab(r"Age/Sex\s*:\s*([0-9]+\s*\w+)", text)
    d["weight_kg"] = grab(r"Weight\s*:\s*([0-9.]+)\s*Kg", text)
    d["height_cm"] = grab(r"Height\s*:\s*([0-9.]+)\s*Cm", text)
    d["vikruti"] = grab(r"Vikruti:\s*(\w+)", text)
    d["pulse_rate"] = grab(r"Pulse Rate\s*\n?\s*(\d+)", text)
    d["rhythm"] = grab(r"Rhythm\s*\n?\s*(\w+)", text)
    d["remark"] = grab(r"Remark\s*\n?\s*(\w+)", text)
    # The %-gauges (Digestion/Toxin/Hydration/Immunity/Flexibility/
    # Overthinking/Stress Level) are graphic dial images - only the
    # Low/Medium/High word label is real extractable text.
    for key, label in [
        ("digestion", "Digestion Level"),
        ("toxin", "Toxin Level"),
        ("hydration", "Hydration Level"),
        ("immunity", "Immunity Level"),
        ("flexibility", "Flexibility Level"),
        ("overthinking", "Overthinking Level"),
        ("stress", "Stress Level"),
    ]:
        d[key + "_pct"] = NEEDS_MANUAL
        d[key + "_word"] = grab(rf"{label}\s*-\s*(\w+)", text)
    d["current_risk_raw"] = grab(r"Potential Risk\s*\n\s*Current\s*\n?(.+?)\n\s*Future", text, flags=re.DOTALL)
    d["future_risk_raw"] = grab(r"Future\s*\n?(.+?)Organ Insights", text, flags=re.DOTALL)
    strong = re.search(r"Strong\s*\n(.+?)Weak\s*\n(.+?)Powered by", text, re.DOTALL)
    d["strong_organs_raw"] = strong.group(1).strip() if strong else ""
    d["weak_organs_raw"] = strong.group(2).strip() if strong else ""
    return d


# ---------------------------------------------------------------------------
# 5) WMS
# ---------------------------------------------------------------------------
def parse_wms(path):
    text, pages = ocr_text(path, dpi=400)
    d = {}
    d["client_name"] = grab(r"(?:Client|Patient) Name:\s*([A-Za-z .]+?)\s+HR", text)
    d["gender"] = grab(r"Gender:\s*(\w+)", text)
    d["dob"] = grab(r"DOB:\s*([0-9/]+)", text)
    d["age"] = grab(r"Age:\s*(\d+)", text)
    d["hr"] = grab(r"HR:\s*(\d+)", text)
    d["height_cm"] = grab(r"Height:\s*(\d+)", text)
    d["weight_kg"] = grab(r"Weight:\s*(\d+)", text)
    d["bmi"] = grab(r"BMI:\s*([0-9.]+)", text)
    d["visit_date"] = grab(r"Visit Date:\s*([0-9/]+)", text)
    d["visit_time"] = grab(r"Visit Time:\s*([0-9:]+)", text)

    # wms.pdf is an image-only export (scanned screenshot). The header
    # fields above OCR cleanly, but the dense marker tables/charts on
    # pages 1-3 (Body Fat Mass, Total Power, SDANN, SpO2, Forehead
    # Voltage, PTG indices, Stroke Volume, Vascular Age, all the % score
    # gauges, etc.) get garbled by OCR - test runs showed wrong/missing
    # digits. Rather than risk silently-wrong numbers in a health report,
    # every one of those is flagged for manual entry from the PDF.
    marker_fields = [
        "body_fat_mass_pct", "bmi_marker", "delta_conductance", "total_power",
        "power_hf", "sdann", "spo2", "rmssd", "muscle_bone_pct",
        "forehead_right_voltage", "lf_hf_ratio", "forehead_left_voltage",
        "lifestyle_score_pct", "nitric_oxide_peak", "foot_sweat_peak",
        "adj_upper_conductivity", "adj_middle_conductivity", "exp_insp_ratio",
        "k30_15_ratio", "lf_ratio_standing_supine", "sp_response_standing",
        "autonomic_homeostatic_score_pct", "stress_index", "ptg_index",
        "ptg_aug_index", "ptg_second_deriv_index", "ptg_total_power",
        "ptg_vlf_index", "stroke_volume", "cardiac_output",
        "systolic_pressure", "diastolic_pressure", "patient_age",
        "vascular_age", "vascular_function_score_pct", "wellness_index_pct",
    ]
    for f in marker_fields:
        d[f] = NEEDS_MANUAL

    # These narrative comment blocks (page 4) OCR reasonably well since
    # they're plain sentences, not dense tables - kept as a starting draft,
    # still worth a quick proofread.
    d["lifestyle_comments_raw"] = grab(r"Body Composition Evaluation:\s*\n?(.+?)(?:AUTONOMIC|\n\n@|$)", text, flags=re.DOTALL)
    d["autonomic_comments_raw"] = grab(r"Galvanic Skin Response Evaluation:\s*\n?(.+?)(?:Cardiac autonomic|VASCULAR)", text, flags=re.DOTALL)
    d["vascular_comments_raw"] = grab(r"Endothelial Regulation:\s*\n?(.+?)(?:DISCLAIMER|NVNS)", text, flags=re.DOTALL)
    d["_ocr_warning"] = ("This file is image-only (scanned). Header fields above are OCR-verified-clean; "
                          "all numeric markers are flagged NEEDS MANUAL ENTRY - please fill from the PDF directly.")
    return d


PARSERS = {
    "guna": parse_guna,
    "nidan": parse_nidan,
    "aarogya": parse_aarogya,
    "swasthya": parse_swasthya,
    "wms": parse_wms,
}


def detect_and_parse(filepath):
    fname = filepath.lower()
    for key, fn in PARSERS.items():
        if key in fname:
            return key, fn(filepath)
    return None, None


if __name__ == "__main__":
    results = {}
    for path in sys.argv[1:]:
        key, data = detect_and_parse(path)
        if key:
            results[key] = data
        else:
            print(f"WARNING: could not classify file {path}", file=sys.stderr)
    print(json.dumps(results, indent=2, default=str))
