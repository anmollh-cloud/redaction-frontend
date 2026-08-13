import base64
import mimetypes
from collections import Counter
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from entities import redact_text_only, find_matches_in_words, ENTITY_CATALOG, Word
from pdf_processor import extract_words, redact_pdf, redact_pdf_rasterized
from image_processor import redact_image, image_dimensions
from azure_ocr import analyze_document, result_to_words, AzureOCRError

app = FastAPI(title="Redact — Redaction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://redaction-frontend-eight.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    text: str
    entities: Optional[List[str]] = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/entities")
def entities():
    return {"entities": ENTITY_CATALOG}


@app.post("/api/redact/text")
def redact_text_endpoint(request: TextRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(400, "No text provided.")
    redacted, found = redact_text_only(request.text, request.entities)
    counts = Counter(f["label"] for f in found)
    return {
        "redacted_text": redacted,
        "entities_found": [{"label": k, "count": v} for k, v in counts.items()],
        "total_redactions": len(found),
    }


def _summarize(matches):
    counts = Counter(m.label for m in matches)
    return [{"label": k, "count": v} for k, v in counts.items()]


@app.post("/api/redact/file")
async def redact_file_endpoint(
    file: UploadFile = File(...),
    entities: Optional[str] = Form(None),  # comma-separated keys, empty = all
    use_azure: bool = Form(False),
    azure_endpoint: Optional[str] = Form(None),
    azure_key: Optional[str] = Form(None),
):
    enabled_keys = [e for e in entities.split(",") if e] if entities else None
    content = await file.read()
    filename = file.filename or "document"
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
    is_image = content_type.startswith("image/") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"))

    if not is_pdf and not is_image:
        raise HTTPException(400, "Only PDF and image files (PNG, JPG, WEBP, TIFF, BMP) are supported.")

    used_ocr = False

    if is_image:
        if not use_azure:
            raise HTTPException(
                400,
                "Images require OCR to locate text. Turn on Azure Document Intelligence "
                "in Settings and add your endpoint + key, then try again.",
            )
        try:
            result = analyze_document(azure_endpoint, azure_key, content, content_type)
        except AzureOCRError as e:
            raise HTTPException(422, str(e))
        words, _ = result_to_words(result)
        matches = find_matches_in_words(words, enabled_keys)
        used_ocr = True
        redacted_bytes = redact_image(content, matches, fmt="PNG")
        out_mime = "image/png"
        page_count = 1

    else:  # PDF
        words, page_count, has_text = extract_words(content)

        if has_text and not use_azure:
            matches = find_matches_in_words(words, enabled_keys)
            redacted_bytes = redact_pdf(content, matches)
            out_mime = "application/pdf"
        elif use_azure:
            try:
                result = analyze_document(
                    azure_endpoint, azure_key, content, "application/pdf"
                )
            except AzureOCRError as e:
                raise HTTPException(422, str(e))
            ocr_words, page_meta = result_to_words(result)
            # Azure returns inch coordinates for PDFs; convert to raster pixels
            # matching the zoom used by redact_pdf_rasterized (72 dpi * zoom).
            zoom = 2.0
            unit = next(iter(page_meta.values()), {}).get("unit", "inch") if page_meta else "inch"
            scale = 72.0 * zoom if unit == "inch" else zoom
            scaled_words = [
                Word(text=w.text, x0=w.x0 * scale, y0=w.y0 * scale,
                     x1=w.x1 * scale, y1=w.y1 * scale, page=w.page)
                for w in ocr_words
            ]
            matches = find_matches_in_words(scaled_words, enabled_keys)
            redacted_bytes = redact_pdf_rasterized(content, matches, zoom=zoom)
            out_mime = "application/pdf"
            used_ocr = True
        else:
            raise HTTPException(
                422,
                "This looks like a scanned / image-based PDF with no selectable text. "
                "Turn on Azure Document Intelligence in Settings to OCR it, then try again.",
            )

    return {
        "filename": f"redacted_{filename}",
        "mime": out_mime,
        "redacted_base64": base64.b64encode(redacted_bytes).decode("ascii"),
        "used_ocr": used_ocr,
        "page_count": page_count,
        "entities_found": _summarize(matches),
        "total_redactions": len(matches),
    }
