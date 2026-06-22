from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Observation:
    """One standardized time-series observation."""

    date: str
    value: Optional[float]
    unit: str = ""
    status: str = "final"
    release_date: Optional[str] = None
    last_updated: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
