"""QR decoding with zxing-cpp."""

from __future__ import annotations

import numpy as np
import zxingcpp


def read_qr_payloads(image: np.ndarray) -> list[str]:
    seen: list[str] = []
    for result in zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode):
        if result.text and result.text not in seen:
            seen.append(result.text)
    return seen
