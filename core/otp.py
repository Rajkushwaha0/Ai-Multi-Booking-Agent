import random
import string

from fastapi import HTTPException, status

from redis_client import get_redis
from logger import app_logger


# ------------------------------------------------------------------------------
# OTP generation
# ------------------------------------------------------------------------------

def generate_otp() -> str:
    """
    Returns a random 6-digit string suitable for email verification.
    Uses random.choices over the digit character set — fast and sufficient
    for a short-lived code that is rate-limited and single-use.
    """
    return "".join(random.choices(string.digits, k=6))


# ------------------------------------------------------------------------------
# OTP storage and verification
# Redis key: otp:{user_id}
# TTL: 600 seconds (10 minutes)
# decode_responses=True on the Redis client means all values are plain strings.
# ------------------------------------------------------------------------------

async def store_otp(user_id: str, otp: str, ttl: int = 600) -> None:
    """
    Persists the OTP in Redis under key otp:{user_id} with the given TTL.
    Calling this a second time silently overwrites any existing OTP for the user,
    which is the correct behaviour for resend-OTP flows.
    """
    redis = get_redis()
    await redis.set(f"otp:{user_id}", otp, ex=ttl)
    app_logger.debug("OTP stored — user_id=%s ttl=%ds", user_id, ttl)


async def verify_otp(user_id: str, submitted_otp: str) -> bool:
    """
    Compares the submitted OTP against the value stored in Redis.

    Returns True  — OTPs match; key deleted (single-use enforced).
    Returns False — key missing (expired or never set), or OTP mismatch.

    Deletion on success means the same code cannot be replayed.
    """
    redis  = get_redis()
    key    = f"otp:{user_id}"
    stored = await redis.get(key)   # str | None (decode_responses=True)

    if stored is None:
        app_logger.debug("OTP verify: key missing or expired — user_id=%s", user_id)
        return False

    if stored != submitted_otp:
        app_logger.debug("OTP verify: mismatch — user_id=%s", user_id)
        return False

    await redis.delete(key)
    app_logger.info("OTP verified and consumed — user_id=%s", user_id)
    return True


# ------------------------------------------------------------------------------
# Rate limiting
# Redis key: otp_rate:{user_id}
# TTL: 600 seconds — counter resets automatically after 10 minutes
# Max: 3 OTP requests per window
# ------------------------------------------------------------------------------

async def check_otp_rate_limit(user_id: str) -> None:
    """
    Enforces a maximum of 3 OTP sends per 10-minute window per user.

    On the first request: SET otp_rate:{user_id} = 1 with EX=600.
    On subsequent requests: INCR the existing key (TTL is preserved).
    When count reaches 3: raise HTTP 429.

    Using SET + INCR (rather than INCR alone) ensures the TTL is attached on
    the very first call — INCR on a non-existent key creates it with no TTL.
    """
    redis = get_redis()
    key   = f"otp_rate:{user_id}"
    count = await redis.get(key)   # str | None

    if count is None:
        # First request in this window — initialise with TTL.
        await redis.set(key, 1, ex=600)
        app_logger.debug("OTP rate limit initialised — user_id=%s", user_id)
        return

    if int(count) >= 3:
        app_logger.warning("OTP rate limit exceeded — user_id=%s count=%s", user_id, count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please try again in 10 minutes.",
        )

    await redis.incr(key)
    app_logger.debug("OTP rate count=%d — user_id=%s", int(count) + 1, user_id)
