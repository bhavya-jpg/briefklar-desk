"""Page images: load, crop to the page, deskew, normalise, resize (spec section 8.0). No model."""

from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps

PDF_DPI = 200
MODEL_LONG_SIDE = 1600  # tune in the gate test: 1280 / 1600 / 2048
MIN_SHARPNESS = 12.0  # variance of the Laplacian; below this the page is treated as unreadable


class UnreadablePage(ValueError):
    pass


def load_pages(data: bytes, filename: str) -> list[np.ndarray]:
    """Decode an upload into BGR page images. PDFs are rasterised at 200 dpi."""
    if filename.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        try:
            return [
                cv2.cvtColor(np.asarray(page.render(scale=PDF_DPI / 72).to_pil().convert("RGB")), cv2.COLOR_RGB2BGR)
                for page in pdf
            ]
        finally:
            pdf.close()
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as exc:
        raise UnreadablePage("This file is not an image or PDF. Use JPEG, PNG or PDF.") from exc
    return [cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)]


def _order_corners(points: np.ndarray) -> np.ndarray:
    points = points.reshape(4, 2).astype(np.float32)
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.array(
        [points[total.argmin()], points[diff.argmin()], points[total.argmax()], points[diff.argmax()]],
        dtype=np.float32,
    )


def find_page_quad(image: np.ndarray) -> np.ndarray | None:
    """The page outline as four corners (tl, tr, br, bl), or None when the page already fills the frame."""
    height, width = image.shape[:2]
    scale = 800 / max(height, width)
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 50, 150), np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(contour)
        if not 0.35 * frame_area < area < 0.97 * frame_area:
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return _order_corners(approx) / scale
    return None


def warp_to_quad(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    return cv2.warpPerspective(image, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE)


def skew_angle(image: np.ndarray) -> float:
    """Median angle (degrees) of near-horizontal text lines; 0 when unsure."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = 1000 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(small, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=120, minLineLength=small.shape[1] // 5, maxLineGap=20)
    if lines is None:
        return 0.0
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4)]
    angles = [a for a in angles if abs(a) < 12]
    return float(np.median(angles)) if len(angles) >= 5 else 0.0


def rotate(image: np.ndarray, angle: float) -> np.ndarray:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def rectify(image: np.ndarray) -> np.ndarray:
    """Crop to the page and straighten it. The result is what the counsellor sees and what OCR reads."""
    quad = find_page_quad(image)
    if quad is not None:
        image = warp_to_quad(image, quad)
    angle = skew_angle(image)
    if 0.3 < abs(angle) < 10:
        image = rotate(image, angle)
    return image


def sharpness(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = 1000 / max(gray.shape)
    return float(cv2.Laplacian(cv2.resize(gray, None, fx=scale, fy=scale), cv2.CV_64F).var())


def check_readable(image: np.ndarray) -> None:
    if sharpness(image) < MIN_SHARPNESS:
        raise UnreadablePage("This page is too blurry to read. Take the photo again in more light.")


def for_model(image: np.ndarray, long_side: int = MODEL_LONG_SIDE) -> np.ndarray:
    """Contrast-normalised (CLAHE) copy with the long side resized for the model."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    scale = long_side / max(out.shape[:2])
    if scale < 1:
        out = cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return out


def encode_jpeg(image: np.ndarray, quality: int = 88) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise UnreadablePage("This page could not be saved. Take the photo again.")
    return buffer.tobytes()
