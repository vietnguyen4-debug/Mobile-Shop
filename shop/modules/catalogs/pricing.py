from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

def _active_promos_for_product(product, now, user):
    return []

def _active_user_promos(product, user, now):
    return []

def _find_valid_code(promo_code: str, product, user, now):
    return None

def _apply(promo, base: Decimal):
    discount_type = getattr(promo, "discount_type", None)
    value = getattr(promo, "value", None)
    if discount_type == "percent" and value:
        cut = (base * Decimal(value) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        new_price = base - cut
    elif discount_type == "amount" and value:
        new_price = base - Decimal(value)
    else:
        new_price = base
    if new_price < 0:
        new_price = Decimal("0.00")
    return new_price, promo

def effective_price(product, user=None, promo_code: str | None = None, now=None):
    now = now or datetime.now(timezone.utc)
    base = Decimal(str(product.price or 0)).quantize(Decimal("0.01"))
    candidates = []

    for promo in _active_promos_for_product(product, now, user):
        candidates.append(_apply(promo, base))
    for promo in _active_user_promos(product, user, now):
        candidates.append(_apply(promo, base))
    if promo_code:
        promo = _find_valid_code(promo_code, product, user, now)
        if promo:
            candidates.append(_apply(promo, base))

    if not candidates:
        return {"base_price": str(base), "price": str(base), "applied": None}

    price, promo = min(candidates, key=lambda x: x[0])
    applied = None
    if promo:
        applied = {
            "id": str(getattr(promo, "id", "")),
            "name": getattr(promo, "name", None),
            "ends_at": getattr(promo, "ends_at", None).isoformat() if getattr(promo, "ends_at", None) else None,
        }
    return {"base_price": str(base), "price": str(price), "applied": applied}