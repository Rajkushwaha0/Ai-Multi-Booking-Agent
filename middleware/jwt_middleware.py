import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import get_settings
from logger import app_logger
settings = get_settings()

# ------------------------------------------------------------------------------
# Routes that skip JWT validation entirely.
# Add any path that should be publicly accessible without a token.
# ------------------------------------------------------------------------------

PUBLIC_ROUTES: set[str] = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/webhooks/stripe",
}


class JWTMiddleware(BaseHTTPMiddleware):
    """
    Intercepts every incoming request and validates the JWT Bearer token.

    On success  → decoded payload is attached to request.state.user
    On failure  → returns 401 immediately without reaching the route handler
    Public routes defined in PUBLIC_ROUTES bypass this check completely.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header."},
            )

        token = auth_header.split(" ", 1)[1]

        try:
            payload = jwt.decode(
                token,
                settings.jwt.secret_key,
                algorithms=[settings.jwt.algorithm],
            )
            request.state.user = payload

        except jwt.ExpiredSignatureError:
            app_logger.warning("JWT validation failed: token expired.")
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired."},
            )

        except jwt.InvalidTokenError as exc:
            app_logger.warning("JWT validation failed: %s", str(exc))
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token."},
            )

        return await call_next(request)
