"""
app/api/v1/endpoints/users.py
------------------------------
User management endpoints: CRUD, activation, role changes, usage stats,
and bulk CSV import.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    Role,
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
    has_minimum_role,
    hash_password,
    validate_password_strength,
)
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


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
    timezone: str
    language: str
    storage_used_bytes: int
    storage_limit_bytes: int
    last_login: datetime | None
    login_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=255)
    role: UserRole = UserRole.VIEWER
    organization_id: uuid.UUID | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    avatar_url: str | None = None
    timezone: str | None = Field(None, max_length=64)
    language: str | None = Field(None, max_length=10)
    theme: str | None = Field(None, pattern=r"^(light|dark|system)$")


class ChangeRoleRequest(BaseModel):
    role: UserRole


class UsageResponse(BaseModel):
    user_id: uuid.UUID
    storage_used_bytes: int
    storage_limit_bytes: int
    storage_used_pct: float
    avatar_count: int
    voice_count: int
    video_count: int
    agent_count: int


class BulkImportResult(BaseModel):
    created: int
    skipped: int
    failed: int
    errors: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _require_admin(token_data: TokenData) -> None:
    if not has_minimum_role(token_data.role, Role.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users (admin only)",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    role: UserRole | None = Query(None),
    is_active: bool | None = Query(None),
    organization_id: uuid.UUID | None = Query(None),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """
    List all users with pagination and filtering.

    Requires ``ADMIN`` role or higher.
    Non-super-admin users see only members of their own organisation.
    """
    _require_admin(token_data)

    query = select(User).where(User.is_deleted.is_(False))

    # Org scoping — non-super-admins only see their org
    if not token_data.role == Role.SUPER_ADMIN and token_data.organization_id:
        query = query.where(User.organization_id == token_data.organization_id)
    elif organization_id:
        query = query.where(User.organization_id == organization_id)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(pattern),
                User.username.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(page_size))
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user (admin only)",
)
async def create_user(
    payload: CreateUserRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a user account directly (bypasses email verification flow)."""
    _require_admin(token_data)

    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username),
            User.is_deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already exists",
        )

    # Admins can only create users within their own org (unless super-admin)
    org_id = payload.organization_id
    if not has_minimum_role(token_data.role, Role.SUPER_ADMIN):
        org_id = token_data.organization_id

    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        organization_id=org_id,
        is_active=True,
        is_verified=True,  # Admin-created accounts skip email verification
    )
    db.add(user)
    await db.flush()

    logger.info("user_created_by_admin", admin_id=str(token_data.user_id), new_user_id=str(user.id))
    return user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
