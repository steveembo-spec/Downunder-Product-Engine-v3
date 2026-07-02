from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Profile data model
# ---------------------------------------------------------------------------

@dataclass
class SupplierProfile:
    supplier_name: str
    file_type: str                          # e.g. "csv", "xlsx"
    encoding: str                           # e.g. "utf-8", "cp1252"
    delimiter: str                          # e.g. ",", ";"
    header_row: int                         # 0-based row index containing headers
    column_mapping: dict[str, str]          # master_field -> detected_header
    last_verified: str                      # ISO 8601 datetime string or empty


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitise_filename(name: str) -> str:
    """Replace characters that are unsafe in Windows/Unix filenames."""
    sanitised = _UNSAFE_CHARS.sub("_", name).strip(". ")
    if not sanitised:
        raise ValueError(f"Supplier name {name!r} produces an empty filename after sanitisation")
    return sanitised


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SupplierProfileManager:
    """
    Persist supplier profiles as individual JSON files under
    config/supplier_profiles/.

    The profiles_dir can be supplied explicitly (useful in tests); otherwise
    it defaults to <project_root>/config/supplier_profiles/ where
    <project_root> is two parents above this file's location.
    """

    def __init__(self, profiles_dir: Optional[Path] = None) -> None:
        if profiles_dir is None:
            # core/product/supplier_profile_manager.py  ->  project root is ../../
            project_root = Path(__file__).resolve().parent.parent.parent
            profiles_dir = project_root / "config" / "supplier_profiles"
        self._profiles_dir = Path(profiles_dir)
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helper
    # ------------------------------------------------------------------

    def get_profile_path(self, supplier_name: str) -> Path:
        """Return the Path for a supplier's JSON file (may not exist yet)."""
        self._validate_name(supplier_name)
        return self._profiles_dir / f"{_sanitise_filename(supplier_name)}.json"

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def save_profile(self, profile: SupplierProfile) -> None:
        """Serialise a SupplierProfile to disk, creating the directory if needed."""
        self._validate_profile(profile)
        path = self.get_profile_path(profile.supplier_name)
        data = asdict(profile)
        # Normalise: sort column_mapping keys for deterministic output
        data["column_mapping"] = dict(sorted(data["column_mapping"].items()))
        path.write_text(json.dumps(data, indent=4, sort_keys=True), encoding="utf-8")

    def load_profile(self, supplier_name: str) -> Optional[SupplierProfile]:
        """Load and return a SupplierProfile, or None if the file does not exist."""
        path = self.get_profile_path(supplier_name)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SupplierProfile(
            supplier_name=data["supplier_name"],
            file_type=data.get("file_type", "csv"),
            encoding=data.get("encoding", "utf-8"),
            delimiter=data.get("delimiter", ","),
            header_row=int(data.get("header_row", 0)),
            column_mapping=dict(data.get("column_mapping", {})),
            last_verified=data.get("last_verified", ""),
        )

    def profile_exists(self, supplier_name: str) -> bool:
        """Return True if a profile JSON file exists for the given supplier."""
        return self.get_profile_path(supplier_name).exists()

    def delete_profile(self, supplier_name: str) -> bool:
        """
        Delete the profile file for a supplier.
        Returns True if deleted, False if it did not exist.
        """
        path = self.get_profile_path(supplier_name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_profiles(self) -> list[str]:
        """
        Return a sorted list of supplier names that have saved profiles.
        Names are derived from JSON filenames (stem).
        """
        return sorted(p.stem for p in self._profiles_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Internal validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_name(supplier_name: str) -> None:
        if not isinstance(supplier_name, str) or not supplier_name.strip():
            raise ValueError("supplier_name must be a non-empty string")

    @staticmethod
    def _validate_profile(profile: SupplierProfile) -> None:
        SupplierProfileManager._validate_name(profile.supplier_name)
        if not isinstance(profile.column_mapping, dict):
            raise TypeError("column_mapping must be a dictionary")
