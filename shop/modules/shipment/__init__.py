from flask import Blueprint

bp = Blueprint("shipments", __name__, url_prefix="/api/shipments")
bp_admin = Blueprint("shipments_admin", __name__, url_prefix="/api/admin/shipments")