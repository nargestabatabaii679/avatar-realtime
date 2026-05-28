"""
app/core/security.py
--------------------
Security utilities for the AI Digital Human Platform.

Provides:
  - Password hashing / verification  (bcrypt via passlib)
  - JWT access-token and refresh-token creation / verification
  - OAuth2PasswordBearer scheme for FastAPI dependency injection
  - API-key generation and hashing
  - Role-based access control (RBAC) helpers and decorators
  - Generic permission-checking utilities
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of *plain_password*."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    return _pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """Return True if the stored hash should be upgraded (e.g. rounds increased)."""
    return _pwd_context.needs_update(hashed_password)


# ---------------------------------------------------------------------------
# Role enumeration
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Platform roles in ascending privilege order."""

    VIEWER = "viewer"
    USER = "user"
    CREATOR = "creator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Privilege hierarchy: higher index == more powerful
_ROLE_HIERARCHY: list[Role] = [
    Role.VIEWER,
    Role.USER,
    Role.CREATOR,
    Role.ADMIN,
    Role.SUPER_ADMIN,
]


def role_rank(role: Role) -> int:
    """Return the numeric rank of *role* (higher = more privileged)."""
    try:
        return _ROLE_HIERARCHY.index(role)
    except ValueError:
        return -1


def has_minimum_role(user_role: Role, required_role: Role) -> bool:
    """Return True if *user_role* satisfies *required_role* or above."""
    return role_rank(user_role) >= role_rank(required_role)


# ---------------------------------------------------------------------------
# JWT token schemas
# ---------------------------------------------------------------------------


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"


class TokenData:
    """Parsed, validated payload from a JWT."""

    __slots__ = (
        "sub",
        "user_id",
        "email",
        "role",
        "organization_id",
        "token_type",
        "jti",
        "scopes",
    )

    def __init__(
        self,
        *,
        sub: str,
        user_id: uuid.UUID,
        email: str,
        role: Role,
        organization_id: uuid.UUID | None,
        token_type: TokenType,
        jti: str,
        scopes: list[str],
    ) -> None:
        self.sub = sub
        self.user_id = user_id
        self.email = email
        self.role = role
        self.organization_id = organization_id
        self.token_type = token_type
        self.jti = jti
        self.scopes = scopes


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _build_token(
    *,
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Internal helper that signs a JWT with the configured secret.

    Args:
        subject:      ``sub`` claim — typically the user's UUID as a string.
        token_type:   Distinguishes access, refresh, and API-key tokens.
        expires_delta: How long until the token expires.
        extra_claims: Additional claims merged into the payload.

    Returns:
        A compact, URL-safe JWT string.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": secrets.token_urlsafe(16),   # unique token id for revocation
        "type": token_type.value,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    role: Role,
    organization_id: uuid.UUID | None = None,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        user_id:         The authenticated user's primary key.
        email:           User's email address (informational claim).
        role:            User's current role.
        organization_id: The active organisation (None for super-admins).
        scopes:          OAuth2-style scope strings.
        expires_delta:   Custom TTL; defaults to ``JWT_ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Signed JWT string.
    """
    delta = expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.ACCESS,
        expires_delta=delta,
        extra_claims={
            "email": email,
            "role": role.value,
            "org_id": str(organization_id) if organization_id else None,
            "scopes": scopes or [],
        },
    )


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a long-lived JWT refresh token.

    The refresh token carries minimal claims; when redeemed it triggers
    a new access-token issuance after re-validating the user in the DB.

    Args:
        user_id:      The authenticated user's primary key.
        expires_delta: Custom TTL; defaults to ``JWT_REFRESH_TOKEN_EXPIRE_DAYS``.

    Returns:
        Signed JWT string.
    """
    delta = expires_delta or timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.REFRESH,
        expires_delta=delta,
    )


