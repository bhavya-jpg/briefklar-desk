"""Pre-processing of one uploaded page (spec section 8.0), with an optional record cache.

The cache (data/replay/preprocess/<sha256 of the upload>.json) makes replay mode reproduce the exact
OCR text that was sent to the model when the responses were recorded, on any machine and with any
Tesseract build. It holds OCR and QR output only and is written only when BRIEFKLAR_RECORD=1.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from briefklar.config import Settings
from briefklar.models import OcrWord
from briefklar.preprocess import image as imaging
from briefklar.preprocess.ocr import detect_language, run_ocr
from briefklar.preprocess.qr import read_qr_payloads


@dataclass
class PageScan:
    sha256: str
    width: int
    height: int
    display_jpeg: bytes  # rectified page, shown to the counsellor
    model_jpeg: bytes  # contrast-normalised, resized for the model
    ocr_text: str
    ocr_words: list[OcrWord]
    qr_payloads: list[str]
    source_language: str


_recorded_now: set[str] = set()  # uploads scanned in this process while recording: no need to OCR them twice


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_path(settings: Settings, sha: str) -> Path:
    return settings.replay_dir / "preprocess" / f"{sha}.json"


def scan_image(image: np.ndarray, sha: str, settings: Settings) -> PageScan:
    """Pre-process one decoded page. `sha` identifies the upload it came from."""
    page = imaging.rectify(image)
    height, width = page.shape[:2]
    record_path = _record_path(settings, sha)
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else None

    if record is None or (settings.mode == "live" and sha not in _recorded_now):
        imaging.check_readable(page)
        text, words = run_ocr(page)
        payloads = read_qr_payloads(page) or read_qr_payloads(image)
        language = detect_language(text)
        if os.environ.get("BRIEFKLAR_RECORD", "0") == "1":
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps({
                "ocr_text": text, "ocr_words": [w.model_dump() for w in words],
                "qr_payloads": payloads, "source_language": language,
            }, ensure_ascii=False), encoding="utf-8")
            _recorded_now.add(sha)
    else:
        text = record["ocr_text"]
        words = [OcrWord(**w) for w in record["ocr_words"]]
        payloads = record["qr_payloads"]
        language = record["source_language"]

    return PageScan(
        sha256=sha, width=width, height=height,
        display_jpeg=imaging.encode_jpeg(page),
        model_jpeg=imaging.encode_jpeg(imaging.for_model(page), quality=85),
        ocr_text=text, ocr_words=words, qr_payloads=payloads, source_language=language,
    )


def scan_upload(data: bytes, filename: str, settings: Settings) -> list[PageScan]:
    """One upload (image or PDF) to one PageScan per page."""
    sha = sha256_of(data)
    images = imaging.load_pages(data, filename)
    return [
        scan_image(img, sha if len(images) == 1 else f"{sha}-p{index}", settings)
        for index, img in enumerate(images)
    ]
