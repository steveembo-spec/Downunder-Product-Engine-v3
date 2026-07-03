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
    # New fields – must have defaults so existing profiles load without them
    supplier_type: str = "generic"          # "managed" or "generic"
    plugin_name: Optional[str] = None       # e.g. "a1", "cassons", "serco"
    input_file_path: Optional[str] = None   # relative path to supplier input file


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
            # New fields – default so old JSON files without them still load
            supplier_type=data.get("supplier_type", "generic"),
            plugin_name=data.get("plugin_name") or None,
            input_file_path=data.get("input_file_path") or None,
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
    # Factory helpers
    # ------------------------------------------------------------------

    def create_managed_profile(
        self,
        supplier_name: str,
        plugin_name: Optional[str] = None,
        input_file_path: Optional[str] = None,
    ) -> SupplierProfile:
        """
        Create and save a managed supplier profile.
        A managed supplier uses an existing plugin (A1, Cassons, Serco).
        Does NOT overwrite an existing profile.
        Returns the new or existing profile.
        """
        if self.profile_exists(supplier_name):
            return self.load_profile(supplier_name)  # type: ignore[return-value]
        profile = SupplierProfile(
            supplier_name=supplier_name,
            file_type="csv",
            encoding="utf-8-sig",
            delimiter=",",
            header_row=0,
            column_mapping={},
            last_verified="",
            supplier_type="managed",
            plugin_name=plugin_name,
            input_file_path=input_file_path,
        )
        self.save_profile(profile)
        return profile

    def create_generic_profile(
        self,
        supplier_name: str,
        file_type: str = "csv",
        encoding: str = "utf-8",
        delimiter: str = ",",
        header_row: int = 0,
        column_mapping: Optional[dict[str, str]] = None,
        last_verified: str = "",
    ) -> SupplierProfile:
        """
        Create and save a generic supplier profile.
        A generic supplier is loaded via the universal CSV importer.
        Does NOT overwrite an existing profile.
        Returns the new or existing profile.
        """
        if self.profile_exists(supplier_name):
            return self.load_profile(supplier_name)  # type: ignore[return-value]
        profile = SupplierProfile(
            supplier_name=supplier_name,
            file_type=file_type,
            encoding=encoding,
            delimiter=delimiter,
            header_row=header_row,
            column_mapping=column_mapping or {},
            last_verified=last_verified,
            supplier_type="generic",
            plugin_name=None,
            input_file_path=None,
        )
        self.save_profile(profile)
        return profile

    def ensure_managed_profiles_exist(self) -> list[str]:
        """
        Create managed profiles for the built-in suppliers (A1, Cassons, Serco)
        if they do not already exist.  Never overwrites existing profiles.
        Returns a list of supplier names that were newly created.
        """
        _MANAGED_SUPPLIERS = [
            {
                "supplier_name": "A1",
                "plugin_name": "a1",
                "input_file_path": "input/A1/A1 pricefile.csv",
            },
            {
                "supplier_name": "Cassons",
                "plugin_name": "cassons",
                "input_file_path": "input/Cassons/Cassons.csv",
            },
            {
                "supplier_name": "Serco",
                "plugin_name": "serco",
                "input_file_path": "input/Serco/serco.csv",
            },
        ]
        created: list[str] = []
        for entry in _MANAGED_SUPPLIERS:
            if not self.profile_exists(entry["supplier_name"]):
                self.create_managed_profile(
                    supplier_name=entry["supplier_name"],
                    plugin_name=entry["plugin_name"],
                    input_file_path=entry["input_file_path"],
                )
                created.append(entry["supplier_name"])
        return created

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
