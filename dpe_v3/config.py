from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"

A1_FILE = INPUT_DIR / "A1" / "A1 pricefile.csv"
CASSONS_FILE = INPUT_DIR / "Cassons" / "Cassons.csv"
SERCO_FILE = INPUT_DIR / "Serco" / "Serco.csv"

IMAGE_LIBRARY_FILE = OUTPUT_DIR / "image_urls.csv"

IMAGE_LIBRARY_DIR = OUTPUT_DIR / "image_library"
IMAGE_LIBRARY_V3_FILE = IMAGE_LIBRARY_DIR / "image_library_v3.csv"
IMAGE_LIBRARY_CACHE_DIR = IMAGE_LIBRARY_DIR / "cache"
IMAGE_LIBRARY_DOWNLOADS_DIR = IMAGE_LIBRARY_DIR / "downloads"

LEGACY_DESCRIPTION_FILES = [
    OUTPUT_DIR / "shopify_import_smart.csv",
    OUTPUT_DIR / "shopify_import.csv",
]

SHOPIFY_STATUS = "draft"

SUPPLIER_PRIORITY = {
    "A1": 1,
    "Cassons": 2,
    "Serco": 3,
}

DEFAULT_VENDOR = "Downunder Dirtbikes"