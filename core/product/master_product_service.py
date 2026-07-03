"""
DPE v4.0 Master Product Service

Service layer for accessing v4.0 master product database.
Provides SQLite-based queries for master products, suppliers, and relationships.

Architecture:
- Reads from: output/dpe_catalogue.db (v4.0 foundation tables)
- Schema: master_products, suppliers, supplier_products, product_intelligence
- Idempotent: Safe to call sync_from_supplier_loader() multiple times
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

import sys

# Add project root to path for imports
from core.paths import get_project_root
PROJECT_ROOT = get_project_root(__file__)
sys.path.insert(0, str(PROJECT_ROOT))

from dpe_v3.supplier_plugins.loader import load_all_suppliers


@dataclass(frozen=True)
class MasterProduct:
    """Represents a master product record."""
    id: int
    sku: str
    title: str
    brand: str
    category: str
    description_status: str
    created_at: str
    v4_migrated_at: str


@dataclass(frozen=True)
class Supplier:
    """Represents a supplier record."""
    id: int
    supplier_code: str
    supplier_name: str
    is_enabled: int
    priority_rank: int
    created_at: str


@dataclass(frozen=True)
class SupplierProduct:
    """Represents a supplier product record."""
    id: int
    master_product_id: int
    supplier_id: int
    supplier_sku: str
    supplier_cost: Optional[float]
    supplier_rrp: Optional[float]
    supplier_stock: Optional[int]
    is_active: int
    created_at: str


class MasterProductService:
    """Service layer for v4.0 master product database."""
    
    def __init__(self, project_root: Path = None):
        """Initialize service with database connection."""
        if project_root is None:
            project_root = PROJECT_ROOT
        
        self.project_root = project_root
        self.db_file = project_root / "output" / "dpe_catalogue.db"
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ============================================================================
    # Master Products Methods
    # ============================================================================
    
    def get_master_product_by_sku(self, sku: str) -> Optional[MasterProduct]:
        """Get a single master product by SKU.
        
        Args:
            sku: Product SKU
            
        Returns:
            MasterProduct or None if not found
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, sku, title, brand, category, description_status,
                       created_at, v4_migrated_at
                FROM master_products
                WHERE sku = ?
            """, (sku,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return MasterProduct(
                id=row[0],
                sku=row[1],
                title=row[2],
                brand=row[3],
                category=row[4],
                description_status=row[5],
                created_at=row[6],
                v4_migrated_at=row[7]
            )
        finally:
            conn.close()
    
    def list_master_products(self, limit: Optional[int] = None) -> List[MasterProduct]:
        """List all master products with optional limit.
        
        Args:
            limit: Maximum number of products to return (None for all)
            
        Returns:
            List of MasterProduct records
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            
            if limit:
                cur.execute("""
                    SELECT id, sku, title, brand, category, description_status,
                           created_at, v4_migrated_at
                    FROM master_products
                    ORDER BY sku
                    LIMIT ?
                """, (limit,))
            else:
                cur.execute("""
                    SELECT id, sku, title, brand, category, description_status,
                           created_at, v4_migrated_at
                    FROM master_products
                    ORDER BY sku
                """)
            
            products = []
            for row in cur.fetchall():
                products.append(MasterProduct(
                    id=row[0],
                    sku=row[1],
                    title=row[2],
                    brand=row[3],
                    category=row[4],
                    description_status=row[5],
                    created_at=row[6],
                    v4_migrated_at=row[7]
                ))
            
            return products
        finally:
            conn.close()
    
    def count_master_products(self) -> int:
        """Count total master products.
        
        Returns:
            Number of master products
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM master_products")
            return cur.fetchone()[0]
        finally:
            conn.close()
    
    def search_master_products(self, query: str, limit: int = 500) -> List[MasterProduct]:
        """Search master products by SKU, title, brand, or category.
        
        Queries the database directly to search across all products.
        
        Args:
            query: Search term (case-insensitive, matches partial strings)
            limit: Maximum number of results to return (default 500, max 1000)
            
        Returns:
            List of MasterProduct records matching the query (up to limit)
        """
        # Cap limit to maximum 1000
        limit = min(limit, 1000)
        
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            # Search in SKU, title, brand, category with LIKE (case-insensitive)
            search_pattern = f"%{query}%"
            
            cur.execute("""
                SELECT id, sku, title, brand, category, description_status,
                       created_at, v4_migrated_at
                FROM master_products
                WHERE sku LIKE ? 
                   OR title LIKE ?
                   OR brand LIKE ?
                   OR category LIKE ?
                ORDER BY sku
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern, search_pattern, limit))
            
            products = []
            for row in cur.fetchall():
                products.append(MasterProduct(
                    id=row[0],
                    sku=row[1],
                    title=row[2],
                    brand=row[3],
                    category=row[4],
                    description_status=row[5],
                    created_at=row[6],
                    v4_migrated_at=row[7]
                ))
            
            return products
        finally:
            conn.close()
    
    # ============================================================================
    # Supplier Products Methods
    # ============================================================================
    
    def list_supplier_products_for_sku(self, sku: str) -> List[SupplierProduct]:
        """Get all supplier products for a master product SKU.
        
        Shows all suppliers that have this product.
        
        Args:
            sku: Master product SKU
            
        Returns:
            List of SupplierProduct records for this SKU
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT sp.id, sp.master_product_id, sp.supplier_id, sp.supplier_sku,
                       sp.supplier_cost, sp.supplier_rrp, sp.supplier_stock,
                       sp.is_active, sp.created_at
                FROM supplier_products sp
                JOIN master_products mp ON sp.master_product_id = mp.id
                WHERE mp.sku = ?
                ORDER BY sp.supplier_id
            """, (sku,))
            
            products = []
            for row in cur.fetchall():
                products.append(SupplierProduct(
                    id=row[0],
                    master_product_id=row[1],
                    supplier_id=row[2],
                    supplier_sku=row[3],
                    supplier_cost=row[4],
                    supplier_rrp=row[5],
                    supplier_stock=row[6],
                    is_active=row[7],
                    created_at=row[8]
                ))
            
            return products
        finally:
            conn.close()
    
    def get_supplier_options_for_sku(self, sku: str) -> List[Supplier]:
        """Get list of suppliers for a given SKU.
        
        Returns which suppliers have this product.
        
        Args:
            sku: Master product SKU
            
        Returns:
            List of Supplier records
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT DISTINCT s.id, s.supplier_code, s.supplier_name,
                       s.is_enabled, s.priority_rank, s.created_at
                FROM suppliers s
                JOIN supplier_products sp ON s.id = sp.supplier_id
                JOIN master_products mp ON sp.master_product_id = mp.id
                WHERE mp.sku = ?
                ORDER BY s.priority_rank
            """, (sku,))
            
            suppliers = []
            for row in cur.fetchall():
                suppliers.append(Supplier(
                    id=row[0],
                    supplier_code=row[1],
                    supplier_name=row[2],
                    is_enabled=row[3],
                    priority_rank=row[4],
                    created_at=row[5]
                ))
            
            return suppliers
        finally:
            conn.close()
    
    # ============================================================================
    # Sync Methods
    # ============================================================================
    
    def sync_from_supplier_loader(self) -> dict:
        """Sync master products and supplier relationships from supplier plugins.
        
        Idempotent: Safe to call multiple times.
        - Checks if data already exists before inserting
        - Returns summary of changes made
        
        Returns:
            Dictionary with sync statistics:
            {
                'suppliers_added': int,
                'suppliers_skipped': int,
                'master_products_added': int,
                'master_products_skipped': int,
                'supplier_products_added': int,
                'supplier_products_skipped': int,
            }
        """
        print("Loading supplier products from plugin pipeline...")
        products = load_all_suppliers()
        print(f"✓ Loaded {len(products):,} supplier products")
        
        stats = {
            'suppliers_added': 0,
            'suppliers_skipped': 0,
            'master_products_added': 0,
            'master_products_skipped': 0,
            'supplier_products_added': 0,
            'supplier_products_skipped': 0,
        }
        
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            
            # =====================================================================
            # Sync Suppliers
            # =====================================================================
            print("  Syncing suppliers...")
            
            # Get existing suppliers
            cur.execute("SELECT supplier_code FROM suppliers")
            existing_suppliers = {row[0] for row in cur.fetchall()}
            
            # Get unique suppliers from products
            supplier_names = {p.get('supplier', '').lower() for p in products if p.get('supplier')}
            
            supplier_metadata = {
                "a1": ("A1", 100),
                "cassons": ("Cassons", 90),
                "serco": ("Serco", 70),
            }
            
            for supplier_code in supplier_names:
                if supplier_code in existing_suppliers:
                    stats['suppliers_skipped'] += 1
                else:
                    name, priority = supplier_metadata.get(supplier_code, (supplier_code, 50))
                    cur.execute("""
                        INSERT INTO suppliers (
                            supplier_code, supplier_name, is_enabled, priority_rank, created_at
                        ) VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                    """, (supplier_code, name, priority))
                    stats['suppliers_added'] += 1
            
            conn.commit()
            
            # =====================================================================
            # Sync Master Products
            # =====================================================================
            print("  Syncing master products...")
            
            # Get existing SKUs
            cur.execute("SELECT sku FROM master_products")
            existing_skus = {row[0] for row in cur.fetchall()}
            
            # Extract unique SKUs from products
            unique_skus = {}
            for product in products:
                sku = product.get('sku')
                if sku and sku not in unique_skus:
                    unique_skus[sku] = {
                        'sku': sku,
                        'title': product.get('title') or sku,
                        'brand': product.get('brand') or '',
                        'category': product.get('category') or 'General',
                    }
            
            # Insert new master products
            for sku_data in unique_skus.values():
                if sku_data['sku'] in existing_skus:
                    stats['master_products_skipped'] += 1
                else:
                    cur.execute("""
                        INSERT INTO master_products (
                            sku, title, brand, category, description_status,
                            created_at, v4_migrated_at
                        ) VALUES (?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        sku_data['sku'],
                        sku_data['title'],
                        sku_data['brand'],
                        sku_data['category']
                    ))
                    stats['master_products_added'] += 1
            
            conn.commit()
            
            # =====================================================================
            # Sync Supplier Products
            # =====================================================================
            print("  Syncing supplier products...")
            
            # Build lookups
            cur.execute("SELECT id, supplier_code FROM suppliers")
            suppliers_map = {row[1].lower(): row[0] for row in cur.fetchall()}
            
            cur.execute("SELECT id, sku FROM master_products")
            products_map = {row[1]: row[0] for row in cur.fetchall()}
            
            # Get existing relationships
            cur.execute("""
                SELECT master_product_id, supplier_id FROM supplier_products
            """)
            existing_relationships = {(row[0], row[1]) for row in cur.fetchall()}
            
            # Insert new supplier products
            for product in products:
                sku = product.get('sku')
                supplier_name = product.get('supplier', '').lower()
                
                master_id = products_map.get(sku)
                supplier_id = suppliers_map.get(supplier_name)
                
                if not master_id or not supplier_id:
                    continue
                
                relationship_key = (master_id, supplier_id)
                if relationship_key in existing_relationships:
                    stats['supplier_products_skipped'] += 1
                else:
                    supplier_sku = sku
                    cost = product.get('cost')
                    rrp = product.get('rrp')
                    stock = product.get('stock')
                    
                    # Convert stock to int if needed
                    if isinstance(stock, str):
                        try:
                            stock = int(stock)
                        except (ValueError, TypeError):
                            stock = 1
                    
                    if stock is None:
                        stock = 1
                    
                    cur.execute("""
                        INSERT OR IGNORE INTO supplier_products (
                            master_product_id, supplier_id, supplier_sku,
                            supplier_cost, supplier_rrp, supplier_stock,
                            is_active, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """, (master_id, supplier_id, supplier_sku, cost, rrp, stock))
                    
                    # Track this insertion so in-run duplicates are caught by
                    # the set check on the next iteration, not by the DB constraint
                    existing_relationships.add(relationship_key)
                    stats['supplier_products_added'] += 1
            
            conn.commit()
            
            return stats
            
        finally:
            conn.close()


if __name__ == "__main__":
    # Quick test
    service = MasterProductService()
    
    # Test basic query
    product = service.get_master_product_by_sku("ABC123")
    if product:
        print(f"Found product: {product.title}")
    else:
        print("Product not found")
    
    # Test count
    count = service.count_master_products()
    print(f"Total master products: {count}")
