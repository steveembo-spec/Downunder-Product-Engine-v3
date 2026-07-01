from pathlib import Path
import json

from core.paths import get_data_root

MANIFEST = get_data_root() / "output" / "build_manifest.json"


def _load_manifest():
    if not MANIFEST.exists():
        return {}

    try:
        with MANIFEST.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except Exception:
        return {}


def _get_int(data, *keys, default=0):
    for key in keys:
        try:
            value = data.get(key)

            if value is not None:
                return int(value)

        except (TypeError, ValueError):
            continue

    return default


def _get_text(data, *keys, default=""):
    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return str(value)

    return default


def load_dashboard():
    data = _load_manifest()

    if not data:
        return {
            "products": "0",
            "images": "0",
            "descriptions": "0",
            "status": "UNKNOWN",
            "run_date": "Never",
        }

    return {
        "products": str(_get_int(data, "products", "unique_skus", "rows_written")),
        "images": str(_get_int(data, "images", "image_matches")),
        "descriptions": str(_get_int(data, "descriptions", "description_matches")),
        "status": _get_text(data, "status", default="SUCCESS"),
        "run_date": _get_text(
            data,
            "run_date",
            "build_timestamp",
            "build_time_iso",
            "timestamp",
            "created_at",
            default="Unknown",
        ),
    }


def load_dashboard_stats():
    return load_dashboard()