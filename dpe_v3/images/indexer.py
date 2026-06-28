import re


def normalise_sku(value):
    value = str(value or "").upper().strip()
    return re.sub(r"[^A-Z0-9]", "", value)


def build_index(records):
    index = {}

    for record in records:
        key = normalise_sku(record.sku)

        if key and key not in index:
            index[key] = record

    return index