import csv
from pathlib import Path


ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin1",
]


def read_csv(path: Path):
    """
    Read a CSV using several common encodings.
    Returns a list of dictionaries.
    """

    for encoding in ENCODINGS:
        try:
            with open(path, newline="", encoding=encoding) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue

    raise Exception(f"Unable to read CSV: {path}")


def write_csv(path: Path, rows, fieldnames):
    """
    Write a CSV with UTF-8 BOM for Excel compatibility.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def clean(value):
    """
    Safely clean text values.
    """

    if value is None:
        return ""

    return str(value).strip()


def money(value):
    """
    Convert money text into a float.

    Examples:
        "$12.95"
        "12.95"
        "1,234.56"
    """

    value = clean(value)

    if value == "":
        return 0.0

    value = (
        value.replace("$", "")
             .replace(",", "")
             .replace("AUD", "")
             .strip()
    )

    try:
        return float(value)
    except:
        return 0.0


def integer(value):
    """
    Convert text into an integer.
    """

    value = clean(value)

    if value == "":
        return 0

    try:
        return int(float(value))
    except:
        return 0


def first_field(row, names):
    """
    Find the first matching column regardless of capitalisation.

    Example:
        first_field(row, ["SKU","Part Number","Product Code"])
    """

    lookup = {}

    for key in row.keys():
        lookup[key.lower().strip()] = key

    for name in names:
        key = lookup.get(name.lower())

        if key:
            return clean(row[key])

    return ""