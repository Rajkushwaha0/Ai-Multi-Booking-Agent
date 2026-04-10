from datetime import datetime, timezone, timedelta

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from config import get_settings
from logger import app_logger

# ------------------------------------------------------------------------------
# Password hashing context — bcrypt is intentionally slow to resist brute force.
# CryptContext handles salt generation and scheme upgrades automatically.
# ------------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    A unique random salt is generated and embedded in the returned hash string.
    Never store plain-text passwords — only the hash goes into the database.
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Checks whether a plain-text password matches a stored bcrypt hash.
    Returns True on match, False otherwise.
    Used during login to validate credentials without ever decrypting.
    """
    return _pwd_context.verify(plain, hashed)


# ------------------------------------------------------------------------------
# JWT helpers
# ------------------------------------------------------------------------------

# Token lifetimes
_ACCESS_TOKEN_EXPIRE_DAYS  = 30
_REFRESH_TOKEN_EXPIRE_DAYS    = 7


def _build_token(payload: dict, expires_delta: timedelta) -> str:
    """
    Internal helper — adds expiry and issued-at timestamps to a payload,
    then signs and encodes it as a JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload.update({
        "iat": now,
        "exp": now + expires_delta,
    })

    return jwt.encode(
        payload,
        settings.jwt.secret_key,   # replace JWT_SECRET_KEY in .env with your actual secret
        algorithm=settings.jwt.algorithm,
    )


def create_access_token(user_id: str, email: str) -> str:
    """
    Creates a short-lived access token (15 minutes).

    Payload:
        sub   — user ID (the token's subject)
        email — included so route handlers can identify the user without a DB hit
        type  — "access" (guards against using a refresh token as an access token)
        iat   — issued-at timestamp
        exp   — expiry (now + 15 min)
    """
    app_logger.debug("Creating access token for user_id=%s", user_id)

    return _build_token(
        payload={"sub": user_id, "email": email, "type": "access"},
        expires_delta=timedelta(days=_ACCESS_TOKEN_EXPIRE_DAYS),
    )


def create_refresh_token(user_id: str) -> str:
    """
    Creates a long-lived refresh token (7 days).

    Payload:
        sub  — user ID
        type — "refresh" (must NOT be accepted by routes that expect an access token)
        iat  — issued-at timestamp
        exp  — expiry (now + 7 days)

    Note: refresh tokens should be stored in the database on issue
    so they can be revoked on logout or suspicious activity.
    """
    app_logger.debug("Creating refresh token for user_id=%s", user_id)

    return _build_token(
        payload={"sub": user_id, "type": "refresh"},
        expires_delta=timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.

    Returns the full payload dict on success.
    Raises HTTP 401 with a specific message for each failure mode:
        - ExpiredSignatureError → token was valid but has expired
        - InvalidTokenError     → token is malformed, tampered, or has a bad signature

    Usage:
        payload = decode_token(token)
        user_id = payload["sub"]
        token_type = payload["type"]   # "access" or "refresh"
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
        app_logger.debug("Token decoded successfully for sub=%s", payload.get("sub"))
        return payload

    except jwt.ExpiredSignatureError:
        app_logger.warning("Token validation failed: token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    except jwt.InvalidTokenError as exc:
        app_logger.warning("Token validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
