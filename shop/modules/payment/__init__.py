from flask import Blueprint

bp = Blueprint("payments", __name__, url_prefix="/api/payments")
bp_admin = Blueprint("payments_admin", __name__, url_prefix="/api/admin/payments")
