#!/usr/bin/env python
"""
DPE Sprint 6 - Milestone 1.1: v4.0 Database Foundation

Safely adds v4.0 foundation tables alongside existing Sprint 4 products table.
Idempotent: safe to run multiple times.
Non-destructive: preserves all existing data.

Architecture: master_products contains ONLY canonical identity data.
All aggregation and scoring fields go in product_intelligence.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Adjust path for new location in tools/database/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    """Check if a table exists."""
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cur.fetchone() is not None


def index_exists(conn, index_name):
    """Check if an index exists."""
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,)
    )
    return cur.fetchone() is not None


def create_master_products_table(conn):
    """Create the master_products foundation table (canonical data only)."""
    if table_exists(conn, "master_products"):
        print("  ✓ master_products already exists (skipping)")
        return
    
    print("  → Creating master_products table...")
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE master_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Core canonical identity (from source data)
            sku TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            
            -- Simple status flags (not calculated)
            description_status TEXT DEFAULT 'Missing',
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            v4_migrated_at TIMESTAMP
        )
    """)
    
    # Indexes for master_products
    if not index_exists(conn, "idx_master_sku"):
        cur.execute("CREATE UNIQUE INDEX idx_master_sku ON master_products (sku)")
    if not index_exists(conn, "idx_master_brand"):
        cur.execute("CREATE INDEX idx_master_brand ON master_products (brand)")
    if not index_exists(conn, "idx_master_category"):
        cur.execute("CREATE INDEX idx_master_category ON master_products (category)")
    
    conn.commit()
    print("  ✓ master_products created with 3 indexes")


def create_product_families_table(conn):
    """Create the product_families foundation table."""
    if table_exists(conn, "product_families"):
        print("  ✓ product_families already exists (skipping)")
        return
    
    print("  → Creating product_families table...")
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE product_families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Family identity
            family_code TEXT NOT NULL UNIQUE,
            family_name TEXT NOT NULL,
            
            -- Family metadata
            parent_sku TEXT,
            family_type TEXT,
            attributes_json TEXT,
            
            -- Metrics
            product_count INTEGER DEFAULT 0,
            active_count INTEGER DEFAULT 0,
            
            -- Lifecycle
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Indexes
    if not index_exists(conn, "idx_family_code"):
        cur.execute("CREATE UNIQUE INDEX idx_family_code ON product_families (family_code)")
    if not index_exists(conn, "idx_family_parent"):
        cur.execute("CREATE INDEX idx_family_parent ON product_families (parent_sku)")
    
    conn.commit()
    print("  ✓ product_families created with 2 indexes")


def create_suppliers_table(conn):
    """Create the suppliers foundation table."""
    if table_exists(conn, "suppliers"):
        print("  ✓ suppliers already exists (skipping)")
        return
    
    print("  → Creating suppliers table...")
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Identity
            supplier_code TEXT NOT NULL UNIQUE,
            supplier_name TEXT NOT NULL,
            
            -- Configuration
            is_enabled BOOLEAN DEFAULT 1,
            priority_rank INTEGER DEFAULT 999,
            
            -- Contact
            contact_email TEXT,
            contact_phone TEXT,
            
            -- Performance metrics
            product_count INTEGER DEFAULT 0,
            avg_cost REAL,
            avg_rrp REAL,
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_import_at TIMESTAMP
        )
    """)
    
    # Indexes
    if not index_exists(conn, "idx_supplier_code"):
        cur.execute("CREATE UNIQUE INDEX idx_supplier_code ON suppliers (supplier_code)")
    if not index_exists(conn, "idx_supplier_enabled"):
        cur.execute("CREATE INDEX idx_supplier_enabled ON suppliers (is_enabled)")
    if not index_exists(conn, "idx_supplier_priority"):
        cur.execute("CREATE INDEX idx_supplier_priority ON suppliers (priority_rank)")
    
    conn.commit()
    print("  ✓ suppliers created with 3 indexes")


def create_supplier_products_table(conn):
    """Create the supplier_products junction table."""
    if table_exists(conn, "supplier_products"):
        print("  ✓ supplier_products already exists (skipping)")
        return
    
    print("  → Creating supplier_products table...")
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE supplier_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Foreign keys
            master_product_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            
            -- Supplier-specific data
            supplier_sku TEXT,
            supplier_cost TEXT,
            supplier_rrp TEXT,
            supplier_stock TEXT,
            
            -- Content
            image_url TEXT,
            description_text TEXT,
            
            -- Status
            is_active BOOLEAN DEFAULT 1,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP,
            
            UNIQUE(master_product_id, supplier_id),
            FOREIGN KEY(master_product_id) REFERENCES master_products(id) ON DELETE CASCADE,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
        )
    """)
    
    # Indexes
    if not index_exists(conn, "idx_sp_master"):
        cur.execute("CREATE INDEX idx_sp_master ON supplier_products (master_product_id)")
    if not index_exists(conn, "idx_sp_supplier"):
        cur.execute("CREATE INDEX idx_sp_supplier ON supplier_products (supplier_id)")
    if not index_exists(conn, "idx_sp_active"):
        cur.execute("CREATE INDEX idx_sp_active ON supplier_products (is_active)")
    
    conn.commit()
    print("  ✓ supplier_products created with 3 indexes")


