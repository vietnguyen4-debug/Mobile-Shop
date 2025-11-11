from bson.errors import InvalidId
from mongoengine import ValidationError as MongoValidationError

from .mappers import _media_public, _spec_public
from .service_helpers import *
from .service_helpers import _invalidate_category_cache, _versioned_make_name, _category_item_version, \
    _category_list_version, _invalidate_product_cache, _safe_get_category_by_id, _invalidate_subcategory_cache, \
    _subcategory_item_version, _subcategory_by_category_version, _safe_parse_oid, _parse_and_get_subcategory, \
    _validate_category_subcategory_relation, _build_media, _build_specs,  \
    _product_list_version, _product_item_version, _product_list_by_sub_version, \
    _product_media_version, _normalize_media_embedded, _normalize_specs_embedded, _product_spec_version, \
    _invalidate_keyword_cache, _product_suggest_version, _invalidate_product_with_ids, _validate_product_instance
from ...core.validation import require_fields
from ...core.utils import *
from .repositories import *
from .mappers import *
from .models import Product
from ...extensions import cache


# ---- CATEGORY ----
def s_category_create(payload: dict) -> dict:
    require_fields(payload, "name")
    name = payload["name"].strip()
    slug = slugify(name)

    try:
        ensure_unique_slug(Category, slug)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to validate slug: {str(e)}", 500, name="DATABASE_ERROR")

    try:
        if Category.objects(slug=slug).first():
            raise AppError("Name already used", 409, name="INVALID_CATEGORY")
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to check category existence: {str(e)}", 500, name="DATABASE_ERROR")

    try:
        c = cat_insert({
            "name": name,
            "slug": slug,
            "icon": payload.get("icon"),
            "description": payload.get("description"),
            "hot": bool(payload.get("hot", False)),
        })
        result = cat_public(c)
        _invalidate_category_cache(result.get("slug"), result.get("id"))
        return result
    except Exception as e:
        raise AppError(f"Failed to create category: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_category_item_version),
)
def s_category_get(slug_or_id: str) -> dict:
    try:
        c = find_by_slug_or_id("category", slug_or_id)
        return cat_public(c)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to retrieve category: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_category_list_version),
)
def s_category_list() -> dict:
    try:
        return {"items": [cat_public(c) for c in cat_list_all()]}
    except Exception as e:
        raise AppError(f"Failed to list categories: {str(e)}", 500, name="DATABASE_ERROR")


def s_category_update(slug_or_id: str, payload: dict) -> dict:
    try:
        c = find_by_slug_or_id("category", slug_or_id)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to find category: {str(e)}", 500, name="DATABASE_ERROR")

    original_slug = getattr(c, "slug", None)
    original_id = str(getattr(c, "id", ""))

    data = {}
    if "name" in payload and payload["name"]:
        name = payload["name"].strip()
        try:
            if name and name != c.name and Category.objects(name=name).first():
                raise AppError("Name already used", 409, name="INVALID_CATEGORY")
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Failed to check name uniqueness: {str(e)}", 500, name="DATABASE_ERROR")
        data["name"] = name
        data["slug"] = slugify(name)

    for k in ("icon", "description", "hot"):
        if k in payload:
            data[k] = payload[k]

    try:
        c = cat_update(c, data)
        result = cat_public(c)
        _invalidate_category_cache(
            slug_or_id,
            original_slug,
            original_id,
            result.get("slug"),
            result.get("id"),
        )
        return result
    except Exception as e:
        raise AppError(f"Failed to update category: {str(e)}", 500, name="DATABASE_ERROR")


def s_category_delete(slug_or_id: str) -> None:
    try:
        c = find_by_slug_or_id("category", slug_or_id)
        slug = getattr(c, "slug", None)
        cid = str(getattr(c, "id", ""))
        mark_products_orphan_by_category(c.id)
        cat_delete(c)
        _invalidate_category_cache(slug_or_id, slug, cid)
        _invalidate_product_cache(
            category_ids=[cid] if cid else None,
            segments=["core"],
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to delete category: {str(e)}", 500, name="DATABASE_ERROR")


# ----SUBCATEGORY-----
def s_subcategory_create(payload: dict) -> dict:
    require_fields(payload, "name", "category_id")
    name = payload["name"].strip()

    cat = _safe_get_category_by_id(payload["category_id"])
    slug = payload.get("slug") or slugify(name, prefix=cat.slug)

    try:
        ensure_unique_slug(SubCategory, slug)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to validate slug: {str(e)}", 500, name="DATABASE_ERROR")

    try:
        s = sub_insert({
            "name": name,
            "slug": slug,
            "icon": payload.get("icon"),
            "category": cat,
            "description": payload.get("description"),
        })
        result = sub_public(s)
        _invalidate_subcategory_cache(
            result.get("slug"),
            result.get("id"),
            category_ids=[str(cat.id) if cat else None],
        )
        return result
    except Exception as e:
        raise AppError(f"Failed to create subcategory: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_subcategory_item_version),
)
def s_subcategory_get(slug_or_id: str) -> dict:
    try:
        s = find_by_slug_or_id("subcategory", slug_or_id)
        return sub_public(s)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to retrieve subcategory: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_subcategory_by_category_version),
)
def s_subcategory_list_by_category(category_id: str) -> dict:
    cat_oid = _safe_parse_oid(category_id, "Category")

    try:
        return {"items": [sub_public(s) for s in sub_list_by_category(cat_oid)]}
    except Exception as e:
        raise AppError(f"Failed to list subcategories: {str(e)}", 500, name="DATABASE_ERROR")


