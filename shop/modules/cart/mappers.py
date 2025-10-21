from decimal import Decimal, InvalidOperation

from ...core.exceptions import AppError
from ..catalogs.pricing import effective_price


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def _product_info(item, user=None):
    product = getattr(item, "product", None)
    if not product:
        return None, None, None, 0.0, 0.0, None
    product_id = str(product.id) if getattr(product, "id", None) else None
    pricing = effective_price(product, user=user)
    unit_price = _to_float(pricing.get("price")) if isinstance(pricing, dict) else 0.0
    base_price = _to_float(pricing.get("base_price")) if isinstance(pricing, dict) else unit_price
    applied = pricing.get("applied") if isinstance(pricing, dict) else None
    return (
        product_id,
        getattr(product, "name", None),
        getattr(product, "slug", None),
        unit_price,
        base_price,
        applied,
    )


def cart_item_public(item, *, user=None):
    try:
        (
            product_id,
            product_name,
            product_slug,
            unit_price,
            base_price,
            applied,
        ) = _product_info(item, user=user)
        quantity = int(getattr(item, "quantity", 0) or 0)
        total_price = unit_price * quantity
        return {
            "id": item.id,
            "product_id": product_id,
            "product_name": product_name,
            "product_slug": product_slug,
            "unit_price": unit_price,
            "quantity": quantity,
            "total_price": total_price,
            "pricing": {
                "base_price": base_price,
                "price": unit_price,
                "applied": applied,
            }
            if product_id
            else None,
            "created_at": item.created_at.isoformat() if getattr(item, "created_at", None) else None,
            "updated_at": item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to map cart item: {str(exc)}", 500, name="MAPPING_ERROR")


def cart_public(cart):
    try:
        items = [cart_item_public(it, user=getattr(cart, "user", None)) for it in cart.items or []]
        total_quantity = sum(it["quantity"] for it in items)
        subtotal = sum(it["total_price"] for it in items)
        return {
            "id": str(cart.id),
            "user_id": str(cart.user.id) if getattr(cart, "user", None) else None,
            "session_id": getattr(cart, "session_id", None),
            "status": cart.status,
            "items": items,
            "total_quantity": total_quantity,
            "subtotal": subtotal,
            "created_at": cart.created_at.isoformat() if getattr(cart, "created_at", None) else None,
            "updated_at": cart.updated_at.isoformat() if getattr(cart, "updated_at", None) else None,
        }
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to map cart: {str(exc)}", 500, name="MAPPING_ERROR")