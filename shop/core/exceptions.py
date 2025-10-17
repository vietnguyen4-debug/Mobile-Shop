# core/exceptions.py

class AppError(Exception):
    def __init__(self, message, status=400, code=None, name=None, detail=None):
        super().__init__(message)
        self.message = message
        self.status = int(status)
        self.code = int(code or status)
        self.name = name
        self.detail = detail or {}