def s_subcategory_update(slug_or_id: str, payload: dict) -> dict:
    try:
        s = find_by_slug_or_id("subcategory", slug_or_id)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to find subcategory: {str(e)}", 500, name="DATABASE_ERROR")

    original_slug = getattr(s, "slug", None)
    original_id = str(getattr(s, "id", ""))
    original_cat_id = str(getattr(getattr(s, "category", None), "id", "")) if getattr(s, "category", None) else None

    data = {}
    if "name" in payload:
        data["name"] = payload["name"].strip()

    new_cat = s.category
    if "category_id" in payload:
        if payload["category_id"] is None:
            raise AppError("Category cannot be null", 400, name="INVALID_CATEGORY")

        new_cat = _safe_get_category_by_id(payload["category_id"])
        data["category"] = new_cat

    if "name" in data or ("category" in data and data["category"] != s.category):
        base_name = data.get("name", s.name)
        cat_for_slug = data.get("category", new_cat)
        data["slug"] = slugify(base_name, prefix=cat_for_slug.slug)
        try:
            ensure_unique_slug(SubCategory, data["slug"])
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Failed to validate slug: {str(e)}", 500, name="DATABASE_ERROR")

    for k in ("icon", "description", "hot"):
        if k in payload:
            data[k] = payload[k]

    try:
        s = sub_update(s, data)
        result = sub_public(s)
        new_cat_id = result.get("category_id")
        category_ids = list({cid for cid in [original_cat_id, new_cat_id] if cid}) or None
        _invalidate_subcategory_cache(
            slug_or_id,
            original_slug,
            original_id,
            result.get("slug"),
            result.get("id"),
            category_ids=category_ids,
        )
        return result
    except Exception as e:
        raise AppError(f"Failed to update subcategory: {str(e)}", 500, name="DATABASE_ERROR")


