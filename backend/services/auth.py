"""Authentication helpers (stdlib only — no new dependencies).

Passwords: PBKDF2-HMAC-SHA256, 600k iterations, 16-byte random salt
(OWASP-recommended parameters), constant-time comparison.
Sessions: 256-bit url-safe tokens validated against the sessions table.
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 600_000
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS, dklen=_KEY_BYTES)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
