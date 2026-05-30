"""
app/api/v1/endpoints/billing.py
---------------------------------
Stripe-backed subscription management endpoints.

Endpoints
---------
GET  /billing/plans           — list available plans and prices
GET  /billing/subscription    — current subscription for the caller's org
POST /billing/checkout        — create a Stripe Checkout Session
POST /billing/portal          — create a Stripe Customer Portal session
POST /billing/webhook         — handle Stripe webhook events
GET  /billing/usage           — current month's usage vs. plan quotas
POST /billing/cancel          — cancel at period end
POST /billing/reactivate      — undo a pending cancellation
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenData, get_current_token_data
from app.models.organization import Organization, OrganizationPlan
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.video import Video

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Plan definitions (static)
# ---------------------------------------------------------------------------

PLAN_LIMITS: dict[str, dict[str, Any]] = {
    "free": {
        "display_name": "رایگان",
        "price_monthly_usd": 0,
        "price_monthly_irr": 0,
        "max_users": 3,
        "max_videos_per_month": 5,
        "max_avatars": 2,
        "max_storage_gb": 5,
        "max_knowledge_docs": 20,
        "heygen_enabled": False,
        "syncso_enabled": False,
        "realtime_sessions": 10,
        "stripe_price_id": None,
    },
    "starter": {
        "display_name": "استارتر",
        "price_monthly_usd": 49,
        "price_monthly_irr": 2_500_000,
        "max_users": 10,
        "max_videos_per_month": 50,
        "max_avatars": 10,
        "max_storage_gb": 50,
        "max_knowledge_docs": 200,
        "heygen_enabled": True,
        "syncso_enabled": False,
        "realtime_sessions": 100,
        "stripe_price_id": settings.STRIPE_PRICE_STARTER,
    },
    "professional": {
        "display_name": "حرفه‌ای",
        "price_monthly_usd": 149,
        "price_monthly_irr": 7_500_000,
        "max_users": 50,
        "max_videos_per_month": 200,
        "max_avatars": 50,
        "max_storage_gb": 200,
        "max_knowledge_docs": 2000,
        "heygen_enabled": True,
        "syncso_enabled": True,
        "realtime_sessions": 500,
        "stripe_price_id": settings.STRIPE_PRICE_PROFESSIONAL,
    },
    "enterprise": {
        "display_name": "سازمانی",
        "price_monthly_usd": 499,
        "price_monthly_irr": 25_000_000,
        "max_users": -1,   # unlimited
        "max_videos_per_month": -1,
        "max_avatars": -1,
        "max_storage_gb": 1000,
        "max_knowledge_docs": -1,
        "heygen_enabled": True,
        "syncso_enabled": True,
        "realtime_sessions": -1,
        "stripe_price_id": settings.STRIPE_PRICE_ENTERPRISE,
    },
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PlanInfo(BaseModel):
    plan: str
    display_name: str
    price_monthly_usd: float
    price_monthly_irr: int
    max_users: int
    max_videos_per_month: int
    max_avatars: int
    max_storage_gb: int
    max_knowledge_docs: int
    heygen_enabled: bool
    syncso_enabled: bool
    realtime_sessions: int
    stripe_price_id: str | None


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    stripe_subscription_id: str | None
    stripe_customer_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_end: datetime | None
    limits: dict[str, Any]


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    portal_url: str


class UsageResponse(BaseModel):
    plan: str
    period_start: datetime
    period_end: datetime
    videos_used: int
    videos_limit: int
    storage_used_gb: float
    storage_limit_gb: int
    users_count: int
    users_limit: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_org_or_403(
    token_data: TokenData,
    db: AsyncSession,
) -> Organization:
    if token_data.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
    org = await db.get(Organization, token_data.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def _get_stripe():
    """Return configured Stripe module, or raise if not configured."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured on this server",
        )
    try:
        import stripe  # noqa: PLC0415
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="stripe Python package is not installed",
        ) from exc


async def _get_or_create_stripe_customer(stripe, org: Organization) -> str:
    """Return existing Stripe customer ID or create a new one."""
    if org.subscription and org.subscription.stripe_customer_id:
        return org.subscription.stripe_customer_id

    customer = stripe.Customer.create(
        name=org.name,
        metadata={"organization_id": str(org.id)},
    )
    return customer.id


