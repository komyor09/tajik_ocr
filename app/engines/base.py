from dataclasses import dataclass
from typing import Protocol

import numpy as np

# Letters Tajik adds to the Russian Cyrillic alphabet
TAJIK_EXTRA_LETTERS = "ҒғӢӣҚқӮӯҲҳҶҷ"


@dataclass
class Line:
    text: str
    score: float  # 0..1
    box: list[list[int]]  # 4 points [x, y], clockwise from top-left


class OcrEngine(Protocol):
    name: str

    def recognize(self, image_bgr: np.ndarray) -> list[Line]: ...

    def info(self) -> dict: ...
