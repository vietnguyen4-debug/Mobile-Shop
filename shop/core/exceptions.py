# core/exceptions.py

class AppError(Exception):
    def __init__(
        self,
        message: str,
        status: int = 400,
        code=None,
        extra: dict | None = None,
        status_code: int | None = None,
        detail: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status = int(status_code) if status_code is not None else int(status)
        self.code = code
        self.extra = extra if extra is not None else (detail or {})

    @property
    def status_code(self) -> int:
        return self.status

    @property
    def detail(self) -> dict:
        return self.extra
