from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel
from PySide6.QtGui import QColor

from app.models.result import FOUND, REVIEW, NOT_FOUND, ERROR, CANCELLED, ScanResult

COLORS = {FOUND: "#16834a", REVIEW: "#a36800", NOT_FOUND: "#bc3d40",
          ERROR: "#bc3d40", CANCELLED: "#64748b"}


class ResultModel(QAbstractTableModel):
    headers = ["Dosya adı", "Tam dosya yolu", "Sayfa", "Eşleşen referans",
               "Benzerlik skoru", "Durum", "Süre (sn)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results: list[ScanResult] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.results)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        result = self.results[index.row()]
        values = [result.file_name, result.file_path, result.best_page or 0,
                  result.match.reference, result.match.score, result.status, result.processing_time]
        if role == Qt.UserRole:
            return values[index.column()]
        if role == Qt.DisplayRole:
            if index.column() == 2:
                return result.best_page or "—"
            if index.column() == 4:
                return f"{result.match.score:.1f} / 100"
            if index.column() == 6:
                return f"{result.processing_time:.2f}"
            return values[index.column()] or "—"
        if role == Qt.ForegroundRole and index.column() in (4, 5):
            return QColor(COLORS[result.status])
        if role == Qt.ToolTipRole:
            return result.error_message or result.file_path
        return None

    def add(self, result: ScanResult):
        row = len(self.results)
        self.beginInsertRows(QModelIndex(), row, row)
        self.results.append(result)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self.results.clear()
        self.endResetModel()


class ResultFilter(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = "Tümü"
        self.review_only = False
        self.setSortRole(Qt.UserRole)

    def filterAcceptsRow(self, row, parent):
        result = self.sourceModel().results[row]
        if self.review_only and result.status == FOUND:
            return False
        return self.status == "Tümü" or result.status == self.status
