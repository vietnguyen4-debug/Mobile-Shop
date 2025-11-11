import os
from typing import Optional, Literal, Tuple, List
from bson import ObjectId

from .repositories import cat_get_by_id, sub_get_by_id
from ...core.utils import parse_oid, AppError
from . import repositories as repo
from .models import Category, SubCategory, Product, Media, Spec
from ...extensions import cache

Kind = Literal["category", "subcategory", "product"]


# ============= CACHE HELPERS =============

def _cache_client():
    return getattr(cache, "client", None)


def _version_key(bucket: str, *parts: Optional[str]) -> str:
    segments = ["catalog", "ver", bucket]
    segments.extend(filter(None, parts))
    return ":".join(segments)


def _get_version(bucket: str, *parts: Optional[str]) -> str:
    client = _cache_client()
    if not client:
        return "0"

    key = _version_key(bucket, *parts)
    version = client.get(key)
    if version is None:
        version = "0"
        client.set(key, version)
    return version


def _bump_version(bucket: str, *parts: Optional[str]) -> None:
    client = _cache_client()
    if not client:
        return

    key = _version_key(bucket, *parts)
    client.incr(key)


def _versioned_make_name(version_resolver):
    def factory(fname):
        def _inner(*args, **kwargs):
            token = version_resolver(*args, **kwargs)
            if token:
                mutable_kwargs = dict(kwargs)
                mutable_kwargs["_ver"] = token
            else:
                mutable_kwargs = kwargs
            return cache._memoize_make_cache_key(fname, *args, **mutable_kwargs)

        return _inner

    return factory


def _compose_token(*parts: Optional[str]) -> str:
    filtered = [part for part in parts if part]
    return "|".join(filtered)


# ============= VERSION RESOLVERS =============

def _category_item_version(slug_or_id: str, *_args, **_kwargs) -> str:
    return _get_version("category", slug_or_id)


def _category_list_version(*_args, **_kwargs) -> str:
    return _get_version("category", "list")


def _subcategory_item_version(slug_or_id: str, *_args, **_kwargs) -> str:
    return _get_version("subcategory", slug_or_id)


def _subcategory_by_category_version(category_id: str, *_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("subcategory", "list"),
        _get_version("subcategory", f"list:{category_id}"),
    )


def _product_item_version(slug_or_id: str, *_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("product", slug_or_id),
        _get_version("product", "segment:core"),
        _get_version("product", "segment:media"),
        _get_version("product", "segment:specs"),
    )


def _product_list_version(*_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("product", "list"),
        _get_version("product", "segment:core"),
        _get_version("product", "segment:media"),
        _get_version("product", "segment:specs"),
    )


def _product_list_by_sub_version(sub_id: str, *_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("product", "list"),
        _get_version("product", "segment:core"),
        _get_version("product", "segment:media"),
        _get_version("product", "segment:specs"),
        _get_version("product", f"sub:{sub_id}"),
    )


def _product_media_version(slug_or_id: str, *_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("product", slug_or_id),
        _get_version("product", "segment:media"),
        _get_version("product", f"media:{slug_or_id}"),
    )


def _product_spec_version(slug_or_id: str, *_args, **_kwargs) -> str:
    return _compose_token(
        _get_version("product", slug_or_id),
        _get_version("product", "segment:specs"),
        _get_version("product", f"spec:{slug_or_id}"),
    )


def _product_suggest_version(*_args, **_kwargs) -> str:
    return _get_version("product", "suggest")


# ============= COLLECTION HELPERS =============

def _collect_category_ids(*products) -> List[str]:
    ids: List[str] = []
    for prod in products:
        cat = getattr(prod, "category", None)
        if cat:
            cid = str(getattr(cat, "id", ""))
            if cid and cid not in ids:
                ids.append(cid)
    return ids


def _collect_subcategory_ids(*products) -> List[str]:
    ids = []
    for prod in products:
        sub = getattr(prod, "subcategory", None)
        if sub:
            sid = str(getattr(sub, "id", ""))
            if sid and sid not in ids:
                ids.append(sid)
    return ids


def _collect_invalidation_ids(p: Product) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """Collect category and subcategory IDs for cache invalidation."""
    cat_ids = _collect_category_ids(p)
    sub_ids = _collect_subcategory_ids(p)
    return cat_ids or None, sub_ids or None


# ============= CACHE INVALIDATION =============

def _invalidate_category_cache(*identifiers: str) -> None:
    _bump_version("category", "list")
    for ident in identifiers:
        if ident:
            _bump_version("category", ident)


def _invalidate_subcategory_cache(*identifiers: str, category_ids: Optional[List[str]] = None) -> None:
    _bump_version("subcategory", "list")
    if category_ids:
        for cid in category_ids:
            if cid:
                _bump_version("subcategory", f"list:{cid}")
    for ident in identifiers:
        if ident:
            _bump_version("subcategory", ident)


