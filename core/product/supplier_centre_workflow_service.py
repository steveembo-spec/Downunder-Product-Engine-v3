"""
SupplierCentre Workflow Service

Encapsulates all business logic for the Supplier Centre UI:
- Validation (managed vs generic suppliers)
- Importing (managed plugin vs universal pipeline)
- Exporting (Shopify CSV)

The UI should only:
1. Read inputs (supplier name, file path)
2. Call workflow service methods
3. Display result messages

This keeps the UI thin and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.product.supplier_import_service import SupplierImportService
from core.product.master_product_service import MasterProductService
from core.product.universal_supplier_reader import UniversalSupplierReader
from core.product.universal_master_product_importer import UniversalMasterProductImporter
from core.product.shopify_export_service import ShopifyExportService


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SupplierWorkflowResult:
    """Result from a supplier workflow operation (validate, import, export)."""
    
    success: bool
    title: str  # e.g., "SUCCESS: Validation Summary"
    message: str  # Multi-line formatted result text
    status_color: str  # "#10B981" (green), "#EF4444" (red), "#F59E0B" (orange), "#9CA3AF" (gray)
    
    # Detailed data (optional, for programmatic use)
    import_data: Optional[dict] = None  # {'rows_read': X, 'rows_imported': Y, ...}
    validation_data: Optional[dict] = None  # {'rows': X, 'encoding': Y, ...}
    export_data: Optional[dict] = None  # {'output_file': '...', 'rows_exported': X}
    
    # Action flag (e.g., "confirm_mapping" to trigger dialog)
    action_type: str = "none"  # "none", "confirm_mapping"


# ---------------------------------------------------------------------------
# Workflow Service
# ---------------------------------------------------------------------------

class SupplierCentreWorkflowService:
    """
    Business logic for Supplier Centre workflow operations.
    No PySide dependencies - purely business logic.
    """

    def __init__(self) -> None:
        self._supplier_import_service = SupplierImportService
        self._master_product_service = MasterProductService
        self._universal_reader = UniversalSupplierReader()
        self._universal_importer = UniversalMasterProductImporter()
        self._shopify_service = ShopifyExportService()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_file(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """
        Validate a supplier file.
        Routes to managed or generic validation based on supplier_name.
        """
        supplier_name = supplier_name.strip()
        
        if not supplier_name:
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: No Supplier Selected",
                message="Please select a managed supplier or enter a custom supplier name.",
                status_color="#EF4444",
            )

        if not file_path or not Path(file_path).exists():
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: File Not Found",
                message=f"Selected file does not exist: {file_path}",
                status_color="#EF4444",
            )

        # Check if this is a managed supplier or generic
        # Managed suppliers will exist in the discovered statuses
        # For now, try managed first; if it fails, assume generic
        is_managed = self._is_managed_supplier(supplier_name)
        
        if is_managed:
            return self._validate_managed_supplier(supplier_name, file_path)
        else:
            return self._validate_generic_supplier(supplier_name, file_path)

    def _is_managed_supplier(self, supplier_name: str) -> bool:
        """Check if a supplier name matches a managed supplier plugin."""
        from dpe_v3.supplier_plugins.loader import discover_plugin_statuses
        try:
            statuses = discover_plugin_statuses()
            supplier_names = [s.supplier_name for s in statuses]
            return supplier_name in supplier_names
        except Exception:
            return False

    def _validate_managed_supplier(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """Validate a managed supplier using SupplierImportService."""
        result = self._supplier_import_service.validate_selected_file(
            file_path,
            supplier_name,
        )

        if not result.valid:
            error_msg = result.error_message or "Unknown error"
            if "Expected:" in error_msg:
                error_msg = error_msg.replace("\\", "/")
                parts = error_msg.split("/")
                if len(parts) > 1 and "Got:" in error_msg:
                    expected_folder = parts[-1]
                    got_part = error_msg.split("Got:")[1].strip()
                    error_msg = (
                        f"File is not in the configured folder for {supplier_name}. "
                        f"Expected: .../{expected_folder}, Got: {got_part}"
                    )
            
            message = (
                f"Supplier:       {supplier_name}\n"
                f"File:           {Path(file_path).name}\n"
                f"Error:          {error_msg}"
            )
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Validation Failed",
                message=message,
                status_color="#EF4444",
            )

        # Dry-run to discover paths
        preview = self._supplier_import_service.install_validated_file(
            file_path,
            supplier_name,
            dry_run=True,
        )

        dest_short = self._shorten_path(preview.destination_file)
        archive_short = (
            self._shorten_path(preview.archived_file)
            if preview.archived_file
            else "(no existing file to archive)"
        )

        row_count_fmt = f"{result.row_count:,}"
        size_fmt = self._format_file_size(result.file_size_bytes)

        message = (
            f"Supplier:       {supplier_name}\n"
            f"Selected File:  {Path(file_path).name}\n"
            f"Destination:    {dest_short}\n"
            f"Archive Target: {archive_short}\n"
            f"Encoding:       {result.encoding}\n"
            f"Rows:           {row_count_fmt}\n"
            f"File Size:      {size_fmt}\n"
            f"\n"
            f"Ready to import - click \"Import Supplier File\" to proceed."
        )

        return SupplierWorkflowResult(
            success=True,
            title="SUCCESS: Validation Summary (Managed Supplier)",
            message=message,
            status_color="#10B981",
            validation_data={
                "supplier_name": supplier_name,
                "file_path": str(file_path),
                "rows": result.row_count,
                "encoding": result.encoding,
                "destination": preview.destination_file,
                "archive": preview.archived_file,
            }
        )

    def _validate_generic_supplier(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """Validate a generic supplier using UniversalSupplierReader."""
        read_result = self._universal_reader.read_supplier_file(supplier_name, file_path)

        if not read_result.success:
            message = (
                f"Supplier:       {supplier_name}\n"
                f"File:           {Path(file_path).name}\n"
                f"Error:          {read_result.error_message}"
            )
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Validation Failed (Generic Import)",
                message=message,
                status_color="#EF4444",
            )

        if read_result.needs_review:
            return SupplierWorkflowResult(
                success=False,
                title="Confirm Column Mapping",
                message="Please confirm the detected column mappings for required fields.",
                status_color="#F59E0B",
                action_type="confirm_mapping",
                validation_data={
                    "supplier_name": supplier_name,
                    "file_path": str(file_path),
                    "encoding": read_result.encoding,
                    "delimiter": read_result.delimiter,
                    "headers": read_result.headers,
                    "detected_mapping": read_result.detected_mapping,  # dict[str, HeaderMatch]
                    "profile_used": read_result.profile_used,
                }
            )

        # Success - show mapping summary
        rows_fmt = f"{len(read_result.preview_rows):,}" if read_result.preview_rows else "0"
        
        mapping_text = "\n".join([
            f"  {field:<20} -> {match.detected_header or '(missing)'} [{match.status}]"
            for field, match in read_result.detected_mapping.items()
            if field in ("sku", "title", "cost", "rrp")
        ])

        message = (
            f"Supplier:       {supplier_name}\n"
            f"Selected File:  {Path(file_path).name}\n"
            f"Encoding:       {read_result.encoding}\n"
            f"Delimiter:      {read_result.delimiter!r}\n"
            f"Preview Rows:   {rows_fmt}\n"
            f"\n"
            f"Column Mapping:\n{mapping_text}\n"
            f"\n"
            f"Profile Used:   {'Yes' if read_result.profile_used else 'No'}\n"
            f"Ready to import - click \"Import Supplier File\" to proceed."
        )

        return SupplierWorkflowResult(
            success=True,
            title="SUCCESS: Validation Summary (Generic Import)",
            message=message,
            status_color="#10B981",
            validation_data={
                "supplier_name": supplier_name,
                "file_path": str(file_path),
                "encoding": read_result.encoding,
                "delimiter": read_result.delimiter,
                "headers": read_result.headers,
                "profile_used": read_result.profile_used,
            }
        )

    # ------------------------------------------------------------------
    # Mapping Confirmation
    # ------------------------------------------------------------------

    def confirm_mapping_and_import(
        self,
        supplier_name: str,
        file_path: str | Path,
        confirmed_mapping: dict[str, str],
        remember_mapping: bool,
    ) -> SupplierWorkflowResult:
        """
        User confirmed mapping in dialog.
        1. Save the profile if remember_mapping is True
        2. Re-run import with the confirmed mapping
        Returns import result.
        """
        try:
            file_path = Path(file_path)
            
            if remember_mapping:
                # Save the profile with confirmed mapping
                from core.product.supplier_profile_manager import SupplierProfileManager, SupplierProfile
                from datetime import datetime
                
                profile_manager = SupplierProfileManager()
                
                # Read the file to get encoding/delimiter info
                reader = UniversalSupplierReader()
                read_result = reader.read_supplier_file(supplier_name, file_path)
                
                if read_result.success:
                    profile = SupplierProfile(
                        supplier_name=supplier_name,
                        file_type="csv",
                        encoding=read_result.encoding,
                        delimiter=read_result.delimiter,
                        header_row=0,
                        column_mapping=confirmed_mapping,
                        last_verified=datetime.now().isoformat(),
                        supplier_type="generic",
                    )
                    profile_manager.save_profile(profile)
            
            # Re-run import with the confirmed mapping
            result = self._import_generic_supplier(supplier_name, file_path)
            return result
        except Exception as e:
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Exception in confirm_mapping_and_import",
                message=f"{type(e).__name__}: {e}",
                status_color="#EF4444",
            )

    # ------------------------------------------------------------------
    # Importing
    # ------------------------------------------------------------------

    def import_file(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """
        Import a supplier file.
        Routes to managed or generic import based on supplier_name.
        """
        supplier_name = supplier_name.strip()
        
        if not supplier_name:
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: No Supplier Selected",
                message="Please select a managed supplier or enter a custom supplier name.",
                status_color="#EF4444",
            )

        if not file_path or not Path(file_path).exists():
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: File Not Found",
                message=f"Selected file does not exist: {file_path}",
                status_color="#EF4444",
            )

        is_managed = self._is_managed_supplier(supplier_name)
        
        if is_managed:
            return self._import_managed_supplier(supplier_name, file_path)
        else:
            return self._import_generic_supplier(supplier_name, file_path)

    def _import_managed_supplier(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """Import a managed supplier using SupplierImportService."""
        # Step 1: Copy file to configured location
        import_result = self._supplier_import_service.install_validated_file(
            file_path,
            supplier_name,
            dry_run=False,
        )

        if not import_result.success:
            message = (
                f"Supplier:  {import_result.supplier_name}\n"
                f"Error:     {import_result.error_message}"
            )
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Import Failed",
                message=message,
                status_color="#EF4444",
            )

        # Step 2: Synchronise Master Product Database
        try:
            service = self._master_product_service()
            sync_stats = service.sync_from_supplier_loader()
            total_products = service.count_master_products()
        except Exception as exc:
            message = (
                f"Supplier:   {import_result.supplier_name}\n"
                f"Installed:  {Path(import_result.destination_file).name}\n"
                f"Error:      {exc}"
            )
            return SupplierWorkflowResult(
                success=False,
                title="WARNING: File Imported - Database Sync Failed",
                message=message,
                status_color="#F59E0B",
                import_data={
                    "supplier_name": import_result.supplier_name,
                    "file_installed": True,
                }
            )

        # Step 3: Build completion summary
        added = sync_stats.get('master_products_added', 0)
        skipped = sync_stats.get('master_products_skipped', 0)
        sp_added = sync_stats.get('supplier_products_added', 0)
        sp_skipped = sync_stats.get('supplier_products_skipped', 0)

        archive_line = ""
        if import_result.archived_file:
            archive_line = f"Archived:                  {Path(import_result.archived_file).name}\n"

        message = (
            f"Supplier:                  {import_result.supplier_name}\n"
            f"Installed:                 {Path(import_result.destination_file).name}\n"
            f"{archive_line}"
            f"\n"
            f"New Master Products:       {added:,}\n"
            f"Existing (Skipped):        {skipped:,}\n"
            f"New Supplier Products:     {sp_added:,}\n"
            f"Existing (Skipped):        {sp_skipped:,}\n"
            f"Master Products Total:     {total_products:,}\n"
            f"\n"
            f"Ready to Export Shopify CSV"
        )

        return SupplierWorkflowResult(
            success=True,
            title="SUCCESS: Supplier Import Complete (Managed)",
            message=message,
            status_color="#10B981",
            import_data={
                "supplier_name": import_result.supplier_name,
                "rows_imported": added,
                "rows_skipped": skipped,
                "products_created": added,
                "products_updated": sp_added,
                "total_products": total_products,
            }
        )

    def _import_generic_supplier(
        self,
        supplier_name: str,
        file_path: str | Path,
    ) -> SupplierWorkflowResult:
        """Import a generic supplier using UniversalMasterProductImporter."""
        import_result = self._universal_importer.import_supplier_file(supplier_name, file_path)

        if not import_result.success:
            message = (
                f"Supplier:  {import_result.supplier_name}\n"
                f"Error:     {import_result.error_message}"
            )
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Import Failed (Generic)",
                message=message,
                status_color="#EF4444",
            )

        # Build completion summary
        error_count = len(import_result.errors) if import_result.errors else 0
        errors_line = ""
        if error_count > 0:
            errors_line = f"Rows with Errors:          {error_count}\n"

        message = (
            f"Supplier:                  {import_result.supplier_name}\n"
            f"File:                      {Path(import_result.file_path).name}\n"
            f"\n"
            f"Rows Read:                 {import_result.rows_read}\n"
            f"Rows Imported:             {import_result.rows_imported}\n"
            f"Rows Skipped:              {import_result.rows_skipped}\n"
            f"Products Created:          {import_result.products_created}\n"
            f"Products Updated:          {import_result.products_updated}\n"
            f"{errors_line}"
            f"\n"
            f"Ready to Export Shopify CSV"
        )

        return SupplierWorkflowResult(
            success=True,
            title="SUCCESS: Supplier Import Complete (Generic)",
            message=message,
            status_color="#10B981",
            import_data={
                "supplier_name": import_result.supplier_name,
                "rows_read": import_result.rows_read,
                "rows_imported": import_result.rows_imported,
                "rows_skipped": import_result.rows_skipped,
                "products_created": import_result.products_created,
                "products_updated": import_result.products_updated,
                "errors": error_count,
            }
        )

    # ------------------------------------------------------------------
    # Exporting
    # ------------------------------------------------------------------

    def export_shopify(self) -> SupplierWorkflowResult:
        """Export Master Product Database to Shopify CSV."""
        try:
            result = self._shopify_service.export_all_products()

            if not result.success:
                message = f"Error: {result.error_message}"
                return SupplierWorkflowResult(
                    success=False,
                    title="ERROR: Export Failed",
                    message=message,
                    status_color="#EF4444",
                )

            # Format output path
            output_short = self._shorten_path(result.output_file)

            message = (
                f"Output File:    {output_short}\n"
                f"Rows Exported:  {result.rows_exported:,}\n"
                f"\n"
                f"Ready for Shopify upload"
            )

            return SupplierWorkflowResult(
                success=True,
                title="SUCCESS: Shopify Export Complete",
                message=message,
                status_color="#10B981",
                export_data={
                    "output_file": result.output_file,
                    "rows_exported": result.rows_exported,
                }
            )

        except Exception as exc:
            message = f"Exception: {exc}"
            return SupplierWorkflowResult(
                success=False,
                title="ERROR: Export Failed",
                message=message,
                status_color="#EF4444",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes > 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes > 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"

    @staticmethod
    def _shorten_path(path_str: str) -> str:
        """Shorten a path to last two parts with ellipsis."""
        if not path_str:
            return ""
        parts = str(path_str).replace("\\", "/").split("/")
        if len(parts) > 2:
            return "../" + "/".join(parts[-2:])
        return path_str
