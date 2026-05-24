"""
schemas/user.py
---------------
Pydantic v2 schemas for the User domain.

Schemas are grouped by use-case:
  - UserBase / UserCreate / UserUpdate  — CRUD request bodies
  - UserInDB / UserResponse             — database row ↔ API response mapping
  - UserLogin / TokenResponse           — authentication flow
  - PasswordChangeRequest               — self-service password management
  - UserListResponse                    — paginated list endpoint
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.user import UserRole

# ---------------------------------------------------------------------------
# Reusable annotated types
# ---------------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,100}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

Password = Annotated[
    str,
    Field(min_length=8, max_length=128, description="Raw password (min 8 chars)"),
]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class UserBase(BaseModel):
    """Fields shared across multiple request / response schemas."""

    email: EmailStr = Field(description="Primary login email address")
    username: str = Field(
        min_length=3,
        max_length=100,
        description="URL-safe unique handle (letters, digits, _ or -)",
    )
    full_name: str | None = Field(None, max_length=255, description="Display name")
    timezone: str = Field(
        default="UTC",
        max_length=64,
        description="IANA timezone string, e.g. 'America/New_York'",
    )
    language: str = Field(
        default="en",
        max_length=10,
        description="ISO 639-1 language code",
    )
    theme: str = Field(
        default="system",
        pattern=r"^(light|dark|system)$",
        description="UI colour scheme preference",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-100 characters and contain only "
                "letters, digits, underscores, or hyphens."
            )
        return v.lower()

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class UserCreate(UserBase):
    """Request body for POST /users — self-registration or admin provisioning."""

    password: Password
    role: UserRole = Field(
        default=UserRole.VIEWER,
        description="RBAC role; only admins may set values above 'creator'",
    )
    organization_id: uuid.UUID | None = Field(
        None,
        description="Organisation to assign the user to; omit for super-admin accounts",
    )

    @model_validator(mode="after")
    def check_superadmin_has_no_org(self) -> "UserCreate":
        if self.role == UserRole.SUPER_ADMIN and self.organization_id is not None:
            raise ValueError("Super-admin accounts must not be assigned to an organisation.")
        return self


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class UserUpdate(BaseModel):
    """Request body for PATCH /users/{id} — partial update."""

    full_name: str | None = Field(None, max_length=255)
    avatar_url: AnyHttpUrl | None = Field(None, description="Profile picture URL")
    timezone: str | None = Field(None, max_length=64)
    language: str | None = Field(None, max_length=10)
    theme: str | None = Field(None, pattern=r"^(light|dark|system)$")
    is_active: bool | None = None
    role: UserRole | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# InDB — internal representation (never serialised to the API consumer)
# ---------------------------------------------------------------------------


class UserInDB(UserBase):
    """Internal schema that includes secrets — never expose to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hashed_password: str | None
    api_key: str | None
    oauth_provider: str | None
    oauth_id: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    is_superuser: bool
    organization_id: uuid.UUID | None
    storage_used_bytes: int
    storage_limit_bytes: int
    last_login: datetime | None
    login_count: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: datetime | None


# ---------------------------------------------------------------------------
# Response — safe public representation
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """API response schema; excludes all secrets and internal fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    is_superuser: bool
    organization_id: uuid.UUID | None
    avatar_url: str | None
    timezone: str
    language: str
    theme: str
    last_login: datetime | None
    login_count: int
    storage_used_bytes: int
    storage_limit_bytes: int
    oauth_provider: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------


class UserLogin(BaseModel):
    """Credentials for the OAuth2 password grant flow."""

    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    """JWT pair returned after successful authentication."""

    access_token: str = Field(description="Short-lived JWT access token")
    refresh_token: str = Field(description="Long-lived refresh token")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(description="Access token TTL in seconds")
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Body for POST /auth/refresh."""

    refresh_token: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------


class PasswordChangeRequest(BaseModel):
    """Body for POST /auth/change-password (authenticated user only)."""

    current_password: str = Field(min_length=1)
    new_password: Password
    confirm_password: Password

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self


class PasswordResetRequest(BaseModel):
    """Body for POST /auth/request-password-reset (unauthenticated)."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class PasswordResetConfirm(BaseModel):
    """Body for POST /auth/reset-password."""

    token: str = Field(min_length=1, description="One-time reset token from email")
    new_password: Password
    confirm_password: Password

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetConfirm":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self


# ---------------------------------------------------------------------------
# List response (paginated)
# ---------------------------------------------------------------------------


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    total: int = Field(ge=0, description="Total number of matching users")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")

    @model_validator(mode="after")
    def compute_pages(self) -> "UserListResponse":
        if self.page_size > 0:
            import math
            object.__setattr__(self, "pages", math.ceil(self.total / self.page_size))
        return self


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


class APIKeyResponse(BaseModel):
    """Returned once when an API key is generated; the raw key is never stored."""

    api_key: str = Field(description="Raw API key — store this securely, it won't be shown again")
    created_at: datetime
    message: str = "Store this key securely. It will not be shown again."


class ProfileUpdateResponse(BaseModel):
    """Lightweight confirmation after a profile update."""

    message: str = "Profile updated successfully."
    user: UserResponse
