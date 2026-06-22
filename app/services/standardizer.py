from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .lineage import build_lineage
from .quality_check import build_quality_report


def build_error_response(
    country: str,
    indicator_code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    code: str,
    message: str,
    detail: Any = None,
) -> Dict[str, Any]:
    return {
        "request": {
            "country": country,
            "indicator_code": indicator_code,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
        },
        "series": None,
        "quality_report": None,
        "lineage": None,
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
        },
    }


def standardize_series(
    country: str,
    indicator_code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    observations: List[Dict[str, Any]],
    source_url: str,
    countries: Dict[str, Dict[str, str]],
    indicators: Dict[str, Dict[str, Any]],
    source_mappings: Dict[str, Dict[str, Any]],
    quality_builder: Optional[Callable[[List[Dict[str, Any]], str, str, Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    country_info = countries[country]
    indicator_info = indicators[indicator_code]
    mapping = source_mappings[indicator_code]
    source = {
        "organization": mapping["organization"],
        "dataset": mapping["dataset"],
        "source_series_code": mapping["source_series_code"],
        "source_url": source_url,
    }
    if "derived_from" in mapping:
        source["derived_from"] = mapping["derived_from"]

    observations = sorted(observations, key=lambda x: str(x.get("date", "")))
    quality_fn = quality_builder or build_quality_report
    lineage = build_lineage(
        provider=mapping.get("organization", mapping.get("source", "")),
        dataset=mapping.get("dataset", ""),
        api_url=source_url,
        parser=mapping.get("source", ""),
    )

    series = {
        "series_id": f"{country}.{indicator_code}.{frequency}",
        "indicator_code": indicator_code,
        "indicator_name_zh": indicator_info["indicator_name_zh"],
        "indicator_name_en": indicator_info["indicator_name_en"],
        "country_name_zh": country_info["name_zh"],
        "country_name_en": country_info["name_en"],
        "country_code": country,
        "frequency": frequency,
        "unit": indicator_info["unit"],
        "seasonal_adjustment": indicator_info["seasonal_adjustment"],
        "calculation": indicator_info["calculation"],
        "source": source,
        "last_updated": datetime.utcnow().date().isoformat(),
        "observations": observations,
    }

    return {
        "request": {
            "country": country,
            "indicator_code": indicator_code,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
        },
        "series": series,
        "quality_report": quality_fn(observations, frequency, indicator_info["unit"], source),
        "lineage": lineage,
        "error": None,
    }