def _apply_plan_limits(org: Organization, plan_key: str, db_session: AsyncSession) -> None:
    """Update org quotas to match the new plan."""
    limits = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"])
    org.max_users = limits["max_users"] if limits["max_users"] != -1 else 10000
    org.max_videos_per_month = limits["max_videos_per_month"] if limits["max_videos_per_month"] != -1 else 100000
    org.max_storage_gb = limits["max_storage_gb"]
    org.plan = OrganizationPlan(plan_key)


async def _upsert_subscription(
    db: AsyncSession,
    org_id: uuid.UUID,
    plan: str,
    stripe_data: dict[str, Any],
) -> None:
    """Create or update subscription record from Stripe event data."""
    result = await db.execute(
        select(Subscription).where(Subscription.organization_id == org_id)
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        sub = Subscription(organization_id=org_id)
        db.add(sub)

    sub.plan = SubscriptionPlan(plan)
    sub.status = SubscriptionStatus(stripe_data.get("status", "active"))
    sub.stripe_subscription_id = stripe_data.get("id")
    sub.stripe_customer_id = stripe_data.get("customer")
    sub.stripe_price_id = stripe_data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")

    if stripe_data.get("current_period_start"):
        sub.current_period_start = datetime.fromtimestamp(
            stripe_data["current_period_start"], tz=timezone.utc
        )
    if stripe_data.get("current_period_end"):
        sub.current_period_end = datetime.fromtimestamp(
            stripe_data["current_period_end"], tz=timezone.utc
        )
    if stripe_data.get("trial_end"):
        sub.trial_end = datetime.fromtimestamp(stripe_data["trial_end"], tz=timezone.utc)

    sub.cancel_at_period_end = stripe_data.get("cancel_at_period_end", False)
    sub.extra_metadata = stripe_data

    await db.flush()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PlanInfo], summary="List available subscription plans")
