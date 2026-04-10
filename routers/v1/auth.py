import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from core.otp import generate_otp, store_otp, verify_otp, check_otp_rate_limit
from database import get_database
from models.user import UserCreate, MobileInfo, CurrencyInfo, AddressInfo
from repositories import user_repo
from services.email_service import (
    send_otp_email,
    send_welcome_email,
    send_password_reset_email,
)
from redis_client import get_redis
from logger import app_logger

router = APIRouter()


# ------------------------------------------------------------------------------
# Request / Response schemas — scoped to auth; defined here so models/ stays
# focused on MongoDB document shapes rather than HTTP payloads.
# ------------------------------------------------------------------------------

class SignupRequest(BaseModel):
    full_name: str
    email:     EmailStr
    password:  str

    # Optional at signup — required before a booking can be made.
    mobile:   MobileInfo | None   = None
    currency: CurrencyInfo | None = None
    address:  AddressInfo | None  = None


class SignupResponse(BaseModel):
    message: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp:   str


class ResendOtpRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str


class AuthResponse(BaseModel):
    access_token:        str
    refresh_token:       str
    user_id:             str
    is_profile_complete: bool   # frontend uses this to redirect to profile-completion screen


class AccessTokenResponse(BaseModel):
    access_token: str


# ------------------------------------------------------------------------------
# Internal helper
# ------------------------------------------------------------------------------

def _hash_for_storage(token: str) -> str:
    """
    SHA-256 hashes a token before writing it to MongoDB.
    Fast and one-way — if the database is compromised, raw tokens stay safe.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Step 1 of signup — registers the user and sends a verification OTP.

    The account is created with is_verified=False. No tokens are issued here.
    The user must call POST /auth/verify-otp to complete registration and
    receive their access and refresh tokens.
    """
    existing = await user_repo.find_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    user_id             = str(uuid.uuid4())
    now                 = datetime.now(timezone.utc)
    is_profile_complete = all([body.mobile, body.currency, body.address])

    await user_repo.create_user(db, UserCreate(
        user_id             = user_id,
        full_name           = body.full_name,
        email               = body.email,
        password_hash       = hash_password(body.password),
        mobile              = body.mobile,
        currency            = body.currency,
        address             = body.address,
        is_profile_complete = is_profile_complete,
        is_verified         = False,
        created_at          = now,
        updated_at          = now,
    ))

    await check_otp_rate_limit(user_id)
    otp = generate_otp()
    await store_otp(user_id, otp)
    send_otp_email(body.email, otp, body.full_name)

    app_logger.info("Signup initiated — user_id=%s email=%s", user_id, body.email)

    return SignupResponse(message="Check your email for your verification code.")


@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp_route(
    body: VerifyOtpRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Step 2 of signup — verifies the OTP sent to the user's email.

    On success: marks the account verified, sends a welcome email,
    and issues access + refresh tokens. Registration is now complete.
    """
    user = await user_repo.find_by_email(db, body.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request.",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    otp_valid = await verify_otp(user.user_id, body.otp)

    if not otp_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    await user_repo.verify_user(db, user.user_id)

    send_welcome_email(user.email, user.full_name)

    access_token  = create_access_token(user.user_id, user.email)
    refresh_token = create_refresh_token(user.user_id)

    await user_repo.update_refresh_token(db, user.user_id, _hash_for_storage(refresh_token))

    app_logger.info("Email verified — user_id=%s", user.user_id)

    return AuthResponse(
        access_token        = access_token,
        refresh_token       = refresh_token,
        user_id             = user.user_id,
        is_profile_complete = user.is_profile_complete,
    )


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_otp(
    body: ResendOtpRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Sends a fresh OTP to the user's email.
    Rate limited to 3 requests per 10-minute window via Redis.
    Overwrites any previously stored OTP for this user.
    """
    user = await user_repo.find_by_email(db, body.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account found with this email.",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    await check_otp_rate_limit(user.user_id)

    otp = generate_otp()
    await store_otp(user.user_id, otp)
    send_otp_email(user.email, otp, user.full_name)

    app_logger.info("OTP resent — user_id=%s", user.user_id)

    return {"message": "A new verification code has been sent."}


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Authenticates a verified user and issues tokens.

    Returns the same 401 for unknown email and wrong password — prevents
    user enumeration (attacker cannot distinguish the two failure modes).
    Unverified accounts get a distinct 403 directing them to complete verification.
    """
    user = await user_repo.find_by_email(db, body.email)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in.",
        )

    access_token  = create_access_token(user.user_id, user.email)
    refresh_token = create_refresh_token(user.user_id)

    await user_repo.update_refresh_token(db, user.user_id, _hash_for_storage(refresh_token))

    app_logger.info("Login successful — user_id=%s", user.user_id)

    return AuthResponse(
        access_token        = access_token,
        refresh_token       = refresh_token,
        user_id             = user.user_id,
        is_profile_complete = user.is_profile_complete,
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Step 1 of password reset — generates a UUID reset token and emails a link.

    Always returns 200 regardless of whether the email exists in the system.
    This prevents account enumeration: an attacker gets no information about
    which email addresses are registered.

    Reset token stored in Redis as: reset:{token} → user_id   TTL: 15 minutes
    """
    user = await user_repo.find_by_email(db, body.email)

    if user:
        reset_token = str(uuid.uuid4())
        redis       = get_redis()
        await redis.set(f"reset:{reset_token}", user.user_id, ex=900)
        send_password_reset_email(user.email, reset_token, user.full_name)
        app_logger.info("Password reset initiated — user_id=%s", user.user_id)

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Step 2 of password reset — validates the token, updates the password, deletes the token.

    The token is single-use: deleted immediately after the password is updated
    so the same link cannot be reused even within the 15-minute TTL window.
    """
    redis   = get_redis()
    user_id = await redis.get(f"reset:{body.token}")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link has expired or is invalid.",
        )

    await user_repo.update_password(db, user_id, hash_password(body.new_password))
    await redis.delete(f"reset:{body.token}")

    app_logger.info("Password reset completed — user_id=%s", user_id)

    return {"message": "Password updated successfully."}


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Issues a new access token from a valid, non-revoked refresh token.

    Rejects access tokens used here (type check).
    Rejects revoked tokens by comparing hashes stored in MongoDB — this is
    what makes logout actually work. On logout, the hash is nulled, so any
    subsequent refresh attempt fails the comparison.
    """
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user = await user_repo.find_by_id(db, payload["sub"])

    if not user or not user.refresh_token_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )

    if _hash_for_storage(body.refresh_token) != user.refresh_token_hash:
        app_logger.warning("Refresh token mismatch — possible reuse attack. user_id=%s", user.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked. Please log in again.",
        )

    new_access_token = create_access_token(user.user_id, user.email)
    app_logger.info("Token refreshed — user_id=%s", user.user_id)

    return AccessTokenResponse(access_token=new_access_token)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Logs out the current user by nulling their stored refresh token hash.
    Any subsequent call to POST /auth/refresh will fail the revocation check.
    user_id is sourced from request.state, set by JWTMiddleware.
    """
    user_id = request.state.user_id
    await user_repo.revoke_refresh_token(db, user_id)
    app_logger.info("Logout successful — user_id=%s", user_id)
    return {"message": "Logged out successfully."}
