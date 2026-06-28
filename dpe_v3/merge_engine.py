from dpe_v3.config import SUPPLIER_PRIORITY


def stock_score(value):
    value = str(value).strip().lower()

    if value in ["in stock", "available", "yes", "true"]:
        return 100

    if value in ["out of stock", "unavailable", "no", "false", "n/a"]:
        return 0

    try:
        return int(float(value))
    except:
        return 0


def choose_best_supplier(existing, candidate):
    existing_stock = stock_score(existing.get("stock", ""))
    candidate_stock = stock_score(candidate.get("stock", ""))

    existing_priority = SUPPLIER_PRIORITY.get(existing.get("supplier"), 999)
    candidate_priority = SUPPLIER_PRIORITY.get(candidate.get("supplier"), 999)

    existing_cost = existing.get("cost", 0) or 0
    candidate_cost = candidate.get("cost", 0) or 0

    if candidate_stock > existing_stock:
        return candidate

    if candidate_stock == existing_stock:
        if candidate_priority < existing_priority:
            return candidate

        if candidate_cost > 0 and existing_cost > 0 and candidate_cost < existing_cost:
            return candidate

    return existing


def merge_duplicate_skus(products):
    merged = {}

    for product in products:
        sku = product["sku"]

        if sku not in merged:
            product["supplier_options"] = [product["supplier"]]
            merged[sku] = product
        else:
            existing = merged[sku]

            supplier_options = set(existing.get("supplier_options", []))
            supplier_options.add(product["supplier"])

            best = choose_best_supplier(existing, product)
            best["supplier_options"] = sorted(supplier_options)

            merged[sku] = best

    return list(merged.values())