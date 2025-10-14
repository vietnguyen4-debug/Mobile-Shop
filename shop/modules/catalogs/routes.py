from flask import request
from flask_jwt_extended import jwt_required
from ...core.responses import ok, created, no_content
from ...core.rbac import *
from . import bp, bp_admin
from .services import *

#------PUBLIC-------
@bp.get("/categories")
def r_cat_list():
    return ok(s_category_list())

@bp.get("/categories/<slug_or_id>")
def r_cat_get(slug_or_id):
    return ok(s_category_get(slug_or_id))

@bp.get("/subcategories")
def r_sub_list_by_cat():
    return ok(s_subcategory_list_by_category(request.args.get("category_id")))

@bp.get("/subcategories/<slug_or_id>")
def r_sub_get(slug_or_id):
    return ok(s_subcategory_get(slug_or_id))

@bp.get("/products")
def r_product_list():
    page = request.args.get("page", 1)
    limit = request.args.get("limit", 20)
    return ok(s_product_list(page, limit))

@bp.get("/products/by-sub/<sub_id>")
def r_products_by_sub(sub_id):
    page = request.args.get("page", 1)
    limit = request.args.get("limit", 20)
    return ok(s_product_list_by_sub(sub_id, page, limit, active_only=True))

@bp.get("/products/<slug_or_id>")
def r_product_get(slug_or_id):
    return ok(s_product_get(slug_or_id))

@bp.get("/home/suggest")
def r_home_suggest():
    kw = request.args.get("keyword", "")
    limit = request.args.get("limit", 20)
    return ok(s_product_suggest(kw, int(limit)))

@bp.get("/product/suggest")
def r_product_suggest():
    kw = request.args.get("keyword", "")
    limit = request.args.get("limit", 20)
    return ok(s_product_suggest(kw, int(limit)))

#-----ADMIN-------
@bp_admin.post("/categories")
@jwt_required()
@roles_required("admin")
def r_category_create():
    return created(s_category_create(request.get_json() or {}))

@bp_admin.put("/categories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_category_update(slug_or_id):
    return ok(s_category_update(slug_or_id, request.get_json() or {}))

@bp_admin.delete("/categories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_category_delete(slug_or_id):
    return ok(s_category_delete(slug_or_id))

@bp_admin.post("/subcategories")
@jwt_required()
@roles_required("admin")
def r_subcategory_create():
    return created(s_subcategory_create(request.get_json() or {}))

@bp_admin.put("/subcategories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_subcategory_update(slug_or_id):
    return ok(s_subcategory_update(slug_or_id, request.get_json() or {}))

@bp_admin.delete("/subcategories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_subcategory_delete(slug_or_id):
    return ok(s_subcategory_delete(slug_or_id))

@bp_admin.post("/products")
@jwt_required()
@roles_required("admin")
def r_product_create():
    return created(s_product_create(request.get_json() or {}))

@bp_admin.put("/products/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_product_update(slug_or_id):
    return ok(s_product_update(slug_or_id, request.get_json() or {}))

@bp_admin.delete("/products/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_product_delete(slug_or_id):
    return ok(s_product_delete(slug_or_id))

@bp_admin.get("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keywords_list(pid):
    return ok(s_keywords_list(pid))

@bp_admin.post("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keyword_upsert(pid):
    return created(s_keyword_upsert(pid, request.get_json() or {}))

@bp_admin.put("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keywords_replace(pid):
    return ok(s_keywords_replace(pid, request.get_json() or {}))

@bp_admin.delete("/keywords/<kid>")
@jwt_required()
@roles_required("admin")
def r_admin_keyword_delete(kid):
    s_keyword_delete(kid)
    return no_content()






