from typing import Optional, Literal, Tuple
from bson import ObjectId

from .repositories import cat_get_by_id, sub_get_by_id
from ...core.utils import parse_oid
from ...core.exceptions import AppError
from . import repositories as repo
from .models import Category, SubCategory, Product

Kind = Literal["category", "subcategory", "product"]


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


# ---- UNIFIED HELPER FUNCTIONS ----
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
