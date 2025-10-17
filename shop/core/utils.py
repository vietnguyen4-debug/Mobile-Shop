import re, unicodedata
from typing import Tuple
from bson import ObjectId

def slugify(text: str, prefix: str | None = None) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return f"{prefix}-{text}" if prefix else text

def parse_oid(oid: str):
    if not isinstance(oid, str): return None
    s = oid.strip()
    return ObjectId(s) if ObjectId.is_valid(s) else None

def parse_pagination(page: int | str | None, limit: int | str | None, *, max_limit=100) -> Tuple[int, int]:
    p = max(int(page or 1), 1)
    l = min(max(int(limit or 20), 1), max_limit)
    return p, l

def ensure_unique_slug(model, slug: str, *, field="slug"):
    from .exceptions import AppError
    if not slug:
        raise AppError("Slug required", 400)
    if model.objects(**{field: slug}).first():
        raise AppError("Slug already used", 409)

def resolve_by_slug_or_id(model, identifier: str):
    obj = model.objects(slug=identifier).first()
    if obj:
        return obj
    oid = parse_oid(identifier)
    return model.objects(id=oid).first() if oid else None



