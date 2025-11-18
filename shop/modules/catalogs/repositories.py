from typing import Optional, Tuple, Iterable
from bson import ObjectId
from .models import Category, SubCategory, Product, ProductKeyword, Media, Spec
from ...core.utils import parse_oid
MAX_MEDIA = 20
MAX_SPECS = 80

# ---- CATEGORY ----
def cat_get_by_id(oid: ObjectId) -> Optional[Category]:
    return Category.objects(id=oid).first()

def cat_get_by_slug(slug: str) -> Optional[Category]:
    return Category.objects(slug=slug).first()

def cat_list_all():
    return list(Category.objects.order_by("name"))

def cat_insert(data: dict) -> Category:
    return Category(**data).save()

def cat_update(c: Category, data: dict) -> Category:
    for k,v in data.items(): setattr(c,k,v)
    return c.save()

def cat_delete(c: Category) -> None:
    c.delete()

# ---- SUBCATEGORY ----
def sub_get_by_id(oid: ObjectId) -> Optional[SubCategory]:
    return SubCategory.objects(id=oid).first()

def sub_get_by_slug(slug: str) -> Optional[SubCategory]:
    return SubCategory.objects(slug=slug).first()

def sub_list_by_category(cat_oid: ObjectId):
    return list(SubCategory.objects(category=cat_oid).order_by("name"))

def sub_insert(data: dict) -> SubCategory:
    return SubCategory(**data).save()

def sub_update(s: SubCategory, data: dict) -> SubCategory:
    for k,v in data.items(): setattr(s,k,v)
    return s.save()

def sub_delete(s: SubCategory) -> None:
    s.delete()

# -------- Product --------
def prod_get_by_id(oid: ObjectId) -> Optional[Product]:
    return Product.objects(id=oid).first()

def prod_get_by_slug(slug: str) -> Optional[Product]:
    return Product.objects(slug=slug).first()

def prod_list_all(page: int, limit: int) -> Tuple[list[Product], int]:
    qs = Product.objects
    total = qs.count()
    items = list(qs.order_by("-created_at").skip((page-1)*limit).limit(limit))
    return items, total

def prod_list_by_sub(sub_oid: ObjectId, page: int, limit: int, *, active_only=True) -> Tuple[list[Product], int]:
    qs = Product.objects(subcategory=sub_oid)
    if active_only: qs = qs.filter(is_active=True, is_orphan=False)
    total = qs.count()
    items = list(qs.order_by("-created_at").skip((page-1)*limit).limit(limit))
    return items, total

def prod_search_by_name(keyword: str, page: int, limit: int, *, active_only=True) -> Tuple[list[Product], int]:
    kw = (keyword or "").strip()
    if not kw:
        return [], 0

    # Clamp pagination to keep queries predictable and avoid huge skips/limits.
    page = max(int(page or 1), 1)
    limit = max(1, min(int(limit or 20), 100))

    qs = Product.objects(name__icontains=kw)
    if active_only:
        qs = qs.filter(is_active=True, is_orphan=False)

    total = qs.count()
    items = list(qs.order_by("-created_at").skip((page - 1) * limit).limit(limit))
    return items, total

def prod_insert(data: dict) -> Product:
    return Product(**data).save()

def prod_update(p: Product, data: dict) -> Product:
    for k,v in data.items(): setattr(p,k,v)
    return p.save()

def prod_delete(p: Product) -> None:
    p.delete()

def mark_products_orphan_by_category(cat_oid: ObjectId):
    for p in Product.objects(category=cat_oid):
        p.category = None; p.is_orphan = True; p.is_active = False; p.orphan_reason = "category_deleted"; p.save()

def mark_products_orphan_by_subcategory(sub_oid: ObjectId):
    for p in Product.objects(subcategory=sub_oid):
        p.subcategory = None; p.is_orphan = True; p.is_active = False; p.orphan_reason = "subcategory_deleted"; p.save()

# -------- Product Media--------
def media_list(p: Product) -> list[Media]:
    return sorted(p.media or [], key=lambda m: (not bool(getattr(m, "is_primary", False)), getattr(m, "order", 0) or 0))

def media_get(p: Product, media_id: str) -> Media | None:
    for m in p.media or []:
        if m.id == media_id: return m
    return None

def media_upsert(p: Product, item: dict) -> Product:
    mid = item.get("id")
    if mid:
        m = media_get(p, mid)
    else:
        m = None
    if m:
        for k in ("kind", "url", "alt", "is_primary", "order"):
            if k in item:
                setattr(m, k, item[k])
    else:
        p.media = list(p.media or [])
        p.media.append(Media(
            id=mid,
            kind=item.get("kind") or "image",
            url=item.get("url"),
            alt=item.get("alt"),
            is_primary=bool(item.get("is_primary", False)),
            order=int(item.get("order") or 0),
        ))
    return p.save()

