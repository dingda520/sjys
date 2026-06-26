from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Union


@dataclass
class SourceMetadata:
    """Official source metadata used for traceability."""

    organization: str
    dataset: str
    source_series_code: str
    source_url: str = ""
    source: str = ""
    supported_countries: Union[str, List[str]] = "all"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class SeriesMetadata:
    """Standard metadata describing a normalized macroeconomic series."""

    series_id: str
    indicator_code: str
    indicator_name_zh: str
    indicator_name_en: str
    country_code: str
    country_name_zh: str
    country_name_en: str
    frequency: str
    unit: str
    seasonal_adjustment: str
    calculation: str
    source: SourceMetadata
    source_updated_at: str
    last_updated: str

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data
