import csv
import json
from pathlib import Path

from app.models.result import ScanResult


def spreadsheet_safe(value: str) -> str:
    # Prevent file names and error text from becoming spreadsheet formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_csv(path: str | Path, results: list[ScanResult]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["dosya_adi", "dosya_yolu", "sayfa", "referans", "skor", "durum",
                         "sure_saniye", "good_matches", "inlier_count", "inlier_ratio",
                         "bounding_box", "polygon", "goruntu_boyutu", "taranan_sayfa",
                         "toplam_sayfa", "hata_mesaji"])
        for result in results:
            match = result.match
            writer.writerow([spreadsheet_safe(result.file_name), spreadsheet_safe(result.file_path),
                             result.best_page or "", spreadsheet_safe(match.reference), match.score,
                             result.status, result.processing_time, match.good_matches, match.inlier_count,
                             round(match.inlier_ratio, 4), json.dumps(result.bounding_box),
                             json.dumps(match.polygon), json.dumps(match.image_size),
                             result.pages_scanned, result.total_pages, spreadsheet_safe(result.error_message)])
