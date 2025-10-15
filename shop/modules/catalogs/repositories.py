from typing import Optional, Tuple, Iterable
from bson import ObjectId
from .models import Category, SubCategory, Product, ProductKeyword
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

# ----PRODUCT KEYWORD-----
def pk_list_by_product(pid: str) -> list[ProductKeyword]:
    oid = parse_oid(pid)
    return ProductKeyword.objects(id=oid).first() if oid else []

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
        out.append(pk_upsert(product, kw, it.get("weight") or 1))
    if out: ProductKeyword.objects.insert(out)
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

