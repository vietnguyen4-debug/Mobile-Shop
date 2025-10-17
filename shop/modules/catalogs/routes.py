from flask import request
from flask_jwt_extended import jwt_required
from ...core.responses import ok, created, no_content
from ...core.rbac import *
from . import bp, bp_admin
from .services import *

#------PUBLIC-------
@bp.get("/categories")
def r_cat_list():
    return ok(s_category_list(), "Categories listed successfully.")

@bp.get("/categories/<slug_or_id>")
def r_cat_get(slug_or_id):
    return ok(s_category_get(slug_or_id), "Category retrieved successfully.")

@bp.get("/subcategories")
def r_sub_list_by_cat():
    return ok(s_subcategory_list_by_category(request.args.get("category_id")), "Subcategories listed successfully.")

@bp.get("/subcategories/<slug_or_id>")
def r_sub_get(slug_or_id):
    return ok(s_subcategory_get(slug_or_id), "Subcategory retrieved successfully.")

@bp.get("/products")
def r_product_list():
    page = request.args.get("page", 1)
    limit = request.args.get("limit", 20)
    return ok(s_product_list(page, limit), "Products listed successfully.")

@bp.get("/products/by-sub/<sub_id>")
def r_products_by_sub(sub_id):
    page = request.args.get("page", 1)
    limit = request.args.get("limit", 20)
    return ok(s_product_list_by_sub(sub_id, page, limit, active_only=True), "Products listed successfully.")

@bp.get("/products/<slug_or_id>")
def r_product_get(slug_or_id):
    return ok(s_product_get(slug_or_id), "Product retrieved successfully.")

@bp.get("/products/<slug_or_id>/media")
def r_product_media(slug_or_id):
    return ok(s_media_list(slug_or_id), "Media listed successfully.")

@bp.get("/products/<slug_or_id>/specs")
def r_product_specs(slug_or_id):
    return ok(s_specs_list(slug_or_id), "Specs listed successfully.")

@bp.get("/home/suggest")
def r_home_suggest():
    kw = request.args.get("keyword", "")
    limit = request.args.get("limit", 20)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        raise AppError("Invalid limit parameter", 400, name="INVALID_LIMIT")
    return ok(s_keyword_suggest(kw, limit), "Home suggest products listed successfully.")


@bp.get("/product/suggest")
def r_product_suggest():
    kw = request.args.get("keyword", "")
    limit = request.args.get("limit", 20)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        raise AppError("Invalid limit parameter", 400, name="INVALID_LIMIT")
    return ok(s_keyword_suggest(kw, limit), "Product suggest products listed successfully.")


#=============ADMIN==============
#-------CATEGORY----------
@bp_admin.post("/categories")
@jwt_required()
@roles_required("admin")
def r_category_create():
    return created(s_category_create(request.get_json() or {}), "Category created successfully.")

