"""Render a letter to an image and degrade it the way a scanner or a phone would (spec 14.4)."""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
from jinja2 import Environment, FileSystemLoader

from bench.generator.content import TEMPLATE_DIR, LetterSpec
from briefklar.render.handout import font_faces

DPI = 200
QUALITIES = ("clean", "phone", "bad")
_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


def qr_bill_svg(qr: dict) -> str:
    """A valid Swiss QR-bill (payment part) as an SVG data URL, made with the `qrbill` library."""
    from qrbill import QRBill

    kwargs = dict(account=qr["account"], creditor=qr["creditor"], debtor=qr["debtor"], amount=str(qr["amount"]),
                  language=qr["language"], additional_information=qr["message"][:60])
    if qr.get("reference"):
        kwargs["reference_number"] = qr["reference"]
    bill = QRBill(**kwargs)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bill.svg"
        bill.as_svg(str(path))
        data = path.read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def letter_html(spec: LetterSpec) -> str:
    css, stack = font_faces()
    return _env.get_template("_letter.html.j2").render(
        **spec.ctx, font_css=css, font_stack=stack, qr_svg=qr_bill_svg(spec.qr) if spec.qr else None,
    )


def render_page(spec: LetterSpec) -> np.ndarray:
    """HTML -> PDF (WeasyPrint) -> BGR image at 200 dpi."""
    import pypdfium2 as pdfium
    from weasyprint import HTML

    pdf_bytes = HTML(string=letter_html(spec), base_url=str(TEMPLATE_DIR)).write_pdf()
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    try:
        image = np.asarray(pdf[0].render(scale=DPI / 72).to_pil().convert("RGB"))
    finally:
        pdf.close()
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def _desk(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    base = np.array([58, 84, 112], dtype=np.float32) * rng.uniform(0.8, 1.15)  # wood-like brown (BGR)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (height, width)).astype(np.float32), (0, 0), sigmaX=40, sigmaY=3)
    desk = base[None, None, :] * (1 + 0.12 * grain[..., None])
    return np.clip(desk, 0, 255).astype(np.uint8)


def _photograph(page: np.ndarray, rng: np.random.Generator, jitter: float, margin: float) -> np.ndarray:
    """Put the page on a desk and photograph it at a slight angle."""
    h, w = page.shape[:2]
    canvas_h, canvas_w = int(h * (1 + 2 * margin)), int(w * (1 + 2 * margin))
    ox, oy = int(w * margin), int(h * margin)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    offsets = rng.uniform(-jitter, jitter, (4, 2)) * [w, h]
    dst = np.float32(src + [ox, oy] + offsets)
    matrix = cv2.getPerspectiveTransform(src, dst)
    out = _desk(canvas_h, canvas_w, rng)
    warped = cv2.warpPerspective(page, matrix, (canvas_w, canvas_h), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), matrix, (canvas_w, canvas_h))
    out[mask > 127] = warped[mask > 127]
    return out


def _lighting(image: np.ndarray, rng: np.random.Generator, low: float) -> np.ndarray:
    h, w = image.shape[:2]
    angle = rng.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ramp = (np.cos(angle) * xx / w + np.sin(angle) * yy / h)
    ramp = (ramp - ramp.min()) / (ramp.max() - ramp.min())
    gain = low + (1.04 - low) * ramp
    return np.clip(image.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)


def _shadow_band(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = image.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    position = rng.uniform(0.25, 0.75)
    distance = np.abs((xx / w) * 0.6 + (yy / h) - position - 0.3)
    gain = 1 - 0.38 * np.exp(-(distance / 0.09) ** 2)
    return np.clip(image.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)


def _crumple(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = image.shape[:2]
    noise = cv2.resize(rng.normal(0, 1, (h // 60 + 2, w // 60 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    gain = 1 + 0.045 * noise
    return np.clip(image.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)


def _resize_long_side(image: np.ndarray, long_side: int) -> np.ndarray:
    scale = long_side / max(image.shape[:2])
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image


def degrade(page: np.ndarray, quality: str, seed: int) -> bytes:
    """Return JPEG bytes for one capture quality: clean (scanner), phone, bad."""
    rng = np.random.default_rng(seed)
    if quality == "clean":
        image, jpeg = page, 88
    elif quality == "phone":
        image = _photograph(page, rng, jitter=0.022, margin=0.06)
        image = _lighting(cv2.GaussianBlur(image, (0, 0), 0.8), rng, low=0.8)
        image, jpeg = _resize_long_side(image, 1900), 75
    elif quality == "bad":
        image = _photograph(_crumple(page, rng), rng, jitter=0.05, margin=0.08)
        image = _lighting(_shadow_band(cv2.GaussianBlur(image, (0, 0), 1.3), rng), rng, low=0.62)
        image, jpeg = _resize_long_side(image, 1200), 55
    else:
        raise ValueError(quality)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, jpeg])
    assert ok
    return buffer.tobytes()
