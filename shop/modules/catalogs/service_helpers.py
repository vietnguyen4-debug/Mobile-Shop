from typing import Optional, Literal, Tuple
from ...core.utils import parse_oid
from ...core.exceptions import AppError
from . import repositories as repo
from .models import Category, SubCategory, Product

Kind = Literal["category", "subcategory", "product"]

def _find_raw(kind:Kind, slug_or_id: str):
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
        obj = repo.prod_get_by_slug(slug_or_id)
        if obj: return obj
        oid = parse_oid(slug_or_id)
        return repo.prod_get_by_id(oid) if oid else None

    return None

def find_by_slug_or_id(kind:Kind, slug_or_id: str, *, invalid_id_400 = False) -> Optional[Category | SubCategory | Product]:
    obj = _find_raw(kind, slug_or_id)
    if obj: return obj
    if invalid_id_400 and not parse_oid(slug_or_id):
        raise AppError("Invalid ID", 400, name = "INVALID_ID")

    raise AppError(f"{kind.capitalize()} not found", 404, name = f"INVALID_{kind.upper()}_NOT_FOUND")

def find_cat_and_sub_by_slug_or_id(slug_or_id: str) -> Tuple[Category, SubCategory]:
    cat = find_by_slug_or_id("category", slug_or_id)
    sub = find_by_slug_or_id("subcategory", slug_or_id)
    if sub.category.id != cat.id:
        raise AppError("Subcategory not in category", 400, name="INVALID_CATEGORY_OR_SUBCATEGORY")
    return cat, sub