@bp_admin.put("/categories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_category_update(slug_or_id):
    return ok(s_category_update(slug_or_id, request.get_json() or {}), "Category updated successfully.")

@bp_admin.delete("/categories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_category_delete(slug_or_id):
    s_category_delete(slug_or_id)
    return no_content("Category deleted successfully.")

#-------SUBCATEGORY----------
@bp_admin.post("/subcategories")
@jwt_required()
@roles_required("admin")
def r_subcategory_create():
    return created(s_subcategory_create(request.get_json() or {}), "Subcategory created successfully.")

@bp_admin.put("/subcategories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_subcategory_update(slug_or_id):
    return ok(s_subcategory_update(slug_or_id, request.get_json() or {}), "Subcategory updated successfully.")

@bp_admin.delete("/subcategories/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_subcategory_delete(slug_or_id):
    s_subcategory_delete(slug_or_id)
    return no_content("Subcategory deleted successfully.")

#-------PRODUCT----------
@bp_admin.post("/products")
@jwt_required()
@roles_required("admin")
def r_product_create():
    return created(s_product_create(request.get_json() or {}), "Product created successfully.")

@bp_admin.put("/products/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_product_update(slug_or_id):
    return ok(s_product_update(slug_or_id, request.get_json() or {}), "Product updated successfully.")

@bp_admin.delete("/products/<slug_or_id>")
@jwt_required()
@roles_required("admin")
def r_product_delete(slug_or_id):
    s_product_delete(slug_or_id)
    return no_content("Product deleted successfully.")

#---------MEDIA---------
@bp_admin.post("/products/<slug_or_id>/media")
@jwt_required()
@roles_required("admin")
def r_media_add(slug_or_id):
    return created(s_media_add(slug_or_id, request.get_json() or {}), "Media added successfully.")

@bp_admin.put("/products/<slug_or_id>/media/<media_id>")
@jwt_required()
@roles_required("admin")
def r_media_update(slug_or_id, media_id):
    return ok(s_media_update(slug_or_id, media_id, request.get_json() or {}), "Media updated successfully.")

@bp_admin.delete("/products/<slug_or_id>/media/<media_id>")
@jwt_required()
@roles_required("admin")
def r_media_delete(slug_or_id, media_id):
    s_media_delete(slug_or_id, media_id)
    return no_content("Media deleted successfully.")

@bp_admin.put("/products/<slug_or_id>/media/reorder")
@jwt_required()
@roles_required("admin")
def r_media_reorder(slug_or_id):
    body = request.get_json() or {}
    order = body.get("order") or body.get("ids") or []
    return ok(s_media_reorder(slug_or_id, order), "Media reordered successfully.")

@bp_admin.post("/products/<slug_or_id>/media/<media_id>/set-primary")
@jwt_required()
@roles_required("admin")
def r_media_set_primary(slug_or_id, media_id):
    return ok(s_media_set_primary(slug_or_id, media_id), "Primary media set successfully.")

@bp_admin.put("/products/<slug_or_id>/media/replace")
@jwt_required()
@roles_required("admin")
def r_media_replace(slug_or_id):
    return ok(s_media_replace(slug_or_id, request.get_json() or {}), "Media replaced successfully.")

#--------SPECS-----------
@bp_admin.post("/products/<slug_or_id>/specs")
@jwt_required()
@roles_required("admin")
def r_spec_add(slug_or_id):
    return created(s_specs_add(slug_or_id, request.get_json() or {}), "Spec added successfully.")

@bp_admin.put("/products/<slug_or_id>/specs/<spec_id>")
@jwt_required()
@roles_required("admin")
def r_spec_update(slug_or_id, spec_id):
    return ok(s_specs_update(slug_or_id, spec_id, request.get_json() or {}), "Spec updated successfully.")

@bp_admin.delete("/products/<slug_or_id>/specs/<spec_id>")
@jwt_required()
@roles_required("admin")
def r_spec_delete(slug_or_id, spec_id):
    s_specs_delete(slug_or_id, spec_id)
    return no_content("Spec deleted successfully.")

@bp_admin.put("/products/<slug_or_id>/specs/reorder")
@jwt_required()
@roles_required("admin")
def r_specs_reorder(slug_or_id):
    body = request.get_json() or {}
    order = body.get("order") or body.get("ids") or []
    return ok(s_specs_reorder(slug_or_id, order), "Specs reordered successfully.")

@bp_admin.put("/products/<slug_or_id>/specs/replace")
@jwt_required()
@roles_required("admin")
def r_specs_replace(slug_or_id):
    return ok(s_specs_replace(slug_or_id, request.get_json() or {}), "Specs replaced successfully.")

#-------KEYWORD----------
@bp_admin.get("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keywords_list(pid):
    return ok(s_keyword_list(pid), "Keywords listed successfully.")

@bp_admin.post("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keyword_upsert(pid):
    return created(s_keyword_upsert(pid, request.get_json() or {}), "Keyword created successfully.")

@bp_admin.put("/products/<pid>/keywords")
@jwt_required()
@roles_required("admin")
def r_admin_keywords_replace(pid):
    return ok(s_keyword_bulk_replace(pid, request.get_json() or {}), "Keywords replaced successfully.")

@bp_admin.delete("/products/<pid>/keywords/<keyword>")
@jwt_required()
@roles_required("admin")
def r_admin_keyword_delete(pid, keyword):
    s_keyword_delete(pid, keyword)
    return no_content("Keyword deleted successfully.")







