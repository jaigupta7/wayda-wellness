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


def _render_page(path, page_index, dpi=400):
    from pdf2image import convert_from_path
    images = convert_from_path(path, dpi=dpi, first_page=page_index + 1, last_page=page_index + 1)
    return images[0], dpi / 72.0


def _isolate_and_ocr(crop_img, dark_mask=True, color_target=None, color_tol=60,
                      restrict=None, whitelist="0123456789%"):
    """Find a tight bounding box of either dark/black text or a specific
    text color within crop_img, crop to it, upscale, and OCR with psm 8
    (single word) which proved far more reliable than psm 7 for these
    bold gauge numbers."""
    import numpy as np
    import pytesseract
    arr = np.array(crop_img.convert("RGB"))
    h, w, _ = arr.shape
    if dark_mask:
        mask = (arr[:, :, 0] < 100) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)
    else:
        dist = np.sqrt(((arr.astype(int) - np.array(color_target)) ** 2).sum(axis=2))
        mask = dist < color_tol
    if restrict:
        x0f, x1f, y0f, y1f = restrict
        region = np.zeros_like(mask)
        region[int(h * y0f):int(h * y1f), int(w * x0f):int(w * x1f)] = True
        mask = mask & region
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return ""
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pad = 10
    tight = crop_img.crop((max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)))
    tight = tight.resize((tight.width * 3, tight.height * 3))
    return pytesseract.image_to_string(
        tight, config=f"--psm 8 -c tessedit_char_whitelist={whitelist}"
    ).strip()


def extract_guna_gauges(path):
    """Extracts the 5 Laghu/Guru-style bar-pair % values + Thoughts/Stress %
    from the Nadi Guna PDF, which render these as chart images, not text."""
    out = {}
    try:
        with pdfplumber.open(path) as pdf:
            page4_words = pdf.pages[3].extract_words() if len(pdf.pages) > 3 else []
            page5_words = pdf.pages[4].extract_words() if len(pdf.pages) > 4 else []

        def find_top(words, text):
            for w in words:
                if w["text"] == text:
                    return w["top"], w["bottom"]
            return None

        img4, scale = _render_page(path, 3, dpi=400)
        pairs = [("laghu_guru_pct", "Laghu"), ("kathina_mrudu_pct", "Kathina"),
                 ("sthula_sukshma_pct", "Sthula"), ("tikshna_manda_pct", "Tikshna"),
                 ("snigdha_ruksha_pct", "Snigdha")]
        for key, label in pairs:
            pos = find_top(page4_words, label)
            if not pos:
                out[key] = NEEDS_MANUAL
                continue
            top, bottom = pos
            y0, y1 = top - 12, bottom + 12
            left = img4.crop((int(140 * scale), int(y0 * scale), int(225 * scale), int(y1 * scale)))
            right = img4.crop((int(385 * scale), int(y0 * scale), int(460 * scale), int(y1 * scale)))
            lval, rval = _isolate_and_ocr(left), _isolate_and_ocr(right)
            out[key] = f"{lval} / {rval}" if lval and rval else NEEDS_MANUAL

        img5, scale5 = _render_page(path, 4, dpi=400)
        for key, label in [("thoughts_pct", "Current")]:
            pass  # handled below explicitly since "Current" appears twice
        positions = [w for w in page5_words if w["text"] == "Current" and w["x0"] < 100]
        if len(positions) >= 2:
            t_top, t_bottom = positions[0]["top"], positions[0]["bottom"]
            s_top, s_bottom = positions[1]["top"], positions[1]["bottom"]
            thoughts_crop = img5.crop((int(85 * scale5), int((t_top - 5) * scale5),
                                        int(200 * scale5), int((t_bottom + 5) * scale5)))
            stress_crop = img5.crop((int(85 * scale5), int((s_top - 5) * scale5),
                                      int(200 * scale5), int((s_bottom + 5) * scale5)))
            out["thoughts_pct"] = _isolate_and_ocr(thoughts_crop) or NEEDS_MANUAL
            out["stress_pct"] = _isolate_and_ocr(stress_crop) or NEEDS_MANUAL
        else:
            out["thoughts_pct"] = NEEDS_MANUAL
            out["stress_pct"] = NEEDS_MANUAL
    except Exception:
        for k in ["laghu_guru_pct", "kathina_mrudu_pct", "sthula_sukshma_pct",
                  "tikshna_manda_pct", "snigdha_ruksha_pct", "thoughts_pct", "stress_pct"]:
            out[k] = NEEDS_MANUAL
    return out


