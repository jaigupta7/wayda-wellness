"""
Builds the final wellness report PDF:
  - Page 1 (cover) and pages 4-9 (dynamic content) are generated fresh from
    confirmed client data + rules-engine narrative text.
  - Pages 2, 3, and 10-onward are copied as-is from the Final.pdf template
    (static, doesn't change per client).
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER
from pypdf import PdfReader, PdfWriter

TEAL = colors.HexColor("#0E5C5C")
DARK = colors.HexColor("#1A1A1A")
ORANGE = colors.HexColor("#E0654B")
RED = colors.HexColor("#C0392B")
LIGHT_GREY = colors.HexColor("#F2F2F2")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=TEAL, fontSize=22, spaceAfter=14)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=TEAL, fontSize=15, spaceAfter=8)
BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)
CENTER = ParagraphStyle("Center", parent=BODY, alignment=TA_CENTER)
WHITE_BOLD = ParagraphStyle("WhiteBold", parent=BODY, textColor=colors.white, fontName="Helvetica-Bold")
WHITE_BODY = ParagraphStyle("WhiteBody", parent=BODY, textColor=colors.white)


def _g(d, *keys, default="—"):
    for k in keys:
        v = d.get(k)
        if v and "NEEDS MANUAL ENTRY" not in str(v):
            return v
    return default


def build_cover_and_dynamic_pages(confirmed: dict, narrative: dict, out_path: str):
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                             topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                             leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    story = []

    # ---------------- PAGE 1: COVER ----------------
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("WAYDA", ParagraphStyle("Logo", parent=H1, alignment=TA_CENTER, fontSize=32)))
    story.append(Paragraph("Ayurvedic Pulse Diagnosis &amp; Wellness Assessment",
                            ParagraphStyle("Sub", parent=CENTER, textColor=colors.grey)))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Integrated Wellness Assessment Report", ParagraphStyle("Title", parent=H1, alignment=TA_CENTER)))
    story.append(Paragraph("YOUR PERSONAL HEALTH SUMMARY", ParagraphStyle("Tag", parent=CENTER, textColor=colors.grey)))
    story.append(Spacer(1, 0.5 * inch))

    client_name = _g(confirmed, "customer_name", "patient_name", "client_name")
    age_sex = _g(confirmed, "age_sex")
    if age_sex == "—":
        age = _g(confirmed, "age")
        gender = _g(confirmed, "gender")
        age_sex = f"{age} / {gender}" if age != "—" else "—"
    height = _g(confirmed, "height_cm")
    weight = _g(confirmed, "weight_kg")
    nadi_date = _g(confirmed, "visit_date", "report_date")
    wms_date = _g(confirmed, "wms_visit_date")

    cover_rows = [
        ["Client name", client_name],
        ["Age / Gender", age_sex],
        ["Height / Weight", f"{height} cm / {weight} kg"],
        ["Nadi Tarangini assessment", nadi_date],
        ["WMS assessment", wms_date],
        ["Report compiled on", ""],
    ]
    t = Table(cover_rows, colWidths=[2.6 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.white),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("CONFIDENTIAL · PREPARED FOR THE NAMED CLIENT ONLY",
                            ParagraphStyle("Conf", parent=CENTER, textColor=colors.grey, fontSize=8)))
    story.append(PageBreak())

    # ---------------- PAGE 4: YOUR BODY, AT A GLANCE ----------------
    story.append(Paragraph("2. Your Body, At a Glance", H1))
    wellness_score = _g(confirmed, "wellness_index_pct")
    pulse = _g(confirmed, "pulse_bpm", "pulse", "pulse_rate")
    rhythm = _g(confirmed, "rhythm")
    bmi = _g(confirmed, "bmi", "wms_bmi")
    vikruti = _g(confirmed, "vikruti")

    score_table = Table([[
        Paragraph(f"<b>OVERALL WELLNESS SCORE</b><br/><font size=24>{wellness_score}</font>"
                  f"{'%' if wellness_score != '—' else ''}", WHITE_BOLD),
        Paragraph("Summarised from your Nadi and WMS assessment results.", WHITE_BODY),
    ]], colWidths=[2.6 * inch, 3.4 * inch])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.15 * inch))

    metrics = Table([[
        Paragraph(f"<b>PULSE RATE</b><br/><font size=14>{pulse} bpm</font><br/>{rhythm}", BODY),
        Paragraph(f"<b>BMI - HEALTH</b><br/><font size=14>{bmi}</font>", BODY),
        Paragraph(f"<b>CURRENT IMBALANCE</b><br/><font size=14 color='#E0654B'>{vikruti}</font>", BODY),
    ]], colWidths=[2 * inch, 2 * inch, 2 * inch])
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (0, 0), 0.5, colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(metrics)
    story.append(Spacer(1, 0.3 * inch))
    story.append(PageBreak())

    # ---------------- PAGE 5: HEALTH AGE VS BODY AGE ----------------
    story.append(Paragraph("Health Age VS Body Age", H1))
    real_age = _g(confirmed, "age", "patient_age")
    vascular_age = _g(confirmed, "vascular_age")
    age_table = Table([[
        Paragraph(f"<b>REAL AGE</b><br/><font size=22>{real_age}</font>", WHITE_BOLD),
        Paragraph(f"<b>VASCULAR AGE</b><br/><font size=22>{vascular_age}</font>", WHITE_BOLD),
    ]], colWidths=[3 * inch, 3 * inch])
    age_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#C9962F")),
        ("BACKGROUND", (1, 0), (1, 0), TEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 16), ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(age_table)
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("What does this mean?", H2))
    story.append(Paragraph(
        "Vascular age higher than real age means your cardiovascular system is showing more "
        "wear than your chronological age would suggest - a sign that lifestyle, stress, or "
        "metabolic factors are placing extra load on circulation.", BODY))
    story.append(PageBreak())

    # ---------------- PAGE 6: SCORECARD ----------------
    story.append(Paragraph("Your Complete Scorecard", H1))
    score_items = [
        ("IMMUNITY", _g(confirmed, "inner_health_quotient")),
        ("GUT HEALTH", _g(confirmed, "gut_health_quotient")),
        ("MIND HEALTH", _g(confirmed, "mind_health_quotient")),
        ("AGNI", _g(confirmed, "agni_pct")),
        ("AMA", _g(confirmed, "stress_index")),
    ]
    score_row = [[Paragraph(f"<b>{label}</b><br/>{val}/100" if val != "—" else f"<b>{label}</b><br/>—", BODY)
                  for label, val in score_items]]
    sc_table = Table(score_row, colWidths=[1.2 * inch] * 5)
    sc_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                   ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(sc_table)
    story.append(Spacer(1, 0.2 * inch))

    bp_row = Table([[
        Paragraph(f"<b>BLOOD PRESSURE</b><br/>{_g(confirmed, 'systolic_pressure')}/{_g(confirmed, 'diastolic_pressure')}", WHITE_BOLD),
        Paragraph(f"<b>STROKE VOLUME</b><br/>{_g(confirmed, 'stroke_volume')} ml", WHITE_BOLD),
        Paragraph(f"<b>CARDIAC OUTPUT</b><br/>{_g(confirmed, 'cardiac_output')} L/min", WHITE_BOLD),
    ]], colWidths=[2 * inch, 2 * inch, 2 * inch])
    bp_row.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RED),
                                 ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(bp_row)
    story.append(PageBreak())

    # ---------------- PAGE 7-8: YEH CHEEZEIN DHYAN MAANGTI HAIN ----------------
    story.append(Paragraph("3. Yeh Cheezein Dhyan Maangti Hain", H1))
    for block in narrative.get("dhyan_maangti_hain", []):
        color = RED if block["severity"] == "CRITICAL" else TEAL
        story.append(Paragraph(f"<b><font color='{color.hexval()}'>{block['title']}</font></b> "
                                f"<font size=8 color='grey'>[{block['severity']}]</font>", BODY))
        story.append(Paragraph(block["text"], BODY))
        story.append(Spacer(1, 0.12 * inch))
    if not narrative.get("dhyan_maangti_hain"):
        story.append(Paragraph("No critical/watch items triggered by current data.", BODY))
    story.append(Spacer(1, 0.2 * inch))

    achha_urgent = narrative.get("jo_achha_jo_urgent", {})
    achha = achha_urgent.get("achha", []) or ["—"]
    urgent = achha_urgent.get("urgent", []) or ["—"]
    au_table = Table([[
        Paragraph("<b>JO ACHHA HAI</b><br/>" + "<br/>".join(achha), BODY),
        Paragraph("<b>JO URGENT HAI</b><br/>" + "<br/>".join(urgent), WHITE_BODY),
    ]], colWidths=[3 * inch, 3 * inch])
    au_table.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), RED),
        ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#2ECC71")),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(au_table)
    story.append(PageBreak())

    # ---------------- PAGE 9: AGAR ABHI ACTION NAHI LIYA TOH ----------------
    story.append(Paragraph("4. Agar Abhi Action Nahi Liya Toh...", H1))
    for risk in narrative.get("future_risks", []):
        story.append(Paragraph(f"<b><font color='{RED.hexval()}'>{risk['title']}</font></b>", BODY))
        story.append(Paragraph(risk["text"], BODY))
        story.append(Spacer(1, 0.12 * inch))
    if not narrative.get("future_risks"):
        story.append(Paragraph("No future-risk predictions triggered by current data.", BODY))

    doc.build(story)


def merge_with_static_template(dynamic_pdf_path: str, template_pdf_path: str, out_path: str):
    """
    dynamic_pdf_path has pages in order: [cover, p4, p5, p6, p7-8, p9] (6 pages)
    template_pdf_path is the original Final.pdf - we pull its pages 2, 3, and
    10-onward as static content.
    Final order: dyn[0] (cover), tmpl[1] (p2), tmpl[2] (p3),
                 dyn[1..5] (p4-9), tmpl[9:] (p10 onward)
    """
    dyn = PdfReader(dynamic_pdf_path)
    tmpl = PdfReader(template_pdf_path)
    writer = PdfWriter()

    writer.add_page(dyn.pages[0])          # cover
    writer.add_page(tmpl.pages[1])         # static page 2
    writer.add_page(tmpl.pages[2])         # static page 3
    for i in range(1, len(dyn.pages)):      # dynamic pages 4-9
        writer.add_page(dyn.pages[i])
    for i in range(9, len(tmpl.pages)):     # static pages 10 onward
        writer.add_page(tmpl.pages[i])

    with open(out_path, "wb") as f:
        writer.write(f)


def generate_final_report(confirmed: dict, narrative: dict, template_pdf_path: str, out_path: str):
    tmp_dynamic = out_path.replace(".pdf", "_dynamic_tmp.pdf")
    build_cover_and_dynamic_pages(confirmed, narrative, tmp_dynamic)
    merge_with_static_template(tmp_dynamic, template_pdf_path, out_path)
    os.remove(tmp_dynamic)
