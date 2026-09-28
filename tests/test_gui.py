import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.gui.result_model import ResultModel, ResultFilter
from app.gui.result_viewer import ResultViewer
from app.models.result import FOUND, ERROR, REVIEW, MatchResult, ScanResult
from app.processing.image_preprocessor import load_reference
from app.utils.config import ScanSettings
from app.workers.scan_worker import ScanWorker
from tests.fixtures import stamp_image, write_image, make_pdf


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def pump_until(self, predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(.01)
        self.application.processEvents()
        self.assertTrue(predicate(), "Arka plan işlemi zamanında tamamlanmadı")

    def test_numeric_sort_and_review_filter(self):
        model = ResultModel()
        model.add(ScanResult("a.pdf", match=MatchResult(score=90), status=FOUND))
        model.add(ScanResult("b.pdf", match=MatchResult(score=9), status=ERROR))
        model.add(ScanResult("c.pdf", match=MatchResult(score=60), status=REVIEW))
        proxy = ResultFilter()
        proxy.setSourceModel(model)
        proxy.sort(4, Qt.AscendingOrder)
        self.assertEqual(proxy.index(0, 4).data(Qt.UserRole), 9)
        proxy.review_only = True
        proxy.invalidate()
        self.assertEqual(proxy.rowCount(), 2)

    def test_window_and_empty_input(self):
        window = MainWindow()
        messages = []
        window.notify = messages.append
        window.start_scan()
        self.assertIn("referans", messages[0])
        window.show()
        self.application.processEvents()
        self.assertTrue(window.isVisible())
        window.close()

    def test_window_scan_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "muhur.png"
            write_image(path, stamp_image())
            make_pdf(root / "document.pdf", stamp_image(), pages=2, stamp_page=1)
            window = MainWindow()
            messages = []
            window.notify = messages.append
            window.reference_loaded(load_reference(path))
            window.folder.setText(folder)
            window.dpi.setCurrentText("150")
            window.start.click()
            self.assertFalse(window.start.isEnabled())
            self.pump_until(lambda: window.worker is None)
            self.assertEqual(messages, [])
            self.assertTrue(window.start.isEnabled())
            self.assertEqual(window.model.rowCount(), 1)
            self.assertEqual(window.model.results[0].best_page, 2)
            window.table.selectRow(0)
            self.assertEqual(window.selected_result().status, FOUND)
            window.only_review.setChecked(True)
            self.assertEqual(window.proxy.rowCount(), 0)
            window.close()

    def test_parallel_scan_preview_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference_path = root / "reference.png"
            write_image(reference_path, stamp_image())
            reference = load_reference(reference_path)
            make_pdf(root / "a.pdf", stamp_image())
            make_pdf(root / "b.pdf")
            (root / "broken.pdf").write_bytes(b"broken")
            worker = ScanWorker(folder, False, [reference], ScanSettings(dpi=150, workers=2))
            results, failures = [], []
            worker.result_ready.connect(results.append)
            worker.failed.connect(failures.append)
            worker.start()
            self.pump_until(lambda: not worker.isRunning())
            self.assertEqual(failures, [])
            self.assertEqual(len(results), 3)
            self.assertEqual(sum(result.status == ERROR for result in results), 1)
            found = next(result for result in results if result.status == FOUND)
            viewer = ResultViewer(found, 150)
            viewer.show()
            self.pump_until(lambda: viewer.loader is not None and not viewer.loader.isRunning())
            self.assertEqual(len(viewer.scene.items()), 1)
            viewer.close()
            cancelled = ScanWorker(folder, False, [reference], ScanSettings(dpi=150, workers=2))
            completion = []
            cancelled.completed.connect(lambda *args: completion.append(args))
            cancelled.cancel()
            cancelled.start()
            self.pump_until(lambda: not cancelled.isRunning())
            self.assertEqual(completion[0], (True, 0, 3))


if __name__ == "__main__":
    unittest.main()
