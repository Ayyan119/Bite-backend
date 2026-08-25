"""Security utilities for password hashing and verification."""

import hashlib
import hmac
import os
from typing import Optional


def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(plain_password: str, stored_hash: Optional[str] = None) -> bool:
    """Verifies a plain password against stored hash with backward compatibility."""
    if not stored_hash or not plain_password:
        return False

    # Backward compatibility with legacy plain text or test dummy accounts
    if "$" not in stored_hash:
        return plain_password == stored_hash

    try:
        salt, expected_hash = stored_hash.split("$", 1)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        ).hex()
        return hmac.compare_digest(pwd_hash, expected_hash)
    except Exception:
        return False
