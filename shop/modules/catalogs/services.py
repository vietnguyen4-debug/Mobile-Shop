from ...core.exceptions import AppError
from ...core.validation import require_fields
from ...core.utils import *
from .repositories import *
from .mappers import *

# ---- CATEGORY ----
def s_category_create(payload: dict) -> dict:
    require_fields(payload, "name")
    name = payload["name"].strip()
    slug = slugify(name)
    ensure_unique_slug(Category, slug)
    if Category.objects(slug=slug).first(): raise AppError("Name already used", 409)
    c = cat_insert({
        "name": name,
        "slug": slug,
        "icon": payload.get("icon"),
        "description": payload.get("description"),
        "hot": bool(payload.get("hot", False)),
    })
    return cat_public(c)

def s_category_get(slug_or_id: str) -> dict:
    c = cat_get_by_slug(slug_or_id) or cat_get_by_id(ObjectId(slug_or_id))
    if not c: raise AppError("Category not found", 404)
    return cat_public(c)

def s_category_list() -> dict:
    return {
        "items": [ cat_public(c) for c in cat_list_all()]
    }

def s_category_update(slug_or_id: str, payload: dict) -> dict:
    c = cat_get_by_slug(slug_or_id) or cat_get_by_id(ObjectId(slug_or_id))
    if not c: raise AppError("Category not found", 404)

    data = {}
    if "name" in payload:
        name = payload["name"].strip()
        if name and name != c.name and Category.objects(name=name).first():
            raise AppError("Name already used", 409)
        data["name"] = name

    data["slug"] = slugify(data.get("name"))

    for k in ("icon", "description", "hot"):
        if k in payload: data[k] = payload[k]

    c = cat_update(c, data)
    return cat_public(c)

def s_category_delete(slug_or_id: str) -> None:
    from bson import ObjectId
    c = cat_get_by_slug(slug_or_id) or cat_get_by_id(ObjectId(slug_or_id))
    if not c: raise AppError("Category not found", 404)
    mark_products_orphan_by_category(c.id)
    cat_delete(c)

# ----SUBCATEGORY-----

def s_subcategory_create(payload: dict) -> dict:
    require_fields(payload, "name", "category_id")
    name = payload["name"].strip()
    cat_oid = parse_oid(payload["category_id"])
    if not cat_oid: raise AppError("Category not found", 404)
    cat = cat_get_by_id(cat_oid)
    if not cat: raise AppError("Category not found", 404)
    slug = payload.get("slug") or slugify(name, prefix=cat.slug)
    ensure_unique_slug(SubCategory, slug)
    s = sub_insert({
        "name": name,
        "slug": slug,
        "icon": payload.get("icon"),
        "description": payload.get("description"),
    })

    return sub_public(s)

def s_subcategory_get(slug_or_id: str) -> dict:
    s = sub_get_by_slug(slug_or_id) or sub_get_by_id(ObjectId(slug_or_id))
    if not s: raise AppError("Subcategory not found", 404)
    return sub_public(s)

def s_subcategory_list_by_category(category_id: str) -> dict:
    cat_oid = parse_oid(category_id)
    if not cat_oid: raise AppError("Subcategory not found", 404)
    return {
        "items": [ sub_public(s) for s in sub_list_by_category(cat_oid) ]
    }

def s_subcategory_update(slug_or_id: str, payload: dict) -> dict:
    s = sub_get_by_slug(slug_or_id) or sub_get_by_id(ObjectId(slug_or_id))
    if not s: raise AppError("Subcategory not found", 404)

    data = {}
    if "name" in payload:
        data["name"] = payload["name"].strip()
    if "category_id" in payload:
        cat_oid = parse_oid(payload["category_id"])
        if not cat_oid: raise AppError("Category not found", 404)
        cat = cat_get_by_id(cat_oid)
        if not cat: raise AppError("Category not found", 404)
        data["category_id"] = cat

    data["slug"] = slugify(data.get("name"), prefix=cat.slug)
    for k in ("icon", "description"):
        if k in payload: data[k] = payload[k]

    s = sub_update(s, data)
    return sub_public(s)

def s_subcategory_delete(slug_or_id: str) -> None:
    s = sub_get_by_slug(slug_or_id) or sub_get_by_id(ObjectId(slug_or_id))
    if not s: raise AppError("Subcategory not found", 404)
    mark_products_orphan_by_subcategory(s.id)
    sub_delete(s)

# -----PRODUCT-----

