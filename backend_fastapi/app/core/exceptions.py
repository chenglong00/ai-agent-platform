"""Application exceptions. Registered handlers map these to HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AuthenticationError(Exception):
    """Raised when authentication fails or the account is not allowed to sign in."""

    def __init__(
        self,
        message: str = "Invalid email or password",
        *,
        status_code: int = 401,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConflictError(Exception):
    """Raised when a resource already exists (e.g. email already registered)."""

    def __init__(self, message: str = "Resource already exists") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain exceptions to HTTP status codes."""

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        _request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(
        _request: Request,
        exc: ConflictError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        _request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})
