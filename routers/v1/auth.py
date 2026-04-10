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
from database import get_database
from models.user import UserCreate, MobileInfo, CurrencyInfo, AddressInfo
from repositories import user_repo
from logger import app_logger

router = APIRouter()


# ------------------------------------------------------------------------------
# Request / Response schemas — scoped to auth, defined here to keep models/
# focused on DB document shapes rather than HTTP payloads.
# ------------------------------------------------------------------------------

class SignupRequest(BaseModel):
    full_name: str
    email:     EmailStr
    password:  str

    # Optional at signup — mandatory before the user can make any booking.
    # Frontend should prompt for these immediately after account creation.
    mobile:   MobileInfo | None   = None
    currency: CurrencyInfo | None = None
    address:  AddressInfo | None  = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


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
    SHA-256 hashes a refresh token before persisting it.
    Fast, one-way, and sufficient — tokens are already long and random.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Registers a new user.
    Rejects duplicate emails (409). Hashes the password before storage.
    Returns both tokens so the user is immediately authenticated post-signup.
    """
    existing = await user_repo.find_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    user_id       = str(uuid.uuid4())
    now           = datetime.now(timezone.utc)
    access_token  = create_access_token(user_id, body.email)
    refresh_token = create_refresh_token(user_id)

    # Profile is complete only if all three mandatory objects are provided at signup.
    is_profile_complete = all([body.mobile, body.currency, body.address])

    await user_repo.create_user(db, UserCreate(
        user_id             = user_id,
        full_name           = body.full_name,
        email               = body.email,
        password_hash       = hash_password(body.password),
        refresh_token_hash  = _hash_for_storage(refresh_token),
        mobile              = body.mobile,
        currency            = body.currency,
        address             = body.address,
        is_profile_complete = is_profile_complete,
        created_at          = now,
        updated_at          = now,
    ))

    app_logger.info("Signup successful — user_id=%s profile_complete=%s", user_id, is_profile_complete)

    return AuthResponse(
        access_token        = access_token,
        refresh_token       = refresh_token,
        user_id             = user_id,
        is_profile_complete = is_profile_complete,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Authenticates an existing user.
    Returns the same 401 for unknown email and wrong password
    to prevent user enumeration attacks.
    """
    user = await user_repo.find_by_email(db, body.email)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    access_token  = create_access_token(user.user_id, user.email)
    refresh_token = create_refresh_token(user.user_id)

    await user_repo.update_refresh_token(
        db, user.user_id, _hash_for_storage(refresh_token)
    )

    app_logger.info("Login successful — user_id=%s", user.user_id)

    return AuthResponse(
        access_token        = access_token,
        refresh_token       = refresh_token,
        user_id             = user.user_id,
        is_profile_complete = user.is_profile_complete,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Issues a new access token from a valid, non-revoked refresh token.
    Rejects access tokens used here (type check).
    Rejects revoked tokens by comparing hashes stored in MongoDB.
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
        app_logger.warning("Refresh token mismatch — possible reuse. user_id=%s", user.user_id)
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
    Logs out the current user by revoking their stored refresh token.
    user_id is sourced from request.state.user, set by JWTMiddleware.
    Any cached refresh token is rejected on next use.
    """
    user_id = request.state.user_id

    await user_repo.revoke_refresh_token(db, user_id)

    app_logger.info("Logout successful — user_id=%s", user_id)
    return {"message": "Logged out successfully."}
