"""Application exceptions. API layer maps these to HTTP status codes."""


class AuthenticationError(Exception):
    """Raised when email/password verification fails. API layer maps to 401."""

    def __init__(self, message: str = "Invalid email or password") -> None:
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    """Raised when a resource already exists (e.g. email already registered). API layer maps to 409."""

    def __init__(self, message: str = "Resource already exists") -> None:
        self.message = message
        super().__init__(message)