def s_subcategory_delete(slug_or_id: str) -> None:
    try:
        s = find_by_slug_or_id("subcategory", slug_or_id)
        slug = getattr(s, "slug", None)
        sid = str(getattr(s, "id", ""))
        cat_id = str(getattr(getattr(s, "category", None), "id", "")) if getattr(s, "category", None) else None
        mark_products_orphan_by_subcategory(s.id)
        sub_delete(s)
        category_ids = [cid for cid in [cat_id] if cid] or None
        _invalidate_subcategory_cache(
            slug_or_id,
            slug,
            sid,
            category_ids=category_ids,
        )
        _invalidate_product_cache(
            subcategory_ids=[sid] if sid else None,
            category_ids=category_ids,
            segments=["core"],
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to delete subcategory: {str(e)}", 500, name="DATABASE_ERROR")


# -----PRODUCT-----
def s_product_create(payload: dict) -> dict:
    require_fields(payload, "name", "price")
    name = payload["name"].strip()
    try:
        price = float(payload["price"])
    except (ValueError, TypeError) as e:
        raise AppError(f"Price must be a valid number: {str(e)}", 400, name="INVALID_PRICE")

    if price < 0:
        raise AppError("Price must be positive", 400, name="INVALID_PRICE")

    cat = sub = None
    if "category_id" in payload:
        cat = _safe_get_category_by_id(payload["category_id"])

    if "subcategory_id" in payload:
        sub = _parse_and_get_subcategory(payload["subcategory_id"], cat)

    _validate_category_subcategory_relation(cat, sub)

    slug = slugify(name)
    try:
        ensure_unique_slug(Product, slug)
    except Exception as e:
        raise AppError(f"Failed to validate slug uniqueness: {str(e)}", 500, name="DATABASE_ERROR")

    try:
        media = _build_media(payload.get("media"))
        specs = _build_specs(payload.get("specs"))
    except (ValueError, TypeError, KeyError) as e:
        raise AppError(f"Invalid media or specs format: {str(e)}", 400, name="INVALID_FORMAT")

    if len(media) > MAX_MEDIA:
        raise AppError(f"Too many media items (max {MAX_MEDIA})", 400, name="INVALID_MEDIA")
    if len(specs) > MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")

    try:
        p = prod_insert({
            "name": name,
            "slug": slug,
            "price": price,
            "description": payload.get("description"),
            "category": cat,
            "subcategory": sub,
            "media": media,
            "specs": specs,
            "is_active": payload.get("is_active", True),
            "is_orphan": payload.get("is_orphan", False),
            "orphan_reason": payload.get("orphan_reason", None),
        })
        result = product_public(p)

        # Only invalidate page 1 - new products appear at the top
        _invalidate_product_with_ids(
            result.get("slug"),
            p,
            ["core", "media", "specs"],
            result.get("id"),
            affected_pages=[1],
            invalidate_all_pages=False,
        )
        return result
    except MongoValidationError as e:
        raise AppError(f"Database validation error: {str(e)}", 400, name="VALIDATION_ERROR")
    except Exception as e:
        raise AppError(f"Failed to create product: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_item_version),
)
def s_product_get(slug_or_id: str) -> dict:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        return product_public(p)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to retrieve product: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_list_version),
)
def s_product_list(page, limit) -> dict:
    try:
        p, l = parse_pagination(page, limit)
    except (ValueError, TypeError) as e:
        raise AppError(f"Invalid pagination parameters: {str(e)}", 400, name="INVALID_PAGINATION")

    try:
        items, total = prod_list_all(p, l)
        return {"items": [product_public(x) for x in items], "total": total, "page": p, "limit": l}
    except Exception as e:
        raise AppError(f"Failed to retrieve products: {str(e)}", 500, name="DATABASE_ERROR")


@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_list_by_sub_version),
)
def s_product_list_by_sub(sub_id, page, limit, *, active_only=True) -> dict:
    try:
        p, l = parse_pagination(page, limit)
    except (ValueError, TypeError) as e:
        raise AppError(f"Invalid pagination parameters: {str(e)}", 400, name="INVALID_PAGINATION")

    try:
        sub_oid = parse_oid(sub_id)
    except (InvalidId, Exception):
        return {"items": [], "total": 0, "page": p, "limit": l}

    if not sub_oid:
        return {"items": [], "total": 0, "page": p, "limit": l}

    try:
        items, total = prod_list_by_sub(sub_oid, p, l, active_only=active_only)
        return {"items": [product_public(x) for x in items], "total": total, "page": p, "limit": l}
    except Exception as e:
        raise AppError(f"Failed to retrieve products: {str(e)}", 500, name="DATABASE_ERROR")


def s_product_update(slug_or_id: str, payload: dict) -> dict:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to find product: {str(e)}", 500, name="DATABASE_ERROR")

    original_slug = getattr(p, "slug", None)
    original_id = str(getattr(p, "id", ""))
    original_cat_id = (
        str(getattr(getattr(p, "category", None), "id", ""))
        if getattr(p, "category", None)
        else None
    )
    original_sub_id = (
        str(getattr(getattr(p, "subcategory", None), "id", ""))
        if getattr(p, "subcategory", None)
        else None
    )

    data = {}
    need_new_slug = False
    if "name" in payload and payload["name"]:
        data["name"] = payload["name"].strip()

    if "price" in payload:
        try:
            price = float(payload["price"])
        except (ValueError, TypeError) as e:
            raise AppError(f"Price must be a valid number: {str(e)}", 400, name="INVALID_PRICE")

        if price < 0:
            raise AppError("Price must be positive", 400, name="INVALID_PRICE")
        data["price"] = price

    cat = p.category
    sub = p.subcategory

    if "category_id" in payload:
        if payload["category_id"] is None:
            cat = None
        else:
            cat = _safe_get_category_by_id(payload["category_id"])
            need_new_slug = True

    if "subcategory_id" in payload:
        if payload["subcategory_id"] is None:
            sub = None
        else:
            sub = _parse_and_get_subcategory(payload["subcategory_id"], cat)
            need_new_slug = True

    _validate_category_subcategory_relation(cat, sub)

    data["category"] = cat
    data["subcategory"] = sub

    if need_new_slug or ("category_id" in payload) or ("subcategory_id" in payload):
        base = data.get("name", p.name)
        prefix = sub.slug if sub else (cat.slug if cat else None)
        data["slug"] = slugify(base, prefix=prefix)

    for k in ("description", "is_active"):
        if k in payload:
            data[k] = payload[k]

    if data["category"] is None or data["subcategory"] is None:
        data["is_orphan"] = True
        data["is_active"] = False
        data["orphan_reason"] = "invalid_link"
    else:
        data["is_orphan"] = False
        data["orphan_reason"] = None

    try:
        p = prod_update(p, data)
        result = product_public(p)
        _invalidate_product_with_ids(
            slug_or_id,
            p,
            ["core"],
            original_slug,
            original_id,
            result.get("slug"),
            result.get("id"),
            additional_cat_ids=[original_cat_id] if original_cat_id else None,
            additional_sub_ids=[original_sub_id] if original_sub_id else None,
        )
        return result
    except MongoValidationError as e:
        raise AppError(f"Database validation error: {str(e)}", 400, name="VALIDATION_ERROR")
    except Exception as e:
        raise AppError(f"Failed to update product: {str(e)}", 500, name="DATABASE_ERROR")


