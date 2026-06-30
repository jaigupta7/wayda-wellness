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
1. Push this folder to a GitHub repo (public or private)
2. Go to https://share.streamlit.io -> "New app"
3. Connect your GitHub repo, select `app.py` as the entry point
4. Deploy — `packages.txt` and `requirements.txt` are auto-detected and
   installed (this is what gets poppler/tesseract for OCR working)
5. You'll get a public URL like `yourapp.streamlit.app` to share with
   your friend

## Known limitations (current version)
- Some source PDFs render key numbers (gauge charts, quotient dials) as
  images rather than text. These can't be reliably auto-extracted (OCR
  was tested and is too unreliable for small chart numbers) — they're
  flagged "NEEDS MANUAL ENTRY" in the review step instead of guessing.
- `wms.pdf` is itself a scanned/image-only export; only its header
  fields (name, age, HR, height, weight, BMI, visit date) are OCR-clean.
  Its detailed marker table needs manual entry per report.
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
