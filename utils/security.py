"""Lightweight encryption helper for sensitive employee fields."""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import SECRET_KEY_PATH


def _ensure_key(key_path: Path = SECRET_KEY_PATH) -> bytes:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        key = key_path.read_bytes().strip()
        if key:
            return key
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_ensure_key())


def encrypt_text(value: str) -> str:
    """Encrypt text and return URL-safe string."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    token = _fernet().encrypt(text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: str) -> str:
    """Decrypt token string and return plain text."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        plain = _fernet().decrypt(text.encode("utf-8"))
        return plain.decode("utf-8")
    except (InvalidToken, ValueError):
        # Backward compatibility: return as-is if data is plain.
        try:
            decoded = base64.urlsafe_b64decode(text.encode("utf-8"))
            return decoded.decode("utf-8")
        except Exception:
            return text