async def get_user(
    user_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Retrieve a user's profile. Users can view their own profile; admins can view any."""
    user = await _get_user_or_404(db, user_id)
    assert_owner_or_admin(user.id, token_data)

    # Org isolation for non-super-admins
    if (
        not has_minimum_role(token_data.role, Role.SUPER_ADMIN)
        and token_data.user_id != user.id
        and user.organization_id != token_data.organization_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user profile",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update a user's profile fields. Users can update their own; admins can update any."""
    user = await _get_user_or_404(db, user_id)
    assert_owner_or_admin(user.id, token_data)

    update_values: dict[str, Any] = {}
    if payload.full_name is not None:
        update_values["full_name"] = payload.full_name
    if payload.avatar_url is not None:
        update_values["avatar_url"] = payload.avatar_url
    if payload.timezone is not None:
        update_values["timezone"] = payload.timezone
    if payload.language is not None:
        update_values["language"] = payload.language
    if payload.theme is not None:
        update_values["theme"] = payload.theme

    if update_values:
        await db.execute(update(User).where(User.id == user_id).values(**update_values))
        await db.refresh(user)

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a user",
)
async def delete_user(
    user_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a user account. Requires admin role."""
    _require_admin(token_data)
    user = await _get_user_or_404(db, user_id)

    # Prevent self-deletion
    if user.id == token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account via this endpoint",
        )

    user.soft_delete()
    logger.info("user_soft_deleted", admin_id=str(token_data.user_id), target_user_id=str(user_id))


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Toggle user active status",
)
async def activate_user(
    user_id: uuid.UUID,
    activate: bool = Query(..., description="True to activate, False to deactivate"),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Activate or deactivate a user account. Requires admin role."""
    _require_admin(token_data)
    user = await _get_user_or_404(db, user_id)

    await db.execute(update(User).where(User.id == user_id).values(is_active=activate))
    await db.refresh(user)

    logger.info(
        "user_activation_changed",
        admin_id=str(token_data.user_id),
        target_user_id=str(user_id),
        active=activate,
    )
    return user


@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Change a user's role",
)
async def change_role(
    user_id: uuid.UUID,
    payload: ChangeRoleRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Change a user's RBAC role.

    Admins can assign up to ADMIN; only SUPER_ADMIN can assign SUPER_ADMIN.
    """
    _require_admin(token_data)

    # Super-admin gate for SUPER_ADMIN assignment
    if payload.role == UserRole.SUPER_ADMIN and not has_minimum_role(
        token_data.role, Role.SUPER_ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can assign the super_admin role",
        )

    user = await _get_user_or_404(db, user_id)
    await db.execute(update(User).where(User.id == user_id).values(role=payload.role))
    await db.refresh(user)

    logger.info(
        "user_role_changed",
        admin_id=str(token_data.user_id),
        target_user_id=str(user_id),
        new_role=payload.role.value,
    )
    return user


@router.get(
    "/{user_id}/usage",
    response_model=UsageResponse,
    summary="Get storage and resource usage for a user",
)
async def get_user_usage(
    user_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Return storage consumption and per-resource counts for a user."""
    user = await _get_user_or_404(db, user_id)
    assert_owner_or_admin(user.id, token_data)

    # Import models inline to avoid circular imports
    from app.models.avatar import Avatar  # noqa: PLC0415
    from app.models.voice_model import VoiceModel  # noqa: PLC0415
    from app.models.video import Video  # noqa: PLC0415

    # Dynamic counts via separate queries
    avatar_count = (
        await db.execute(
            select(func.count(Avatar.id)).where(
                Avatar.user_id == user_id, Avatar.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    voice_count = (
        await db.execute(
            select(func.count(VoiceModel.id)).where(
                VoiceModel.user_id == user_id, VoiceModel.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    video_count = (
        await db.execute(
            select(func.count(Video.id)).where(
                Video.user_id == user_id, Video.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    used = user.storage_used_bytes
    limit = user.storage_limit_bytes
    pct = round(used / limit * 100, 2) if limit > 0 else 0.0

    return UsageResponse(
        user_id=user_id,
        storage_used_bytes=used,
        storage_limit_bytes=limit,
        storage_used_pct=pct,
        avatar_count=avatar_count,
        voice_count=voice_count,
        video_count=video_count,
        agent_count=len(user.agents) if user.agents else 0,
    )


@router.post(
    "/bulk-import",
    response_model=BulkImportResult,
    status_code=status.HTTP_200_OK,
    summary="Bulk import users from a CSV file (admin only)",
)
async def bulk_import_users(
    file: UploadFile = File(..., description="CSV file with columns: email,username,full_name,role"),
    organization_id: uuid.UUID | None = Query(None),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    """
    Import multiple users from a CSV file.

    Expected columns: ``email``, ``username``, ``full_name`` (optional), ``role`` (optional).
    Rows with duplicate email/username are skipped.
    Temporary password ``ChangeMe123!`` is set — users should reset on first login.
    """
    _require_admin(token_data)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be a .csv",
        )

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV file must be UTF-8 encoded",
        )

    reader = csv.DictReader(io.StringIO(text))
    required_columns = {"email", "username"}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV must contain columns: {', '.join(required_columns)}",
        )

    created = 0
    skipped = 0
    failed = 0
    errors: list[dict[str, str]] = []

    org_id = organization_id or token_data.organization_id
    temp_password = hash_password("ChangeMe123!")

    for row_num, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip().lower()
        username = (row.get("username") or "").strip()

        if not email or not username:
            errors.append({"row": str(row_num), "error": "Missing email or username"})
            failed += 1
            continue

        # Check duplicates
        existing = await db.execute(
            select(User).where(
                (User.email == email) | (User.username == username),
                User.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        role_str = (row.get("role") or "viewer").strip().lower()
        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.VIEWER

        try:
            user = User(
                email=email,
                username=username,
                full_name=(row.get("full_name") or "").strip() or None,
                hashed_password=temp_password,
                role=role,
                organization_id=org_id,
                is_active=True,
                is_verified=False,
            )
            db.add(user)
            await db.flush()
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"row": str(row_num), "error": str(exc)})
            failed += 1
            await db.rollback()

    logger.info(
        "bulk_import_completed",
        admin_id=str(token_data.user_id),
        created=created,
        skipped=skipped,
        failed=failed,
    )
    return BulkImportResult(created=created, skipped=skipped, failed=failed, errors=errors)
