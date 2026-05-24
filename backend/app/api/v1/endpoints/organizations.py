"""
app/api/v1/endpoints/organizations.py
--------------------------------------
Multi-tenant organization management: CRUD, member management, invitations,
and statistics.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    Role,
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
    has_minimum_role,
)
from app.models.organization import Organization, OrganizationPlan
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: str | None
    plan: str
    is_active: bool
    max_users: int
    max_storage_gb: int
    max_videos_per_month: int
    logo_url: str | None
    primary_color: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    total: int
    page: int
    page_size: int


class CreateOrganizationRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    domain: str | None = Field(None, max_length=255)
    plan: OrganizationPlan = OrganizationPlan.FREE


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    domain: str | None = Field(None, max_length=255)
    logo_url: str | None = None
    primary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    settings: dict[str, Any] | None = None


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    last_login: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.VIEWER


class OrgStatsResponse(BaseModel):
    organization_id: uuid.UUID
    member_count: int
    avatar_count: int
    voice_count: int
    video_count: int
    agent_count: int
    storage_used_bytes: int
    storage_limit_bytes: int
    storage_used_pct: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_org_or_404(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id, Organization.is_deleted.is_(False)
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def _require_org_access(token_data: TokenData, org_id: uuid.UUID) -> None:
    """Verify the caller can access the given organization."""
    if has_minimum_role(token_data.role, Role.SUPER_ADMIN):
        return
    if token_data.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this organization is denied",
        )


def _require_admin(token_data: TokenData) -> None:
    if not has_minimum_role(token_data.role, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=OrganizationListResponse,
    summary="List organizations",
)
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> OrganizationListResponse:
    """
    List organizations.

    Super-admins see all orgs; other users see only their own.
    """
    query = select(Organization).where(Organization.is_deleted.is_(False))

    if not has_minimum_role(token_data.role, Role.SUPER_ADMIN):
        if token_data.organization_id is None:
            return OrganizationListResponse(items=[], total=0, page=page, page_size=page_size)
        query = query.where(Organization.id == token_data.organization_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Organization.created_at.desc()).offset(offset).limit(page_size)
    )
    orgs = result.scalars().all()

    return OrganizationListResponse(
        items=[OrganizationResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    payload: CreateOrganizationRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Create a new organization. Requires ADMIN role."""
    _require_admin(token_data)

    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(
            Organization.slug == payload.slug, Organization.is_deleted.is_(False)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists",
        )

    org = Organization(
        name=payload.name,
        slug=payload.slug,
        domain=payload.domain,
        plan=payload.plan,
    )
    db.add(org)
    await db.flush()

    logger.info("organization_created", org_id=str(org.id), name=org.name)
    return org


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details",
)
async def get_organization(
    org_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Retrieve organization details. Members can view their own org."""
    _require_org_access(token_data, org_id)
    return await _get_org_or_404(db, org_id)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization settings",
)
async def update_organization(
    org_id: uuid.UUID,
    payload: UpdateOrganizationRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Update organization metadata. Requires ADMIN role within the org."""
    _require_admin(token_data)
    _require_org_access(token_data, org_id)

    org = await _get_org_or_404(db, org_id)
    update_values: dict[str, Any] = {}

    if payload.name is not None:
        update_values["name"] = payload.name
    if payload.domain is not None:
        update_values["domain"] = payload.domain
    if payload.logo_url is not None:
        update_values["logo_url"] = payload.logo_url
    if payload.primary_color is not None:
        update_values["primary_color"] = payload.primary_color
    if payload.settings is not None:
        # Merge settings rather than replace
        merged = dict(org.settings or {})
        merged.update(payload.settings)
        update_values["settings"] = merged

    if update_values:
        await db.execute(update(Organization).where(Organization.id == org_id).values(**update_values))
        await db.refresh(org)

    return org


@router.get(
    "/{org_id}/members",
    response_model=MemberListResponse,
    summary="List organization members",
)
async def list_members(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> MemberListResponse:
    """List all members of an organization."""
    _require_org_access(token_data, org_id)
    await _get_org_or_404(db, org_id)

    query = select(User).where(
        User.organization_id == org_id, User.is_deleted.is_(False)
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(User.created_at.asc()).offset(offset).limit(page_size)
    )
    members = result.scalars().all()

    return MemberListResponse(
        items=[MemberResponse.model_validate(m) for m in members],
        total=total,
    )


@router.post(
    "/{org_id}/invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Invite a user to join the organization",
)
async def invite_member(
    org_id: uuid.UUID,
    payload: InviteMemberRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Send an invitation email to a new or existing user.

    If the user already exists they are immediately added to the org.
    New users receive an invitation link to create their account.
    """
    _require_admin(token_data)
    _require_org_access(token_data, org_id)

    org = await _get_org_or_404(db, org_id)

    # Check seat limit
    member_count = (
        await db.execute(
            select(func.count(User.id)).where(
                User.organization_id == org_id, User.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    if member_count >= org.max_users:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Organization has reached its seat limit of {org.max_users}",
        )

    # Check if user already exists
    existing_user = await db.execute(
        select(User).where(User.email == payload.email, User.is_deleted.is_(False))
    )
    user = existing_user.scalar_one_or_none()

    if user:
        if user.organization_id == org_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization",
            )
        # Add existing user to org
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(organization_id=org_id, role=payload.role)
        )
        logger.info("member_added", org_id=str(org_id), user_id=str(user.id))
    else:
        # Store invitation token in Redis
        invite_token = secrets.token_urlsafe(32)
        try:
            from app.core.redis_client import redis_client  # noqa: PLC0415
            await redis_client.setex(
                f"invite:{invite_token}",
                7 * 86400,  # 7 days
                f"{org_id}:{payload.role.value}:{payload.email}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("invite_token_store_failed", error=str(exc))

        # In production, send email with the invitation link
        background_tasks.add_task(
            _send_invite_email, payload.email, org.name, invite_token
        )
        logger.info("invite_sent", org_id=str(org_id), email=payload.email)

    return {"detail": "Invitation sent successfully"}


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the organization",
)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a user from the organization by setting their org_id to NULL."""
    _require_admin(token_data)
    _require_org_access(token_data, org_id)

    # Prevent removing self
    if user_id == token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself from the organization",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == org_id,
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organization",
        )

    await db.execute(
        update(User).where(User.id == user_id).values(organization_id=None)
    )
    logger.info("member_removed", org_id=str(org_id), user_id=str(user_id))


@router.get(
    "/{org_id}/stats",
    response_model=OrgStatsResponse,
    summary="Get organization statistics",
)
async def get_org_stats(
    org_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> OrgStatsResponse:
    """Return aggregate resource and storage statistics for an organization."""
    _require_org_access(token_data, org_id)
    org = await _get_org_or_404(db, org_id)

    from app.models.avatar import Avatar  # noqa: PLC0415
    from app.models.video import Video  # noqa: PLC0415
    from app.models.voice_model import VoiceModel  # noqa: PLC0415

    member_count = (
        await db.execute(
            select(func.count(User.id)).where(
                User.organization_id == org_id, User.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    avatar_count = (
        await db.execute(
            select(func.count(Avatar.id)).where(
                Avatar.organization_id == org_id, Avatar.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    voice_count = (
        await db.execute(
            select(func.count(VoiceModel.id)).where(
                VoiceModel.organization_id == org_id, VoiceModel.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    video_count = (
        await db.execute(
            select(func.count(Video.id)).where(
                Video.organization_id == org_id, Video.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    # Storage = sum of all members' storage_used_bytes
    storage_used = (
        await db.execute(
            select(func.coalesce(func.sum(User.storage_used_bytes), 0)).where(
                User.organization_id == org_id, User.is_deleted.is_(False)
            )
        )
    ).scalar_one()

    storage_limit = int(org.max_storage_gb) * 1024 ** 3
    storage_pct = round(storage_used / storage_limit * 100, 2) if storage_limit > 0 else 0.0

    return OrgStatsResponse(
        organization_id=org_id,
        member_count=member_count,
        avatar_count=avatar_count,
        voice_count=voice_count,
        video_count=video_count,
        agent_count=len(org.agents) if org.agents else 0,
        storage_used_bytes=storage_used,
        storage_limit_bytes=storage_limit,
        storage_used_pct=storage_pct,
    )


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------


async def _send_invite_email(email: str, org_name: str, token: str) -> None:
    logger.info("send_invite_email", email=email, org=org_name, token_prefix=token[:8])
    # TODO: integrate with email service
