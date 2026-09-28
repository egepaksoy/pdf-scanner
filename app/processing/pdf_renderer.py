import math
import threading
from contextlib import contextmanager

import cv2
import pymupdf as fitz
import numpy as np

MAX_RENDER_PIXELS = 20_000_000
MAX_RENDER_SIDE = 6000
PDF_LOCK = threading.RLock()


@contextmanager
def open_document(path):
    # PyMuPDF must not execute concurrently in two threads of one process.
    # Parallel PDF scanning uses separate processes instead.
    with PDF_LOCK:
        document = fitz.open(path)
    try:
        yield document
    finally:
        with PDF_LOCK:
            document.close()


def render_page(page: fitz.Page, dpi: int = 200) -> np.ndarray:
    width, height = page.rect.width, page.rect.height
    if width <= 0 or height <= 0 or not math.isfinite(width * height):
        raise ValueError("Geçersiz PDF sayfa boyutu.")
    zoom = min(dpi / 72, math.sqrt(MAX_RENDER_PIXELS / (width * height)),
               MAX_RENDER_SIDE / max(width, height))
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False)
    rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
