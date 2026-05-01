"""Input normalization and validation helpers."""


def normalize_email(email: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return email.lower().strip()


def normalize_password(password: str) -> str:
    """Strip leading/trailing whitespace from a password."""
    return password.strip()
