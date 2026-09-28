from dataclasses import dataclass, field
from pathlib import Path

FOUND = "Mühür bulundu"
REVIEW = "Manuel kontrol"
NOT_FOUND = "Mühür bulunamadı"
ERROR = "İşleme hatası"
CANCELLED = "İptal edildi"


@dataclass
class MatchResult:
    reference: str = ""
    score: float = 0.0
    good_matches: int = 0
    inlier_count: int = 0
    inlier_ratio: float = 0.0
    polygon: list[list[float]] | None = None
    image_size: tuple[int, int] = (0, 0)


@dataclass
class ScanResult:
    file_path: str
    best_page: int | None = None
    match: MatchResult = field(default_factory=MatchResult)
    status: str = NOT_FOUND
    processing_time: float = 0.0
    error_message: str = ""
    pages_scanned: int = 0
    total_pages: int = 0

    @property
    def file_name(self) -> str:
        return Path(self.file_path).name

    @property
    def bounding_box(self) -> list[float] | None:
        if not self.match.polygon:
            return None
        x, y = zip(*self.match.polygon)
        return [min(x), min(y), max(x), max(y)]
