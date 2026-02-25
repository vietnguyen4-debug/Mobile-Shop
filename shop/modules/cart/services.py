from uuid import uuid4

from ...core.exceptions import AppError
from ...core.validation import require_fields
from .mappers import cart_public
from .service_helpers import (
    build_identity,
    ensure_cart,
    get_cart,
    find_item_by_id,
    load_product,
    merge_carts,
    parse_quantity,
    remove_item,
    set_item_quantity,
    upsert_item,
)


def s_get_cart(user_id: str | None, session_id: str | None) -> dict:
    generate_session_id: str | None = None
    try:
        if not user_id and not session_id:
            generate_session_id = str(uuid4())
            session_id = generate_session_id

        identity = build_identity(user_id, session_id)
        if identity.user and identity.session_id:
            merged = s_merge_cart_on_login(str(identity.user.id), identity.session_id)
            if merged is not None:
                return merged
        cart = ensure_cart(identity, create=True)
        result = cart_public(cart)
        if generate_session_id and not result.get("session_id"):
            result["session_id"] = generate_session_id
        return result
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to get cart: {str(e)}", 500, name="DATABASE_ERROR")


def s_add_item(user_id: str | None, session_id: str | None, payload: dict) -> dict:
    require_fields(payload, "product_id")
    identifier = str(payload.get("product_id"))
    quantity_value = payload.get("quantity", 1)

    generate_session_id: str | None = None

    try:
        if not user_id and not session_id:
            generate_session_id = str(uuid4())
            session_id = generate_session_id

        identity = build_identity(user_id, session_id)
        quantity = parse_quantity(quantity_value)
        product = load_product(identifier)
        cart = ensure_cart(identity, create=True)
        cart = upsert_item(cart, product, quantity)
        result = cart_public(cart)
        if generate_session_id and not result.get("session_id"):
            result["session_id"] = generate_session_id
        return result
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to add item to cart: {str(e)}", 500, name="DATABASE_ERROR")


def s_update_item(user_id: str | None, session_id: str | None, item_id: str, payload: dict) -> dict:
    require_fields(payload, "quantity")
    quantity_value = payload.get("quantity")

    try:
        identity = build_identity(user_id, session_id)
        cart = ensure_cart(identity, create=False)
        item = find_item_by_id(cart, item_id)
        if not item:
            raise AppError("Cart item not found", 404, name="INVALID_CART_ITEM")
        quantity = parse_quantity(quantity_value, allow_zero=True)
        cart = set_item_quantity(cart, item, quantity)
        return cart_public(cart)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to update cart item: {str(e)}", 500, name="DATABASE_ERROR")


def s_remove_item(user_id: str | None, session_id: str | None, item_id: str) -> dict:
    try:
        identity = build_identity(user_id, session_id)
        cart = ensure_cart(identity, create=False)
        if not find_item_by_id(cart, item_id):
            raise AppError("Cart item not found", 404, name="INVALID_CART_ITEM")
        cart = remove_item(cart, item_id)
        return cart_public(cart)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to remove cart item: {str(e)}", 500, name="DATABASE_ERROR")


def s_merge_cart_on_login(user_id: str, session_id: str | None) -> dict | None:
    if not session_id:
        return None

    try:
        user_identity = build_identity(user_id, None)
        guest_identity = build_identity(None, session_id)
        guest_cart = get_cart(guest_identity, create=False)
        if not guest_cart:
            return None
        user_cart = get_cart(user_identity, create=False)
        merged = merge_carts(user_cart, guest_cart, user_identity.user)
        return cart_public(merged)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to merge carts: {str(e)}", 500, name="DATABASE_ERROR")