def s_product_delete(slug_or_id: str) -> None:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        slug = getattr(p, "slug", None)
        pid = str(getattr(p, "id", ""))

        prod_delete(p)

        # Delete affects all pages (items shift)
        _invalidate_product_with_ids(
            slug_or_id,
            p,
            ["core", "media", "specs"],
            slug,
            pid,
            invalidate_all_pages=True,  # Delete affects pagination
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to delete product: {str(e)}", 500, name="DATABASE_ERROR")


# ------MEDIA-------
@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_media_version),
)
def s_media_list(slug_or_id: str) -> dict:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        p = _normalize_media_embedded(p)
        return {"items": [_media_public(m) for m in p.media]}
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to list media: {str(e)}", 500, name="DATABASE_ERROR")


def s_media_add(slug_or_id: str, payload: dict):
    require_fields(payload, "kind", "url")
    try:
        p = find_by_slug_or_id("product", slug_or_id)
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to find product: {str(e)}", 500, name="DATABASE_ERROR")

    _validate_product_instance(p, MAX_MEDIA, "media")

    try:
        p = media_upsert(p, payload)
        p = _normalize_media_embedded(p)
        result = {"items": [_media_public(m) for m in p.media]}
        _invalidate_product_with_ids(slug_or_id, p, ["media"])
        return result
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to add media: {str(e)}", 500, name="DATABASE_ERROR")


