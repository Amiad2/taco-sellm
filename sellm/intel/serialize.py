"""Canonical JSON for the dossiers: the same input gives the same bytes."""

import json
import math
from pathlib import Path


def clean(obj):
    """Tuples to lists, floats rounded to 6 places; NaN and infinity are an error, not data."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("not a finite number")
        return round(obj, 6) + 0.0
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [clean(v) for v in obj]
    return obj


def dumps(obj):
    return json.dumps(clean(obj), sort_keys=True, ensure_ascii=False, indent=1, allow_nan=False) + "\n"


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(obj), encoding="utf-8")
