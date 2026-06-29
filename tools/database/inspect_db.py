#!/usr/bin/env python
"""Inspect current SQLite database structure."""

import sqlite3
from pathlib import Path

# Adjust path for new location in tools/database/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"

if not DB_FILE.exists():
    print(f"❌ Database not found: {DB_FILE}")
    exit(1)

print(f"Database: {DB_FILE}")
print(f"Size: {DB_FILE.stat().st_size / 1024:.1f} KB")
print()

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# Get tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()

print(f"Tables ({len(tables)}):")
for table_name, in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    
    # Get columns
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()
    col_names = [col[1] for col in columns]
    
    print(f"  ✓ {table_name} ({count:,} rows)")
    print(f"    Columns: {', '.join(col_names)}")

# Get indexes
cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
indexes = cur.fetchall()

print()
print(f"Indexes ({len(indexes)}):")
for idx_name, in indexes:
    print(f"  ✓ {idx_name}")

conn.close()
print()
print("✅ Database inspection complete")
