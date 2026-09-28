import logging
from pathlib import Path
import time
from typing import Callable

from app.models.result import CANCELLED, ERROR, FOUND, ScanResult
from app.processing.pdf_renderer import render_page, open_document, PDF_LOCK
from app.processing.scoring import classify
from app.processing.stamp_matcher import StampMatcher

logger = logging.getLogger(__name__)


def find_pdfs(folder: str, recursive: bool = True) -> list[Path]:
    root = Path(folder)
    if not root.is_dir():
        raise ValueError("Geçerli bir PDF klasörü seçin.")
    paths = root.rglob("*") if recursive else root.iterdir()
    return sorted((path.resolve() for path in paths if path.is_file() and path.suffix.lower() == ".pdf"),
                  key=lambda path: str(path).casefold())


def scan_pdf(path: str | Path, matcher: StampMatcher, cancelled: Callable[[], bool],
             progress: Callable[[int, int], None] | None = None) -> ScanResult:
    started = time.perf_counter()
    result = ScanResult(str(Path(path).resolve()))
    errors = []
    try:
        if not matcher.references:
            raise ValueError("Referans listesi boş.")
        matcher.settings.validate()
        with open_document(path) as document:
            with PDF_LOCK:
                if document.needs_pass:
                    raise ValueError("PDF şifreli; önce şifresiz bir kopyasını kaydedin.")
                result.total_pages = len(document)
            if not result.total_pages:
                raise ValueError("PDF içinde sayfa bulunamadı.")
            for index in range(result.total_pages):
                if cancelled():
                    result.status = CANCELLED
                    break
                if progress:
                    progress(index + 1, result.total_pages)
                try:
                    with PDF_LOCK:
                        image = render_page(document[index], matcher.settings.dpi)
                    match = matcher.match_page(image, cancelled)
                    del image
                    if cancelled():
                        result.status = CANCELLED
                        break
                    result.pages_scanned += 1
                    if classify(match.score, matcher.settings, match.polygon is not None) == FOUND:
                        result.match, result.best_page = match, index + 1
                        logger.info("Eşik sağlandı; PDF taraması erken tamamlandı: %s, sayfa %d/%d",
                                    path, index + 1, result.total_pages)
                        break
                    if match.score > result.match.score:
                        result.match, result.best_page = match, index + 1
                except Exception as exc:
                    errors.append(f"Sayfa {index + 1}: {exc}")
                    logger.exception("PDF sayfa hatası: %s, sayfa %d", path, index + 1)
            if result.status != CANCELLED:
                result.status = ERROR if errors else classify(result.match.score, matcher.settings,
                                                              result.match.polygon is not None)
            result.error_message = "\n".join(errors)
    except Exception as exc:
        result.status, result.error_message = ERROR, str(exc)
        logger.exception("PDF işlenemedi: %s", path)
    result.processing_time = round(time.perf_counter() - started, 3)
    logger.info("PDF: %s | %s | skor %.1f | %.2fs", path, result.status,
                result.match.score, result.processing_time)
    return result