def create_product_intelligence_table(conn):
    """Create the product_intelligence foundation table (includes aggregations)."""
    if table_exists(conn, "product_intelligence"):
        print("  ✓ product_intelligence already exists (skipping)")
        return
    
    print("  → Creating product_intelligence table...")
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE product_intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Reference
            master_product_id INTEGER NOT NULL UNIQUE,
            
            -- Aggregated pricing (calculated from supplier_products)
            cost_avg REAL,
            cost_min REAL,
            cost_max REAL,
            rrp_avg REAL,
            rrp_min REAL,
            rrp_max REAL,
            
            -- Aggregated inventory (calculated from supplier_products)
            stock_total INTEGER DEFAULT 0,
            stock_suppliers INTEGER DEFAULT 0,
            
            -- Aggregated content metrics (calculated from supplier_products)
            image_count INTEGER DEFAULT 0,
            
            -- Recommendations (from Sprint 4.2.2 logic)
            recommended_supplier_id INTEGER,
            recommendation_score INTEGER DEFAULT 0,
            recommendation_reason TEXT,
            
            -- Scoring components
            supplier_priority_score INTEGER DEFAULT 0,
            stock_availability_score INTEGER DEFAULT 0,
            image_availability_score INTEGER DEFAULT 0,
            description_availability_score INTEGER DEFAULT 0,
            cost_competitiveness_score INTEGER DEFAULT 0,
            
            -- Analysis flags
            has_critical_issues BOOLEAN DEFAULT 0,
            issue_flags_json TEXT,
            
            -- Lifecycle
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            recalculated_at TIMESTAMP,
            
            FOREIGN KEY(master_product_id) REFERENCES master_products(id) ON DELETE CASCADE,
            FOREIGN KEY(recommended_supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        )
    """)
    
    # Indexes
    if not index_exists(conn, "idx_pi_master"):
        cur.execute("CREATE UNIQUE INDEX idx_pi_master ON product_intelligence (master_product_id)")
    if not index_exists(conn, "idx_pi_recommended"):
        cur.execute("CREATE INDEX idx_pi_recommended ON product_intelligence (recommended_supplier_id)")
    if not index_exists(conn, "idx_pi_score"):
        cur.execute("CREATE INDEX idx_pi_score ON product_intelligence (recommendation_score DESC)")
    
    conn.commit()
    print("  ✓ product_intelligence created with 3 indexes")


def migrate():
    """Run the v4.0 migration."""
    print()
    print("=" * 60)
    print("DPE Sprint 6 - Milestone 1.1: v4.0 Database Migration")
    print("=" * 60)
    print()
    
    if not DB_FILE.exists():
        print(f"❌ Database not found: {DB_FILE}")
        print("   Run: python tools/dpe_catalogue_db.py")
        return False
    
    print(f"Database: {DB_FILE}")
    print(f"Size: {DB_FILE.stat().st_size / 1024:.1f} KB")
    print()
    
    conn = get_connection()
    
    try:
        print("Checking existing tables:")
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        existing_tables = [row[0] for row in cur.fetchall()]
        for table in existing_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  ✓ {table} ({count:,} rows)")
        print()
        
        print("Creating v4.0 foundation tables:")
        create_master_products_table(conn)
        create_product_families_table(conn)
        create_suppliers_table(conn)
        create_supplier_products_table(conn)
        create_product_intelligence_table(conn)
        
        print()
        print("✅ Migration complete!")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
