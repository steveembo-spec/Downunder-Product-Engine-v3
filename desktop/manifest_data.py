from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "output" / "build_manifest.json"


class ManifestData:
    def __init__(self, manifest_path: Path | None = None):
        self.manifest_path = manifest_path or DEFAULT_MANIFEST_PATH
        self.data = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}

        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if isinstance(data, dict):
                return data

            return {}

        except Exception:
            return {}

    def exists(self) -> bool:
        return self.manifest_path.exists()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.data.get(key, default)

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @property
    def build_timestamp(self) -> str:
        return str(
            self.get("build_timestamp")
            or self.get("timestamp")
            or self.get("created_at")
            or ""
        )

    @property
    def supplier_rows_loaded(self) -> int:
        return self.get_int("supplier_rows_loaded")

    @property
    def unique_skus(self) -> int:
        return self.get_int("unique_skus")

    @property
    def rows_written(self) -> int:
        return self.get_int("rows_written")

    @property
    def image_matches(self) -> int:
        return self.get_int("image_matches")

    @property
    def missing_images(self) -> int:
        return self.get_int("missing_images")

    @property
    def description_matches(self) -> int:
        return self.get_int("description_matches")

    @property
    def default_descriptions_used(self) -> int:
        return self.get_int("default_descriptions_used")

    @property
    def suppliers(self) -> list[dict[str, Any]]:
        suppliers = self.get("suppliers", [])

        if isinstance(suppliers, list):
            return [item for item in suppliers if isinstance(item, dict)]

        return []

    @property
    def output_files(self) -> dict[str, Any]:
        output_files = self.get("output_files", {})

        if isinstance(output_files, dict):
            return output_files

        return {}

    def summary(self) -> dict[str, Any]:
        return {
            "build_timestamp": self.build_timestamp,
            "supplier_rows_loaded": self.supplier_rows_loaded,
            "unique_skus": self.unique_skus,
            "rows_written": self.rows_written,
            "image_matches": self.image_matches,
            "missing_images": self.missing_images,
            "description_matches": self.description_matches,
            "default_descriptions_used": self.default_descriptions_used,
            "suppliers": self.suppliers,
            "output_files": self.output_files,
        }