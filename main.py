from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import connect_database, ping_database, close_database
from redis_client import connect_redis, ping_redis, close_redis
from middleware import JWTMiddleware
from routers import api_router
from logger import app_logger


# ------------------------------------------------------------------------------
# Lifespan — startup and shutdown in one clean block.
# Runs before the first request and after the last one.
# ------------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    app_logger.info("Starting up Multi Booking Agent...")

    await connect_database()
    await ping_database()

    await connect_redis()
    await ping_redis()

    app_logger.info("All connections healthy. Application is ready.")

    yield  # Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    app_logger.info("Shutting down Multi Booking Agent...")

    await close_database()
    await close_redis()

    app_logger.info("All connections closed. Goodbye.")


# ------------------------------------------------------------------------------
# App initialisation
# ------------------------------------------------------------------------------

app = FastAPI(
    title="Multi Booking Agent",
    description="AI-powered booking agent for movies, cabs, doctors, and restaurants.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Middlewares ────────────────────────────────────────────────────────────────
# Order matters: CORS runs first (outermost), then JWT validation.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(JWTMiddleware)


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(api_router)


# ------------------------------------------------------------------------------
# Health check — public route, no auth required.
# ------------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """Returns a simple alive signal. Used by load balancers and monitoring."""
    return {"status": "ok", "service": "multi-booking-agent"}


# ------------------------------------------------------------------------------
# Stripe Webhook — raw bytes endpoint.
#
# Stripe computes an HMAC signature over the raw request body.
# If FastAPI parses the body as JSON first, the bytes change and the
# signature check fails. We read raw bytes here and pass them untouched
# to the payment service for verification.
# ------------------------------------------------------------------------------

@app.post("/webhooks/stripe", tags=["Webhooks"])
async def stripe_webhook(request: Request):
    """
    Receives raw Stripe webhook events.
    Stripe signature verification happens inside the payment service.
    """
    raw_body: bytes = await request.body()
    stripe_signature = request.headers.get("stripe-signature")

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature header.")

    # TODO: wire into payment_service.handle_stripe_event(raw_body, stripe_signature)
    return {"received": True}
