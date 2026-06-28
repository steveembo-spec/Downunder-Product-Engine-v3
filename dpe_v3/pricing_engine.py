def calculate_price(product):
    rrp = product.get("rrp", 0) or 0
    cost = product.get("cost", 0) or 0

    # Main rule: use supplier RRP where available
    if rrp > 0:
        return round(rrp, 2)

    # Fallback only if RRP is missing
    if cost <= 0:
        return 0.0

    if cost < 20:
        return round(cost * 1.8, 2)

    if cost < 100:
        return round(cost * 1.55, 2)

    if cost < 300:
        return round(cost * 1.4, 2)

    return round(cost * 1.3, 2)


def inventory_quantity(stock):
    stock_text = str(stock).strip().lower()

    if stock_text in ["in stock", "available", "yes", "true"]:
        return 10

    if stock_text in ["out of stock", "unavailable", "no", "false", "n/a"]:
        return 0

    try:
        return int(float(stock_text))
    except:
        return 0


def apply_business_rules(products):
    ruled = []

    for product in products:
        product["shopify_price"] = calculate_price(product)
        product["inventory_quantity"] = inventory_quantity(product.get("stock", ""))
        product["status"] = "draft"

        ruled.append(product)

    return ruled