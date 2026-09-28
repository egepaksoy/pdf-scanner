from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import logging
import multiprocessing
import threading

import cv2
from PySide6.QtCore import QThread, Signal

from app.models.reference_stamp import ReferenceStamp
from app.models.result import ERROR, ScanResult
from app.processing.image_preprocessor import load_reference
from app.processing.scanner import find_pdfs, scan_pdf
from app.processing.stamp_matcher import StampMatcher
from app.utils.config import ScanSettings

_process_matcher = None
_process_cancel = None


def _initialize_process(references, settings, cancel_event):
    global _process_matcher, _process_cancel
    cv2.setNumThreads(1)
    _process_matcher = StampMatcher(references, settings)
    _process_cancel = cancel_event


def _scan_in_process(path: str) -> ScanResult:
    return scan_pdf(path, _process_matcher, _process_cancel.is_set)


class ReferenceLoader(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self):
        cv2.setNumThreads(1)
        for path in self.paths:
            if self.isInterruptionRequested():
                break
            try:
                reference = load_reference(path)
                self.loaded.emit(reference)
                logging.info("Referans eklendi: %s (%d özellik)", path, len(reference.points))
            except Exception as exc:
                logging.exception("Referans yüklenemedi: %s", path)
                self.failed.emit(f"{path}\n{exc}")


class ScanWorker(QThread):
    result_ready = Signal(object)
    progress = Signal(int, int, str)
    page_progress = Signal(str)
    failed = Signal(str)
    completed = Signal(bool, int, int)

    def __init__(self, folder: str, recursive: bool, references: list[ReferenceStamp],
                 settings: ScanSettings, parent=None):
        super().__init__(parent)
        self.folder, self.recursive = folder, recursive
        self.references, self.settings = references[:], settings
        self.cancel_event = threading.Event()
        self.process_cancel = None

    def cancel(self):
        self.cancel_event.set()
        if self.process_cancel is not None:
            self.process_cancel.set()

    def run(self):
        done, total = 0, 0
        try:
            self.settings.validate()
            if not self.references:
                raise ValueError("En az bir geçerli referans mühür ekleyin.")
            self.progress.emit(0, 0, "PDF dosyaları bulunuyor…")
            paths = find_pdfs(self.folder, self.recursive)
            total = len(paths)
            if not paths:
                raise ValueError("Seçilen klasörde PDF dosyası bulunamadı.")
            logging.info("Tarama başladı: %d PDF, DPI=%d, işlem=%d", total,
                         self.settings.dpi, self.settings.process_count)
            if self.settings.process_count == 1:
                cv2.setNumThreads(1)
                matcher = StampMatcher(self.references, self.settings)
                for path in paths:
                    if self.cancel_event.is_set():
                        break
                    self.progress.emit(done, total, str(path))
                    result = scan_pdf(path, matcher, self.cancel_event.is_set,
                                      lambda page, count: self.page_progress.emit(f"Sayfa {page} / {count}"))
                    self.result_ready.emit(result)
                    done += 1
                    self.progress.emit(done, total, str(path))
            else:
                context = multiprocessing.get_context("spawn")
                self.process_cancel = context.Event()
                if self.cancel_event.is_set():
                    self.process_cancel.set()
                with ProcessPoolExecutor(max_workers=self.settings.process_count, mp_context=context,
                                         initializer=_initialize_process,
                                         initargs=(self.references, self.settings, self.process_cancel)) as pool:
                    pending = {}
                    iterator = iter(paths)

                    def submit_next():
                        if self.cancel_event.is_set():
                            return
                        path = next(iterator, None)
                        if path is not None:
                            pending[pool.submit(_scan_in_process, str(path))] = path

                    for _ in range(min(total, self.settings.process_count)):
                        submit_next()
                    while pending:
                        self.progress.emit(done, total, " | ".join(path.name for path in pending.values()))
                        ready, _ = wait(pending, timeout=0.15, return_when=FIRST_COMPLETED)
                        if self.cancel_event.is_set():
                            self.process_cancel.set()
                        for future in ready:
                            path = pending.pop(future)
                            try:
                                result = future.result()
                            except Exception as exc:
                                result = ScanResult(str(path), status=ERROR, error_message=str(exc))
                            logging.info("PDF: %s | %s | %.2fs | %s", path, result.status,
                                         result.processing_time, result.error_message)
                            self.result_ready.emit(result)
                            done += 1
                            submit_next()
                    self.progress.emit(done, total, "")
        except Exception as exc:
            logging.exception("Tarama hatası")
            self.failed.emit(str(exc))
        finally:
            logging.info("Tarama sona erdi: %d/%d, iptal=%s", done, total, self.cancel_event.is_set())
            self.completed.emit(self.cancel_event.is_set(), done, total)