def extract_aarogya_quotients(path):
    """Extracts Inner/Gut/Mind Health Quotient numbers (rendered as a blue
    bold number on a gauge bar image) from the Aarogya Darshika PDF."""
    out = {}
    try:
        with pdfplumber.open(path) as pdf:
            words = pdf.pages[1].extract_words()
        img, scale = _render_page(path, 1, dpi=600)

        def find_top(label):
            for w in words:
                if w["text"] == label:
                    return w["top"], w["bottom"]
            return None

        rows = [("inner_health_quotient", "Inner"), ("gut_health_quotient", "Gut"),
                ("mind_health_quotient", "Mind")]
        # the gauge image block spans the full content width per row; we use
        # the known relative row image bboxes (title+bar+number) and isolate
        # the blue number text within the right 60%, bottom 60% of each block.
        blocks_pt = [(51, 564, 301, 352), (51, 564, 421, 472), (51, 564, 540, 591)]
        for (key, _), (x0, x1, y0, y1) in zip(rows, blocks_pt):
            crop = img.crop((int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale)))
            val = _isolate_and_ocr(
                crop, dark_mask=False, color_target=[0, 179, 220], color_tol=70,
                restrict=(0.42, 1.0, 0.40, 1.0), whitelist="0123456789"
            )
            out[key] = val if val else NEEDS_MANUAL
    except Exception:
        out = {k: NEEDS_MANUAL for k in
               ["inner_health_quotient", "gut_health_quotient", "mind_health_quotient"]}
    return out


def extract_swasthya_dials(path):
    """Extracts the 7 Digestion/Toxin/.../Stress % dial values from the
    Swasthya Darshika PDF (plain black '70%' text inside a colored ring
    image, positioned just left of each label)."""
    out = {}
    field_map = [
        ("digestion_pct", "Digestion"), ("toxin_pct", "Toxin"), ("hydration_pct", "Hydration"),
        ("immunity_pct", "Immunity"), ("flexibility_pct", "Flexibility"),
        ("overthinking_pct", "Overthinking"), ("stress_pct", "Stress"),
    ]
    try:
        with pdfplumber.open(path) as pdf:
            words = pdf.pages[3].extract_words()
        img, scale = _render_page(path, 3, dpi=400)

        def find_top(label):
            for w in words:
                if w["text"] == label:
                    return w["top"], w["bottom"]
            return None

        for key, label in field_map:
            pos = find_top(label)
            if not pos:
                out[key] = NEEDS_MANUAL
                continue
            top, bottom = pos
            y0, y1 = top - 25, bottom + 25
            crop = img.crop((int(15 * scale), int(y0 * scale), int(108 * scale), int(y1 * scale)))
            val = _isolate_and_ocr(crop)
            out[key] = val if val else NEEDS_MANUAL
    except Exception:
        out = {k: NEEDS_MANUAL for k, _ in field_map}
    return out


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
    # The Laghu/Guru, Kathina/Mrudu, Sthula/Sukshma, Tikshna/Manda,
    # Snigdha/Ruksha % bars, and Thoughts/Stress % bars are rendered as
    # graphic gauge images - extracted via targeted image-crop OCR.
    d.update(extract_guna_gauges(path))
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
    # The Inner/Gut/Mind Health Quotient numbers sit on a graphic gauge bar -
    # extracted via targeted color-isolation OCR.
    d.update(extract_aarogya_quotients(path))
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
    # Overthinking/Stress Level) are graphic dial images - extracted via
    # targeted dark-text isolation OCR. The Low/Medium/High word label is
    # also kept since it's real extractable text (useful cross-check).
    dial_values = extract_swasthya_dials(path)
    for key, label in [
        ("digestion", "Digestion Level"),
        ("toxin", "Toxin Level"),
        ("hydration", "Hydration Level"),
        ("immunity", "Immunity Level"),
        ("flexibility", "Flexibility Level"),
        ("overthinking", "Overthinking Level"),
        ("stress", "Stress Level"),
    ]:
        d[key + "_pct"] = dial_values.get(key + "_pct", NEEDS_MANUAL)
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
