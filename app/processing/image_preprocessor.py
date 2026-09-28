from pathlib import Path

import cv2
import numpy as np

from app.models.reference_stamp import ReferenceStamp


def read_image(path: str | Path) -> np.ndarray:
    # imdecode supports Windows paths containing Turkish characters.
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise ValueError("Görsel okunamadı.")
    if image.dtype == np.uint16:
        image = (image / 257).astype(np.uint8)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255
        image = (image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return image[:, :, :3]


def preprocess(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.GaussianBlur(gray, (3, 3), 0.5)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def color_mask(image: np.ndarray, mode: str) -> np.ndarray | None:
    if mode == "off":
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    if mode == "red":
        mask = cv2.inRange(hsv, (0, 45, 35), (12, 255, 255))
        mask |= cv2.inRange(hsv, (168, 45, 35), (179, 255, 255))
    else:
        mask = cv2.inRange(hsv, (90, 40, 30), (135, 255, 255))
    # Include nearby black strokes and borders; no color gating by default.
    return cv2.dilate(mask, np.ones((21, 21), np.uint8))


def load_reference(path: str | Path) -> ReferenceStamp:
    path = Path(path).resolve()
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
        raise ValueError("Desteklenmeyen görsel biçimi.")
    image = read_image(path)
    height, width = image.shape[:2]
    if min(height, width) < 24:
        raise ValueError("Referans çok küçük; en az 24 × 24 piksel gereklidir.")
    scale = min(1.0, 1600 / max(height, width))
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = preprocess(image)
    keypoints, descriptors = cv2.SIFT_create(nfeatures=3000).detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 8:
        raise ValueError("En az 8 ayırt edici özellik bulunamadı. Daha net bir mühür görseli seçin.")
    return ReferenceStamp(str(path), gray.shape[1], gray.shape[0],
                          np.float32([point.pt for point in keypoints]), descriptors)
