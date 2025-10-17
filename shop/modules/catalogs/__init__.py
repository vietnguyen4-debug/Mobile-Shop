from flask import Blueprint
bp = Blueprint('catalogs', __name__, url_prefix='/api')
bp_admin = Blueprint('catalogs_admin', __name__, url_prefix='/api/admin')