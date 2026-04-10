from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.dependencies import get_current_user
from database import get_database
from models.user import User, UserResponse, UserUpdateRequest
from repositories import user_repo
from logger import app_logger

router = APIRouter()


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _to_response(user: User) -> UserResponse:
    """
    Converts an internal User model to a safe UserResponse.
    Ensures password_hash and refresh_token_hash never leave the server.
    """
    return UserResponse(
        user_id             = user.user_id,
        full_name           = user.full_name,
        email               = user.email,
        mobile              = user.mobile,
        currency            = user.currency,
        address             = user.address,
        is_profile_complete = user.is_profile_complete,
        created_at          = user.created_at,
        updated_at          = user.updated_at,
    )


# ------------------------------------------------------------------------------
# GET /users/me — fetch the current user's profile
# ------------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the authenticated user's full profile.
    Identity is resolved from the JWT token via get_current_user().
    No user_id in the path — a user can only read their own profile.
    """
    app_logger.info("GET /users/me — user_id=%s", current_user.user_id)
    return _to_response(current_user)


# ------------------------------------------------------------------------------
# PATCH /users/me — update any profile field
# ------------------------------------------------------------------------------

@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Partially updates the authenticated user's profile.

    Any combination of fields can be sent — only the fields present in the
    request body are written to MongoDB. Omitted fields are left unchanged.

    Examples:
      {"full_name": "Raj"}                    → updates name only
      {"mobile": {"mobile_no": "...", ...}}   → updates mobile only
      {"currency": {...}, "address": {...}}   → updates two fields

    Also recomputes is_profile_complete after every update, so filling in
    the last required field automatically flips the flag to true.
    """
    updated_user = await user_repo.update_user(db, current_user.user_id, body)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    app_logger.info("PATCH /users/me — user_id=%s", current_user.user_id)
    return _to_response(updated_user)
