"""
DPE v4.0 Supplier Import Service

Service layer for validating and preparing supplier CSV files for import.
Handles validation without database modifications or data imports.

Architecture:
- No database writes
- No file copies or replacements
- No supplier plugin execution
- Pure validation and metadata collection
"""

import csv
from dataclasses import dataclass
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
        
        Args:
            file_path: Path to the CSV file
            supplier_name: Name of the supplier for metadata
            expected_file_path: Expected path for this supplier (for folder matching)
            
        Returns:
            ValidationResult with validation status and metadata
        """
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
