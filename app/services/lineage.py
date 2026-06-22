from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict


def build_lineage(provider: str, dataset: str, api_url: str, parser: str = "") -> Dict[str, Any]:
    """Build a lightweight lineage record for traceability."""

    cache_key = hashlib.sha256(api_url.encode("utf-8")).hexdigest() if api_url else ""
    return {
        "provider": provider,
        "dataset": dataset,
        "api_url": api_url,
        "retrieved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "parser": parser,
        "raw_cache_key": cache_key,
    }
