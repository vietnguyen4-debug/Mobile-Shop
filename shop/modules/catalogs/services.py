from typing import List

from .mappers import _media_public, _spec_public
from ...core.validation import require_fields
from ...core.utils import *
from .repositories import *
from .mappers import *
from .models import Media, Spec
from .service_helpers import *
# ---- CATEGORY ----
def s_category_create(payload: dict) -> dict:
    require_fields(payload, "name")
    name = payload["name"].strip()
    slug = slugify(name)
    ensure_unique_slug(Category, slug)
    if Category.objects(slug=slug).first(): raise AppError("Name already used", 409, name = "INVALID_CATEGORY")
    c = cat_insert({
        "name": name,
        "slug": slug,
        "icon": payload.get("icon"),
        "description": payload.get("description"),
        "hot": bool(payload.get("hot", False)),
    })
    return cat_public(c)

def s_category_get(slug_or_id: str) -> dict:
    c = find_by_slug_or_id("category", slug_or_id)
    return cat_public(c)

def s_category_list() -> dict:
    return {
        "items": [ cat_public(c) for c in cat_list_all()]
    }

def s_category_update(slug_or_id: str, payload: dict) -> dict:
    c = find_by_slug_or_id("category", slug_or_id)

    data = {}
    if "name" in payload and payload["name"]:
        name = payload["name"].strip()
        if name and name != c.name and Category.objects(name=name).first():
            raise AppError("Name already used", 409, name = "INVALID_CATEGORY")
        data["name"] = name
        data["slug"] = slugify(name)

    for k in ("icon", "description", "hot"):
        if k in payload: data[k] = payload[k]

    c = cat_update(c, data)
    return cat_public(c)

def s_category_delete(slug_or_id: str) -> None:
    c = find_by_slug_or_id("category", slug_or_id)
    mark_products_orphan_by_category(c.id)
    cat_delete(c)

# ----SUBCATEGORY-----
def s_subcategory_create(payload: dict) -> dict:
    require_fields(payload, "name", "category_id")
    name = payload["name"].strip()
    cat_oid = parse_oid(payload["category_id"])
    if not cat_oid: raise AppError("Category not found", 404, name = "INVALID_CATEGORY")
    cat = cat_get_by_id(cat_oid)
    if not cat: raise AppError("Category not found", 404, name = "INVALID_CATEGORY")
    slug = payload.get("slug") or slugify(name, prefix=cat.slug)
    ensure_unique_slug(SubCategory, slug)
    s = sub_insert({
        "name": name,
        "slug": slug,
        "icon": payload.get("icon"),
        "category": cat,
        "description": payload.get("description"),
    })

    return sub_public(s)

def s_subcategory_get(slug_or_id: str) -> dict:
    s = find_by_slug_or_id("subcategory", slug_or_id)
    return sub_public(s)

def s_subcategory_list_by_category(category_id: str) -> dict:
    cat_oid = parse_oid(category_id)
    if not cat_oid: raise AppError("Subcategory not found", 404, name = "INVALID_CATEGORY")
    return {
        "items": [ sub_public(s) for s in sub_list_by_category(cat_oid) ]
    }

def s_subcategory_update(slug_or_id: str, payload: dict) -> dict:
    s = find_by_slug_or_id("subcategory", slug_or_id)

    data = {}
    if "name" in payload:
        data["name"] = payload["name"].strip()
    new_cat = s.category
    if "category_id" in payload:
        if payload["category_id"] is None:
            raise AppError("Category cannot be null", 400, name = "INVALID_CATEGORY")
        cat_oid = parse_oid(payload["category_id"])
        if not cat_oid:
            raise AppError("Category not found", 404, name = "INVALID_CATEGORY")
        new_cat = cat_get_by_id(cat_oid)
        if not new_cat:
            raise AppError("Category not found", 404, name = "INVALID_CATEGORY")
        data["category"] = new_cat

    if "name" in data or ("category" in data and data["category"] != s.category):
        base_name = data.get("name", s.name)
        cat_for_slug = data.get("category", new_cat)
        data["slug"] = slugify(base_name, prefix=cat_for_slug.slug)
        ensure_unique_slug(SubCategory, data["slug"])

    for k in ("icon", "description", "hot"):
        if k in payload:
            data[k] = payload[k]

    s = sub_update(s, data)
    return sub_public(s)

def s_subcategory_delete(slug_or_id: str) -> None:
    s = find_by_slug_or_id("subcategory", slug_or_id)
    mark_products_orphan_by_subcategory(s.id)
    sub_delete(s)

# -----PRODUCT-----
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
    items = [{
        "id": m.id, "kind": m.kind, "url": m.url, "alt": m.alt,
        "is_primary": bool(getattr(m, "is_primary", False)),
        "order": int(getattr(m, "order", 0) or 0),
    } for m in (p.media or [])]
    p.media = _build_media(items)
    return p.save()

