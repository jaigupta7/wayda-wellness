"""
Rule-based generator for the narrative blocks on report pages 7-9:
  - "Yeh Cheezein Dhyan Maangti Hain" (Critical / Watch items)
  - "Jo Achha Hai" / "Jo Urgent Hai"
  - "Agar Abhi Action Nahi Liya Toh..." (future risk predictions)

Rules are intentionally simple threshold checks on the confirmed data so
they're easy to read, tweak, or extend later. Each rule returns a block
only if its condition is met; if a relevant numeric field is missing
(marked NEEDS MANUAL ENTRY / blank), that rule is skipped rather than
guessed.
"""


def merge_field(existing, new_value):
    """Prefer a real value over a NEEDS-MANUAL placeholder or blank."""
    existing_bad = (not existing) or "NEEDS MANUAL ENTRY" in str(existing)
    new_bad = (not new_value) or "NEEDS MANUAL ENTRY" in str(new_value)
    if existing_bad and not new_bad:
        return new_value
    if existing is None:
        return new_value
    return existing


def flatten_sources(results: dict) -> dict:
    """Merge field dicts from all 5 sources into one flat dict, keeping the
    first good (non-manual, non-blank) value found for each field name."""
    flat = {}
    for source_key, fields in results.items():
        for field, value in fields.items():
            if field.startswith("_") or isinstance(value, list):
                continue
            flat[field] = merge_field(flat.get(field), value)
            flat[f"{source_key}_{field}"] = value  # namespaced copy, no merging
    return flat


def _num(value, default=None):
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return default


def build_dhyan_maangti_hain(d: dict) -> list:
    """Critical / Watch blocks for pages 7-8."""
    blocks = []
    bmi = _num(d.get("bmi") or d.get("wms_bmi"))
    vikruti = (d.get("vikruti") or "").strip().lower()
    sdann = _num(d.get("sdann"))
    overthinking = (d.get("overthinking_word") or "").strip().lower()
    stress_word = (d.get("stress_level") or d.get("stress_word") or "").strip().lower()

    if vikruti == "pitta" and bmi is not None and bmi >= 27:
        blocks.append({
            "title": "Liver Channels & Bile Flow",
            "severity": "CRITICAL",
            "text": ("High Pitta intensity combined with elevated BMI is creating inflammation "
                     "pressure on the hepatic and biliary systems. This can obstruct normal bile "
                     "flow and lead to digestive distress if unaddressed."),
        })

    if bmi is not None and bmi >= 30:
        blocks.append({
            "title": "Obesity Type 1 & Body Fat Mass",
            "severity": "CRITICAL",
            "text": (f"BMI of {bmi:g} falls in the Obese Type 1 category. This level of fat "
                     "accumulation places direct physical and metabolic stress on the organs."),
        })
    elif bmi is not None and bmi >= 25:
        blocks.append({
            "title": "Overweight Status",
            "severity": "WATCH",
            "text": (f"BMI of {bmi:g} falls in the overweight category, which is worth bringing "
                     "down before it compounds with other imbalances."),
        })

    if overthinking in ("medium", "high") or stress_word in ("medium", "high"):
        blocks.append({
            "title": "Adrenal Glands & Overthinking",
            "severity": "WATCH",
            "text": ("Persistent stress and an overthinking mental pattern are placing ongoing "
                     "strain on the adrenal glands and nervous system coordination."),
        })

    if sdann is not None and 20 <= sdann <= 35:
        blocks.append({
            "title": "Sedentary Conditioning",
            "severity": "WATCH",
            "text": (f"SDANN score of {sdann:g} sits in the borderline range, indicating the body "
                     "is trending toward sedentary conditioning and reduced dynamic energy."),
        })

    return blocks


def build_jo_achha_jo_urgent(d: dict) -> dict:
    """Returns {'achha': [...], 'urgent': [...]} bullet lists for pages 7-8."""
    achha, urgent = [], []
    hydration = (d.get("hydration_level") or d.get("hydration_word") or "").strip().lower()
    rhythm = (d.get("rhythm") or "").strip().lower()
    pulse = d.get("pulse_bpm") or d.get("pulse") or d.get("pulse_rate")
    bmi = _num(d.get("bmi") or d.get("wms_bmi"))
    vikruti = (d.get("vikruti") or "").strip()
    immunity = (d.get("ojas_level") or d.get("immunity_word") or "").strip().lower()

    if hydration in ("high", "excellent"):
        achha.append("Body Hydration: Excellent")
    if rhythm == "regular":
        achha.append(f"Pulse Rhythm: Regular and steady ({pulse} bpm)" if pulse else "Pulse Rhythm: Regular and steady")

    if vikruti:
        urgent.append(f"{vikruti} Imbalance: Needs active management to bring back to balance")
    if bmi is not None and bmi >= 25:
        urgent.append(f"Weight Management: Bring BMI ({bmi:g}) down toward a healthy range")
    if immunity in ("low", "medium"):
        urgent.append(f"Immunity (Ojas): {immunity.title()} immunity needs attention")

    return {"achha": achha, "urgent": urgent}


def build_future_risks(d: dict) -> list:
    """Risk-prediction blocks for page 9."""
    risks = []
    bmi = _num(d.get("bmi") or d.get("wms_bmi"))
    vikruti = (d.get("vikruti") or "").strip().lower()
    sdann = _num(d.get("sdann"))
    immunity = (d.get("ojas_level") or d.get("immunity_word") or "").strip().lower()
    overthinking = (d.get("overthinking_word") or "").strip().lower()

    if bmi is not None and bmi >= 27 and vikruti == "pitta":
        risks.append({
            "title": "Fatty Liver Disease",
            "text": ("Elevated BMI combined with Pitta heat is creating metabolic strain on the "
                      "liver. Continued fat deposition can progress to chronic fatty liver tissue."),
        })
        risks.append({
            "title": "Gallstones Discomfort (Bile Sludge)",
            "text": ("High Pitta activity is obstructing biliary channels, which can thicken bile "
                      "in the gallbladder and raise the risk of painful gallstones."),
        })

    if immunity in ("low", "medium") and overthinking in ("medium", "high"):
        risks.append({
            "title": "Chronic Fatigue Syndrome",
            "text": ("Reduced immunity combined with persistent overthinking is depleting energy "
                      "reserves; unmanaged, this can manifest as lasting fatigue and slower recovery."),
        })

    if sdann is not None and sdann <= 35:
        risks.append({
            "title": "Metabolic Deconditioning",
            "text": ("Borderline SDANN scores point to declining physical conditioning. Left "
                      "unaddressed, stamina and dynamic energy may continue to decline."),
        })

    return risks


def generate_narrative(confirmed: dict) -> dict:
    return {
        "dhyan_maangti_hain": build_dhyan_maangti_hain(confirmed),
        "jo_achha_jo_urgent": build_jo_achha_jo_urgent(confirmed),
        "future_risks": build_future_risks(confirmed),
    }
