from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class ReferenceStamp:
    path: str
    width: int
    height: int
    points: np.ndarray
    descriptors: np.ndarray

    @property
    def name(self) -> str:
        return Path(self.path).name
