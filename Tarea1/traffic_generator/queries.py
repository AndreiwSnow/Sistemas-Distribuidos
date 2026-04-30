from dataclasses import dataclass, field
from typing import List

ZONE_IDS: List[str] = ["Z1", "Z2", "Z3", "Z4", "Z5"]


ZONE_PAIRS: List[tuple] = [
    ("Z1", "Z2"), ("Z1", "Z3"), ("Z1", "Z4"), ("Z1", "Z5"),
    ("Z2", "Z3"), ("Z2", "Z4"), ("Z2", "Z5"),
    ("Z3", "Z4"), ("Z3", "Z5"),
    ("Z4", "Z5"),
]

CONFIDENCE_LEVELS: List[float] = [0.0, 0.5, 0.7, 0.9]
BINS_OPTIONS: List[int] = [5, 10]


QUERY_TYPE_WEIGHTS = {"Q1": 0.40, "Q2": 0.20, "Q3": 0.20, "Q4": 0.10, "Q5": 0.10}


@dataclass
class Query:
    query_type: str
    zone_id: str
    confidence_min: float = 0.0
    zone_id_b: str = ""
    bins: int = 5

    def to_dict(self) -> dict:
        return {
            "query_type": self.query_type,
            "zone_id": self.zone_id,
            "confidence_min": self.confidence_min,
            "zone_id_b": self.zone_id_b,
            "bins": self.bins,
        }
