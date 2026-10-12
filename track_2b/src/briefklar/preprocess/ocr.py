"""Tesseract OCR with word boxes, QR-free language guess, and alignment of phrases to word boxes."""

from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
import pytesseract
from rapidfuzz import fuzz

from briefklar.models import OcrWord

WANTED_LANGS = ("deu", "fra", "ita")
MIN_CONFIDENCE = 30
ALIGN_THRESHOLD = 72

_STOPWORDS = {
    "de": {"der", "die", "das", "und", "ist", "nicht", "sie", "mit", "für", "von", "den", "wir", "ihre", "innert",
           "bitte", "zu", "auf", "eine", "bis", "werden", "oder", "dem", "des", "ein", "wird"},
    "fr": {"le", "la", "les", "et", "est", "vous", "nous", "pour", "dans", "des", "une", "votre", "du", "que",
           "avec", "sur", "pas", "veuillez", "jours", "au", "par", "ou", "ce", "cette", "un"},
    "it": {"il", "la", "le", "e", "è", "di", "che", "per", "con", "non", "una", "del", "della", "vostro", "entro",
           "giorni", "si", "da", "al", "nel", "sono", "gli", "lei", "suo", "un"},
}


@lru_cache
def ocr_languages() -> str:
    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        available = set()
    chosen = [lang for lang in WANTED_LANGS if lang in available]
    return "+".join(chosen) if chosen else "eng"


def run_ocr(image: np.ndarray) -> tuple[str, list[OcrWord]]:
    """Return (text, words). Word boxes are normalised to 0..1 of the page."""
    height, width = image.shape[:2]
    data = pytesseract.image_to_data(
        image[..., ::-1], lang=ocr_languages(), config="--psm 3", output_type=pytesseract.Output.DICT
    )
    words: list[OcrWord] = []
    lines: dict[tuple[int, int, int], list[str]] = {}
    line_ids: dict[tuple[int, int, int], int] = {}
    for i, raw in enumerate(data["text"]):
        text = raw.strip()
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1
        if not text or confidence < MIN_CONFIDENCE:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line = line_ids.setdefault(key, len(line_ids))
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(OcrWord(
            text=text, line=line,
            bbox=(round(x / width, 4), round(y / height, 4), round((x + w) / width, 4), round((y + h) / height, 4)),
        ))
        lines.setdefault(key, []).append(text)
    return "\n".join(" ".join(tokens) for tokens in lines.values()), words


def detect_language(text: str) -> str:
    """Stopword count over the OCR text (de / fr / it)."""
    tokens = re.findall(r"[a-zàâäçéèêëìîïòôöùûüß']+", text.casefold())
    counts = {lang: sum(token in words for token in tokens) for lang, words in _STOPWORDS.items()}
    return max(counts, key=counts.get) if any(counts.values()) else "de"  # type: ignore[arg-type]


def _norm(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.casefold())


def align_phrase(phrase: str, words: list[OcrWord]) -> tuple[float, float, float, float] | None:
    """Find the OCR words that best match `phrase` and return their union box, or None."""
    target = _norm(phrase)
    if not target or not words:
        return None
    count = max(1, len(phrase.split()))
    normed = [_norm(w.text) for w in words]
    best_score, best_span = 0.0, None
    for size in {max(1, count - 1), count, count + 1, count + 2}:
        for start in range(0, len(words) - size + 1):
            candidate = "".join(normed[start : start + size])
            if not candidate or abs(len(candidate) - len(target)) > max(4, len(target) // 2):
                continue
            score = fuzz.ratio(target, candidate)
            if score > best_score:
                best_score, best_span = score, (start, start + size)
                if score == 100:
                    break
    if best_span is None or best_score < ALIGN_THRESHOLD:
        return None
    boxes = [w.bbox for w in words[best_span[0] : best_span[1]]]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
