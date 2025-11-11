from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ...core.exceptions import AppError
from ...core.utils import parse_oid
from ..users.models import User
from ..catalogs.models import Product
from ..catalogs.service_helpers import find_by_slug_or_id
from .models import Cart, CartItem
from . import repositories as repo


@dataclass
class CartIdentity:
    user: Optional[User]
    session_id: Optional[str]


def _normalize_session_id(session_id: Optional[str]) -> Optional[str]:
    if session_id is None:
        return None
    if not isinstance(session_id, str):
        raise AppError("Invalid session identifier", 400, name="INVALID_SESSION")
    sid = session_id.strip()
    if not sid:
        return None
    if len(sid) > 120:
        raise AppError("Session identifier too long", 400, name="INVALID_SESSION")
    return sid


def _load_user(user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    oid = parse_oid(str(user_id))
    if not oid:
        raise AppError("Invalid user ID", 400, name="INVALID_USER")
    try:
        user = User.objects(id=oid).first()
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to retrieve user: {str(exc)}", 500, name="DATABASE_ERROR")
    if not user:
        raise AppError("User not found", 404, name="INVALID_USER")
    return user


def build_identity(user_id: Optional[str], session_id: Optional[str]) -> CartIdentity:
    user = _load_user(user_id)
    sid = _normalize_session_id(session_id)
    if not user and not sid:
        raise AppError("Missing cart identity", 400, name="MISSING_CART_IDENTITY")
    return CartIdentity(user=user, session_id=sid)


def _save_cart(cart: Cart, *, message: str) -> Cart:
    try:
        return repo.cart_save(cart)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"{message}: {str(exc)}", 500, name="DATABASE_ERROR")


def get_cart(identity: CartIdentity, *, create: bool = False) -> Optional[Cart]:
    try:
        cart = repo.cart_get_active_by_user(identity.user) if identity.user else None
        if not cart and identity.session_id:
            cart = repo.cart_get_active_by_session(identity.session_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to retrieve cart: {str(exc)}", 500, name="DATABASE_ERROR")

    if cart or not create:
        return cart

    data: dict[str, Any] = {"items": [], "status": "active"}
    if identity.user:
        data["user"] = identity.user
    if identity.session_id:
        data["session_id"] = identity.session_id

    try:
        return repo.cart_create(data)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to create cart: {str(exc)}", 500, name="DATABASE_ERROR")


def ensure_cart(identity: CartIdentity, *, create: bool = True) -> Cart:
    cart = get_cart(identity, create=create)
    if not cart:
        raise AppError("Cart not found", 404, name="INVALID_CART")
    # If this is a logged-in user's cart, drop stale session_id to avoid
    # propagating guest session cookies in user flow.
    if identity.user and getattr(cart, "session_id", None):
        cart.session_id = None
        cart = _save_cart(cart, message="Failed to save cart")
    return cart


def parse_quantity(value, *, allow_zero: bool = False) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise AppError("Quantity must be a number", 400, name="INVALID_QUANTITY")
    if quantity < 0 or (quantity == 0 and not allow_zero):
        raise AppError("Quantity must be greater than zero", 400, name="INVALID_QUANTITY")
    return quantity


def load_product(identifier: str) -> Product:
    try:
        product = find_by_slug_or_id("product", identifier, invalid_id_400=True)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to load product: {str(exc)}", 500, name="DATABASE_ERROR")

    if not product or not getattr(product, "is_active", True):
        raise AppError("Product is not available", 400, name="PRODUCT_UNAVAILABLE")
    return product


def find_item_by_id(cart: Cart, item_id: str) -> Optional[CartItem]:
    if not item_id:
        return None
    for item in cart.items or []:
        if item.id == item_id:
            return item
    return None


def find_item_by_product(cart: Cart, product: Product) -> Optional[CartItem]:
    if not product:
        return None
    product_id = str(product.id)
    for item in cart.items or []:
        if item.product and str(item.product.id) == product_id:
            return item
    return None


def _touch_item(item: CartItem) -> None:
    item.updated_at = datetime.now(timezone.utc)


def upsert_item(cart: Cart, product: Product, quantity: int) -> Cart:
    existing = find_item_by_product(cart, product)
    if existing:
        existing.quantity += quantity
        if existing.quantity < 1:
            existing.quantity = 1
        _touch_item(existing)
    else:
        now = datetime.now(timezone.utc)
        new_item = CartItem(product=product, quantity=quantity)
        new_item.created_at = now
        new_item.updated_at = now
        if not cart.items:
            cart.items = []
        cart.items.append(new_item)
    return _save_cart(cart, message="Failed to save cart")


def set_item_quantity(cart: Cart, item: CartItem, quantity: int) -> Cart:
    if quantity <= 0:
        cart.items = [it for it in cart.items or [] if it.id != item.id]
    else:
        item.quantity = quantity
        _touch_item(item)
    return _save_cart(cart, message="Failed to update cart item")


def remove_item(cart: Cart, item_id: str) -> Cart:
    cart.items = [it for it in cart.items or [] if it.id != item_id]
    return _save_cart(cart, message="Failed to remove cart item")


def merge_carts(user_cart: Optional[Cart], guest_cart: Cart, user: User) -> Cart:
    if not guest_cart:
        raise AppError("Guest cart not found", 404, name="INVALID_CART")

    if not user_cart:
        guest_cart.user = user
        guest_cart.session_id = None
        guest_cart.status = "active"
        return _save_cart(guest_cart, message="Failed to assign guest cart to user")

    existing_map: dict[str, CartItem] = {}
    for item in user_cart.items or []:
        if item.product:
            existing_map[str(item.product.id)] = item

    for guest_item in guest_cart.items or []:
        if not guest_item.product or guest_item.quantity <= 0:
            continue
        key = str(guest_item.product.id)
        target = existing_map.get(key)
        if target:
            target.quantity += guest_item.quantity
            _touch_item(target)
        else:
            clone = CartItem(product=guest_item.product, quantity=guest_item.quantity)
            clone.created_at = guest_item.created_at or datetime.now(timezone.utc)
            clone.updated_at = datetime.now(timezone.utc)
            user_cart.items = list(user_cart.items or [])
            user_cart.items.append(clone)
            existing_map[key] = clone

    # Ensure user cart does not carry session_id in logged-in flow
    user_cart.user = user
    user_cart.session_id = None
    saved = _save_cart(user_cart, message="Failed to merge carts")

    try:
        repo.cart_delete(guest_cart)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to remove guest cart: {str(exc)}", 500, name="DATABASE_ERROR")

    return saved
