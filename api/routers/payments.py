"""Stripe payment endpoints.

CO: Router FastAPI obsługujący płatności Stripe dla VSE.
PO CO: Umożliwia userowi zakup planu (Starter/Pro/Agency) przez Stripe Checkout
       i zarządzanie subskrypcją przez Customer Portal.
JAK: Trzy endpointy:
  POST /v1/payments/create-checkout-session  — tworzy sesję Stripe Checkout
  POST /v1/payments/webhook                  — obsługuje eventy Stripe (sygnatura HMAC)
  GET  /v1/payments/portal-session           — tworzy link Customer Portal
"""
import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.db import get_db
from api.models.user import Plan, User

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/v1/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    plan_id: str  # 'starter' | 'pro' | 'agency'


@router.post("/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Tworzy Stripe Checkout Session i zwraca URL do przekierowania.

    CO: Endpoint przyjmuje plan_id, sprawdza stripe_price_id w tabeli plans
        i tworzy sesję Checkout w trybie 'subscription'.
    PO CO: User klika 'Subskrybuj' na stronie cennika i jest przekierowany
           do Stripe-hosted checkout — nie buildujemy custom formularza.
    JAK: Jeśli user ma już stripe_customer_id, używamy go (continuity).
         Jeśli nie — Stripe stworzy nowego Customer automatycznie.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    # Pobierz plan z DB
    result = await db.execute(
        select(Plan).where(Plan.id == body.plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{body.plan_id}' not found",
        )
    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{body.plan_id}' has no Stripe price configured",
        )

    try:
        session_kwargs: dict = {
            "mode": "subscription",
            "line_items": [
                {"price": plan.stripe_price_id, "quantity": 1}
            ],
            "success_url": f"{FRONTEND_URL}/platnosci/sukces?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{FRONTEND_URL}/cennik",
            "metadata": {
                "user_id": str(current_user.id),
                "plan_id": plan.id,
            },
            "customer_email": current_user.email
            if not current_user.stripe_customer_id
            else None,
        }

        if current_user.stripe_customer_id:
            session_kwargs["customer"] = current_user.stripe_customer_id
            session_kwargs.pop("customer_email", None)

        session = stripe.checkout.Session.create(**session_kwargs)
        return {"session_url": session.url}

    except stripe.StripeError as e:
        logger.error("Stripe error creating checkout session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Stripe webhook handler — obsługuje eventy subskrypcji.

    CO: Odbiera HTTP POST od Stripe z podpisem HMAC-SHA256.
    PO CO: Utrzymuje synchronizację między Stripe a DB — aktualizuje plan usera
           po opłacie, zmianie planu lub anulowaniu subskrypcji.
    JAK: Weryfikuje sygnaturę przez STRIPE_WEBHOOK_SECRET.
         Obsługiwane eventy:
           checkout.session.completed    → aktywuj plan
           customer.subscription.updated → zmień plan
           customer.subscription.deleted → downgrade do free
           invoice.payment_failed        → log warning

    WAŻNE: Endpoint NIE używa JWT auth — Stripe wysyła bez Bearer tokena.
           Bezpieczeństwo zapewnia weryfikacja sygnatury Stripe.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        event_data = await request.json()
        event = type("Event", (), {"type": event_data.get("type"), "data": type("Data", (), {"object": event_data.get("data", {}).get("object", {})})()} )()
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except stripe.SignatureVerificationError as e:
            logger.warning("Stripe webhook signature verification failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature",
            )

    logger.info("Stripe webhook event: %s", event["type"])

    if event["type"] == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.updated":
        await _handle_subscription_updated(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.deleted":
        await _handle_subscription_deleted(event["data"]["object"], db)

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        logger.warning(
            "invoice.payment_failed: customer=%s, invoice=%s",
            invoice.get("customer"),
            invoice.get("id"),
        )

    return {"received": True}


async def _handle_checkout_completed(
    session: dict, db: AsyncSession
) -> None:
    """Po udanym checkout — ustaw plan i zapisz stripe IDs."""
    user_id = session.get("metadata", {}).get("user_id")
    plan_id = session.get("metadata", {}).get("plan_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id or not plan_id:
        logger.error("checkout.session.completed missing metadata: %s", session)
        return

    result = await db.execute(
        select(User)
        .options(selectinload(User.plan))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        logger.error("checkout.session.completed: user not found: %s", user_id)
        return

    user.plan_id = plan_id
    user.stripe_customer_id = customer_id
    user.stripe_subscription_id = subscription_id
    await db.commit()
    logger.info(
        "User %s upgraded to plan=%s, sub=%s", user_id, plan_id, subscription_id
    )


async def _handle_subscription_updated(
    subscription: dict, db: AsyncSession
) -> None:
    """Po zmianie planu w Customer Portal."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    # Znajdź user po stripe_customer_id
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning("subscription.updated: no user for customer %s", customer_id)
        return

    # Ustal nowy plan na podstawie price_id
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        if price_id:
            plan_result = await db.execute(
                select(Plan).where(Plan.stripe_price_id == price_id)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                user.plan_id = plan.id
                user.stripe_subscription_id = subscription.get("id")
                await db.commit()
                logger.info(
                    "User %s plan updated to %s via Customer Portal",
                    user.id,
                    plan.id,
                )


async def _handle_subscription_deleted(
    subscription: dict, db: AsyncSession
) -> None:
    """Po anulowaniu subskrypcji — downgrade do free."""
    customer_id = subscription.get("customer")
    deleted_sub_id = subscription.get("id")
    if not customer_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning("subscription.deleted: no user for customer %s", customer_id)
        return

    # GUARD: degraduj TYLKO jeśli kasowana sub = aktywna sub usera
    if user.stripe_subscription_id != deleted_sub_id:
        logger.info(
            "subscription.deleted ignored: deleted_sub=%s != active_sub=%s",
            deleted_sub_id, user.stripe_subscription_id,
        )
        return

    user.plan_id = "free"
    user.stripe_subscription_id = None
    await db.commit()
    logger.info("User %s downgraded to free (subscription cancelled)", user.id)


@router.get("/portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Tworzy Stripe Customer Portal URL.

    CO: Zwraca jednorazowy link do Stripe Customer Portal.
    PO CO: User może zarządzać subskrypcją (zmiana planu, anulowanie,
           aktualizacja metody płatności) bez budowania custom UI.
    JAK: Wymaga stripe_customer_id — user musi wcześniej przejść przez checkout.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe subscription found. Please subscribe first.",
        )

    try:
        portal = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/dashboard",
        )
        return {"portal_url": portal.url}
    except stripe.StripeError as e:
        logger.error("Stripe error creating portal session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )
