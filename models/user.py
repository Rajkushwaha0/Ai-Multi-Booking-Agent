from datetime import datetime
from pydantic import BaseModel, EmailStr


# ------------------------------------------------------------------------------
# Nested models — each represents one embedded object in the user document.
# ------------------------------------------------------------------------------

class CurrencyInfo(BaseModel):
    code:   str    # e.g. "INR", "USD", "EUR"
    symbol: str    # e.g. "₹", "$", "€"


class MobileInfo(BaseModel):
    mobile_no:   str   # e.g. "9876543210"
    mobile_code: str   # e.g. "+91", "+1"


class Coordinates(BaseModel):
    latitude:  float
    longitude: float


class AddressInfo(BaseModel):
    country:      str
    country_code: str             # ISO 3166-1 alpha-2, e.g. "IN", "US"
    state:        str
    state_code:   str             # e.g. "MH", "DL", "CA"
    address:      str             # street / flat / building
    pin_code:     str
    coordinates:  Coordinates | None = None   # optional — not all users share location


# ------------------------------------------------------------------------------
# User — mirrors the MongoDB document stored in the `users` collection.
#
# is_profile_complete:
#   False immediately after signup (only name + email + password collected).
#   Must be flipped to True once mobile, currency, and address are provided.
#   Booking services should gate on this flag before allowing a reservation.
# ------------------------------------------------------------------------------

class User(BaseModel):
    user_id:             str
    full_name:           str
    email:               EmailStr
    password_hash:       str
    refresh_token_hash:  str | None = None

    # Profile fields — mandatory to complete before booking, optional at signup
    mobile:              MobileInfo | None = None
    currency:            CurrencyInfo | None = None
    address:             AddressInfo | None = None

    # Profile completion gate
    is_profile_complete: bool = False

    # Email verification gate — False until OTP is confirmed at signup
    is_verified:         bool = False

    created_at:          datetime
    updated_at:          datetime


# ------------------------------------------------------------------------------
# UserResponse — safe public shape returned by the API.
# Sensitive fields (password_hash, refresh_token_hash) are never exposed.
# ------------------------------------------------------------------------------

class UserResponse(BaseModel):
    user_id:             str
    full_name:           str
    email:               EmailStr
    mobile:              MobileInfo | None = None
    currency:            CurrencyInfo | None = None
    address:             AddressInfo | None = None
    is_profile_complete: bool
    is_verified:         bool
    created_at:          datetime
    updated_at:          datetime


# ------------------------------------------------------------------------------
# UserUpdateRequest — all fields optional.
# Only fields explicitly sent by the client will be written to MongoDB.
# Pydantic's model_dump(exclude_unset=True) ensures untouched fields are ignored.
# ------------------------------------------------------------------------------

class UserUpdateRequest(BaseModel):
    full_name: str | None           = None
    mobile:    MobileInfo | None    = None
    currency:  CurrencyInfo | None  = None
    address:   AddressInfo | None   = None


# ------------------------------------------------------------------------------
# UserCreate — typed payload for inserting a new user document.
# Profile fields are optional here; is_profile_complete starts as False.
# ------------------------------------------------------------------------------

class UserCreate(BaseModel):
    user_id:             str
    full_name:           str
    email:               EmailStr
    password_hash:       str
    refresh_token_hash:  str | None = None   # None at signup; set after OTP verification

    mobile:              MobileInfo | None = None
    currency:            CurrencyInfo | None = None
    address:             AddressInfo | None = None

    is_profile_complete: bool = False
    is_verified:         bool = False

    created_at:          datetime
    updated_at:          datetime
