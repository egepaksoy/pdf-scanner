import cv2
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QUrl
from PySide6.QtGui import QImage, QPixmap, QPainter, QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QGraphicsView, QGraphicsScene, QSpinBox)

from app.models.result import ScanResult
from app.processing.pdf_renderer import render_page, open_document, PDF_LOCK
from app.gui.result_model import COLORS


class PageLoader(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, result, page, dpi, parent=None):
        super().__init__(parent)
        self.result, self.page, self.dpi = result, page, dpi

    def run(self):
        try:
            with open_document(self.result.file_path) as document:
                with PDF_LOCK:
                    if document.needs_pass:
                        raise ValueError("Bu PDF şifreli.")
                    image = render_page(document[self.page - 1], self.dpi)
            match = self.result.match
            if self.page == self.result.best_page and match.polygon:
                import numpy as np
                scale = np.array([image.shape[1] / match.image_size[0],
                                  image.shape[0] / match.image_size[1]])
                polygon = np.int32(np.array(match.polygon) * scale)
                color = COLORS[self.result.status].lstrip("#")
                rgb = tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))
                cv2.polylines(image, [polygon], True, rgb[::-1], max(3, image.shape[1] // 450))
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            self.loaded.emit(QImage(image.data, image.shape[1], image.shape[0],
                                    image.strides[0], QImage.Format_RGB888).copy())
        except Exception as exc:
            self.failed.emit(str(exc))


class ZoomView(QGraphicsView):
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
        else:
            super().wheelEvent(event)

    def zoom(self, factor):
        if 0.025 <= self.transform().m11() * factor <= 10:
            self.scale(factor, factor)


class ResultViewer(QDialog):
    def __init__(self, result: ScanResult, dpi: int, parent=None):
        super().__init__(parent)
        self.result, self.dpi = result, dpi
        self.loader = None
        self.setWindowTitle(f"İncele — {result.file_name}")
        self.resize(1000, 850)
        layout = QVBoxLayout(self)
        title = QLabel(f"{result.file_name}\n{result.status}  •  Skor: {result.match.score:.1f} / 100"
                       f"  •  Referans: {result.match.reference or '—'}")
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        layout.addWidget(title)
        evidence = QLabel(f"Eşleşmeler: {result.match.good_matches}  •  Geometrik uyumlu: {result.match.inlier_count}"
                          f"  •  Inlier oranı: {result.match.inlier_ratio:.2f}"
                          f"  •  Taranan sayfa: {result.pages_scanned}/{result.total_pages}")
        layout.addWidget(evidence)
        if result.error_message:
            error = QLabel(result.error_message)
            error.setTextFormat(Qt.PlainText)
            error.setWordWrap(True)
            layout.addWidget(error)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("Sayfa:"))
        self.page = QSpinBox()
        self.page.setRange(1, max(1, result.total_pages))
        self.page.setValue(result.best_page or 1)
        self.page.valueChanged.connect(self.load_page)
        tools.addWidget(self.page)
        for text, callback in [("−", lambda: self.view.zoom(1 / 1.25)),
                               ("+", lambda: self.view.zoom(1.25)),
                               ("Sayfaya sığdır", self.fit), ("PDF’yi aç", self.open_pdf)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            tools.addWidget(button)
        tools.addStretch()
        tools.addWidget(QLabel("Yakınlaştır: Ctrl + fare tekerleği"))
        layout.addLayout(tools)
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        layout.addWidget(self.message)
        self.scene = QGraphicsScene(self)
        self.view = ZoomView(self.scene)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        layout.addWidget(self.view)
        QTimer.singleShot(0, self.load_page)

    def open_pdf(self):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.result.file_path)):
            self.message.setText("PDF açılamadı. Varsayılan PDF okuyucunuzu kontrol edin.")

    def fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def load_page(self):
        if self.loader is not None and self.loader.isRunning():
            return
        if self.loader is not None:
            self.loader.deleteLater()
        self.page.setEnabled(False)
        self.message.setText("Sayfa yükleniyor…")
        self.loader = PageLoader(self.result, self.page.value(), self.dpi, self)
        self.loader.loaded.connect(self.show_image)
        self.loader.failed.connect(self.show_error)
        self.loader.finished.connect(lambda: self.page.setEnabled(True))
        self.loader.start()

    def show_error(self, message):
        self.scene.clear()
        self.message.setText(f"Sayfa gösterilemedi: {message}")

    def show_image(self, image):
        self.scene.clear()
        item = self.scene.addPixmap(QPixmap.fromImage(image))
        self.scene.setSceneRect(item.boundingRect())
        self.fit()
        self.message.setText("Doğrulanan mühür bölgesi çerçeveyle gösterilir. Skor bir olasılık değildir.")

    def reject(self):
        if self.loader and self.loader.isRunning():
            self.message.setText("Sayfanın yüklenmesi bitince pencereyi kapatabilirsiniz.")
            return
        super().reject()

    def closeEvent(self, event):
        if self.loader and self.loader.isRunning():
            event.ignore()
        else:
            event.accept()
