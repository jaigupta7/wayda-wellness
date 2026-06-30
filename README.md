# Wayda Wellness Report Builder

A Streamlit web app: upload the 5 source PDFs (Nadi Guna, Nadi Nidan,
Aarogya Darshika, Swasthya Darshika, WMS) → review/edit extracted data →
generate the final wellness report PDF (styled to match Final.pdf, pages
2/3/10+ reused as static content).

## Files
- `app.py` — the Streamlit web app (UI)
- `extract.py` — pulls fields from the 5 source PDFs (text + OCR fallback)
- `rules_engine.py` — generates the narrative blocks for report pages 7-9
- `report_generator.py` — builds the final PDF and merges with the static
  template pages
- `db.py` — SQLite database (stores client records / history)
- `requirements.txt` / `packages.txt` — dependencies

## Run locally
```bash
pip install -r requirements.txt
sudo apt-get install poppler-utils tesseract-ocr   # for OCR support
streamlit run app.py
```
Opens at http://localhost:8501

## Deploy for a public link (free) — Streamlit Community Cloud
1. Push this folder to a GitHub repo (the repo needs to be Public, or
   Streamlit needs explicit access granted to a Private repo via its
   GitHub App settings)
2. Go to https://share.streamlit.io -> "New app"
3. Connect your GitHub repo, select `app.py` as the entry point
4. Deploy — `packages.txt` and `requirements.txt` are auto-detected and
   installed (this is what gets poppler/tesseract for OCR working)
5. You'll get a public URL like `yourapp.streamlit.app` to share with
   your friend

## Template (Final.pdf design)
`template.pdf` is bundled directly in this repo — no need to re-upload
it each time. Its pages 2, 3, and 10-onward are reused as-is (static
content) when generating each client's final report. To change the
template design, just replace `template.pdf` in the repo and redeploy.

## Data extraction accuracy
Most numeric values that appear as charts/gauge images (not real text)
in the Nadi software reports are now extracted reliably using targeted
image-crop + OCR (isolating just the colored/dark digit pixels at each
gauge's known position, rather than OCR-ing the whole busy page):
- Nadi Guna: all 5 bar-pair %s (Laghu/Guru, Kathina/Mrudu, etc.) +
  Thoughts/Stress %s — extracted automatically
- Aarogya Darshika: Inner/Gut/Mind Health Quotient numbers — extracted
  automatically
- Swasthya Darshika: all 7 dial %s (Digestion, Toxin, Hydration,
  Immunity, Flexibility, Overthinking, Stress) — extracted automatically

**wms.pdf remains a manual-entry case.** Unlike the other 4 reports
(which are clean vector-based PDF exports), wms.pdf is itself a
scanned/flattened screenshot — there's no underlying text or consistent
color-coded layout to anchor a crop on, and whole-page OCR on its dense
marker table proved unreliable (digit misreads). Only its header fields
(name, age, HR, height, weight, BMI, visit date) are OCR-clean; the
detailed marker table (Body Fat Mass, SDANN, SpO2, Stroke Volume, etc.)
is flagged "NEEDS MANUAL ENTRY" in the review step. If you can get a
non-scanned/native export of the WMS report, send it over and the same
targeted-crop technique can likely be applied there too.

## Known limitations (current version)
- `wms.pdf` is itself a scanned/image-only export with no clean anchor
  points; only its header fields OCR cleanly, its detailed marker table
  still needs manual entry per report (see "Data extraction accuracy"
  above for why, and what would fix it).
- The final PDF's dynamic pages (cover + pages 4-9) use a clean styled
  layout inspired by Final.pdf's colors/structure, not a pixel-identical
  recreation of the Canva design (gauges, donut charts, etc. would need
  a separate custom-graphics pass — happy to build that next if wanted).
- The SQLite database (`wellness.db`) is a local file. On Streamlit
  Community Cloud this resets whenever the app restarts/sleeps — fine
  for testing, but for permanent history storage you'd want a hosted DB
  (e.g. Supabase free tier) instead. Ask if you want this swapped in.

## Database
Currently SQLite (`wellness.db`), auto-created on first run. Stores:
client name, extracted data, confirmed data, status, report filename.