def _invalidate_product_cache(
        *identifiers: str,
        category_ids: Optional[List[str]] = None,
        subcategory_ids: Optional[List[str]] = None,
        segments: Optional[List[str]] = None,
        affected_pages: Optional[List[int]] = None,
        invalidate_all_pages: bool = True,
) -> None:
    """
    Invalidate product cache with page-level granularity.

    Args:
        affected_pages: Specific page numbers to invalidate (e.g., [1])
        invalidate_all_pages: If True, bump global list version (affects all pages)
    """
    if invalidate_all_pages:
        # Global invalidation - affects all pages
        _bump_version("product", "list")
    elif affected_pages:
        # Selective invalidation - only specific pages
        for page_num in affected_pages:
            _bump_version("product", f"page:{page_num}")
            # Also invalidate sub-specific pages if subcategory_ids provided
            if subcategory_ids:
                for sid in subcategory_ids:
                    _bump_version("product", f"sub:{sid}:page:{page_num}")

    _bump_version("product", "suggest")

    if category_ids:
        for cid in category_ids:
            if cid:
                _bump_version("product", f"cat:{cid}")

    if subcategory_ids:
        for sid in subcategory_ids:
            if sid:
                _bump_version("product", f"sub:{sid}")

    for ident in identifiers:
        if ident:
            _bump_version("product", ident)
            _bump_version("product", f"media:{ident}")
            _bump_version("product", f"spec:{ident}")

    unique_segments = []
    for segment in segments or []:
        if segment and segment not in unique_segments:
            unique_segments.append(segment)
    for segment in unique_segments:
        _bump_version("product", f"segment:{segment}")


def _invalidate_product_with_ids(
        slug_or_id: str,
        product: Product,
        segments: List[str],
        *additional_identifiers: str,
        additional_cat_ids: Optional[List[str]] = None,
        additional_sub_ids: Optional[List[str]] = None,
        affected_pages: Optional[List[int]] = None,
        invalidate_all_pages: bool = True,
) -> None:
    """
    Invalidate product cache with collected IDs.

    Args:
        affected_pages: Specific pages to invalidate (default: None = all pages)
        invalidate_all_pages: Whether to invalidate all pages (default: True)
    """
    cat_ids, sub_ids = _collect_invalidation_ids(product)

    if additional_cat_ids:
        cat_ids = list(set((cat_ids or []) + additional_cat_ids))
    if additional_sub_ids:
        sub_ids = list(set((sub_ids or []) + additional_sub_ids))

    _invalidate_product_cache(
        slug_or_id,
        getattr(product, "slug", None),
        str(getattr(product, "id", "")),
        *additional_identifiers,
        category_ids=cat_ids,
        subcategory_ids=sub_ids,
        segments=segments,
        affected_pages=affected_pages,
        invalidate_all_pages=invalidate_all_pages,
    )


def _invalidate_keyword_cache() -> None:
    _bump_version("product", "suggest")


# ============= ENVIRONMENT HELPERS =============

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ============= CONSTANTS =============

DEFAULT_CACHE_TIMEOUT = _int_env("CATALOG_CACHE_TIMEOUT", _int_env("CACHE_DEFAULT_TIMEOUT", 300))
SUGGEST_CACHE_TIMEOUT = _int_env("CATALOG_SUGGEST_CACHE_TIMEOUT", 60)


# ============= FINDER HELPERS =============

def _find_raw(kind: Kind, slug_or_id: str):
    if kind == "category":
        obj = repo.cat_get_by_slug(slug_or_id)
        if obj: return obj
        oid = parse_oid(slug_or_id)
        return repo.cat_get_by_id(oid) if oid else None

    if kind == "subcategory":
        obj = repo.sub_get_by_slug(slug_or_id)
        if obj: return obj
        oid = parse_oid(slug_or_id)
        return repo.sub_get_by_id(oid) if oid else None

    if kind == "product":
        oid = parse_oid(slug_or_id)
        if oid:
            obj = repo.prod_get_by_id(oid)
            if obj: return obj
        obj = repo.prod_get_by_slug(slug_or_id)
        if obj: return obj
        return None

    return None


def find_by_slug_or_id(kind: Kind, slug_or_id: str, *, invalid_id_400=False) -> Optional[
    Category | SubCategory | Product]:
    obj = _find_raw(kind, slug_or_id)
    if obj: return obj
    if invalid_id_400 and not parse_oid(slug_or_id):
        raise AppError("Invalid ID", 400, name="INVALID_ID")

    raise AppError(f"{kind.capitalize()} not found", 404, name=f"INVALID_{kind.upper()}_NOT_FOUND")


