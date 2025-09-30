from flask import jsonify

class AppError(Exception):
    def __init__(self, message, status_code=400, detail=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}

def register_errors(app):
    @app.errorhandler(AppError)
    def _handle_app_error(error: AppError):
        return jsonify({
            "data": None,
            "error": {
                "code": error.status_code,
                "message": error.message,
                "detail": error.detail
            }
        })

    @app.errorhandler(404)
    def _404_(_):
        return jsonify({
            "data": None,
            "error": {
                "code": 404,
                "message": "Not found"
            }
        }), 404

    @app.errorhandler(500)
    def _500_(_):
        return jsonify({
            "data": None,
            "error": {
                "code": 500,
                "message": "Internal server error"
            }
        }), 500

    @app.errorhandler(405)
    def _405_(_):
        return jsonify({
            "data": None,
            "error": {
                "code": 405,
                "message": "Method not allowed"
            }
        }), 405