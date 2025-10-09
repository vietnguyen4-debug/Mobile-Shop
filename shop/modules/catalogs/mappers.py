def _media_public(m):
    return {"id": m.id, "kind": m.kind, "url": m.url, "alt": m.alt,
            "is_primary": m.is_primary, "order": m.order}

def _spec_public(s):
    return {"id": s.id, "group": s.group, "key": s.key, "value": s.value, "order": s.order}

def cat_public(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "slug": c.slug,
        "icon": getattr(c, "icon", None),
        "description": getattr(c, "description", None),
        "hot": bool(getattr(c, "hot", False)),
    }

def sub_public(s):
    return {
        "id": str(s.id),
        "name": s.name,
        "slug": s.slug,
        "category_id": str(s.category.id) if getattr(s, "category", None) else None,
        "icon": getattr(s, "icon", None),
        "description": getattr(s, "description", None),
    }

def product_public(p):
    primary = None
    if p.media:
        ms = sorted(p.media, key=lambda x: (not x.is_primary, x.order))
        primary = _media_public(ms[0]) if ms else None
    return {
        "id": str(p.id), "name": p.name, "slug": p.slug,
        "description": p.description,
        "base_price": p.price,                # giá gốc; effective price tính ở pricing
        "category_id": str(p.category.id) if p.category else None,
        "subcategory_id": str(p.subcategory.id) if p.subcategory else None,
        "media": [_media_public(m) for m in sorted(p.media, key=lambda x: (not x.is_primary, x.order))],
        "primary_media": primary,
        "specs": [_spec_public(s) for s in sorted(p.specs, key=lambda x: (s.order, s.group or "", s.key))],
        "is_active": p.is_active, "is_orphan": p.is_orphan, "orphan_reason": p.orphan_reason,
        "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()
    }
