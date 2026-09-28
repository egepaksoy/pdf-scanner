"""Heuristic comparison scores, never statistical probabilities."""
import math

from app.models.result import FOUND, NOT_FOUND, REVIEW
from app.utils.config import ScanSettings


def similarity_score(good_matches: int, reference_features: int, inliers: int,
                     inlier_ratio: float, coverage: float, mean_distance: float,
                     reprojection_error: float, ransac_threshold: float,
                     geometry_valid: bool) -> float:
    if not good_matches:
        return 0.0
    feature = min(1.0, good_matches / max(16, reference_features * 0.25))
    distance = max(0.0, 1.0 - mean_distance / 400)
    if not geometry_valid:
        return round(min(49.0, 25 * feature + 15 * distance), 1)
    support = min(1.0, inliers / 32)
    spread = min(1.0, coverage / 0.35)
    precision = math.exp(-reprojection_error / max(0.1, ransac_threshold))
    score = (15 * feature + 25 * inlier_ratio + 20 * support
             + 20 * spread + 10 * distance + 10 * precision)
    return round(max(0.0, min(100.0, score)), 1)


def classify(score: float, settings: ScanSettings, geometry_valid: bool = True) -> str:
    # A user lowering the score threshold cannot bypass geometric verification.
    if geometry_valid and score >= settings.found_threshold:
        return FOUND
    if score >= settings.review_threshold:
        return REVIEW
    return NOT_FOUND