async def list_plans() -> list[PlanInfo]:
    """Return all subscription tiers with pricing and quota details."""
    return [
        PlanInfo(plan=key, **{k: v for k, v in info.items() if k != "stripe_price_id"},
                 stripe_price_id=info.get("stripe_price_id"))
        for key, info in PLAN_LIMITS.items()
    ]


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
)
async def get_subscription(
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Return the caller's organization's active subscription."""
    org = await _get_org_or_403(token_data, db)
    plan_key = org.plan.value if org.plan else "free"

    sub = org.subscription
    return SubscriptionResponse(
        plan=plan_key,
        status=sub.status.value if sub else "active",
        stripe_subscription_id=sub.stripe_subscription_id if sub else None,
        stripe_customer_id=sub.stripe_customer_id if sub else None,
        current_period_start=sub.current_period_start if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
        trial_end=sub.trial_end if sub else None,
        limits=PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"]),
    )


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe Checkout Session",
)
async def create_checkout_session(
    payload: CheckoutRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout Session for upgrading/subscribing.

    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    if payload.plan not in PLAN_LIMITS or payload.plan == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan. Choose: {', '.join(k for k in PLAN_LIMITS if k != 'free')}",
        )

    price_id = PLAN_LIMITS[payload.plan].get("stripe_price_id")
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{payload.plan}' has no configured Stripe price ID",
        )

    org = await _get_org_or_403(token_data, db)
    stripe = _get_stripe()
    customer_id = await _get_or_create_stripe_customer(stripe, org)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
        subscription_data={
            "metadata": {
                "organization_id": str(org.id),
                "plan": payload.plan,
            }
        },
        metadata={"organization_id": str(org.id), "plan": payload.plan},
    )

    logger.info(
        "stripe_checkout_created",
        org_id=str(org.id),
        plan=payload.plan,
        session_id=session.id,
    )

    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create Stripe Customer Portal session",
)
async def create_portal_session(
    return_url: str,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> PortalResponse:
    """
    Open the Stripe Customer Portal so users can manage their subscription,
    update payment methods, and download invoices.
    """
    org = await _get_org_or_403(token_data, db)

    if not org.subscription or not org.subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Stripe subscription found for this organization",
        )

    stripe = _get_stripe()
    session = stripe.billing_portal.Session.create(
        customer=org.subscription.stripe_customer_id,
        return_url=return_url,
    )

    return PortalResponse(portal_url=session.url)


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Handle Stripe webhook events",
    include_in_schema=False,  # Not shown in OpenAPI — webhook secret auth
)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
) -> dict[str, str]:
    """
    Stripe webhook endpoint.  Verifies the signature and processes events:

    - ``checkout.session.completed`` → activate subscription
    - ``customer.subscription.updated`` → update plan / status
    - ``customer.subscription.deleted`` → downgrade to free
    - ``invoice.payment_failed`` → mark past_due
    """
    body = await request.body()

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured",
        )

    stripe = _get_stripe()
    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature or "", settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("stripe_webhook_signature_invalid", error=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except Exception as exc:
        logger.error("stripe_webhook_parse_error", error=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook parse error")

    event_type: str = event["type"]
    event_data: dict[str, Any] = event["data"]["object"]

    logger.info("stripe_webhook_received", event_type=event_type, event_id=event["id"])

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(db, event_data)
        elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
            await _handle_subscription_updated(db, event_data)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, event_data)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, event_data)
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, event_data)
        else:
            logger.debug("stripe_webhook_unhandled", event_type=event_type)

        await db.commit()
    except Exception as exc:
        logger.error("stripe_webhook_handler_error", event_type=event_type, error=str(exc))
        await db.rollback()
        # Return 200 anyway to prevent Stripe from retrying indefinitely for non-transient errors
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok"}


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Get current billing period usage",
)
async def get_usage(
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """
    Return the organization's current-month resource consumption vs. plan limits.
    """
    org = await _get_org_or_403(token_data, db)
    plan_key = org.plan.value if org.plan else "free"
    limits = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"])

    # Current billing period (calendar month if no Stripe subscription)
    now = datetime.now(timezone.utc)
    sub = org.subscription
    if sub and sub.current_period_start and sub.current_period_end:
        period_start = sub.current_period_start
        period_end = sub.current_period_end
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # Count videos generated this period
    video_count_result = await db.execute(
        select(func.count(Video.id)).where(
            Video.organization_id == org.id,
            Video.created_at >= period_start,
            Video.created_at <= period_end,
            Video.is_deleted.is_(False),
        )
    )
    videos_used: int = video_count_result.scalar_one()

    # Count active users
    from app.models.user import User  # noqa: PLC0415
    user_count_result = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id == org.id,
            User.is_active.is_(True),
        )
    )
    users_count: int = user_count_result.scalar_one()

    return UsageResponse(
        plan=plan_key,
        period_start=period_start,
        period_end=period_end,
        videos_used=videos_used,
        videos_limit=limits["max_videos_per_month"],
        storage_used_gb=0.0,   # TODO: sum from MinIO metrics
        storage_limit_gb=limits["max_storage_gb"],
        users_count=users_count,
        users_limit=limits["max_users"],
    )


@router.post("/cancel", status_code=status.HTTP_200_OK, summary="Cancel subscription at period end")
async def cancel_subscription(
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Schedule the subscription to cancel at the end of the current billing period."""
    org = await _get_org_or_403(token_data, db)

    if not org.subscription or not org.subscription.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active subscription")

    stripe = _get_stripe()
    stripe.Subscription.modify(
        org.subscription.stripe_subscription_id,
        cancel_at_period_end=True,
    )

    await db.execute(
        update(Subscription)
        .where(Subscription.organization_id == org.id)
        .values(cancel_at_period_end=True)
    )
    return {"status": "scheduled_for_cancellation"}


@router.post("/reactivate", status_code=status.HTTP_200_OK, summary="Undo pending cancellation")
async def reactivate_subscription(
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove the cancel_at_period_end flag to keep the subscription active."""
    org = await _get_org_or_403(token_data, db)

    if not org.subscription or not org.subscription.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active subscription")

    stripe = _get_stripe()
    stripe.Subscription.modify(
        org.subscription.stripe_subscription_id,
        cancel_at_period_end=False,
    )

    await db.execute(
        update(Subscription)
        .where(Subscription.organization_id == org.id)
        .values(cancel_at_period_end=False)
    )
    return {"status": "reactivated"}


# ---------------------------------------------------------------------------
# Webhook event handlers
# ---------------------------------------------------------------------------


async def _handle_checkout_completed(db: AsyncSession, data: dict[str, Any]) -> None:
    """Activate subscription after successful checkout."""
    org_id_str: str = data.get("metadata", {}).get("organization_id", "")
    plan: str = data.get("metadata", {}).get("plan", "starter")

    if not org_id_str:
        logger.warning("stripe_checkout_no_org_id")
        return

    org_id = uuid.UUID(org_id_str)
    org = await db.get(Organization, org_id)
    if not org:
        logger.warning("stripe_checkout_org_not_found", org_id=org_id_str)
        return

    _apply_plan_limits(org, plan, db)

    # If there's a subscription ID in the session, fetch it
    stripe_sub_id: str | None = data.get("subscription")
    sub_data: dict[str, Any] = {"id": stripe_sub_id, "customer": data.get("customer"), "status": "active"}
    await _upsert_subscription(db, org_id, plan, sub_data)

    logger.info("subscription_activated", org_id=org_id_str, plan=plan)


async def _handle_subscription_updated(db: AsyncSession, data: dict[str, Any]) -> None:
    """Sync subscription status and plan on Stripe updates."""
    org_id_str: str = data.get("metadata", {}).get("organization_id", "")
    if not org_id_str:
        # Find org by customer ID
        customer_id: str = data.get("customer", "")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            org_id_str = str(sub.organization_id)
        else:
            return

    org_id = uuid.UUID(org_id_str)

    # Determine plan from price ID
    price_id: str = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
    plan = _price_id_to_plan(price_id)

    org = await db.get(Organization, org_id)
    if org:
        _apply_plan_limits(org, plan, db)

    await _upsert_subscription(db, org_id, plan, data)
    logger.info("subscription_updated", org_id=org_id_str, plan=plan, status=data.get("status"))


async def _handle_subscription_deleted(db: AsyncSession, data: dict[str, Any]) -> None:
    """Downgrade to free when subscription is cancelled."""
    customer_id: str = data.get("customer", "")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    org = await db.get(Organization, sub.organization_id)
    if org:
        _apply_plan_limits(org, "free", db)

    await db.execute(
        update(Subscription)
        .where(Subscription.organization_id == sub.organization_id)
        .values(
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.CANCELED,
            canceled_at=datetime.now(timezone.utc),
        )
    )
    logger.info("subscription_cancelled", org_id=str(sub.organization_id))


async def _handle_payment_failed(db: AsyncSession, data: dict[str, Any]) -> None:
    """Mark subscription as past_due on failed payment."""
    subscription_id: str = data.get("subscription", "")
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(status=SubscriptionStatus.PAST_DUE)
    )
    logger.warning("payment_failed", stripe_subscription_id=subscription_id)


async def _handle_payment_succeeded(db: AsyncSession, data: dict[str, Any]) -> None:
    """Restore active status after successful payment."""
    subscription_id: str = data.get("subscription", "")
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(status=SubscriptionStatus.ACTIVE)
    )
    logger.info("payment_succeeded", stripe_subscription_id=subscription_id)


def _price_id_to_plan(price_id: str) -> str:
    mapping = {
        settings.STRIPE_PRICE_STARTER: "starter",
        settings.STRIPE_PRICE_PROFESSIONAL: "professional",
        settings.STRIPE_PRICE_ENTERPRISE: "enterprise",
    }
    return mapping.get(price_id, "starter")


# ---------------------------------------------------------------------------
# Quota enforcement dependency (used by other endpoints)
# ---------------------------------------------------------------------------


async def check_video_quota(
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    FastAPI dependency that raises 429 if the organization has exceeded
    its monthly video generation quota.

    Usage::

        @router.post("/generate", dependencies=[Depends(check_video_quota)])
        async def generate_video(...):
            ...
    """
    if token_data.organization_id is None:
        return

    org = await db.get(Organization, token_data.organization_id)
    if not org:
        return

    plan_key = org.plan.value if org.plan else "free"
    limits = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"])
    max_videos = limits["max_videos_per_month"]

    if max_videos == -1:
        return  # unlimited

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    count_result = await db.execute(
        select(func.count(Video.id)).where(
            Video.organization_id == token_data.organization_id,
            Video.created_at >= period_start,
            Video.is_deleted.is_(False),
        )
    )
    videos_used: int = count_result.scalar_one()

    if videos_used >= max_videos:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"ماهیانه {max_videos} ویدیو مجاز است. "
                f"این ماه {videos_used} ویدیو ساخته‌اید. "
                "برای ارتقاء پلن به /billing/checkout مراجعه کنید."
            ),
        )
