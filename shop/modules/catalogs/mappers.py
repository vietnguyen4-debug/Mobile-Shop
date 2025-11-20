from functools import wraps

from ...core.exceptions import AppError


def mapping_guard(entity: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                raise AppError(f"Failed to map {entity}: {str(e)}", 500, name="MAPPING_ERROR")

        return wrapper

    return decorator


@mapping_guard("media")
def _media_public(m):
    return {
        "id": m.id,
        "kind": m.kind,
        "url": m.url,
        "alt": m.alt,
        "is_primary": m.is_primary,
        "order": m.order,
    }


@mapping_guard("spec")
def _spec_public(s):
    return {"id": s.id, "group": s.group, "key": s.key, "value": s.value, "order": s.order}


@mapping_guard("category")
def cat_public(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "slug": c.slug,
        "icon": getattr(c, "icon", None),
        "description": getattr(c, "description", None),
        "hot": bool(getattr(c, "hot", False)),
    }


@mapping_guard("subcategory")
def sub_public(s):
    return {
        "id": str(s.id),
        "name": s.name,
        "slug": s.slug,
        "category_id": str(s.category.id) if getattr(s, "category", None) else None,
        "icon": getattr(s, "icon", None),
        "description": getattr(s, "description", None),
    }


@mapping_guard("product")
def product_public(p):
    media_sorted = sorted(
        p.media or [],
        key=lambda m: (not bool(getattr(m, "is_primary", False)), getattr(m, "order", 0) or 0),
    )
    specs_sorted = sorted(
        p.specs or [],
        key=lambda sp: (getattr(sp, "order", 0) or 0, getattr(sp, "group", "") or "", getattr(sp, "key", "") or ""),
    )
    primary = _media_public(media_sorted[0]) if media_sorted else None

    return {
        "id": str(p.id),
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "base_price": p.price,
        "category_id": str(p.category.id) if p.category else None,
        "subcategory_id": str(p.subcategory.id) if p.subcategory else None,
        "media": [_media_public(m) for m in media_sorted],
        "primary_media": primary,
        "specs": [_spec_public(sp) for sp in specs_sorted],
        "is_active": p.is_active,
        "is_orphan": p.is_orphan,
        "orphan_reason": p.orphan_reason,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


@mapping_guard("keyword")
def kw_public(kw):
    return {
        "product_id": str(kw.product.id) if kw.product else None,
        "keyword": kw.keyword,
        "weight": kw.weight,
    }


@mapping_guard("category_summary")
def cat_summary(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "slug": c.slug,
    }


@mapping_guard("subcategory_summary")
def sub_summary(s):
    return {
        "id": str(s.id),
        "name": s.name,
        "slug": s.slug,
        "category_id": str(s.category.id) if getattr(s, "category", None) else None,
    }


@mapping_guard("product_summary")
def product_summary(p):
    primary_media = None
    best_score = None
    for m in p.media or []:
        score = (
            0 if bool(getattr(m, "is_primary", False)) else 1,
            getattr(m, "order", 0) or 0,
        )
        if primary_media is None or score < best_score:
            primary_media = m
            best_score = score

    primary = None
    if primary_media:
        primary = {
            "id": primary_media.id,
            "kind": primary_media.kind,
            "url": primary_media.url,
            "alt": primary_media.alt,
        }

    return {
        "id": str(p.id),
        "name": p.name,
        "slug": p.slug,
        "base_price": p.price,
        "primary_media": primary,
    }

