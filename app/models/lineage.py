from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass
class DataLineage:
    """How, where and when a series was retrieved."""

    provider: str
    dataset: str
    api_url: str
    retrieved_at: str
    parser: str = ""
    raw_cache_key: Optional[str] = None
    source_version: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
