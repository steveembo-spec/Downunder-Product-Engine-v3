import csv
import html
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


PROJECT_ROOT = Path(__file__).resolve().parent

MISSING_REPORT = PROJECT_ROOT / "output" / "missing_images_report.csv"
IMAGE_LIBRARY = PROJECT_ROOT / "output" / "image_urls.csv"
DISCOVERY_OUTPUT = PROJECT_ROOT / "output" / "image_library" / "discovered_image_urls.csv"

TEST_LIMIT = 50
REQUEST_DELAY_SECONDS = 1.5

BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "pinterest.com",
    "youtube.com",
    "ebay.com",
    "amazon.com",
}


def read_csv(path):
    if not path.exists():
        return []

    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_image_library(rows):
    existing = read_csv(IMAGE_LIBRARY)
    existing_skus = {
        str(row.get("SKU") or row.get("sku") or "").strip().upper()
        for row in existing
    }

    new_rows = []

    for row in rows:
        sku = row["sku"].strip().upper()

        if sku and sku not in existing_skus:
            new_rows.append({
                "SKU": sku,
                "Image URL": row["image_url"],
                "Image Source": row["source"],
            })
            existing_skus.add(sku)

    if not new_rows:
        print("No new image rows to append.")
        return 0

    IMAGE_LIBRARY.parent.mkdir(parents=True, exist_ok=True)

    file_exists = IMAGE_LIBRARY.exists()

    with open(IMAGE_LIBRARY, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["SKU", "Image URL", "Image Source"],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(new_rows)

    return len(new_rows)


def fetch_url(url, timeout=8):
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-AU,en;q=0.9",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def clean_url(value):
    value = html.unescape(str(value or "").strip())
    value = value.strip("\"' ")

    if value.startswith("//"):
        value = "https:" + value

    return value


def is_blocked_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def looks_like_image(url):
    lower = url.lower()
    return any(
        ext in lower
        for ext in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ]
    )


def extract_og_image(page_html):
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.IGNORECASE)

        if match:
            image_url = clean_url(match.group(1))

            if image_url and looks_like_image(image_url):
                return image_url

    return ""


def extract_first_product_image(page_html):
    image_matches = re.findall(
        r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
        page_html,
        re.IGNORECASE,
    )

    for image_url in image_matches:
        image_url = clean_url(image_url)

        lower = image_url.lower()

        if not looks_like_image(image_url):
            continue

        if any(skip in lower for skip in ["logo", "icon", "sprite", "payment", "placeholder"]):
            continue

        return image_url

    return ""


def search_duckduckgo(query):
    search_url = "https://duckduckgo.com/html/?q=" + quote_plus(query)

    try:
        page = fetch_url(search_url)
    except Exception:
        return []

    links = re.findall(
        r'<a rel="nofollow" class="result__a" href="([^"]+)"',
        page,
        re.IGNORECASE,
    )

    cleaned = []

    for link in links:
        link = html.unescape(link)

        if "uddg=" in link:
            match = re.search(r"uddg=([^&]+)", link)
            if match:
                from urllib.parse import unquote
                link = unquote(match.group(1))

        if link.startswith("http") and not is_blocked_url(link):
            cleaned.append(link)

    return cleaned[:5]


def find_image_for_product(product):
    sku = str(product.get("sku", "")).strip()
    title = str(product.get("title", "")).strip()

    if not sku:
        return None

    query = f'"{sku}" "{title}" motorcycle product image'

    links = search_duckduckgo(query)

    for link in links:
        try:
            page = fetch_url(link)
        except (HTTPError, URLError, TimeoutError, Exception):
            continue

        image_url = extract_og_image(page) or extract_first_product_image(page)

        if image_url:
            return {
                "sku": sku,
                "title": title,
                "supplier": product.get("supplier", ""),
                "image_url": image_url,
                "source": urlparse(link).netloc,
                "product_page": link,
            }

    return None


def main():
    print("=" * 60)
    print("DPE FAST IMAGE DISCOVERY")
    print("=" * 60)

    missing = read_csv(MISSING_REPORT)

    if not missing:
        print(f"No missing image report found: {MISSING_REPORT}")
        return

    print(f"Missing rows loaded: {len(missing):,}")
    print(f"Test limit: {TEST_LIMIT:,}")

    found = []

    for index, product in enumerate(missing[:TEST_LIMIT], start=1):
        sku = product.get("sku", "")
        title = product.get("title", "")

        print(f"[{index}/{TEST_LIMIT}] Searching {sku} - {title[:60]}")

        result = find_image_for_product(product)

        if result:
            found.append(result)
            print(f"  FOUND: {result['image_url']}")
        else:
            print("  Not found")

        time.sleep(REQUEST_DELAY_SECONDS)

    write_csv(
        DISCOVERY_OUTPUT,
        found,
        [
            "sku",
            "title",
            "supplier",
            "image_url",
            "source",
            "product_page",
        ],
    )

    appended = append_image_library(found)

    print("-" * 60)
    print(f"Images found: {len(found):,}")
    print(f"Images appended to image_urls.csv: {appended:,}")
    print(f"Discovery output: {DISCOVERY_OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()