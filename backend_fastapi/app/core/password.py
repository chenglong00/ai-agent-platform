"""Password hashing and verification. Used by auth (login, credentials) and initial owner setup."""

from pwdlib import PasswordHash

# Algorithm name we store in AuthIdentity.password_algo for credentials
PASSWORD_ALGO = "argon2"

_hasher = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    """Return a secure hash of the password (e.g. Argon2)."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain password matches the stored hash."""
    return _hasher.verify(plain, hashed)