def _normalize_specs_embedded(p: Product) -> Product:
    items = [{
        "id": s.id, "group": s.group, "key": s.key,
        "value": s.value, "order": int(getattr(s, "order", 0) or 0),
    } for s in (p.specs or [])]
    p.specs = _build_specs(items)
    return p.save()

def s_product_create(payload: dict) -> dict:
    require_fields(payload, "name", "price")
    name = payload["name"].strip()
    try:
        price = float(payload["price"])
    except Exception:
        raise AppError("Price must be a number", 400, name="INVALID_PRICE")
    if price < 0:
        raise AppError("Price must be positive", 400, name="INVALID_PRICE")
    cat = sub = None
    if "category_id" in payload:
        cat_oid = parse_oid(payload["category_id"])
        if not cat_oid: raise AppError("Category not found", 404, name="INVALID_CATEGORY")
        cat = cat_get_by_id(cat_oid)
        if not cat: raise AppError("Category not found", 404, name ="INVALID_CATEGORY")
    if "subcategory_id" in payload:
        sub_oid = parse_oid(payload["subcategory_id"])
        if not sub_oid: raise AppError("Subcategory not found", 404, name="INVALID_SUBCATEGORY")
        if not cat:
            raise AppError(
                "Category required for subcategory", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY"
            )
        sub = sub_get_by_id(sub_oid)
    if cat and sub and sub.category.id != cat.id:
        raise AppError("Subcategory not in category", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY")
    slug = slugify(name)
    ensure_unique_slug(Product, slug)

    media = _build_media(payload.get("media"))
    specs = _build_specs(payload.get("specs"))

    if len(media) > MAX_MEDIA:
        raise AppError(f"Too many media items (max {MAX_MEDIA})", 400, name="INVALID_MEDIA")
    if len(specs) > MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")


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
    return product_public(p)

def s_product_get(slug_or_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    return product_public(p)

def s_product_list(page, limit) -> dict:
    p, l = parse_pagination(page, limit)
    items, total = prod_list_all(p, l)
    return {"items": [product_public(x) for x in items], "total": total, "page": p, "limit": l}

def s_product_list_by_sub(sub_id, page, limit, *, active_only = True) -> dict:
    p, l = parse_pagination(page, limit)
    sub_oid = parse_oid(sub_id)
    if not sub_oid:
        return {"items": [], "total": 0, "page": p, "limit": l}
    items, total = prod_list_by_sub(sub_oid, p, l, active_only = active_only)
    return {"items": [product_public(x) for x in items], "total": total, "page": p, "limit": l}

def s_product_update(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)

    data = {}
    need_new_slug = False
    if "name" in payload and payload["name"]:
        data["name"] = payload["name"].strip()
    if "price" in payload:
        price = float(payload["price"])
        if price < 0: raise AppError("Price must be positive", 400, name="INVALID_PRICE")
        data["price"] = price

    cat = p.category; sub = p.subcategory
    if "category_id" in payload:
        if payload["category_id"] is None:
            cat = None
        else:
            cat_oid = parse_oid(payload["category_id"])
            if not cat_oid: raise AppError("Category not found", 404, name="INVALID_CATEGORY")
            cat = cat_get_by_id(cat_oid)
            if not cat: raise AppError("Category not found", 404, name="INVALID_CATEGORY")
            need_new_slug = True

    if "subcategory_id" in payload:
        if payload["subcategory_id"] is None:
            sub = None
        else:
            sub_oid = parse_oid(payload["subcategory_id"])
            if not sub_oid: raise AppError("Subcategory not found", 404, name="INVALID_SUBCATEGORY")
            if not cat:
                raise AppError(
                    "Category required for subcategory", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY"
                )
            sub = sub_get_by_id(sub_oid)
            if not sub: raise AppError("Subcategory not found", 404, name="INVALID_SUBCATEGORY")
            need_new_slug = True
    if cat and sub and sub.category.id != cat.id:
        raise AppError("Subcategory not in category", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY")

    data["category"] = cat; data["subcategory"] = sub

    if need_new_slug or ("category_id" in payload) or ("subcategory_id" in payload):
        base = data.get("name", p.name)
        prefix = sub.slug if sub else (cat.slug if cat else None)
        data["slug"] = slugify(base, prefix=prefix)

    for k in ("description", "is_active"):
        if k in payload: data[k] = payload[k]

    if data["category"] is None or data["subcategory"] is None:
        data["is_orphan"] = True
        data["is_active"] = False
        data["orphan_reason"] = "invalid_link"
    else:
        data["is_orphan"] = False
        data["orphan_reason"] = None

    p = prod_update(p, data)
    return product_public(p)

def s_product_delete(slug_or_id: str) -> None:
    p = find_by_slug_or_id("product", slug_or_id)
    prod_delete(p)

#------MEDIA-------
def s_media_list(slug_or_id: str) ->dict:
    p = find_by_slug_or_id("product", slug_or_id)
    p = _normalize_media_embedded(p)
    return {"items": [_media_public(m) for m in p.media]}

def s_media_add(slug_or_id: str, payload: dict):
    require_fields(payload, "kind", "url")
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(p.media) >= MAX_MEDIA:
        raise AppError(f"Too many media items (max {MAX_MEDIA})", 400, name="INVALID_MEDIA")
    p = media_upsert(p, payload)
    p = _normalize_media_embedded(p)
    return {"items": [_media_public(m) for m in p.media]}

def s_media_update(slug_or_id: str, media_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(p.media or []) >= MAX_MEDIA:
        raise AppError(f"Too many media items (max {MAX_MEDIA})", 400, name="INVALID_MEDIA")
    payload = dict(payload or {})
    payload["id"] = media_id
    p = media_upsert(p, payload)
    p = _normalize_media_embedded(p)
    return {"items": [_media_public(m) for m in p.media]}


def s_media_delete(slug_or_id: str, media_id: str) -> None:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    media_delete(p, media_id)
    _normalize_media_embedded(p)

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
    return {"items": [_media_public(m) for m in p.media]}

def s_media_reorder(slug_or_id: str, order_ids: List[str]) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(order_ids) != len(p.media or []):
        raise AppError("Invalid order ids", 400, name="INVALID_ORDER_IDS")
    p = media_reorder(p, order_ids)
    p = _normalize_media_embedded(p)
    return {"items": [_media_public(m) for m in p.media]}

def s_media_set_primary(slug_or_id: str, media_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")

    p = media_set_primary(p, media_id)
    p = _normalize_media_embedded(p)
    return {"items": [_media_public(m) for m in p.media]}

#------SPECS--------
def s_specs_list(slug_or_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    p = _normalize_specs_embedded(p)
    return {"items": [_spec_public(s) for s in p.specs]}

def s_specs_add(slug_or_id: str, payload: dict):
    require_fields(payload, "group", "key")
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(p.specs) >= MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")
    p = spec_upsert(p, payload)
    p = _normalize_specs_embedded(p)
    return {"items": [_spec_public(s) for s in p.specs]}

def s_specs_update(slug_or_id: str, spec_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(p.specs or []) >= MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")
    payload = dict(payload or {})
    payload["id"] = spec_id
    p = spec_upsert(p, payload)
    p = _normalize_specs_embedded(p)
    return {"items": [_spec_public(s) for s in p.specs]}

def s_specs_delete(slug_or_id: str, spec_id: str) -> None:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    spec_delete(p, spec_id)
    _normalize_specs_embedded(p)

def s_specs_replace(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = (payload or {}).get("items") or (payload or {}).get("specs") or []
    built = _build_specs(items)
    if len(built) > MAX_SPECS:
        raise AppError(f"Too many specs items (max {MAX_SPECS})", 400, name="INVALID_SPECS")
    p = specs_replace(p, items)
    p = _normalize_specs_embedded(p)
    return {"items": [_spec_public(s) for s in p.specs]}

def s_specs_reorder(slug_or_id: str, order_ids: List[str]) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    if len(order_ids) != len(p.specs or []):
        raise AppError("Invalid order ids", 400, name="INVALID_ORDER_IDS")
    p = specs_reorder(p, order_ids)
    p = _normalize_specs_embedded(p)
    return {"items": [_spec_public(s) for s in p.specs]}

#------KEYWORD------
def s_keyword_list(slug_or_id: str) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = pk_list_by_product(str(p.id)) or []
    return {"items": items}

def s_keyword_upsert(slug_or_id: str, payload: dict):
    p = find_by_slug_or_id("product", slug_or_id)
    if not isinstance(p, Product):
        raise AppError("Product not found", 404, name="INVALID_PRODUCT")
    kw = (payload.get("keyword") or "").strip()
    if not kw:
        raise AppError("Keyword required", 400, name="INVALID_KEYWORD")
    weight = payload.get("weight") or 1
    rec = pk_upsert(p, kw, weight)
    return {"item": rec}

def s_keyword_bulk_replace(slug_or_id: str, payload: dict) -> dict:
    p = find_by_slug_or_id("product", slug_or_id)
    items = (payload or {}).get("items") or (payload or {}).get("keywords") or []
    out = pk_bulk_replace(p, items) or []
    return {"items": out}

def s_keyword_delete(slug_or_id: str, keyword_id: str) -> None:
    oid = parse_oid(keyword_id)
    if not oid:
        raise AppError("Invalid keyword id", 400, name="INVALID_KEYWORD_ID")
    p = find_by_slug_or_id("product", slug_or_id)
    from .models import ProductKeyword
    rec = ProductKeyword.objects(id=oid, product=p).first()
    if not rec:
        raise AppError("Keyword not found", 404, name="KEYWORD_NOT_FOUND")
    pk_delete(rec)

def s_keyword_suggest(keyword: str, limit:int = 20) -> dict:
    items = pk_suggest(keyword, limit = limit) or []
    return {"items": items}




