"""
Native-text PDF handling with PyMuPDF.

Extraction pulls per-word bounding boxes so entities can be matched.
Redaction uses fitz's redact annotations, which physically strip the
underlying text/vector content under the box (not just paint over it).
"""
import fitz  # PyMuPDF
from typing import List, Tuple
from entities import Word, Match

BLACK = (0, 0, 0)


def extract_words(pdf_bytes: bytes) -> Tuple[List[Word], int, bool]:
    """Returns (words, page_count, has_extractable_text)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    words: List[Word] = []
    total_chars = 0
    for page_index, page in enumerate(doc):
        for w in page.get_text("words"):
            x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
            if text.strip():
                words.append(Word(text=text, x0=x0, y0=y0, x1=x1, y1=y1, page=page_index))
                total_chars += len(text)
    has_text = total_chars > 20  # heuristic: near-zero text => likely scanned
    page_count = doc.page_count
    doc.close()
    return words, page_count, has_text


def render_page_preview(pdf_bytes: bytes, page_index: int = 0, zoom: float = 1.6) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    png = pix.tobytes("png")
    doc.close()
    return png


def redact_pdf(pdf_bytes: bytes, matches: List[Match], label_boxes: bool = True) -> bytes:
    """
    Applies true, content-stripping redaction boxes to a native-text PDF.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    by_page = {}
    for m in matches:
        by_page.setdefault(m.page, []).append(m)

    for page_index, page_matches in by_page.items():
        if page_index >= doc.page_count:
            continue
        page = doc[page_index]
        for m in page_matches:
            for box in m.boxes:
                rect = fitz.Rect(*box)
                rect.x0 -= 1.5
                rect.y0 -= 1.5
                rect.x1 += 1.5
                rect.y1 += 1.5
                page.add_redact_annot(rect, fill=BLACK)
        page.apply_redactions()

    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out


def redact_pdf_rasterized(pdf_bytes: bytes, matches: List[Match], zoom: float = 2.0) -> bytes:
    """
    Fallback for scanned/OCR'd PDFs with no real text layer: rasterize each
    page and paint solid boxes directly onto the pixels (true burn-in,
    since there is no vector text to strip).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    by_page = {}
    for m in matches:
        by_page.setdefault(m.page, []).append(m)

    out_doc = fitz.open()
    for page_index in range(doc.page_count):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        new_page = out_doc.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
        for m in by_page.get(page_index, []):
            for box in m.boxes:
                x0, y0, x1, y1 = box
                rect = fitz.Rect(x0 * zoom - 2, y0 * zoom - 2, x1 * zoom + 2, y1 * zoom + 2)
                new_page.draw_rect(rect, color=BLACK, fill=BLACK)
    out = out_doc.tobytes(garbage=4, deflate=True)
    out_doc.close()
    doc.close()
    return out
