"""
DPE v4.0 Supplier Import Service

Service layer for validating and installing supplier CSV files.
Handles validation, archiving and safe file replacement.

Architecture:
- No database writes
- No supplier plugin execution
- File copy/archive only on explicit install_validated_file call
"""

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    """Result of supplier file validation."""
    valid: bool
    supplier_name: str
    file_path: str
    file_exists: bool
    file_size_bytes: int
    row_count: int
    encoding: str
    expected_file_path: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ImportResult:
    """Result of a supplier file install operation."""
    success: bool
    supplier_name: str
    source_file: str
    destination_file: str
    dry_run: bool = True
    archived_file: Optional[str] = None
    error_message: Optional[str] = None


class SupplierImportService:
    """Service layer for supplier file validation and import preparation."""
    
    ENCODINGS_TO_TRY = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    @staticmethod
    def validate_selected_file(
        file_path: str,
        supplier_name: str,
        expected_file_path: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a selected supplier CSV file.
        
        Internally discovers supplier configuration if expected_file_path is None.
        
        Args:
            file_path: Path to the CSV file
            supplier_name: Name of the supplier for metadata
            expected_file_path: Expected path for this supplier (for folder matching).
                                If None, will be discovered automatically.
            
        Returns:
            ValidationResult with validation status and metadata
        """
        # If expected_file_path not provided, discover it from supplier configuration
        if expected_file_path is None:
            expected_file_path = SupplierImportService._get_supplier_file_path(supplier_name)
        
        # Initialize result with defaults
        result = ValidationResult(
            valid=False,
            supplier_name=supplier_name,
            file_path=file_path,
            file_exists=False,
            file_size_bytes=0,
            row_count=0,
            encoding="unknown",
            expected_file_path=expected_file_path,
            error_message=None
        )
        
        # Check if file exists
        path = Path(file_path)
        if not path.exists():
            result.error_message = f"File not found: {file_path}"
            return result
        
        result.file_exists = True
        
        # Check file/supplier folder match if expected path is provided
        if expected_file_path:
            expected_path = Path(expected_file_path)
            selected_path = Path(file_path)
            
            # Get the parent directories (folders) for comparison
            expected_folder = expected_path.parent.resolve()
            selected_folder = selected_path.parent.resolve()
            
            if selected_folder != expected_folder:
                expected_relative = str(expected_path.parent)
                result.error_message = (
                    f"Selected file is not in the configured folder for {supplier_name}. "
                    f"Expected: {expected_relative}, Got: {selected_folder.name}"
                )
                return result
        
        # Check file extension
        if path.suffix.lower() != '.csv':
            result.error_message = f"Invalid file extension: {path.suffix}. Expected .csv"
            return result
        
        # Get file size
        try:
            result.file_size_bytes = path.stat().st_size
        except Exception as e:
            result.error_message = f"Cannot read file stats: {str(e)}"
            return result
        
        # Determine encoding and count rows
        encoding = SupplierImportService._detect_encoding(path)
        if encoding is None:
            result.error_message = "Cannot determine file encoding"
            return result
        
        result.encoding = encoding
        
        # Count rows
        try:
            row_count = SupplierImportService._count_rows(path, encoding)
            result.row_count = row_count
        except Exception as e:
            result.error_message = f"Cannot read CSV file: {str(e)}"
            return result
        
        # All checks passed
        result.valid = True
        result.error_message = None
        return result
    
    @staticmethod
    def install_validated_file(
        file_path: str,
        supplier_name: str,
        dry_run: bool = True,
    ) -> "ImportResult":
        """
        Validate and optionally install a supplier CSV file.

        When dry_run=True (default):
            Validates the file, determines destination and archive paths,
            and returns an ImportResult describing what WOULD happen.
            No files are created, copied, or replaced.

        When dry_run=False:
            Performs the full archive + copy operation.

        Args:
            file_path: Path to the source CSV selected by the user.
            supplier_name: Supplier name to look up the destination.
            dry_run: If True, preview only - no file operations performed.

        Returns:
            ImportResult describing the outcome or preview.
        """
        destination = SupplierImportService._get_supplier_file_path(supplier_name)

        base_result = ImportResult(
            success=False,
            supplier_name=supplier_name,
            source_file=file_path,
            destination_file=destination or "",
            dry_run=dry_run,
        )

        # Re-validate first (always, regardless of dry_run)
        validation = SupplierImportService.validate_selected_file(file_path, supplier_name)
        if not validation.valid:
            base_result.error_message = f"Re-validation failed: {validation.error_message}"
            return base_result

        if not destination:
            base_result.error_message = (
                f"No configured input file found for supplier '{supplier_name}'"
            )
            return base_result

        dest_path = Path(destination)
        source_path = Path(file_path)

        # Determine the archive path (used in both dry-run and live modes)
        archived_file: Optional[str] = None
        if dest_path.exists():
            archive_dir = dest_path.parent / "_archive"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{dest_path.stem}_{timestamp}{dest_path.suffix}"
            archive_path = archive_dir / archive_name
            archived_file = str(archive_path)

        if dry_run:
            # Preview only - no folders created, no files copied or replaced
            return ImportResult(
                success=True,
                supplier_name=supplier_name,
                source_file=str(source_path),
                destination_file=str(dest_path),
                dry_run=True,
                archived_file=archived_file,
            )

        # --- Live import (dry_run=False) ---

        # Create archive folder and archive existing destination file
        if archived_file:
            try:
                archive_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                base_result.error_message = f"Cannot create archive folder: {e}"
                return base_result

            try:
                shutil.copy2(dest_path, archive_path)
            except Exception as e:
                base_result.error_message = f"Cannot archive existing file: {e}"
                return base_result

        # Copy source to destination (skip if source and destination are the same file)
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if source_path.resolve() != dest_path.resolve():
                shutil.copy2(source_path, dest_path)
        except Exception as e:
            base_result.error_message = f"Cannot copy file to destination: {e}"
            return base_result

        return ImportResult(
            success=True,
            supplier_name=supplier_name,
            source_file=str(source_path),
            destination_file=str(dest_path),
            dry_run=False,
            archived_file=archived_file,
        )

    @staticmethod
    def _get_supplier_file_path(supplier_name: str) -> Optional[str]:
        """
        Get the configured file path for a supplier by name.

        Args:
            supplier_name: Name of the supplier to look up
            
        Returns:
            Full file path for the supplier, or None if not found
        """
        try:
            from dpe_v3.supplier_plugins.loader import discover_plugin_statuses
            
            statuses = discover_plugin_statuses()
            for status in statuses:
                if status.supplier_name == supplier_name:
                    return status.input_file
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def _detect_encoding(file_path: Path) -> Optional[str]:
        """
        Detect the encoding of a file by actually trying to read it.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Encoding name if detected, None otherwise
        """
        for encoding in SupplierImportService.ENCODINGS_TO_TRY:
            try:
                with open(file_path, 'r', encoding=encoding, newline='') as f:
                    # Try to read the entire file with csv.reader to verify encoding works
                    reader = csv.reader(f)
                    for _ in reader:
                        pass
                return encoding
            except (UnicodeDecodeError, LookupError, Exception):
                continue
        
        return None
    
    @staticmethod
    def _count_rows(file_path: Path, encoding: str) -> int:
        """
        Count the number of rows in a CSV file.
        
        Args:
            file_path: Path to the CSV file
            encoding: Encoding to use when reading
            
        Returns:
            Number of rows (including header)
        """
        row_count = 0
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f)
                for _ in reader:
                    row_count += 1
        except Exception:
            raise
        
        return row_count
