import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from logger import app_logger

settings = get_settings()

# ------------------------------------------------------------------------------
# Public routes — these bypass token validation entirely.
# Any route that does not require an authenticated user goes here.
# ------------------------------------------------------------------------------

PUBLIC_ROUTES: set[str] = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/signup",
    "/api/v1/auth/verify-otp",
    "/api/v1/auth/resend-otp",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",        # user may not have a valid access token when refreshing
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/webhooks/stripe",            # Stripe signs this payload independently
}


class JWTMiddleware(BaseHTTPMiddleware):
    """
    Runs before every request and validates the JWT Bearer token.

    Flow:
      1. Skip validation entirely for PUBLIC_ROUTES.
      2. Read the Authorization header — expect "Bearer <token>".
      3. Decode the token using PyJWT (checks signature + expiry).
      4. Verify token type is "access" — refresh tokens are rejected here.
      5. Attach user_id to request.state.user_id for downstream use.
      6. Proceed to the route handler.

    On any failure → return 401 immediately, route handler is never called.
    """

    async def dispatch(self, request: Request, call_next):

        # ── Public route — skip auth entirely ─────────────────────────────────
        if request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        # ── Require Authorization header ───────────────────────────────────────
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header required."},
            )

        token = auth_header.split(" ", 1)[1]

        # ── Decode and validate ────────────────────────────────────────────────
        try:
            payload = jwt.decode(
                token,
                settings.jwt.secret_key,
                algorithms=[settings.jwt.algorithm],
            )
        except jwt.ExpiredSignatureError:
            app_logger.warning("Auth middleware: token expired.")
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired."},
            )
        except jwt.InvalidTokenError as exc:
            app_logger.warning("Auth middleware: invalid token — %s", str(exc))
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token."},
            )

        # ── Reject refresh tokens used as access tokens ────────────────────────
        if payload.get("type") != "access":
            app_logger.warning("Auth middleware: non-access token used on protected route.")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token type. Access token required."},
            )

        # ── Attach user_id to request state ───────────────────────────────────
        # Route handlers and dependencies read from request.state.user_id.
        request.state.user_id = payload["sub"]

        return await call_next(request)
