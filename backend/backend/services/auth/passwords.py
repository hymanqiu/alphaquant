"""bcrypt password hashing.

Wraps the ``bcrypt`` library with a thin API. Hashes are stored as UTF-8
strings; verification handles both bytes and strings on input.
"""

from __future__ import annotations

import bcrypt

# bcrypt cost factor. 12 ~= 250ms on a modern laptop core; suitable for
# interactive logins. Bump in prod if hardware speeds up.
_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt-hashed password as an ASCII string."""
    if not isinstance(plain, str) or len(plain) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(plain) > 256:
        raise ValueError("Password must be at most 256 characters")
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    digest = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return digest.decode("ascii")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Return True iff *plain* matches the stored *hashed* digest.

    Returns False (not raises) for empty/None hashes — useful for users
    created via OAuth/magic link who have no password set.
    """
    if not hashed or not isinstance(plain, str):
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False