def find_cat_and_sub_by_slug_or_id(slug_or_id: str) -> Tuple[Category, SubCategory]:
    cat = find_by_slug_or_id("category", slug_or_id)
    sub = find_by_slug_or_id("subcategory", slug_or_id)
    if sub.category.id != cat.id:
        raise AppError("Subcategory not in category", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY")
    return cat, sub


# ============= UNIFIED HELPER FUNCTIONS =============

def _safe_parse_oid(id_str: str, entity_name: str = "Entity") -> ObjectId:
    """Parse ObjectId with unified error handling."""
    try:
        oid = parse_oid(id_str)
    except Exception as e:
        raise AppError(f"Invalid {entity_name.lower()} ID: {str(e)}", 400,
                       name=f"INVALID_{entity_name.upper()}_ID")

    if not oid:
        raise AppError(f"{entity_name} not found", 404, name=f"INVALID_{entity_name.upper()}")

    return oid


def _safe_get_by_id(get_func, oid: ObjectId, entity_name: str = "Entity"):
    try:
        obj = get_func(oid)
    except Exception as e:
        raise AppError(f"Failed to retrieve {entity_name.lower()}: {str(e)}", 500,
                       name="DATABASE_ERROR")

    if not obj:
        raise AppError(f"{entity_name} not found", 404, name=f"INVALID_{entity_name.upper()}")

    return obj


def _safe_get_category_by_id(category_id: str) -> Category:
    oid = _safe_parse_oid(category_id, "Category")
    return _safe_get_by_id(cat_get_by_id, oid, "Category")


def _parse_and_get_subcategory(subcategory_id: str, category: Category = None) -> SubCategory:
    if category is None:
        raise AppError(
            "Category required for subcategory", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY"
        )

    oid = _safe_parse_oid(subcategory_id, "Subcategory")
    return _safe_get_by_id(sub_get_by_id, oid, "Subcategory")


def _validate_category_subcategory_relation(cat: Category, sub: SubCategory):
    if cat and sub and sub.category and sub.category.id != cat.id:
        raise AppError("Subcategory not in category", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY")


# ============= VALIDATION HELPERS =============

def _validate_product_instance(p, max_items: int, item_type: str) -> None:
    """Validate product instance and check max items limit."""
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    current_items = getattr(p, item_type, [])
    if len(current_items or []) >= max_items:
        raise AppError(
            f"Too many {item_type} items (max {max_items})",
            400,
            name=f"INVALID_{item_type.upper()}"
        )


# ============= MEDIA & SPECS BUILDERS =============

def _build_media(items: List[dict]) -> List[Media]:
    out: List[Media] = []
    pending: List[Tuple[dict, int]] = []
    max_order = -1

    for index, m in enumerate(items or []):
        url = (m.get("url") or "").strip()
        if not url:
            raise AppError("Media url is required", 400, name="INVALID_MEDIA")

        raw_order = m.get("order")
        has_explicit_order = raw_order is not None and f"{raw_order}".strip() != ""
        order_value = 0

        if has_explicit_order:
            try:
                order_value = int(raw_order)
            except (TypeError, ValueError):
                has_explicit_order = False
            else:
                max_order = max(max_order, order_value)
        if not has_explicit_order:
            pending.append((m, index))
            continue

        out.append(Media(
            id=m.get("id"),
            kind=(m.get("kind") or "image"),
            url=url,
            alt=m.get("alt"),
            is_primary=bool(m.get("is_primary", False)),
            order=order_value,
        ))

    next_order = max_order + 1 if max_order >= 0 else 0

    for m, _ in sorted(pending, key=lambda item: item[1]):
        out.append(Media(
            id=m.get("id"),
            kind=(m.get("kind") or "image"),
            url=(m.get("url") or "").strip(),
            alt=m.get("alt"),
            is_primary=bool(m.get("is_primary", False)),
            order=next_order,
        ))
        next_order += 1

    if out and not any(getattr(x, "is_primary", False) for x in out):
        sorted(out, key=lambda x: (getattr(x, "order", 0) or 0))[0].is_primary = True
    out = sorted(out, key=lambda x: (
        not bool(getattr(x, "is_primary", False)),
        getattr(x, "order", 0) or 0
    ))

    for idx, media in enumerate(out):
        media.order = idx
    return out


def _build_specs(items: List[dict]) -> List[Spec]:
    out: List[Spec] = []
    for s in items or []:
        out.append(Spec(
            id=s.get("id"),
            group=s.get("group"),
            key=s.get("key"),
            value=s.get("value"),
            order=int(s.get("order") or 0),
        ))
    # sort: order → group → key (tăng dần)
    out = sorted(out, key=lambda sp: (
        getattr(sp, "order", 0) or 0,
        (getattr(sp, "group", "") or ""),
        (getattr(sp, "key", "") or "")
    ))
    return out


def _normalize_media_embedded(p: Product) -> Product:
    try:
        items = [{
            "id": m.id, "kind": m.kind, "url": m.url, "alt": m.alt,
            "is_primary": bool(getattr(m, "is_primary", False)),
            "order": int(getattr(m, "order", 0) or 0),
        } for m in (p.media or [])]
        p.media = _build_media(items)
        return p.save()
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to normalize media: {str(e)}", 500, name="DATABASE_ERROR")


def _normalize_specs_embedded(p: Product) -> Product:
    try:
        items = [{
            "id": s.id, "group": s.group, "key": s.key,
            "value": s.value, "order": int(getattr(s, "order", 0) or 0),
        } for s in (p.specs or [])]
        p.specs = _build_specs(items)
        return p.save()
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"Failed to normalize specs: {str(e)}", 500, name="DATABASE_ERROR")