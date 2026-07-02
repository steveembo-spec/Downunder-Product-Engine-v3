from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.product.header_detection import (
    HeaderMatch,
    detect_header_mapping,
    mapping_needs_review,
    STATUS_MATCHED,
    STATUS_MISSING,
)
from core.product.supplier_profile_manager import SupplierProfileManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1"]
_SUPPORTED_EXTENSIONS = {".csv"}
_PREVIEW_ROWS = 5

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class UniversalSupplierReadResult:
    success: bool
    supplier_name: str
    file_path: str
    encoding: str
    delimiter: str
    headers: list[str]
    preview_rows: list[list[str]]
    detected_mapping: dict[str, HeaderMatch]
    profile_used: bool
    needs_review: bool
    error_message: str


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class UniversalSupplierReader:
    """
    Read a supplier CSV file, auto-detect encoding and delimiter, run header
    detection, and optionally apply a saved supplier profile.
    """

    def __init__(self, profiles_dir: Optional[Path] = None) -> None:
        self._profile_manager = SupplierProfileManager(profiles_dir=profiles_dir)

    def read_supplier_file(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> UniversalSupplierReadResult:
        """
        Main entry point.  Returns an UniversalSupplierReadResult.
        Never raises – errors are captured in the result.
        """
        file_path = Path(file_path)
        _empty: dict[str, HeaderMatch] = {}

        # --- Validate --------------------------------------------------
        if not supplier_name or not supplier_name.strip():
            return self._error(supplier_name, file_path, "supplier_name must not be empty")

        if not file_path.exists():
            return self._error(supplier_name, file_path, f"File not found: {file_path}")

        if file_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return self._error(
                supplier_name,
                file_path,
                f"Unsupported file type '{file_path.suffix}'. Only .csv is supported.",
            )

        # --- Detect encoding -------------------------------------------
        encoding = self._detect_encoding(file_path)
        if encoding is None:
            return self._error(
                supplier_name,
                file_path,
                "Could not detect file encoding. Try saving the file as UTF-8.",
            )

        # --- Read raw text ---------------------------------------------
        try:
            raw_text = file_path.read_text(encoding=encoding, errors="replace")
        except OSError as exc:
            return self._error(supplier_name, file_path, f"Could not read file: {exc}")

        # --- Detect delimiter ------------------------------------------
        delimiter = self._detect_delimiter(raw_text)

        # --- Parse headers + preview rows ------------------------------
        try:
            headers, preview_rows = self._parse_headers_and_preview(
                raw_text, delimiter
            )
        except Exception as exc:
            return self._error(supplier_name, file_path, f"Could not parse CSV: {exc}")

        if not headers:
            return self._error(supplier_name, file_path, "File appears to have no headers.")

        # --- Header detection -----------------------------------------
        detected_mapping = detect_header_mapping(headers)

        # --- Load saved profile (if any) and override mapping ---------
        profile_used = False
        if self._profile_manager.profile_exists(supplier_name):
            profile = self._profile_manager.load_profile(supplier_name)
            if profile and profile.column_mapping:
                detected_mapping = self._apply_profile_mapping(
                    detected_mapping, profile.column_mapping, headers
                )
                profile_used = True

        # --- Determine needs_review -----------------------------------
        needs_review = not profile_used and mapping_needs_review(detected_mapping)
        if not needs_review:
            # Even with a profile, flag if required fields are still missing
            from core.product.header_detection import required_fields_missing, REQUIRED_MASTER_FIELDS
            for f_name in REQUIRED_MASTER_FIELDS:
                m = detected_mapping.get(f_name)
                if m is None or m.status == STATUS_MISSING:
                    needs_review = True
                    break

        return UniversalSupplierReadResult(
            success=True,
            supplier_name=supplier_name,
            file_path=str(file_path),
            encoding=encoding,
            delimiter=delimiter,
            headers=headers,
            preview_rows=preview_rows,
            detected_mapping=detected_mapping,
            profile_used=profile_used,
            needs_review=needs_review,
            error_message="",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_encoding(file_path: Path) -> Optional[str]:
        raw = file_path.read_bytes()
        for enc in _CANDIDATE_ENCODINGS:
            try:
                raw.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return None

    @staticmethod
    def _detect_delimiter(raw_text: str) -> str:
        # Feed only the first 4 KB to the sniffer for speed
        sample = raw_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            return ","

    @staticmethod
    def _parse_headers_and_preview(
        raw_text: str,
        delimiter: str,
    ) -> tuple[list[str], list[list[str]]]:
        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) > _PREVIEW_ROWS + 1:  # header + preview rows
                break

        if not rows:
            return [], []

        headers = [h.strip() for h in rows[0]]
        preview_rows = [
            [cell.strip() for cell in row]
            for row in rows[1 : _PREVIEW_ROWS + 1]
        ]
        return headers, preview_rows

    @staticmethod
    def _apply_profile_mapping(
        detected: dict[str, HeaderMatch],
        saved_mapping: dict[str, str],
        headers: list[str],
    ) -> dict[str, HeaderMatch]:
        """
        Override detected mapping with values from a saved profile.
        Only overrides if the saved header is present in the current file.
        """
        result = dict(detected)
        headers_set = set(headers)
        for master_field, saved_header in saved_mapping.items():
            if saved_header in headers_set:
                result[master_field] = HeaderMatch(
                    master_field=master_field,
                    detected_header=saved_header,
                    confidence=100,
                    status=STATUS_MATCHED,
                    reason="Matched via saved supplier profile",
                )
        return result

    @staticmethod
    def _error(
        supplier_name: str,
        file_path: Path,
        message: str,
    ) -> UniversalSupplierReadResult:
        from core.product.header_detection import HeaderMatch
        return UniversalSupplierReadResult(
            success=False,
            supplier_name=supplier_name,
            file_path=str(file_path),
            encoding="",
            delimiter="",
            headers=[],
            preview_rows=[],
            detected_mapping={},
            profile_used=False,
            needs_review=True,
            error_message=message,
        )