def media_delete(p: Product, media_id: str) -> Product:
    p.media = [m for m in (p.media or []) if m.id != media_id]
    return p.save()

def media_replace(p: Product, items: list[dict]) -> Product:
    p.media = []
    for it in items or []:
        p.media.append(Media(
            id=it.get("id"),
            kind=it.get("kind") or "image",
            url=it.get("url"),
            alt=it.get("alt"),
            is_primary=bool(it.get("is_primary", False)),
            order=int(it.get("order") or 0),
        ))
    return p.save()

def media_reorder(p: Product, order_ids: list[str]) -> Product:
    order_map = {mid: i for i, mid in enumerate(order_ids)}
    for m in p.media or []:
        if m.id in order_map:
            m.order = order_map[m.id]
    return p.save()

def media_set_primary(p: Product, media_id: str) -> Product:
    for m in p.media or []:
        m.is_primary = (m.id == media_id)
    return p.save()

# -------- Product Specs--------
def specs_list(p: Product) -> list[Spec]:
    return sorted(p.specs or [], key=lambda s: (getattr(s, "order", 0) or 0,
                                                (s.group or ""), (s.key or "")))

def spec_get(p: Product, spec_id: str) -> Spec | None:
    for s in p.specs or []:
        if s.id == spec_id:
            return s
    return None

def spec_upsert(p: Product, item: dict) -> Product:
    sid = item.get("id")
    s = spec_get(p, sid) if sid else None
    if s:
        for k in ("group", "key", "value", "order"):
            if k in item:
                setattr(s, k, item[k])
    else:
        p.specs = list(p.specs or [])
        p.specs.append(Spec(
            id=sid,
            group=item.get("group"),
            key=item.get("key"),
            value=item.get("value"),
            order=int(item.get("order") or 0),
        ))
    return p.save()

def spec_delete(p: Product, spec_id: str) -> Product:
    p.specs = [s for s in (p.specs or []) if s.id != spec_id]
    return p.save()

def specs_replace(p: Product, items: list[dict]) -> Product:
    p.specs = []
    for it in items or []:
        p.specs.append(Spec(
            id=it.get("id"),
            group=it.get("group"),
            key=it.get("key"),
            value=it.get("value"),
            order=int(it.get("order") or 0),
        ))
    return p.save()

def specs_reorder(p: Product, order_ids: list[str]) -> Product:
    order_map = {sid: i for i, sid in enumerate(order_ids)}
    for s in p.specs or []:
        if s.id in order_map:
            s.order = order_map[s.id]
    return p.save()


# ----PRODUCT KEYWORD-----
def pk_list_by_product(pid: str) -> list[ProductKeyword]:
    oid = parse_oid(pid)
    return list(ProductKeyword.objects(product=oid) if oid else None)

def pk_get_by_id(kid: str) -> list[ProductKeyword]:
    oid = parse_oid(kid)
    return list(ProductKeyword.objects(id=oid) if oid else None)

def pk_find(product: Product, keyword: str) -> Optional[ProductKeyword]:
    return ProductKeyword.objects(product=product, keyword=keyword).first()

def pk_upsert(product: Product, keyword: str, weight: int = 1) -> ProductKeyword:
    rec = pk_find(product, keyword)
    if rec:
        rec.weight = weight
        rec.save()
        return rec
    return ProductKeyword(product=product, keyword=keyword, weight=weight).save()

def pk_bulk_replace(product: Product, items: Iterable[dict]) -> list[ProductKeyword]:
    ProductKeyword.objects(product=product).delete()
    out = []
    for it in items:
        kw = (it.get("keyword") or "").strip()
        if not kw: continue
        out.append(ProductKeyword(product=product, keyword=kw, weight=it.get("weight") or 1))
    if out:
        for rec in out:
            rec.save()
    return out


def pk_delete(pk: ProductKeyword) -> None:
    pk.delete()

def pk_suggest(keyword: str, limit: int = 20) -> list[ProductKeyword]:
    kw = (keyword or "").strip()
    if not kw: return []

    exact = ProductKeyword.objects(keyword=kw).order_by("-weight").limit(limit)
    remain = max(0, limit - exact.count())
    pref = []
    cont = []

    if remain > 0:
        pref = list(ProductKeyword.objects(keyword__istartswith=kw).order_by("-weight").limit(remain))
        remain = max(0, limit - exact.count() - len(pref))

    if remain > 0:
        cont = list(ProductKeyword.objects(keyword__icontains=kw).order_by("-weight").limit(remain))

    seen = set(); out = []
    for rec in list(exact) + list(pref) + list(cont):
        pid = str(rec.product.id) if rec.product else None
        if pid and pid not in seen:
            seen.add(pid)
            out.append(rec)
        if len(out) >= limit: break
    return out

