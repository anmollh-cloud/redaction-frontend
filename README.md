# Redact — precise, private document redaction

A redaction tool for text, PDFs and images. Paste text or upload a file,
pick which entity types matter, and get back a copy with the sensitive
parts permanently removed — not just painted over.

## What it does

- **Paste text** — regex-based detection of email, phone, PAN, Aadhaar,
  GSTIN, passport, credit card (Luhn-checked), SSN, IFSC, IP address and
  dates. Redacted inline.
- **Upload a PDF** — if the PDF has a real text layer, it's redacted
  locally: every matched word's underlying text and vector content is
  stripped via PyMuPDF's redaction annotations (recoverable-by-copy-paste
  is not possible afterwards, unlike a black rectangle drawn on top).
- **Upload a scanned PDF or an image** — these have no selectable text, so
  they're OCR'd first. Turn on **Azure Document Intelligence** in
  Settings, add your endpoint + key, and the app will call Azure's
  `prebuilt-read` model, map the returned word boxes back onto the page,
  and burn black boxes into the rasterized output.
- Your Azure credentials never touch a server-side store — they live in
  `sessionStorage` in your browser tab and are sent with each request.

## Project layout

```
backend/     FastAPI app (Python)
  main.py            API routes
  entities.py        regex patterns + word-level entity matcher
  pdf_processor.py    PyMuPDF extraction + true redaction
  image_processor.py  Pillow-based box burn-in for images
  azure_ocr.py         Azure Document Intelligence REST client
frontend/    React + Vite app
  src/App.jsx   the whole UI (tabs, dropzone, settings drawer, preview)
  src/App.css   styling
  src/api.js    fetch wrappers for the backend
```

## Running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

By default the frontend calls `http://localhost:8000`. To point it at a
deployed backend, create `frontend/.env` with:

```
VITE_API_URL=https://your-backend.example.com
```

## Setting up Azure Document Intelligence

1. In the [Azure Portal](https://portal.azure.com), create a **Document
   Intelligence** (formerly Form Recognizer) resource.
2. Copy the resource's **Endpoint** and **Key1** from its "Keys and
   Endpoint" page.
3. In the app, click **Azure OCR** in the top bar, paste them in, and
   flip the switch on. Nothing is saved beyond the current browser tab.

Any tier works — the app only calls the `prebuilt-read` model, which is
available on the free (F0) tier.

## Notes on the redaction guarantee

- **Native-text PDFs**: redaction is applied via `page.add_redact_annot`
  + `apply_redactions()`, which PyMuPDF implements by deleting the
  underlying content stream data under the box — the text is gone, not
  hidden.
- **Scanned PDFs / images**: there's no text layer to strip in the first
  place; the black boxes are painted directly into the pixel data at the
  OCR'd coordinates, so the covered pixels no longer exist in the output.
- Nothing uploaded is written to disk — files are processed in memory for
  the duration of the request only.
