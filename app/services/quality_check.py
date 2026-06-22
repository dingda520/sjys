from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional


def normalize_month(value: str) -> str:
    value = str(value)
    if len(value) == 4:
        return f"{value}-01"
    parts = value.split("-")
    if len(parts) >= 2:
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}"
    return value


def month_range(start: str, end: str) -> List[str]:
    y, m = map(int, normalize_month(start).split("-")[:2])
    ey, em = map(int, normalize_month(end).split("-")[:2])
    out: List[str] = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def year_range(start: str, end: str) -> List[str]:
    sy = int(str(start)[:4])
    ey = int(str(end)[:4])
    return [str(y) for y in range(sy, ey + 1)]


def robust_outlier_count(values: List[Optional[float]]) -> int:
    clean = [float(v) for v in values if v is not None and isinstance(v, (int, float))]
    if len(clean) < 8:
        return 0
    diffs = [clean[i] - clean[i - 1] for i in range(1, len(clean))]
    if len(diffs) < 6:
        return 0
    med = statistics.median(diffs)
    mad = statistics.median([abs(x - med) for x in diffs])
    if mad == 0:
        return 0
    return sum(1 for x in diffs if abs(x - med) / mad > 8)


def build_quality_report(observations: List[Dict[str, Any]], frequency: str, unit: str, source: Dict[str, Any]) -> Dict[str, Any]:
    dates = [str(o.get("date")) for o in observations if o.get("date") is not None]
    duplicate_records = len(dates) - len(set(dates))

    missing_periods: List[str] = []
    if dates:
        sorted_dates = sorted(set(dates))
        if frequency == "M" and "-" in sorted_dates[0] and "-" in sorted_dates[-1]:
            expected = set(month_range(sorted_dates[0], sorted_dates[-1]))
            missing_periods = sorted(expected - set(sorted_dates))
        elif frequency == "A":
            expected = set(year_range(sorted_dates[0], sorted_dates[-1]))
            missing_periods = sorted(expected - set(sorted_dates))

    source_ok = bool(source.get("organization") and source.get("dataset") and source.get("source_series_code"))
    outliers = robust_outlier_count([o.get("value") for o in observations])

    checks = {
        "observation_count": len(observations),
        "missing_periods": missing_periods[:20],
        "missing_period_count": len(missing_periods),
        "duplicate_records": duplicate_records,
        "outlier_count": outliers,
        "unit_consistent": bool(unit),
        "traceable_source": source_ok,
        "checked_at": datetime.utcnow().date().isoformat(),
    }
    checks["passed"] = (
        len(observations) > 0
        and duplicate_records == 0
        and bool(unit)
        and source_ok
    )
    return checks