def decode_token(token: str, *, expected_type: TokenType = TokenType.ACCESS) -> TokenData:
    """
    Decode and validate a JWT, returning a ``TokenData`` instance.

    Raises:
        HTTPException(401): If the token is invalid, expired, or of the wrong type.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except JWTError as exc:
        logger.warning("jwt_decode_failed", error=str(exc))
        raise credentials_exc from exc

    token_type_str: str = payload.get("type", "")
    if token_type_str != expected_type.value:
        logger.warning(
            "jwt_wrong_type",
            expected=expected_type.value,
            got=token_type_str,
        )
        raise credentials_exc

    sub: str | None = payload.get("sub")
    if not sub:
        raise credentials_exc

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_exc from None

    role_str: str = payload.get("role", Role.USER.value)
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.USER

    org_id_str: str | None = payload.get("org_id")
    org_id = uuid.UUID(org_id_str) if org_id_str else None

    return TokenData(
        sub=sub,
        user_id=user_id,
        email=payload.get("email", ""),
        role=role,
        organization_id=org_id,
        token_type=TokenType(token_type_str),
        jti=payload.get("jti", ""),
        scopes=payload.get("scopes", []),
    )


# ---------------------------------------------------------------------------
# OAuth2 scheme
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scopes={
        "avatars:read": "Read avatar information",
        "avatars:write": "Create and update avatars",
        "videos:read": "Read video information",
        "videos:write": "Generate and manage videos",
        "admin": "Full administrative access",
    },
)


async def get_current_token_data(
    token: str = Depends(oauth2_scheme),
) -> TokenData:
    """
    FastAPI dependency that parses the Bearer token and returns ``TokenData``.

    Usage::

        @router.get("/resource")
        async def resource(token_data: TokenData = Depends(get_current_token_data)):
            ...
    """
    return decode_token(token, expected_type=TokenType.ACCESS)


# ---------------------------------------------------------------------------
# API key support
# ---------------------------------------------------------------------------

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_KEY_PREFIX_LEN = 8   # e.g. "sk_live_" — visible prefix stored in DB


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        A tuple of ``(raw_key, hashed_key)``.

        *raw_key*    — shown once to the user; never stored in plaintext.
        *hashed_key* — stored in the database for verification.

    The key format is ``sk_<env>_<48 random url-safe chars>``.
    """
    env_tag = "live" if settings.is_production else "test"
    raw = f"sk_{env_tag}_{secrets.token_urlsafe(36)}"
    hashed = _pwd_context.hash(raw)
    return raw, hashed


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Return True if *raw_key* matches *hashed_key*."""
    return _pwd_context.verify(raw_key, hashed_key)


async def get_api_key(api_key_header: str | None = Security(_API_KEY_HEADER)) -> str | None:
    """
    FastAPI dependency that extracts the raw API key from ``X-API-Key``.

    Returns None if no key is present (allows endpoints to accept both JWT
    and API-key auth by combining this with ``get_current_token_data``).
    """
    return api_key_header


# ---------------------------------------------------------------------------
# RBAC decorators
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def require_role(minimum_role: Role) -> Callable[[F], F]:
    """
    Endpoint decorator that enforces a minimum role requirement.

    Usage::

        @router.delete("/resource/{id}")
        @require_role(Role.ADMIN)
        async def delete_resource(
            resource_id: UUID,
            token_data: TokenData = Depends(get_current_token_data),
        ):
            ...

    Note: The decorated function *must* accept ``token_data`` as a keyword
    argument (injected by FastAPI's DI system).
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            token_data: TokenData | None = kwargs.get("token_data")
            if token_data is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            if not has_minimum_role(token_data.role, minimum_role):
                logger.warning(
                    "rbac_denied",
                    user_id=str(token_data.user_id),
                    required=minimum_role.value,
                    actual=token_data.role.value,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{minimum_role.value}' or higher required",
                )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def require_scope(scope: str) -> Callable[[F], F]:
    """
    Endpoint decorator that enforces a specific OAuth2 scope.

    Usage::

        @router.post("/avatars")
        @require_scope("avatars:write")
        async def create_avatar(
            token_data: TokenData = Depends(get_current_token_data),
        ):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            token_data: TokenData | None = kwargs.get("token_data")
            if token_data is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            if scope not in token_data.scopes and token_data.role != Role.SUPER_ADMIN:
                logger.warning(
                    "scope_denied",
                    user_id=str(token_data.user_id),
                    required_scope=scope,
                    granted_scopes=token_data.scopes,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Scope '{scope}' required",
                )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Ownership / resource-level permission helpers
# ---------------------------------------------------------------------------


def assert_owner_or_admin(
    resource_owner_id: uuid.UUID,
    token_data: TokenData,
    *,
    allow_org_admin: bool = True,
) -> None:
    """
    Raise 403 if *token_data* does not represent the resource owner or an admin.

    Args:
        resource_owner_id: UUID of the user who owns the resource.
        token_data:        Authenticated request's token data.
        allow_org_admin:   If True, organisation admins also pass this check.

    Raises:
        HTTPException(403): If the caller is not the owner and not an admin.
    """
    is_owner = token_data.user_id == resource_owner_id
    is_admin = has_minimum_role(
        token_data.role, Role.ADMIN if allow_org_admin else Role.SUPER_ADMIN
    )

    if not (is_owner or is_admin):
        logger.warning(
            "ownership_check_failed",
            requesting_user=str(token_data.user_id),
            resource_owner=str(resource_owner_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )


def assert_same_organization(
    resource_org_id: uuid.UUID,
    token_data: TokenData,
) -> None:
    """
    Raise 403 if the resource belongs to a different organisation.

    Super-admins bypass this check.

    Args:
        resource_org_id: Organisation that owns the resource.
        token_data:      Authenticated request's token data.
    """
    if token_data.role == Role.SUPER_ADMIN:
        return

    if token_data.organization_id != resource_org_id:
        logger.warning(
            "org_isolation_violated",
            requesting_org=str(token_data.organization_id),
            resource_org=str(resource_org_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resource belongs to a different organisation",
        )


# ---------------------------------------------------------------------------
# Password strength validation
# ---------------------------------------------------------------------------

_MIN_PASSWORD_LENGTH = 8


def validate_password_strength(password: str) -> list[str]:
    """
    Return a list of rule violations for *password*.

    Returns an empty list if the password satisfies all rules.

    Rules:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
    """
    errors: list[str] = []
    if len(password) < _MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters long")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        errors.append("Password must contain at least one special character")
    return errors


# ---------------------------------------------------------------------------
# User dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    token_data: TokenData = Depends(get_current_token_data),
) -> Any:
    """
    FastAPI dependency: parses Bearer token and fetches the active User from DB.
    Raises HTTP 401 if the token is invalid or the user is not found/inactive.

    Note: DB session is injected lazily to avoid circular imports at module load.
    Endpoints that also need ``db`` should declare it separately via Depends(get_db).
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == token_data.user_id)
        )
        user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
