from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_database
from models.user import User
from repositories import user_repo
from logger import app_logger


async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> User:
    """
    FastAPI dependency — resolves the authenticated user from MongoDB.

    Reads request.state.user_id attached by JWTMiddleware, then fetches
    the full User document from the database.

    Use this in any route that needs the full user object:

        @router.get("/profile")
        async def get_profile(user: User = Depends(get_current_user)):
            return user

    Raises 401 if user_id is missing from request state (should not happen
    on protected routes — middleware would have blocked the request first).
    Raises 404 if the user no longer exists in the database (e.g. deleted account).
    """
    user_id: str | None = getattr(request.state, "user_id", None)

    if not user_id:
        # Safety net — middleware should have caught this before we get here.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    user = await user_repo.find_by_id(db, user_id)

    if not user:
        app_logger.warning("get_current_user: user_id=%s not found in DB.", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user
