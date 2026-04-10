from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import User, UserCreate, UserUpdateRequest
from logger import app_logger

# ------------------------------------------------------------------------------
# User Repository — all MongoDB operations for the `users` collection.
#
# Rules:
#   - No business logic here. Only data access.
#   - Every function takes `db` as its first argument (stateless, easy to test).
#   - Returns typed models, not raw dicts.
# ------------------------------------------------------------------------------

_COLLECTION = "users"


async def find_by_email(db: AsyncIOMotorDatabase, email: str) -> User | None:
    """Returns the user with the given email, or None if not found."""
    doc = await db[_COLLECTION].find_one({"email": email})
    if not doc:
        return None
    app_logger.debug("user_repo.find_by_email — found user email=%s", email)
    return User(**doc)


async def find_by_id(db: AsyncIOMotorDatabase, user_id: str) -> User | None:
    """Returns the user with the given user_id, or None if not found."""
    doc = await db[_COLLECTION].find_one({"user_id": user_id})
    if not doc:
        return None
    app_logger.debug("user_repo.find_by_id — found user_id=%s", user_id)
    return User(**doc)


async def create_user(db: AsyncIOMotorDatabase, payload: UserCreate) -> User:
    """
    Inserts a new user document into the collection.
    Returns the inserted user as a typed User model.
    """
    doc = payload.model_dump()
    await db[_COLLECTION].insert_one(doc)
    app_logger.info("user_repo.create_user — inserted user_id=%s", payload.user_id)
    return User(**doc)


async def update_refresh_token(
    db: AsyncIOMotorDatabase,
    user_id: str,
    token_hash: str,
) -> None:
    """
    Replaces the stored refresh token hash for a user.
    Called after every successful login to rotate the token.
    """
    await db[_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": {
            "refresh_token_hash": token_hash,
            "updated_at":         datetime.now(timezone.utc),
        }},
    )
    app_logger.debug("user_repo.update_refresh_token — rotated token for user_id=%s", user_id)


async def update_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: UserUpdateRequest,
) -> User | None:
    """
    Applies a partial update to the user document.

    Only fields explicitly sent in the request are written — unset fields are
    ignored entirely via model_dump(exclude_unset=True). This means a client
    sending {"full_name": "Raj"} will only update full_name, leaving all other
    fields untouched.

    After update, recomputes is_profile_complete so the flag stays accurate
    if the user fills in their mobile/currency/address through this endpoint.

    Returns the updated User, or None if user_id does not exist.
    """
    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        # Nothing to update — fetch and return the current document as-is.
        return await find_by_id(db, user_id)

    changes["updated_at"] = datetime.now(timezone.utc)

    await db[_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": changes},
    )

    # Re-fetch so is_profile_complete reflects the latest state of all fields.
    updated_user = await find_by_id(db, user_id)

    if updated_user:
        # Recompute profile completion after the update.
        is_complete = all([
            updated_user.mobile,
            updated_user.currency,
            updated_user.address,
        ])
        if updated_user.is_profile_complete != is_complete:
            await db[_COLLECTION].update_one(
                {"user_id": user_id},
                {"$set": {"is_profile_complete": is_complete}},
            )
            updated_user.is_profile_complete = is_complete

    app_logger.info("user_repo.update_user — updated user_id=%s fields=%s", user_id, list(changes.keys()))
    return updated_user


async def revoke_refresh_token(db: AsyncIOMotorDatabase, user_id: str) -> None:
    """
    Clears the stored refresh token hash for a user.
    Called on logout — any cached refresh token will be rejected after this.
    """
    await db[_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": {
            "refresh_token_hash": None,
            "updated_at":         datetime.now(timezone.utc),
        }},
    )
    app_logger.info("user_repo.revoke_refresh_token — revoked token for user_id=%s", user_id)
