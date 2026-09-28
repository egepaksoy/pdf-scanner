from pathlib import Path

import cv2
import pymupdf as fitz
import numpy as np


def stamp_image(label="ANKARA", seed=7):
    image = np.full((360, 360, 3), 255, np.uint8)
    ink = (135, 45, 25)
    cv2.circle(image, (180, 180), 155, ink, 5)
    cv2.circle(image, (180, 180), 140, ink, 2)
    cv2.putText(image, label, (64, 128), cv2.FONT_HERSHEY_SIMPLEX, 1.05, ink, 3, cv2.LINE_AA)
    cv2.putText(image, "KONTROL", (62, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.1, ink, 3, cv2.LINE_AA)
    cv2.putText(image, "2026-047", (82, 244), cv2.FONT_HERSHEY_SIMPLEX, .8, ink, 2, cv2.LINE_AA)
    rng = np.random.default_rng(seed)
    for _ in range(40):
        x, y = rng.integers(70, 290, size=2)
        cv2.circle(image, (int(x), int(y)), int(rng.integers(1, 4)), ink, -1)
    return image


def write_image(path: Path, image):
    cv2.imencode(path.suffix, image)[1].tofile(str(path))


def make_pdf(path: Path, stamp=None, pages=1, stamp_page=0, transformed=False):
    with fitz.open() as document:
        for index in range(pages):
            page = document.new_page(width=432, height=576)
            for line in range(12):
                page.insert_text((32, 40 + 18 * line), f"Belge {index + 1} - Kontrol satiri {line + 1}: 1234567890", fontsize=11)
            if stamp is not None and index == stamp_page:
                image = stamp
                if transformed:
                    matrix = cv2.getRotationMatrix2D((180, 180), 18, .85)
                    image = cv2.warpAffine(stamp, matrix, (360, 360), borderValue=(255, 255, 255))
                page.insert_image(fitz.Rect(180, 310, 330, 460), stream=cv2.imencode(".png", image)[1].tobytes())
        document.save(path)
