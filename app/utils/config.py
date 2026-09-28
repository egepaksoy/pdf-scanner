from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ScanSettings:
    found_threshold: float = 80.0
    review_threshold: float = 50.0
    dpi: int = 200
    lowe_ratio: float = 0.70
    ransac_threshold: float = 5.0
    workers: int = 1
    color_prefilter: str = "off"

    def validate(self) -> None:
        if not 0 < self.review_threshold < self.found_threshold <= 100:
            raise ValueError("Eşikler 0 < manuel kontrol < mühür bulundu ≤ 100 olmalıdır.")
        if self.dpi not in (150, 200, 250, 300):
            raise ValueError("Geçersiz DPI değeri.")
        if not 0.4 <= self.lowe_ratio <= 0.9 or not 1 <= self.ransac_threshold <= 15:
            raise ValueError("Eşleşme parametreleri izin verilen aralığın dışında.")
        if self.workers not in (0, 1, 2, 4, 8):
            raise ValueError("Geçersiz işlem sayısı.")
        if self.color_prefilter not in ("off", "red", "blue"):
            raise ValueError("Geçersiz renk filtresi.")

    @property
    def process_count(self) -> int:
        return self.workers or min(2, max(1, (os.cpu_count() or 2) // 2))
