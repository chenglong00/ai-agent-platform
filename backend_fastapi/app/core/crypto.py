"""Symmetric encryption for sensitive values at rest (e.g. OAuth tokens)."""

from __future__ import annotations

import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


def derive_fernet_key(secret: str, salt: Optional[bytes] = None) -> bytes:
    """Derive a 32-byte Fernet key from a secret string. Uses PBKDF2 with SHA256."""
    if salt is None:
        salt = b"app-core-crypto-v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    return key


def get_fernet(encryption_key: Optional[str] = None) -> Optional[Fernet]:
    """Return a Fernet instance if encryption is configured, else None (plaintext fallback)."""
    if not encryption_key or len(encryption_key) < 32:
        return None
    try:
        # Allow raw base64 key or a passphrase (we derive key for long strings)
        key_bytes = encryption_key.encode("utf-8")
        if len(key_bytes) == 44 and key_bytes.endswith(b"="):
            key = key_bytes  # Likely Fernet key
        else:
            key = derive_fernet_key(encryption_key)
        return Fernet(key)
    except Exception:
        return None


def encrypt_value(plaintext: Optional[str], fernet: Optional[Fernet]) -> Optional[str]:
    """Encrypt a string for storage. Returns None for None/empty; otherwise encrypted base64."""
    if not plaintext or not fernet:
        return plaintext
    try:
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")
    except Exception:
        return plaintext


def decrypt_value(ciphertext: Optional[str], fernet: Optional[Fernet]) -> Optional[str]:
    """Decrypt a stored value. Returns as-is if no fernet or not encrypted."""
    if not ciphertext or not fernet:
        return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ciphertext  # Legacy plaintext
    except Exception:
        return ciphertext


def decrypt_value_with_rotation(ciphertext: Optional[str], fernets: list[Optional[Fernet]]) -> Optional[str]:
    """Decrypt with the first key that succeeds. Supports rotation: try current then previous key."""
    if not ciphertext:
        return ciphertext
    for fernet in fernets:
        if not fernet:
            continue
        try:
            return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            continue
        except Exception:
            continue
    return ciphertext  # Legacy plaintext or unreadable


def _fernet_primary() -> Optional[Fernet]:
    """Lazy Fernet from ENCRYPTION_KEY (for encrypt and first try on decrypt)."""
    from app.core.config import settings
    return get_fernet(settings.ENCRYPTION_KEY)


def _fernets_for_decrypt() -> list[Optional[Fernet]]:
    """Lazy [current, previous] for decryption (key rotation)."""
    from app.core.config import settings
    keys = [settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PREVIOUS] if settings.ENCRYPTION_KEY_PREVIOUS else [settings.ENCRYPTION_KEY]
    return [get_fernet(k) for k in keys]


class EncryptedString(TypeDecorator[str]):
    """Stores strings encrypted at rest. Uses Fernet; if ENCRYPTION_KEY is unset, stores plaintext."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt_value(value, _fernet_primary())

    def process_result_value(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        if value is None:
            return None
        return decrypt_value_with_rotation(value, _fernets_for_decrypt())
