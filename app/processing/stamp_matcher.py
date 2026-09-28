import cv2
import numpy as np

from app.models.reference_stamp import ReferenceStamp
from app.models.result import FOUND, MatchResult
from app.processing.image_preprocessor import color_mask, preprocess
from app.processing.scoring import classify, similarity_score
from app.utils.config import ScanSettings

MIN_GOOD_MATCHES = 8
MIN_INLIERS = 8


def valid_polygon(polygon: np.ndarray, width: int, height: int,
                  reference: ReferenceStamp) -> bool:
    if not np.isfinite(polygon).all():
        return False
    contour = polygon.astype(np.float32).reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour):
        return False
    # Signed area rejects mirrored and folded transforms.
    area = cv2.contourArea(contour, oriented=True)
    if not 100 <= area <= width * height * 0.9:
        return False
    if ((polygon[:, 0] < -0.03 * width).any() or (polygon[:, 0] > 1.03 * width).any()
            or (polygon[:, 1] < -0.03 * height).any() or (polygon[:, 1] > 1.03 * height).any()):
        return False
    edges = np.linalg.norm(np.roll(polygon, -1, axis=0) - polygon, axis=1)
    if edges.min() < 8 or max(edges[0] / edges[2], edges[2] / edges[0],
                              edges[1] / edges[3], edges[3] / edges[1]) > 4:
        return False
    aspect = (edges[0] + edges[2]) / (edges[1] + edges[3])
    distortion = aspect / (reference.width / reference.height)
    return 0.25 < distortion < 4 and area / (edges.max() ** 2) > 0.025


class StampMatcher:
    def __init__(self, references: list[ReferenceStamp], settings: ScanSettings):
        self.references = references
        self.settings = settings
        self.sift = cv2.SIFT_create(nfeatures=12000)
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)

    def match_page(self, image: np.ndarray, cancelled=lambda: False) -> MatchResult:
        gray = preprocess(image)
        keypoints, descriptors = self.sift.detectAndCompute(
            gray, color_mask(image, self.settings.color_prefilter))
        best = MatchResult(image_size=(gray.shape[1], gray.shape[0]))
        if descriptors is None or len(keypoints) < 2:
            return best
        points = np.float32([keypoint.pt for keypoint in keypoints])
        for reference in self.references:
            if cancelled():
                break
            result = self._match(reference, points, descriptors, gray.shape[1], gray.shape[0])
            if classify(result.score, self.settings, result.polygon is not None) == FOUND:
                return result
            if result.score > best.score:
                best = result
        return best

    def _match(self, reference: ReferenceStamp, page_points: np.ndarray,
               descriptors: np.ndarray, width: int, height: int) -> MatchResult:
        pairs = self.matcher.knnMatch(reference.descriptors, descriptors, k=2)
        candidates = [a for pair in pairs if len(pair) == 2
                      for a, b in [pair] if a.distance < self.settings.lowe_ratio * b.distance]
        # Repeated reference features may otherwise vote for the same page feature.
        unique = {}
        for match in sorted(candidates, key=lambda item: item.distance):
            unique.setdefault(match.trainIdx, match)
        good = list(unique.values())
        result = MatchResult(reference=reference.name, good_matches=len(good),
                             image_size=(width, height))
        if not good:
            return result
        mean_distance = float(np.mean([match.distance for match in good]))
        coverage, error, geometry_valid = 0.0, 100.0, False
        if len(good) >= MIN_GOOD_MATCHES:
            source = reference.points[[match.queryIdx for match in good]]
            target = page_points[[match.trainIdx for match in good]]
            homography, mask = cv2.findHomography(source, target, cv2.RANSAC,
                                                self.settings.ransac_threshold,
                                                maxIters=3000, confidence=0.995)
            if homography is not None and mask is not None and np.isfinite(homography).all():
                inliers = mask.ravel().astype(bool)
                result.inlier_count = int(inliers.sum())
                result.inlier_ratio = result.inlier_count / len(good)
                if result.inlier_count >= MIN_INLIERS and result.inlier_ratio >= 0.4:
                    coverage = cv2.contourArea(cv2.convexHull(source[inliers])) / (reference.width * reference.height)
                    corners = np.float32([[0, 0], [reference.width, 0],
                                          [reference.width, reference.height], [0, reference.height]])
                    # The projective horizon must not cross the reference rectangle.
                    denominators = np.c_[corners, np.ones(4)] @ homography[2]
                    stable = np.all(denominators > 1e-6) or np.all(denominators < -1e-6)
                    polygon = cv2.perspectiveTransform(corners.reshape(-1, 1, 2), homography).reshape(-1, 2)
                    projected = cv2.perspectiveTransform(source[inliers].reshape(-1, 1, 2), homography).reshape(-1, 2)
                    error = float(np.mean(np.linalg.norm(projected - target[inliers], axis=1)))
                    geometry_valid = bool(stable and coverage >= 0.08
                                          and valid_polygon(polygon, width, height, reference)
                                          and error <= self.settings.ransac_threshold)
                    if geometry_valid:
                        result.polygon = polygon.tolist()
        result.score = similarity_score(len(good), len(reference.points), result.inlier_count,
                                        result.inlier_ratio, coverage, mean_distance, error,
                                        self.settings.ransac_threshold, geometry_valid)
        return result