def s_media_update(slug_or_id: str, media_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    _validate_product_instance(p, MAX_MEDIA, "media")

    payload = dict(payload or {})
    payload["id"] = media_id
    p = media_upsert(p, payload)
    p = _normalize_media_embedded(p)
    result = {"items": [_media_public(m) for m in p.media]}
    _invalidate_product_with_ids(slug_or_id, p, ["media"])
    return result


def s_media_delete(slug_or_id: str, media_id: str) -> None:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        _validate_product_instance(p, MAX_MEDIA, "media")
        media_delete(p, media_id)
        _normalize_media_embedded(p)
        _invalidate_product_with_ids(slug_or_id, p, ["media"])
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to delete media: {str(e)}", 500, name="DATABASE_ERROR")


def s_media_replace(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    items = (payload or {}).get("items") or (payload or {}).get("media") or []
    built = _build_media(items)
    if len(built) >= MAX_MEDIA:
        raise AppError(f"Too many media items (max {MAX_MEDIA})", 400, name="INVALID_MEDIA")

    p = media_replace(p, items)
    p = _normalize_media_embedded(p)
    result = {"items": [_media_public(m) for m in p.media]}
    _invalidate_product_with_ids(slug_or_id, p, ["media"])
    return result


def s_media_reorder(slug_or_id: str, order_ids: List[str]) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(order_ids) != len(p.media or []):
        raise AppError("Invalid order ids", 400, name="INVALID_ORDER_IDS")

    p = media_reorder(p, order_ids)
    p = _normalize_media_embedded(p)
    result = {"items": [_media_public(m) for m in p.media]}
    _invalidate_product_with_ids(slug_or_id, p, ["media"])
    return result


def s_media_set_primary(slug_or_id: str, media_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    p = media_set_primary(p, media_id)
    p = _normalize_media_embedded(p)
    result = {"items": [_media_public(m) for m in p.media]}
    _invalidate_product_with_ids(slug_or_id, p, ["media"])
    return result


# ------SPECS--------
@cache.memoize(
    timeout=DEFAULT_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_spec_version),
)
def s_specs_list(slug_or_id: str) -> dict:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        p = _normalize_specs_embedded(p)
        return {"items": [_spec_public(s) for s in p.specs]}
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to list specs: {str(e)}", 500, name="DATABASE_ERROR")


def s_specs_add(slug_or_id: str, payload: dict):
    require_fields(payload, "group", "key")
    p = find_by_slug_or_id("product", slug_or_id)
    _validate_product_instance(p, MAX_SPECS, "specs")

    p = spec_upsert(p, payload)
    p = _normalize_specs_embedded(p)
    result = {"items": [_spec_public(s) for s in p.specs]}
    _invalidate_product_with_ids(slug_or_id, p, ["specs"])
    return result


def s_specs_update(slug_or_id: str, spec_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    _validate_product_instance(p, MAX_SPECS, "specs")

    payload = dict(payload or {})
    payload["id"] = spec_id
    p = spec_upsert(p, payload)
    p = _normalize_specs_embedded(p)
    result = {"items": [_spec_public(s) for s in p.specs]}
    _invalidate_product_with_ids(slug_or_id, p, ["specs"])
    return result


def s_specs_delete(slug_or_id: str, spec_id: str) -> None:
    try:
        p = find_by_slug_or_id("product", slug_or_id)
        _validate_product_instance(p, MAX_SPECS, "specs")
        spec_delete(p, spec_id)
        _normalize_specs_embedded(p)
        _invalidate_product_with_ids(slug_or_id, p, ["specs"])
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to delete spec: {str(e)}", 500, name="DATABASE_ERROR")


def s_specs_replace(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = (payload or {}).get("items") or (payload or {}).get("specs") or []
    built = _build_specs(items)
    if len(built) > MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")

    p = specs_replace(p, items)
    p = _normalize_specs_embedded(p)
    result = {"items": [_spec_public(s) for s in p.specs]}
    _invalidate_product_with_ids(slug_or_id, p, ["specs"])
    return result


def s_specs_reorder(slug_or_id: str, order_ids: List[str]) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(order_ids) != len(p.specs or []):
        raise AppError("Invalid order ids", 400, name="INVALID_ORDER_IDS")

    p = specs_reorder(p, order_ids)
    p = _normalize_specs_embedded(p)
    result = {"items": [_spec_public(s) for s in p.specs]}
    _invalidate_product_with_ids(slug_or_id, p, ["specs"])
    return result


# ------KEYWORD------
def s_keyword_list(slug_or_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = pk_list_by_product(str(p.id)) or []
    return {"items": [kw_public(x) for x in items]}


def s_keyword_upsert(slug_or_id: str, payload: dict):
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    items = (payload or {}).get("items") or []
    if not items:
        raise AppError("Keywords items required", 400, name="INVALID_KEYWORD")

    results = []
    for item in items:
        kw = (item.get("keyword") or "").strip()
        if not kw:
            continue
        weight = item.get("weight") or 1
        rec = pk_upsert(p, kw, weight)
        results.append(rec)

    if not results:
        raise AppError("No valid keywords provided", 400, name="INVALID_KEYWORD")

    result = {"items": [kw_public(x) for x in results]}
    _invalidate_keyword_cache()
    return result


def s_keyword_bulk_replace(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = (payload or {}).get("items") or (payload or {}).get("keywords") or []
    out = pk_bulk_replace(p, items) or []
    result = {"items": [kw_public(x) for x in out]}
    _invalidate_keyword_cache()
    return result


def s_keyword_delete(slug_or_id: str, keyword_or_id: str) -> None:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    oid = parse_oid(keyword_or_id)
    if oid:
        from .models import ProductKeyword
        rec = ProductKeyword.objects(id=oid, product=p).first()
    else:
        rec = pk_find(p, keyword_or_id)

    if not rec:
        raise AppError("Keyword not found", 404, name="KEYWORD_NOT_FOUND")

    pk_delete(rec)
    _invalidate_keyword_cache()


@cache.memoize(
    timeout=SUGGEST_CACHE_TIMEOUT,
    make_name=_versioned_make_name(_product_suggest_version),
)
def s_keyword_suggest(keyword: str, limit: int = 20) -> dict:
    try:
        limit = int(limit)
        if limit <= 0 or limit > 100:
            limit = 20
    except (ValueError, TypeError):
        limit = 20

    try:
        items = pk_suggest(keyword, limit=limit) or []
        return {"items": [kw_public(x) for x in items]}
    except Exception as e:
        raise AppError(f"Failed to retrieve keyword suggestions: {str(e)}", 500, name="DATABASE_ERROR")





