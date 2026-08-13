"""
Thin REST client for Azure AI Document Intelligence (prebuilt-read model).

We call the REST API directly with `requests` rather than pulling in the
full azure-ai-documentintelligence SDK, since the backend only needs one
operation: submit a document, poll, get words + polygons back.

The user supplies their own endpoint + key from the frontend Settings
panel; nothing is stored server-side.
"""
import time
import requests
from typing import List, Tuple
from fastapi import HTTPException
from entities import Word

API_VERSION = "2024-11-30"
POLL_INTERVAL_SECS = 1.0
POLL_TIMEOUT_SECS = 60


class AzureOCRError(Exception):
    pass


def _analyze_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    return f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version={API_VERSION}&outputContentFormat=text"


def analyze_document(endpoint: str, api_key: str, file_bytes: bytes, content_type: str) -> dict:
    """Submits a document to Azure DI and polls until the result is ready."""
    if not endpoint or not api_key:
        raise AzureOCRError("Azure Document Intelligence endpoint and key are required for OCR.")

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": content_type,
    }
    try:
        resp = requests.post(_analyze_url(endpoint), headers=headers, data=file_bytes, timeout=30)
    except requests.RequestException as e:
        raise AzureOCRError(f"Could not reach Azure Document Intelligence: {e}")

    if resp.status_code == 401:
        raise AzureOCRError("Azure rejected the API key (401 Unauthorized). Check your key.")
    if resp.status_code == 404:
        raise AzureOCRError("Azure endpoint not found (404). Check the endpoint URL.")
    if resp.status_code not in (200, 202):
        raise AzureOCRError(f"Azure Document Intelligence error {resp.status_code}: {resp.text[:300]}")

    op_location = resp.headers.get("Operation-Location")
    if not op_location:
        raise AzureOCRError("Azure did not return an Operation-Location to poll.")

    waited = 0.0
    while waited < POLL_TIMEOUT_SECS:
        time.sleep(POLL_INTERVAL_SECS)
        waited += POLL_INTERVAL_SECS
        poll = requests.get(op_location, headers={"Ocp-Apim-Subscription-Key": api_key}, timeout=30)
        if poll.status_code != 200:
            raise AzureOCRError(f"Azure polling error {poll.status_code}: {poll.text[:300]}")
        body = poll.json()
        status = body.get("status")
        if status == "succeeded":
            return body.get("analyzeResult", {})
        if status == "failed":
            raise AzureOCRError(f"Azure OCR analysis failed: {body}")
    raise AzureOCRError("Timed out waiting for Azure Document Intelligence to finish.")


def result_to_words(analyze_result: dict) -> Tuple[List[Word], dict]:
    """
    Converts Azure's analyzeResult into our flat Word list.
    Returns (words, page_meta) where page_meta maps page index -> {width, height, unit}.
    """
    words: List[Word] = []
    page_meta = {}
    for page in analyze_result.get("pages", []):
        page_no = page.get("pageNumber", 1) - 1
        page_meta[page_no] = {
            "width": page.get("width"),
            "height": page.get("height"),
            "unit": page.get("unit", "pixel"),
        }
        for w in page.get("words", []):
            poly = w.get("polygon", [])
            if len(poly) < 8:
                continue
            xs = poly[0::2]
            ys = poly[1::2]
            words.append(Word(
                text=w.get("content", ""),
                x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
                page=page_no,
            ))
    return words, page_meta
