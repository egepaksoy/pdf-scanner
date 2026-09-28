from pathlib import Path

from PySide6.QtCore import Qt, QSize, QSettings, QUrl, QTimer
from PySide6.QtGui import QIcon, QDesktopServices, QImageReader, QCloseEvent
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QPushButton, QLabel, QListWidget, QListWidgetItem, QLineEdit,
                               QFileDialog, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                               QFormLayout, QProgressBar, QTableView, QHeaderView,
                               QAbstractItemView, QMessageBox, QSplitter)

from app.gui.result_model import ResultModel, ResultFilter
from app.gui.result_viewer import ResultViewer
from app.models.result import FOUND, REVIEW, NOT_FOUND, ERROR, CANCELLED
from app.utils.config import ScanSettings
from app.utils.report import export_csv
from app.workers.scan_worker import ReferenceLoader, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.references = []
        self.worker = None
        self.reference_loader = None
        self.reference_errors = []
        self.last_settings = ScanSettings()
        self.closing = False
        self.preferences = QSettings()
        self.setWindowTitle("Mühür Kontrol")
        self.resize(1380, 900)
        self.setMinimumSize(1020, 680)
        self.setStyleSheet("""
            QMainWindow, QDialog { background: #f3f6fa; }
            QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #182b43; }
            QGroupBox { font-weight: 600; border: 1px solid #d7e0eb; border-radius: 8px;
                        margin-top: 12px; padding: 12px 8px 8px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QPushButton { padding: 7px 12px; border: 1px solid #c9d5e3; border-radius: 5px; background: white; }
            QPushButton:hover { background: #e7effb; }
            QPushButton:disabled { color: #9aa7b5; background: #eff2f6; }
            QPushButton#primary { background: #205fbc; color: white; font-weight: 600; }
            QPushButton#primary:disabled { background: #9bb3d5; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 5px; background: white;
                        border: 1px solid #ccd6e2; border-radius: 4px; }
            QTableView, QListWidget { background: white; alternate-background-color: #f5f8fc;
                        border: 1px solid #dae2ed; selection-background-color: #dbeafe; selection-color: #182b43; }
            QHeaderView::section { background: #eaf0f7; padding: 8px; border: none; font-weight: 600; }
            QProgressBar { border: 1px solid #d5dfec; border-radius: 5px; text-align: center; min-height: 22px; }
            QProgressBar::chunk { background: #4285d4; border-radius: 4px; }
        """)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        heading = QLabel("MÜHÜR KONTROL")
        heading.setStyleSheet("font-size: 23pt; font-weight: 700; padding: 5px;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("PDF belgelerinizde referans mühürleri arayın. Tüm işlemler bilgisayarınızda yapılır."))
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)
        self.controls = QWidget()
        controls = QVBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 8, 0)
        refs = QGroupBox("1  Referans mühürler")
        refs_layout = QVBoxLayout(refs)
        self.ref_list = QListWidget()
        self.ref_list.setIconSize(QSize(76, 76))
        self.ref_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ref_list.setMinimumHeight(150)
        refs_layout.addWidget(self.ref_list)
        ref_buttons = QHBoxLayout()
        for text, callback in [("+ Ekle", self.add_references), ("Seçileni sil", self.remove_references),
                               ("Temizle", self.clear_references)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            ref_buttons.addWidget(button)
        refs_layout.addLayout(ref_buttons)
        controls.addWidget(refs, 1)
        folder_group = QGroupBox("2  PDF klasörü")
        folder_layout = QVBoxLayout(folder_group)
        self.folder = QLineEdit(str(self.preferences.value("folder", "")))
        self.folder.setPlaceholderText("PDF belgelerinin bulunduğu klasör")
        folder_layout.addWidget(self.folder)
        choose = QPushButton("Klasör seç")
        choose.clicked.connect(self.choose_folder)
        folder_layout.addWidget(choose)
        self.recursive = QCheckBox("Alt klasörleri de tara")
        self.recursive.setChecked(True)
        folder_layout.addWidget(self.recursive)
        controls.addWidget(folder_group)
        settings_group = QGroupBox("3  Tarama ayarları")
        settings_layout = QFormLayout(settings_group)
        self.found = QSpinBox()
        self.found.setRange(1, 100)
        self.found.setValue(80)
        self.review = QSpinBox()
        self.review.setRange(1, 99)
        self.review.setValue(50)
        self.dpi = QComboBox()
        self.dpi.addItems(["150", "200", "250", "300"])
        self.dpi.setCurrentText("200")
        settings_layout.addRow("Mühür bulundu eşiği", self.found)
        settings_layout.addRow("Manuel kontrol eşiği", self.review)
        settings_layout.addRow("Görüntü kalitesi (DPI)", self.dpi)
        advanced_button = QPushButton("Gelişmiş ayarlar ▾")
        settings_layout.addRow(advanced_button)
        self.advanced = QWidget()
        advanced_layout = QFormLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(0.4, 0.9)
        self.ratio.setSingleStep(0.05)
        self.ratio.setValue(0.7)
        self.ransac = QDoubleSpinBox()
        self.ransac.setRange(1, 15)
        self.ransac.setValue(5)
        self.processes = QComboBox()
        for label, value in [("1 (önerilen)", 1), ("2", 2), ("4", 4), ("8", 8), ("Otomatik (en çok 2)", 0)]:
            self.processes.addItem(label, value)
        self.color = QComboBox()
        for label, value in [("Kapalı", "off"), ("Kırmızı mühür", "red"), ("Mavi mühür", "blue")]:
            self.color.addItem(label, value)
        advanced_layout.addRow("Lowe oranı", self.ratio)
        advanced_layout.addRow("RANSAC toleransı (px)", self.ransac)
        advanced_layout.addRow("Paralel işlem", self.processes)
        advanced_layout.addRow("Renk ön filtresi", self.color)
        settings_layout.addRow(self.advanced)
        self.advanced.hide()
        advanced_button.clicked.connect(lambda: self.advanced.setVisible(not self.advanced.isVisible()))
        controls.addWidget(settings_group)
        splitter.addWidget(self.controls)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        actions = QHBoxLayout()
        self.start = QPushButton("Taramayı başlat")
        self.start.setObjectName("primary")
        self.start.clicked.connect(self.start_scan)
        self.stop = QPushButton("Taramayı durdur")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.stop_scan)
        actions.addWidget(self.start)
        actions.addWidget(self.stop)
        right_layout.addLayout(actions)
        self.progress = QProgressBar()
        right_layout.addWidget(self.progress)
        self.current = QLabel("Referans mühür ekleyin ve PDF klasörünü seçin.")
        self.current.setTextFormat(Qt.PlainText)
        self.current.setWordWrap(True)
        right_layout.addWidget(self.current)
        self.page_status = QLabel("")
        right_layout.addWidget(self.page_status)
        filters = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tümü", FOUND, REVIEW, NOT_FOUND, ERROR, CANCELLED])
        self.filter_combo.currentTextChanged.connect(self.update_filter)
        self.only_review = QCheckBox("Sadece kontrol gerekenler")
        self.only_review.toggled.connect(self.update_filter)
        filters.addWidget(self.filter_combo)
        filters.addWidget(self.only_review)
        low_first = QPushButton("En düşük skor önce")
        low_first.clicked.connect(lambda: self.table.sortByColumn(4, Qt.AscendingOrder))
        filters.addWidget(low_first)
        right_layout.addLayout(filters)
        self.model = ResultModel(self)
        self.proxy = ResultFilter(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(4, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for index, width in enumerate([185, 220, 58, 160, 135, 160, 90]):
            self.table.setColumnWidth(index, width)
        self.table.doubleClicked.connect(self.inspect_result)
        right_layout.addWidget(self.table, 1)
        self.summary = QLabel("Henüz sonuç yok.")
        right_layout.addWidget(self.summary)
        result_actions = QHBoxLayout()
        for label, callback in [("İncele", self.inspect_result), ("PDF’yi aç", self.open_pdf),
                                ("CSV dışarı aktar", self.save_csv)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            result_actions.addWidget(button)
        right_layout.addLayout(result_actions)
        note = QLabel("Eşiğe ulaşan ilk doğrulanmış mühürde sonraki PDF’ye geçilir. "
                      "Benzerlik skoru istatistiksel olasılık değildir.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #596c83; padding: 5px;")
        right_layout.addWidget(note)
        splitter.addWidget(right)
        splitter.setSizes([350, 1000])
        self.statusBar().showMessage("Hazır • Yerel çalışma")

    def notify(self, message):
        QMessageBox.information(self, "Mühür Kontrol", message)

    def add_references(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Referans mühür ekle", "",
                                                "Görseller (*.png *.jpg *.jpeg *.bmp)")
        existing = {reference.path.casefold() for reference in self.references}
        paths = list(dict.fromkeys(str(Path(path).resolve()) for path in paths))
        paths = [path for path in paths if path.casefold() not in existing]
        if not paths:
            return
        self.reference_errors = []
        self.controls.setEnabled(False)
        self.start.setEnabled(False)
        self.statusBar().showMessage("Referans özellikleri hazırlanıyor…")
        self.reference_loader = ReferenceLoader(paths, self)
        self.reference_loader.loaded.connect(self.reference_loaded)
        self.reference_loader.failed.connect(self.reference_errors.append)
        self.reference_loader.finished.connect(self.references_finished)
        self.reference_loader.start()

    def reference_loaded(self, reference):
        self.references.append(reference)
        reader = QImageReader(reference.path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(76, 76, Qt.KeepAspectRatio))
        from PySide6.QtGui import QPixmap
        item = QListWidgetItem(QIcon(QPixmap.fromImage(reader.read())),
                               f"{reference.name}\n{len(reference.points)} özellik")
        item.setToolTip(reference.path)
        self.ref_list.addItem(item)

    def references_finished(self):
        self.reference_loader.deleteLater()
        self.reference_loader = None
        self.controls.setEnabled(True)
        self.start.setEnabled(True)
        self.statusBar().showMessage(f"{len(self.references)} referans hazır")
        if self.reference_errors and not self.closing:
            self.notify("Bazı referanslar yüklenemedi:\n\n" + "\n\n".join(self.reference_errors))
        if self.closing:
            QTimer.singleShot(0, self.close)

    def remove_references(self):
        for row in sorted((self.ref_list.row(item) for item in self.ref_list.selectedItems()), reverse=True):
            self.ref_list.takeItem(row)
            self.references.pop(row)

    def clear_references(self):
        self.references.clear()
        self.ref_list.clear()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "PDF klasörünü seç", self.folder.text())
        if path:
            self.folder.setText(path)
            self.preferences.setValue("folder", path)

    def read_settings(self):
        settings = ScanSettings(self.found.value(), self.review.value(), int(self.dpi.currentText()),
                                self.ratio.value(), self.ransac.value(), self.processes.currentData(),
                                self.color.currentData())
        settings.validate()
        return settings

    def start_scan(self):
        if not self.references:
            self.notify("En az bir geçerli referans mühür ekleyin.")
            return
        if not Path(self.folder.text()).is_dir() or not self.folder.text().strip():
            self.notify("Geçerli bir PDF klasörü seçin.")
            return
        try:
            settings = self.read_settings()
        except ValueError as exc:
            self.notify(str(exc))
            return
        if self.model.results and QMessageBox.question(
                self, "Yeni tarama", "Mevcut sonuçlar yeni taramayla değiştirilecek. Devam edilsin mi?"
                "\nSaklamak istiyorsanız önce CSV olarak dışarı aktarın.") != QMessageBox.Yes:
            return
        self.last_settings = settings
        self.model.clear()
        self.update_summary()
        self.page_status.clear()
        self.controls.setEnabled(False)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.worker = ScanWorker(self.folder.text(), self.recursive.isChecked(), self.references, settings, self)
        self.worker.result_ready.connect(self.add_result)
        self.worker.progress.connect(self.show_progress)
        self.worker.page_progress.connect(self.page_status.setText)
        self.worker.failed.connect(self.notify)
        self.worker.completed.connect(self.scan_completed)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def stop_scan(self):
        if self.worker:
            self.worker.cancel()
            self.stop.setEnabled(False)
            self.current.setText("Durduruluyor… Devam eden görüntü işleminin bitmesi bekleniyor.")

    def show_progress(self, done, total, current):
        self.progress.setRange(0, total if total else 0)
        self.progress.setValue(done)
        self.progress.setFormat(f"{done} / {total} PDF  •  %p%" if total else "PDF dosyaları bulunuyor…")
        if not self.worker.cancel_event.is_set():
            self.current.setText(current)

    def add_result(self, result):
        self.model.add(result)
        self.update_summary()

    def scan_completed(self, cancelled, done, total):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.progress.setFormat(f"{done} / {total} PDF  •  %p%")
        self.current.setText(f"{'Tarama durduruldu' if cancelled else 'Tarama sona erdi'}: {done} / {total} PDF.")
        self.page_status.clear()

    def worker_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.controls.setEnabled(True)
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.statusBar().showMessage("Hazır • Sonuçlar bellekte; CSV olarak kaydedebilirsiniz.")
        if self.closing:
            QTimer.singleShot(0, self.close)

    def update_filter(self):
        self.proxy.status = self.filter_combo.currentText()
        self.proxy.review_only = self.only_review.isChecked()
        self.proxy.invalidate()
        self.update_summary()

    def update_summary(self):
        total = len(self.model.results)
        found = sum(result.status == FOUND for result in self.model.results)
        self.summary.setText(f"{total} belge  •  {found} mühür bulundu  •  {total - found} kontrol gerekiyor"
                             f"  •  {self.proxy.rowCount()} gösteriliyor")

    def selected_result(self):
        index = self.table.currentIndex()
        if not index.isValid():
            self.notify("Önce tablodan bir sonuç seçin.")
            return None
        return self.model.results[self.proxy.mapToSource(index).row()]

    def inspect_result(self):
        result = self.selected_result()
        if result:
            viewer = ResultViewer(result, self.last_settings.dpi, self)
            viewer.exec()
            viewer.deleteLater()

    def open_pdf(self):
        result = self.selected_result()
        if result and not QDesktopServices.openUrl(QUrl.fromLocalFile(result.file_path)):
            self.notify("PDF açılamadı. Varsayılan PDF okuyucunuzu kontrol edin.")

    def save_csv(self):
        if not self.model.results:
            self.notify("Dışarı aktarılacak sonuç yok.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Tüm sonuçları CSV olarak kaydet", "muhur_raporu.csv", "CSV (*.csv)")
        if path:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                export_csv(path, self.model.results)
                self.statusBar().showMessage(f"Tüm {len(self.model.results)} sonuç kaydedildi: {path}")
            except OSError as exc:
                self.notify(f"Rapor kaydedilemedi: {exc}")

    def closeEvent(self, event: QCloseEvent):
        scanning = self.worker is not None and self.worker.isRunning()
        loading = self.reference_loader is not None and self.reference_loader.isRunning()
        if scanning or loading:
            self.closing = True
            self.stop_scan()
            if loading:
                self.reference_loader.requestInterruption()
            self.statusBar().showMessage("İşlem güvenli biçimde durduktan sonra uygulama kapanacak…")
            event.ignore()
        else:
            event.accept()
