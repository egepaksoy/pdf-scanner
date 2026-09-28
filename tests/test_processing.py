import csv
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import pymupdf as fitz
import numpy as np

from app.models.result import CANCELLED, ERROR, FOUND, NOT_FOUND, MatchResult, ScanResult
from app.processing.image_preprocessor import load_reference
from app.processing.scanner import find_pdfs, scan_pdf
from app.processing.scoring import classify
from app.processing.stamp_matcher import StampMatcher, valid_polygon
from app.utils.config import ScanSettings
from app.utils.report import export_csv
from tests.fixtures import make_pdf, stamp_image, write_image


class ProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cv2.setNumThreads(1)
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.stamp = stamp_image()
        cls.reference_path = cls.root / "mühür.png"
        write_image(cls.reference_path, cls.stamp)
        cls.reference = load_reference(cls.reference_path)
        cls.settings = ScanSettings(dpi=150)
        cls.matcher = StampMatcher([cls.reference], cls.settings)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_single_page_match(self):
        path = self.root / "single.pdf"
        make_pdf(path, self.stamp)
        result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, FOUND)
        self.assertEqual(result.best_page, 1)
        self.assertEqual(result.match.reference, "mühür.png")
        self.assertGreaterEqual(result.match.score, 80)
        self.assertIsNotNone(result.bounding_box)
        self.assertGreaterEqual(result.match.inlier_count, 8)

    def test_multiple_pages_references_and_rotation(self):
        path = self.root / "multi.pdf"
        make_pdf(path, self.stamp, pages=3, stamp_page=1, transformed=True)
        other_path = self.root / "other.png"
        other = np.full((360, 360, 3), 255, np.uint8)
        cv2.putText(other, "IZMIR", (25, 160), cv2.FONT_HERSHEY_TRIPLEX, 2, (0, 0, 0), 3)
        cv2.putText(other, "8457", (20, 230), cv2.FONT_HERSHEY_TRIPLEX, 2, (0, 0, 0), 3)
        write_image(other_path, other)
        matcher = StampMatcher([load_reference(other_path), self.reference], self.settings)
        result = scan_pdf(path, matcher, lambda: False)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.best_page, 2)
        self.assertEqual(result.match.reference, "mühür.png")
        self.assertEqual(result.status, FOUND)

    def test_plain_document_and_blank_page(self):
        path = self.root / "plain.pdf"
        make_pdf(path, pages=2)
        result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, NOT_FOUND)
        self.assertEqual(result.pages_scanned, 2)
        blank = self.matcher.match_page(np.full((500, 500, 3), 255, np.uint8))
        self.assertEqual(blank.score, 0)

    def test_first_found_stamp_skips_remaining_pages(self):
        path = self.root / "early.pdf"
        make_pdf(path, self.stamp, pages=4)
        from app.processing.pdf_renderer import render_page
        with patch("app.processing.scanner.render_page", wraps=render_page) as render:
            result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, FOUND)
        self.assertEqual(result.best_page, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.total_pages, 4)
        self.assertEqual(render.call_count, 1)

    def test_threshold_and_geometry_control_early_exit(self):
        path = self.root / "threshold.pdf"
        make_pdf(path, pages=3)
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        candidates = [MatchResult(score=90), MatchResult(score=79, polygon=polygon),
                      MatchResult(score=80, polygon=polygon)]
        with patch.object(self.matcher, "match_page", side_effect=candidates) as match:
            result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(match.call_count, 3)
        self.assertEqual(result.best_page, 3)
        self.assertEqual(result.match.score, 80)
        self.assertEqual(result.status, FOUND)

    def test_first_found_stamp_skips_remaining_references(self):
        matcher = StampMatcher([self.reference, self.reference], self.settings)
        page = np.full((600, 600, 3), 255, np.uint8)
        page[100:460, 100:460] = self.stamp
        with patch.object(matcher, "_match", wraps=matcher._match) as match:
            result = matcher.match_page(page)
        self.assertGreaterEqual(result.score, self.settings.found_threshold)
        self.assertIsNotNone(result.polygon)
        self.assertEqual(match.call_count, 1)

    def test_render_failure_keeps_scanning_other_pages(self):
        from app.processing.pdf_renderer import render_page
        path = self.root / "render_failure.pdf"
        make_pdf(path, self.stamp, pages=3, stamp_page=2)

        def render_with_failure(page, dpi):
            if page.number == 1:
                raise RuntimeError("Test render hatası")
            return render_page(page, dpi)

        with patch("app.processing.scanner.render_page", side_effect=render_with_failure):
            result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, ERROR)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.best_page, 3)
        self.assertIn("Sayfa 2", result.error_message)

    def test_bad_pdf_and_empty_references(self):
        path = self.root / "bad.pdf"
        path.write_bytes(b"This is not a PDF")
        result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, ERROR)
        self.assertTrue(result.error_message)
        result = scan_pdf(path, StampMatcher([], self.settings), lambda: False)
        self.assertEqual(result.status, ERROR)

    def test_password_protected(self):
        path = self.root / "encrypted.pdf"
        with fitz.open() as document:
            document.new_page()
            document.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        result = scan_pdf(path, self.matcher, lambda: False)
        self.assertEqual(result.status, ERROR)
        self.assertIn("şifreli", result.error_message)

    def test_no_descriptors_reference(self):
        path = self.root / "blank.png"
        write_image(path, np.full((200, 200, 3), 255, np.uint8))
        with self.assertRaises(ValueError):
            load_reference(path)

    def test_transparent_reference(self):
        rgba = cv2.cvtColor(self.stamp, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = np.where(self.stamp.min(axis=2) < 250, 255, 0)
        path = self.root / "alpha.png"
        write_image(path, rgba)
        reference = load_reference(path)
        self.assertGreater(len(reference.points), 8)

    def test_empty_folder_and_case_insensitive_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(find_pdfs(folder), [])
            nested = Path(folder) / "nested"
            nested.mkdir()
            (nested / "file.PDF").touch()
            self.assertEqual(len(find_pdfs(folder)), 1)
            self.assertEqual(len(find_pdfs(folder, False)), 0)

    def test_cancel_does_not_classify_partial_pdf(self):
        path = self.root / "cancel.pdf"
        make_pdf(path, self.stamp, pages=3, stamp_page=2)
        cancelled = [False]

        def progress(page, count):
            if page == 2:
                cancelled[0] = True

        result = scan_pdf(path, self.matcher, lambda: cancelled[0], progress)
        self.assertEqual(result.status, CANCELLED)
        self.assertLess(result.pages_scanned, result.total_pages)

    def test_geometry_guard_and_thresholds(self):
        settings = replace(self.settings, found_threshold=20, review_threshold=10)
        self.assertNotEqual(classify(40, settings, False), FOUND)
        with self.assertRaises(ValueError):
            replace(settings, review_threshold=30).validate()
        mirrored = np.float32([[300, 0], [0, 0], [0, 300], [300, 300]])
        self.assertFalse(valid_polygon(mirrored, 1000, 1000, self.reference))
        collinear = np.float32([[0, 0], [50, 0], [100, 0], [150, 0]])
        self.assertFalse(valid_polygon(collinear, 1000, 1000, self.reference))

    def test_csv_unicode_formula_and_diagnostics(self):
        path = self.root / "report.csv"
        export_csv(path, [ScanResult(str(self.root / "=mühür.pdf"), error_message="=1+1")])
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter=";"))
        self.assertTrue(rows[0]["dosya_adi"].startswith("'="))
        self.assertEqual(rows[0]["hata_mesaji"], "'=1+1")
        self.assertIn("polygon", rows[0])


if __name__ == "__main__":
    unittest.main()
