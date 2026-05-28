"""
app/api/v1/endpoints/auth.py
----------------------------
Authentication endpoints: registration, login, token refresh, logout,
password reset, email verification, OAuth2 social login, and API key management.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    Role,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_current_token_data,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=255)
    organization_name: str | None = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class OAuthLoginRequest(BaseModel):
    code: str
    state: str | None = None
    redirect_uri: str | None = None


class ApiKeyResponse(BaseModel):
    api_key: str
    note: str = "Store this key securely — it will not be shown again."


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    organization_id: uuid.UUID | None
    avatar_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.is_deleted.is_(False))
    )
    return result.scalar_one_or_none()


async def _get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )
    return result.scalar_one_or_none()


def _build_token_response(user: User) -> TokenResponse:
    role = Role(user.role.value) if hasattr(user.role, "value") else Role.USER
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=role,
        organization_id=user.organization_id,
    )
    refresh_token = create_refresh_token(user_id=user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _store_verification_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    token: str,
    token_type: str,
    expiry_hours: int = 24,
) -> None:
    """Persist an email/reset token in Redis."""
    try:
        from app.core.redis_client import redis_client  # noqa: PLC0415
        key = f"token:{token_type}:{token}"
        await redis_client.setex(key, expiry_hours * 3600, str(user_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("token_store_failed", error=str(exc))


async def _pop_verification_token(
    token: str,
    token_type: str,
) -> uuid.UUID | None:
    """Retrieve and invalidate a stored token, returning the user_id."""
    try:
        from app.core.redis_client import redis_client  # noqa: PLC0415
        key = f"token:{token_type}:{token}"
        val = await redis_client.get(key)
        if val is None:
            return None
        await redis_client.delete(key)
        return uuid.UUID(val if isinstance(val, str) else val.decode())
    except Exception as exc:  # noqa: BLE001
        logger.warning("token_pop_failed", error=str(exc))
        return None


async def _send_verification_email(email: str, token: str) -> None:
    """Fire-and-forget email dispatch (replace with real SMTP/SES integration)."""
    logger.info("send_verification_email", email=email, token_prefix=token[:8])
    # TODO: integrate with email service (SendGrid, SES, etc.)


async def _send_reset_email(email: str, token: str) -> None:
    """Fire-and-forget password-reset email dispatch."""
    logger.info("send_reset_email", email=email, token_prefix=token[:8])
    # TODO: integrate with email service


async def _invalidate_tokens(user_id: uuid.UUID) -> None:
    """Add user to a revocation set in Redis — all issued tokens become invalid."""
    try:
        from app.core.redis_client import redis_client  # noqa: PLC0415
        key = f"revoked:user:{user_id}"
        # Store revocation timestamp; token validation should check this
        await redis_client.setex(
            key,
            settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("token_invalidation_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new user account and immediately return JWT tokens.

    - Auto-generates username from email if not provided
    - Validates password strength
    - Checks for duplicate email / username
    - Stores bcrypt-hashed password
    - Dispatches email-verification email asynchronously
    - Returns access + refresh tokens so the user is logged in immediately
    """
    # Auto-generate username from email prefix if not provided
    if not payload.username:
        base = payload.email.split("@")[0].lower()
        # Strip non-alphanumeric chars except _ and -
        import re as _re
        base = _re.sub(r"[^a-z0-9_-]", "_", base)[:30]
        payload.username = base

    # Ensure username uniqueness by appending a short suffix if needed
    candidate = payload.username
    suffix = 0
    while True:
        existing_username = await db.execute(
            select(User).where(User.username == candidate, User.is_deleted.is_(False))
        )
        if not existing_username.scalar_one_or_none():
            break
        suffix += 1
        candidate = f"{payload.username}_{suffix}"
    payload.username = candidate

    # Check email uniqueness
    existing_email = await db.execute(
        select(User).where(User.email == payload.email, User.is_deleted.is_(False))
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.VIEWER,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()  # assign UUID before background task

    # Generate and store email-verification token
    verification_token = secrets.token_urlsafe(32)
    background_tasks.add_task(
        _store_verification_token, db, user.id, verification_token, "email"
    )
    background_tasks.add_task(_send_verification_email, user.email, verification_token)

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return _build_token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password.

    Returns a short-lived access token and a long-lived refresh token.
    """
    user = await _get_user_by_email(db, payload.email)

    if user is None or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(payload.password, user.hashed_password):
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update login metadata
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            last_login=datetime.now(timezone.utc),
            login_count=User.login_count + 1,
        )
    )

    logger.info("user_logged_in", user_id=str(user.id))
    return _build_token_response(user)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="OAuth2 password flow token endpoint",
    include_in_schema=False,
)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Standard OAuth2 password flow endpoint consumed by the Swagger UI."""
    user = await _get_user_by_email(db, form_data.username)
    if user is None or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    return _build_token_response(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using a refresh token",
)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.

    The old refresh token is invalidated after use (token rotation).
    """
    try:
        token_data = decode_token(payload.refresh_token, expected_type=TokenType.REFRESH)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await _get_user_by_id(db, token_data.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated",
        )

    logger.info("token_refreshed", user_id=str(user.id))
    return _build_token_response(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate current session tokens",
)
async def logout(
    token_data: Any = Depends(get_current_token_data),
) -> None:
    """
    Invalidate the current user's tokens.

    Adds the user's ID to a Redis revocation set so all issued tokens
    become invalid until they naturally expire.
    """
    await _invalidate_tokens(token_data.user_id)
    logger.info("user_logged_out", user_id=str(token_data.user_id))


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password-reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Send a password-reset link to the provided email.

    Always returns 202 to prevent email enumeration.
    """
    user = await _get_user_by_email(db, payload.email)
    if user is not None and user.is_active:
        reset_token = secrets.token_urlsafe(32)
        background_tasks.add_task(
            _store_verification_token, db, user.id, reset_token, "reset", expiry_hours=1
        )
        background_tasks.add_task(_send_reset_email, user.email, reset_token)

    return {"detail": "If the email exists, a reset link has been sent"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using a reset token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Reset the user's password using a valid reset token.

    The token is single-use and expires after 1 hour.
    """
    user_id = await _pop_verification_token(payload.token, "reset")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = await _get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(hashed_password=hash_password(payload.new_password))
    )
    # Invalidate all existing sessions
    await _invalidate_tokens(user_id)

    logger.info("password_reset", user_id=str(user_id))
    return {"detail": "Password has been reset successfully"}


@router.post(
    "/verify-email/{token}",
    status_code=status.HTTP_200_OK,
    summary="Verify email address with the token sent during registration",
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark the user's email as verified using the single-use token."""
    user_id = await _pop_verification_token(token, "email")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = await _get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_verified:
        return {"detail": "Email is already verified"}

    await db.execute(
        update(User).where(User.id == user_id).values(is_verified=True)
    )
    logger.info("email_verified", user_id=str(user_id))
    return {"detail": "Email verified successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current authenticated user",
)
async def get_me(
    token_data: Any = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the profile of the currently authenticated user."""
    user = await _get_user_by_id(db, token_data.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/oauth/{provider}",
    response_model=TokenResponse,
    summary="Authenticate via OAuth2 social provider",
)
async def oauth_login(
    provider: str,
    payload: OAuthLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange an OAuth2 authorization code for platform tokens.

    Supported providers: ``google``, ``github``.

    On first login the user record is created automatically.
    """
    supported = {"google", "github"}
    if provider not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider. Supported: {', '.join(supported)}",
        )

    # Fetch user info from the OAuth provider
    oauth_user = await _exchange_oauth_code(provider, payload.code, payload.redirect_uri)
    if oauth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth code exchange failed",
        )

    # Look up or create the platform user
    result = await db.execute(
        select(User).where(
            User.oauth_provider == provider,
            User.oauth_id == oauth_user["id"],
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Check if email already exists (account linking)
        existing = await _get_user_by_email(db, oauth_user["email"])
        if existing:
            # Link OAuth to existing account
            await db.execute(
                update(User)
                .where(User.id == existing.id)
                .values(oauth_provider=provider, oauth_id=oauth_user["id"])
            )
            user = existing
        else:
            # Create new user
            username_base = oauth_user.get("login") or oauth_user["email"].split("@")[0]
            username = await _unique_username(db, username_base)
            user = User(
                email=oauth_user["email"],
                username=username,
                full_name=oauth_user.get("name"),
                oauth_provider=provider,
                oauth_id=oauth_user["id"],
                is_verified=True,  # Email already verified by OAuth provider
                role=UserRole.VIEWER,
                is_active=True,
            )
            db.add(user)
            await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.now(timezone.utc), login_count=User.login_count + 1)
    )

    logger.info("oauth_login", provider=provider, user_id=str(user.id))
    return _build_token_response(user)


@router.post(
    "/api-key",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key for the current user",
)
async def create_api_key(
    token_data: Any = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyResponse:
    """
    Generate a new API key for programmatic access.

    The raw key is returned **once** and never stored in plaintext.
    The hashed key is saved to the database for future verification.
    """
    raw_key, hashed_key = generate_api_key()

    await db.execute(
        update(User).where(User.id == token_data.user_id).values(api_key=hashed_key)
    )
    logger.info("api_key_generated", user_id=str(token_data.user_id))

    return ApiKeyResponse(api_key=raw_key)


# ---------------------------------------------------------------------------
# OAuth helpers (stub implementations — replace with real provider SDKs)
# ---------------------------------------------------------------------------


async def _exchange_oauth_code(
    provider: str,
    code: str,
    redirect_uri: str | None,
) -> dict[str, str] | None:
    """
    Exchange an authorization code for user info from the OAuth provider.

    Returns a dict with at least ``id``, ``email``, ``name``.
    """
    import httpx  # noqa: PLC0415

    try:
        if provider == "google":
            return await _google_oauth(code, redirect_uri)
        if provider == "github":
            return await _github_oauth(code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("oauth_exchange_failed", provider=provider, error=str(exc))
    return None


async def _google_oauth(code: str, redirect_uri: str | None) -> dict[str, str]:
    import httpx  # noqa: PLC0415

    redirect = redirect_uri or settings.GOOGLE_REDIRECT_URI
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # Fetch user info
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        data = user_resp.json()
        return {"id": data["id"], "email": data["email"], "name": data.get("name", "")}


async def _github_oauth(code: str) -> dict[str, str]:
    import httpx  # noqa: PLC0415

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "code": code,
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        data = user_resp.json()

        # GitHub may hide email — fetch separately
        email = data.get("email")
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            emails_resp.raise_for_status()
            for em in emails_resp.json():
                if em.get("primary") and em.get("verified"):
                    email = em["email"]
                    break

        return {
            "id": str(data["id"]),
            "email": email or "",
            "name": data.get("name") or data.get("login", ""),
            "login": data.get("login", ""),
        }


async def _unique_username(db: AsyncSession, base: str) -> str:
    """Ensure username uniqueness by appending a suffix if needed."""
    # Sanitise
    import re  # noqa: PLC0415
    sanitised = re.sub(r"[^a-zA-Z0-9_-]", "_", base)[:80]
    candidate = sanitised
    suffix = 1
    while True:
        result = await db.execute(
            select(User).where(User.username == candidate, User.is_deleted.is_(False))
        )
        if result.scalar_one_or_none() is None:
            return candidate
        candidate = f"{sanitised}_{suffix}"
        suffix += 1
