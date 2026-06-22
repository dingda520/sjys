from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .lineage import DataLineage
from .metadata import SeriesMetadata
from .observation import Observation
from .quality import QualityReport


@dataclass
class QueryRequest:
    """Normalized query parameters."""

    country: str
    indicator_code: str
    start_date: str
    end_date: str
    frequency: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ErrorInfo:
    """Structured error object used instead of opaque failures."""

    code: str
    message: str
    detail: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StandardResponse:
    """Unified API response schema shared by all data sources."""

    request: QueryRequest
    metadata: Optional[SeriesMetadata] = None
    observations: List[Observation] = field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    lineage: Optional[DataLineage] = None
    error: Optional[ErrorInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "observations": [item.to_dict() for item in self.observations],
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "lineage": self.lineage.to_dict() if self.lineage else None,
            "error": self.error.to_dict() if self.error else None,
        }
