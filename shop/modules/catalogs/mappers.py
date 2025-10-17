from ...core.exceptions import AppError

def _media_public(m):
    try:
        return {"id": m.id, "kind": m.kind, "url": m.url, "alt": m.alt,
                "is_primary": m.is_primary, "order": m.order}
    except Exception as e:
        raise AppError(f"Failed to map media: {str(e)}", 500, name="MAPPING_ERROR")


def _spec_public(s):
    try:
        return {"id": s.id, "group": s.group, "key": s.key, "value": s.value, "order": s.order}
    except Exception as e:
        raise AppError(f"Failed to map spec: {str(e)}", 500, name="MAPPING_ERROR")


def cat_public(c):
    try:
        return {
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "icon": getattr(c, "icon", None),
            "description": getattr(c, "description", None),
            "hot": bool(getattr(c, "hot", False)),
        }
    except Exception as e:
        raise AppError(f"Failed to map category: {str(e)}", 500, name="MAPPING_ERROR")


def sub_public(s):
    try:
        return {
            "id": str(s.id),
            "name": s.name,
            "slug": s.slug,
            "category_id": str(s.category.id) if getattr(s, "category", None) else None,
            "icon": getattr(s, "icon", None),
            "description": getattr(s, "description", None),
        }
    except Exception as e:
        raise AppError(f"Failed to map subcategory: {str(e)}", 500, name="MAPPING_ERROR")

def product_public(p):
    try:
        primary = None
        if p.media:
            ms = sorted(p.media, key=lambda m: (not bool(getattr(m, "is_primary", False)),
                                                getattr(m, "order", 0) or 0))
            primary = _media_public(ms[0]) if ms else None

        media_sorted = sorted(p.media, key=lambda m: (not bool(getattr(m, "is_primary", False)),
                                                      getattr(m, "order", 0) or 0))
        specs_sorted = sorted(p.specs, key=lambda sp: (getattr(sp, "order", 0) or 0,
                                                       getattr(sp, "group", "") or "",
                                                       getattr(sp, "key", "") or ""))

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
    except Exception as e:
        raise AppError(f"Failed to map product: {str(e)}", 500, name="MAPPING_ERROR")

def kw_public(kw):
    try:
        return {
            "product_id": str(kw.product.id) if kw.product else None,
            "keyword": kw.keyword,
            "weight": kw.weight,
        }
    except Exception as e:
        raise AppError(f"Failed to map keyword: {str(e)}", 500, name="MAPPING_ERROR")