def s_product_create(payload: dict) -> dict:
    require_fields(payload, "name", "price")
    name = payload["name"].strip()
    price = float(payload["price"])
    cat = sub = None
    if "category_id" in payload:
        cat_oid = parse_oid(payload["category_id"])
        if not cat_oid: raise AppError("Category not found", 404)
        cat = cat_get_by_id(cat_oid)
        if not cat: raise AppError("Category not found", 404)
    if "subcategory_id" in payload:
        sub_oid = parse_oid(payload["subcategory_id"])
        if not sub_oid: raise AppError("Subcategory not found", 404)
        sub = sub_get_by_id(sub_oid)
    if cat and sub and str(sub.category.id) != cat.id:
        raise AppError("Subcategory not in category", 400)
    slug = slugify(name, prefix = (sub.slug if sub else (cat.slug if cat else None)))
    ensure_unique_slug(Product, slug)
    p = prod_insert({
        "name": name,
        "slug": slug,
        "price": price,
        "description": payload.get("description"),
        "category": cat,
        "subcategory": sub,
        "is_active": payload.get("is_active", True),
        "is_orphan": payload.get("is_orphan", False),
        "orphan_reason": payload.get("orphan_reason", None),
    })
    return product_public(p)

def s_product_get(slug_or_id: str) -> dict:
    from bson import ObjectId
    p = prod_get_by_slug(slug_or_id) or prod_get_by_id(ObjectId(slug_or_id))
    if not p: raise AppError("Product not found", 404)
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
    from bson import ObjectId
    p = prod_get_by_slug(slug_or_id) or prod_get_by_id(ObjectId(slug_or_id))
    if not p: raise AppError("Product not found", 404)

    data = {}
    if "name" in payload:
        data["name"] = payload["name"].strip()
    if "price" in payload:
        price = float(payload["price"])
        if price < 0: raise AppError("Price must be positive", 400)
        data["price"] = price

    cat = p.category; sub = p.subcategory
    if "category_id" in payload:
        if payload["category_id"] is None:
            cat = None
        else:
            cat_oid = parse_oid(payload["category_id"])
            if not cat_oid: raise AppError("Category not found", 404)
            cat = cat_get_by_id(cat_oid)
            if not cat: raise AppError("Category not found", 404)

    if "subcategory_id" in payload:
        if payload["subcategory_id"] is None:
            sub = None
        else:
            sub_oid = parse_oid(payload["subcategory_id"])
            if not sub_oid: raise AppError("Subcategory not found", 404)
            sub = sub_get_by_id(sub_oid)
            if not sub: raise AppError("Subcategory not found", 404)
    if cat and sub and str(sub.category.id) != cat.id:
        raise AppError("Subcategory not in category", 400)

    data["category"] = cat; data["subcategory"] = sub
    data["slug"] = slugify(data.get("name"), prefix = (sub.slug if sub else (cat.slug if cat else None)))
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
    from bson import ObjectId
    p = prod_get_by_slug(slug_or_id) or prod_get_by_id(ObjectId(slug_or_id))
    if not p: raise AppError("Product not found", 404)
    prod_delete(p)


#------KEYWORD------
def _norm_keyword(s: str) -> str:
    return (s or "").strip().lower()

def s_product_suggest(keyword:str, limit: int = 20) -> dict:
    items_kw = pk_suggest(keyword, limit)
    products = []
    for rec in items_kw:
        p = rec.product
        if not p: continue
        if hasattr(p, "is_active") and not p.is_active: continue
        if hasattr(p, "is_orphan") and p.is_orphan: continue
        products.append(product_public(p))

    return {"items": products}

def s_keywords_list(product_id: str) -> dict:
    oid = parse_oid(product_id)
    if not oid: raise AppError("Invalid product id", 400)
    lst = pk_list_by_product(product_id)
    return {
        "items": [{
            "id": str(x.id),
            "keyword": x.keyword,
            "weight": x.weight
        }for x in lst]
    }

def s_keyword_upsert(product_id: str, payload: dict) -> dict:
    require_fields(payload, "keyword")
    kw = _norm_keyword(payload["keyword"])
    if not kw:
        raise AppError("Keyword required", 400)

    oid = parse_oid(product_id)
    if not oid:
        raise AppError("Invalid product id", 400)
    product = Product.objects(id=oid).first()
    if not product:
        raise AppError("Product not found", 404)

    weight = int(payload.get("weight") or 1)
    rec = pk_upsert(product, kw, weight)
    return {"id": str(rec.id), "keyword": rec.keyword, "weight": rec.weight}

def s_keywords_replace(product_id: str, payload: dict) -> dict:

    oid = parse_oid(product_id)
    if not oid:
        raise AppError("Invalid product id", 400)
    product = Product.objects(id=oid).first()
    if not product:
        raise AppError("Product not found", 404)

    items = payload.get("items") or []
    normed = []
    for it in items:
        kw = _norm_keyword(it.get("keyword", ""))
        if kw:
            normed.append({"keyword": kw, "weight": int(it.get("weight") or 1)})

    pk_bulk_replace(product, normed)
    return s_keywords_list(product_id)

def s_keyword_delete(keyword_id: str) -> None:
    rec = pk_get_by_id(keyword_id)
    if not rec: raise AppError("Invalid keyword id", 400)
    pk_delete(rec)






