from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class QualityReport:
    """Data quality checks shared by all connectors."""

    observation_count: int = 0
    missing_periods: List[str] = field(default_factory=list)
    missing_period_count: int = 0
    duplicate_records: int = 0
    outlier_count: int = 0
    unit_consistent: bool = False
    traceable_source: bool = False
    checked_at: str = ""
    passed: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
