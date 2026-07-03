import sqlite3

from core.paths import get_database_path


def _empty_dashboard(error_text: str = "") -> dict:
    return {
        "products": "0",
        "suppliers": "0",
        "missing_price": "0",
        "missing_image": "0",
        "missing_description": "0",
        "products_by_supplier": [],
        "latest_suppliers": [],
        "status": "DB OFFLINE",
        "run_date": "Never",
        "error": error_text,
    }


def _to_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def load_dashboard():
    db_file = get_database_path()
    if not db_file.exists():
        return _empty_dashboard(f"Database not found: {db_file}")

    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM master_products")
        total_products = _to_int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM suppliers")
        total_suppliers = _to_int(cur.fetchone()[0])

        cur.execute(
            """
            WITH supplier_fallbacks AS (
                SELECT
                    sp.master_product_id,
                    MAX(CASE WHEN sp.is_active = 1 AND CAST(sp.supplier_rrp AS REAL) > 0 THEN 1 ELSE 0 END) AS has_supplier_rrp,
                    MAX(CASE WHEN sp.is_active = 1 AND CAST(sp.supplier_cost AS REAL) > 0 THEN 1 ELSE 0 END) AS has_supplier_cost,
                    MAX(CASE WHEN sp.is_active = 1 AND TRIM(COALESCE(sp.image_url, '')) != '' THEN 1 ELSE 0 END) AS has_supplier_image,
                    MAX(CASE WHEN sp.is_active = 1 AND TRIM(COALESCE(sp.description_text, '')) != '' THEN 1 ELSE 0 END) AS has_supplier_description
                FROM supplier_products sp
                GROUP BY sp.master_product_id
            )
            SELECT COUNT(*)
            FROM master_products mp
            LEFT JOIN supplier_fallbacks sf ON sf.master_product_id = mp.id
                        WHERE (COALESCE(mp.rrp_max, mp.rrp_avg) IS NULL OR COALESCE(mp.rrp_max, mp.rrp_avg) <= 0)
                            AND COALESCE(sf.has_supplier_rrp, 0) = 0
                            AND COALESCE(sf.has_supplier_cost, 0) = 0
            """
        )
        missing_price = _to_int(cur.fetchone()[0])

        cur.execute(
            """
            WITH supplier_fallbacks AS (
                SELECT
                    sp.master_product_id,
                    MAX(CASE WHEN sp.is_active = 1 AND TRIM(COALESCE(sp.image_url, '')) != '' THEN 1 ELSE 0 END) AS has_supplier_image
                FROM supplier_products sp
                GROUP BY sp.master_product_id
            )
            SELECT COUNT(*)
            FROM master_products mp
            LEFT JOIN supplier_fallbacks sf ON sf.master_product_id = mp.id
            WHERE COALESCE(mp.image_count, 0) <= 0
              AND COALESCE(sf.has_supplier_image, 0) = 0
            """
        )
        missing_image = _to_int(cur.fetchone()[0])

        cur.execute(
            """
            WITH supplier_fallbacks AS (
                SELECT
                    sp.master_product_id,
                    MAX(CASE WHEN sp.is_active = 1 AND TRIM(COALESCE(sp.description_text, '')) != '' THEN 1 ELSE 0 END) AS has_supplier_description
                FROM supplier_products sp
                GROUP BY sp.master_product_id
            )
            SELECT COUNT(*)
            FROM master_products mp
            LEFT JOIN supplier_fallbacks sf ON sf.master_product_id = mp.id
            WHERE (
                    mp.description_status IS NULL
                 OR TRIM(mp.description_status) = ''
                 OR LOWER(mp.description_status) IN ('missing', 'pending', 'none', 'default')
                  )
              AND COALESCE(sf.has_supplier_description, 0) = 0
            """
        )
        missing_description = _to_int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT s.supplier_name, COUNT(*) AS product_count
            FROM supplier_products sp
            JOIN suppliers s ON s.id = sp.supplier_id
            GROUP BY s.id, s.supplier_name
            ORDER BY product_count DESC, s.supplier_name
            """
        )
        products_by_supplier = [
            {
                "supplier_name": str(row[0]),
                "product_count": _to_int(row[1]),
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                s.supplier_name,
                COALESCE(last_import_at, updated_at, created_at) AS latest_ts,
                COALESCE(spc.product_count, 0) AS product_count
            FROM suppliers s
            LEFT JOIN (
                SELECT supplier_id, COUNT(*) AS product_count
                FROM supplier_products
                GROUP BY supplier_id
            ) spc ON spc.supplier_id = s.id
            ORDER BY latest_ts DESC, s.supplier_name
            LIMIT 5
            """
        )
        latest_suppliers = [
            {
                "supplier_name": str(row[0]),
                "latest_ts": str(row[1]) if row[1] else "Unknown",
                "product_count": _to_int(row[2]),
            }
            for row in cur.fetchall()
        ]

        run_date = latest_suppliers[0]["latest_ts"] if latest_suppliers else "Unknown"

        return {
            "products": str(total_products),
            "suppliers": str(total_suppliers),
            "missing_price": str(missing_price),
            "missing_image": str(missing_image),
            "missing_description": str(missing_description),
            "products_by_supplier": products_by_supplier,
            "latest_suppliers": latest_suppliers,
            "status": "LIVE DB",
            "run_date": run_date,
            "error": "",
        }

    except Exception as exc:
        return _empty_dashboard(str(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass