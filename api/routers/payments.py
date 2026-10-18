"""Stripe payment endpoints.

CO: Router FastAPI obsługujący płatności Stripe dla VSE.
PO CO: Umożliwia userowi zakup planu (Starter/Pro/Agency) oraz pakietów Top-Up
       (+50 / +150 / +500 filmów) przez Stripe Checkout i zarządzanie subskrypcją
       przez Customer Portal.
JAK: Endpointy:
  POST /v1/payments/create-checkout-session  — tworzy sesję Stripe Checkout (subskrypcja)
  POST /v1/payments/checkout-topup           — tworzy sesję Stripe Checkout dla pakietów Top-Up (jednorazowa)
  POST /v1/payments/webhook                  — obsługuje eventy Stripe (sygnatura HMAC)
  GET  /v1/payments/portal-session           — tworzy link Customer Portal
"""
import logging
import os
from typing import Any, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.db import get_db
from api.models.user import Plan, User, Subscription, UsageLog
from api.quota import check_multilang_access

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/v1/payments", tags=["payments"])

TOPUP_PACKS: dict[str, dict[str, Any]] = {
    "topup_50": {
        "credits": 50,
        "videos": 50,
        "amount_gr": 3900,
        "name": "VSE Pakiet Top-Up +50 filmów",
        "description": "Dodatkowe 50 generacji Video SEO (bezterminowe — nie przepadają na koniec miesiąca)",
    },
    "topup_150": {
        "credits": 150,
        "videos": 150,
        "amount_gr": 9900,
        "name": "VSE Pakiet Top-Up +150 filmów",
        "description": "Dodatkowe 150 generacji Video SEO (bezterminowe — nie przepadają na koniec miesiąca)",
    },
    "topup_500": {
        "credits": 500,
        "videos": 500,
        "amount_gr": 27900,
        "name": "VSE Pakiet Top-Up +500 filmów",
        "description": "Dodatkowe 500 generacji Video SEO (bezterminowe — nie przepadają na koniec miesiąca)",
    },
}


class CheckoutRequest(BaseModel):
    plan_id: Optional[str] = None  # 'starter' | 'pro' | 'agency' | 'multilang_addon' | 'starter_multilang'
    addon: Optional[str] = None    # 'multilang'


class AddonCheckoutRequest(BaseModel):
    addon: str = "multilang"


class TopupCheckoutRequest(BaseModel):
    pack_id: str  # 'topup_50' | 'topup_150' | 'topup_500'


class VerifySessionRequest(BaseModel):
    session_id: Optional[str] = None


def _build_multilang_addon_line_item() -> dict:
    """Return Stripe line_item for Multi-Language Add-on (+29 PLN/mo)."""
    addon_price_id = os.getenv("STRIPE_PRICE_MULTILANG_ADDON", "").strip()
    if addon_price_id:
        return {"price": addon_price_id, "quantity": 1}
    return {
        "price_data": {
            "currency": "pln",
            "unit_amount": 2900,
            "recurring": {"interval": "month"},
            "product_data": {
                "name": "PressAI VSE — Pakiet Wielojęzyczny (Add-on 8 języków)",
                "description": "Odblokowuje wybór dowolnego języka docelowego przy generowaniu oraz tłumaczenie pojedynczych zakładek (Artykuł, YouTube, Meta, Cytaty, Schema) 1 kliknięciem.",
            },
        },
        "quantity": 1,
    }


@router.get("/subscription")
async def get_subscription_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Zwraca szczegóły planu oraz uprawnienia Pakietu Wielojęzycznego (has_multilang_addon)."""
    multilang = await check_multilang_access(current_user.id, db, user=current_user)
    return {
        "plan_id": current_user.plan_id or "free",
        "has_multilang_addon": bool(multilang.get("has_multilang_addon", False)),
        "extra_quota_balance": int(getattr(current_user, "extra_quota_balance", 0) or 0),
        "custom_monthly_quota": getattr(current_user, "custom_monthly_quota", None),
        "multilang": multilang,
    }


@router.post("/checkout-topup")
async def create_topup_checkout_session(
    body: TopupCheckoutRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Tworzy jednorazową sesję Stripe Checkout dla pakietów Top-Up (+50 / +150 / +500 filmów)."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    pack_id = (body.pack_id or "").strip()
    if pack_id not in TOPUP_PACKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieprawidłowy pakiet Top-Up: '{pack_id}'. Dostępne: {', '.join(TOPUP_PACKS.keys())}",
        )

    pack = TOPUP_PACKS[pack_id]
    pack_credits = int(pack.get("credits") or pack.get("videos") or 0)

    try:
        session_kwargs: dict[str, Any] = {
            "mode": "payment",
            "allow_promotion_codes": True,
            "line_items": [
                {
                    "price_data": {
                        "currency": "pln",
                        "unit_amount": pack["amount_gr"],
                        "product_data": {
                            "name": pack["name"],
                            "description": pack["description"],
                        },
                    },
                    "quantity": 1,
                }
            ],
            "success_url": f"{FRONTEND_URL}/dashboard?payment=topup_success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{FRONTEND_URL}/cennik?payment=cancelled",
            "metadata": {
                "user_id": str(current_user.id),
                "type": "topup",
                "pack_id": pack_id,
                "credits": str(pack_credits),
                "videos": str(pack_credits),
            },
            "customer_email": current_user.email
            if not current_user.stripe_customer_id
            else None,
        }

        if current_user.stripe_customer_id:
            session_kwargs["customer"] = current_user.stripe_customer_id
            session_kwargs.pop("customer_email", None)

        session = stripe.checkout.Session.create(**session_kwargs)
        return {"session_url": session.url, "checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error("Stripe error creating topup checkout session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )


@router.post("/checkout-addon")
async def create_addon_checkout_session(
    body: Optional[AddonCheckoutRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Tworzy sesję Stripe Checkout dla Pakietu Wielojęzycznego (+29 zł/mies.).
    Jeśli użytkownik jest na planie Free, automatycznie tworzy pakiet łączony Starter + Multi-Language (49 + 29 = 78 zł/mies.).
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    user_plan = (current_user.plan_id or "free").lower()
    if user_plan == "free":
        return await create_checkout_session(
            CheckoutRequest(plan_id="starter_multilang", addon="multilang"),
            current_user=current_user,
            db=db,
        )

    try:
        session_kwargs: dict = {
            "mode": "subscription",
            "allow_promotion_codes": True,
            "line_items": [_build_multilang_addon_line_item()],
            "success_url": f"{FRONTEND_URL}/platnosci/sukces?session_id={{CHECKOUT_SESSION_ID}}&addon=multilang",
            "cancel_url": f"{FRONTEND_URL}/cennik",
            "metadata": {
                "user_id": str(current_user.id),
                "plan_id": "multilang_addon",
                "addon": "multilang",
            },
            "customer_email": current_user.email
            if not current_user.stripe_customer_id
            else None,
        }

        if current_user.stripe_customer_id:
            session_kwargs["customer"] = current_user.stripe_customer_id
            session_kwargs.pop("customer_email", None)

        session = stripe.checkout.Session.create(**session_kwargs)
        return {"session_url": session.url, "checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error("Stripe error creating addon checkout session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )


@router.post("/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Tworzy Stripe Checkout Session i zwraca URL do przekierowania."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    if body.plan_id == "starter_multilang":
        res_starter = await db.execute(select(Plan).where(Plan.id == "starter"))
        starter_plan = res_starter.scalar_one_or_none()
        if starter_plan is None or not starter_plan.stripe_price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Starter plan has no Stripe price configured",
            )
        try:
            session_kwargs: dict = {
                "mode": "subscription",
                "allow_promotion_codes": True,
                "line_items": [
                    {"price": starter_plan.stripe_price_id, "quantity": 1},
                    _build_multilang_addon_line_item(),
                ],
                "success_url": f"{FRONTEND_URL}/platnosci/sukces?session_id={{CHECKOUT_SESSION_ID}}&addon=multilang",
                "cancel_url": f"{FRONTEND_URL}/cennik",
                "metadata": {
                    "user_id": str(current_user.id),
                    "plan_id": "starter",
                    "addon": "multilang",
                },
                "customer_email": current_user.email
                if not current_user.stripe_customer_id
                else None,
            }
            if current_user.stripe_customer_id:
                session_kwargs["customer"] = current_user.stripe_customer_id
                session_kwargs.pop("customer_email", None)

            session = stripe.checkout.Session.create(**session_kwargs)
            return {"session_url": session.url, "checkout_url": session.url}
        except stripe.StripeError as e:
            logger.error("Stripe error creating starter_multilang checkout session: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe error: {e.user_message or str(e)}",
            )

    if body.addon == "multilang" or body.plan_id in ("multilang_addon", "multilang"):
        return await create_addon_checkout_session(
            AddonCheckoutRequest(addon="multilang"),
            current_user=current_user,
            db=db,
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
        session_kwargs = {
            "mode": "subscription",
            "allow_promotion_codes": True,
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
        return {"session_url": session.url, "checkout_url": session.url}

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
    """Stripe webhook handler — obsługuje eventy subskrypcji oraz Top-Up."""
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
        cust_id = invoice["customer"] if "customer" in invoice else getattr(invoice, "customer", None)
        inv_id = invoice["id"] if "id" in invoice else getattr(invoice, "id", None)
        logger.warning(
            "invoice.payment_failed: customer=%s, invoice=%s",
            cust_id,
            inv_id,
        )

    return {"received": True}


def _cancel_old_subscriptions(
    customer_id: str,
    new_subscription_id: str,
    new_plan_id: str,
    cancel_addon_too: bool = False,
) -> None:
    """Anuluje poprzednie subskrypcje w Stripe przy upgrade planu, aby uniknąć podwójnego naliczania."""
    if not customer_id or not new_subscription_id:
        return
    try:
        active_subs = stripe.Subscription.list(customer=customer_id, status="active")
        subs_data = active_subs["data"] if "data" in active_subs else []
        for s in subs_data:
            s_id = s["id"] if "id" in s else getattr(s, "id", None)
            if not s_id or s_id == new_subscription_id:
                continue
            if new_plan_id in ("pro", "agency") or cancel_addon_too:
                stripe.Subscription.cancel(s_id)
                logger.info(
                    "Cancelled old subscription %s for customer %s after upgrade to %s",
                    s_id, customer_id, new_plan_id,
                )
            elif new_plan_id == "starter":
                # Sprawdź, czy to subskrypcja samego add-onu 29 PLN (jeśli tak, zostaw ją)
                items_obj = s["items"] if "items" in s else None
                items_list = items_obj["data"] if items_obj and "data" in items_obj else []
                is_only_addon = False
                if len(items_list) == 1:
                    price_obj = items_list[0]["price"] if "price" in items_list[0] else None
                    unit_amt = price_obj["unit_amount"] if price_obj and "unit_amount" in price_obj else None
                    if unit_amt == 2900:
                        is_only_addon = True
                if not is_only_addon:
                    stripe.Subscription.cancel(s_id)
                    logger.info(
                        "Cancelled old base subscription %s for customer %s after starter checkout",
                        s_id, customer_id,
                    )
    except Exception as e:
        logger.warning("Could not cancel old subscriptions for customer %s: %s", customer_id, e)


async def _handle_checkout_completed(
    session: Any, db: AsyncSession
) -> None:
    """Po udanym checkout - ustaw plan, add-on lub doładuj kredyty Top-Up."""
    metadata = session["metadata"] if "metadata" in session else getattr(session, "metadata", None)
    if not metadata:
        logger.error("checkout.session.completed: no metadata in session")
        return

    session_id = session["id"] if "id" in session else getattr(session, "id", None)
    user_id = metadata["user_id"] if "user_id" in metadata else getattr(metadata, "user_id", None)
    meta_type = metadata["type"] if "type" in metadata else getattr(metadata, "type", None)
    pack_id = metadata["pack_id"] if "pack_id" in metadata else getattr(metadata, "pack_id", None)
    credits_raw = metadata["credits"] if "credits" in metadata else getattr(metadata, "credits", None)
    if not credits_raw:
        credits_raw = metadata["videos"] if "videos" in metadata else getattr(metadata, "videos", None)
    plan_id = metadata["plan_id"] if "plan_id" in metadata else getattr(metadata, "plan_id", None)
    addon = metadata["addon"] if "addon" in metadata else getattr(metadata, "addon", None)
    customer_id = session["customer"] if "customer" in session else getattr(session, "customer", None)
    subscription_id = session["subscription"] if "subscription" in session else getattr(session, "subscription", None)

    # Obsługa jednorazowych pakietów Top-Up (idempotentna po session_id)
    if meta_type == "topup" or (pack_id and pack_id in TOPUP_PACKS):
        if not user_id or not session_id:
            logger.error("checkout.session.completed topup missing user_id or session_id")
            return

        payment_status = session["payment_status"] if "payment_status" in session else getattr(session, "payment_status", None)
        if payment_status and payment_status not in ("paid", "no_payment_required"):
            logger.info("Ignoring unpaid topup checkout session %s (payment_status=%s)", session_id, payment_status)
            return

        marker_endpoint = f"topup:{session_id}"
        existing_log = await db.execute(
            select(UsageLog).where(UsageLog.endpoint == marker_endpoint).limit(1)
        )
        if existing_log.scalar_one_or_none() is not None:
            logger.info("Top-Up session %s already processed (idempotent skip)", session_id)
            return

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            logger.error("checkout.session.completed topup: user not found: %s", user_id)
            return

        pack_def = TOPUP_PACKS.get(pack_id or "", {})
        default_pack_credits = int(pack_def.get("credits") or pack_def.get("videos") or 0)
        try:
            credits_to_add = int(credits_raw) if credits_raw else default_pack_credits
        except (ValueError, TypeError):
            credits_to_add = default_pack_credits

        if credits_to_add <= 0:
            logger.error("checkout.session.completed topup: invalid credits=%r for pack_id=%r", credits_raw, pack_id)
            return

        current_extra = int(getattr(user, "extra_quota_balance", 0) or 0)
        user.extra_quota_balance = current_extra + credits_to_add
        if customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = customer_id

        db.add(
            UsageLog(
                user_id=user.id,
                endpoint=marker_endpoint,
                youtube_id=pack_id or "topup",
                success=True,
            )
        )
        await db.commit()
        logger.info(
            "User %s credited +%d Top-Up videos (pack=%s, new_balance=%d, session=%s)",
            user.email, credits_to_add, pack_id, user.extra_quota_balance, session_id,
        )
        return

    # Guard: ignoruj checkout sessions z canceled/incomplete subscription
    if subscription_id:
        try:
            sub_obj = stripe.Subscription.retrieve(subscription_id)
            sub_status = sub_obj["status"] if "status" in sub_obj else getattr(sub_obj, "status", None)
            if sub_status in ("canceled", "incomplete_expired"):
                logger.info(
                    "Ignoring checkout for canceled sub=%s (status=%s)",
                    subscription_id, sub_status
                )
                return
        except Exception as e:
            logger.warning("Could not verify subscription %s: %s", subscription_id, e)

    if not user_id or (not plan_id and not addon):
        logger.error("checkout.session.completed missing metadata: user_id=%s, plan_id=%s, addon=%s", user_id, plan_id, addon)
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

    res_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub_row = res_sub.scalar_one_or_none()
    if sub_row is None:
        sub_row = Subscription(
            user_id=user.id,
            plan_name=user.plan_id or "free",
            has_multilang_addon=bool(user.has_multilang_addon),
        )
        db.add(sub_row)

    # Przypadek 1: Pakiet łączony Starter + Multi-Language Add-on
    if plan_id == "starter" and addon == "multilang":
        user.plan_id = "starter"
        user.has_multilang_addon = True
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        sub_row.plan_name = "starter"
        sub_row.has_multilang_addon = True
        if customer_id:
            sub_row.stripe_customer_id = customer_id
        if subscription_id:
            sub_row.stripe_subscription_id = subscription_id
        await db.commit()
        if customer_id and subscription_id:
            _cancel_old_subscriptions(customer_id, subscription_id, "starter", cancel_addon_too=True)
        logger.info(
            "User %s activated Starter + Multi-Language bundle: customer=%s, sub=%s",
            user.email, customer_id, subscription_id,
        )
        return

    # Przypadek 2: Sam Add-on Wielojęzyczny (+29 PLN/mies.)
    if addon == "multilang" or plan_id in ("multilang_addon", "multilang"):
        user.has_multilang_addon = True
        if (user.plan_id or "free") == "free":
            user.plan_id = "starter"
            sub_row.plan_name = "starter"
        if customer_id:
            user.stripe_customer_id = customer_id
            sub_row.stripe_customer_id = customer_id
        if subscription_id:
            if not user.stripe_subscription_id:
                user.stripe_subscription_id = subscription_id
            sub_row.stripe_subscription_id = subscription_id
        sub_row.has_multilang_addon = True
        await db.commit()
        logger.info(
            "User %s activated Multi-Language Add-on (+29 PLN/mo): plan=%s, customer=%s, sub=%s",
            user.email, user.plan_id, customer_id, subscription_id,
        )
        return

    # Przypadek 3: Standardowy plan bazowy (starter / pro / agency)
    old_plan = user.plan_id
    user.plan_id = plan_id
    if customer_id:
        user.stripe_customer_id = customer_id
    if subscription_id:
        user.stripe_subscription_id = subscription_id
    if plan_id in ("pro", "agency"):
        user.has_multilang_addon = True
        sub_row.has_multilang_addon = True
    sub_row.plan_name = plan_id
    if customer_id:
        sub_row.stripe_customer_id = customer_id
    if subscription_id:
        sub_row.stripe_subscription_id = subscription_id
    await db.commit()

    if customer_id and subscription_id and plan_id in ("starter", "pro", "agency"):
        _cancel_old_subscriptions(customer_id, subscription_id, plan_id, cancel_addon_too=(plan_id in ("pro", "agency")))

    logger.info(
        "User %s upgraded: plan %s -> %s, customer=%s, sub=%s",
        user.email, old_plan, plan_id, customer_id, subscription_id
    )


async def _handle_subscription_updated(
    subscription: Any, db: AsyncSession
) -> None:
    """Po zmianie planu w Customer Portal lub odnowieniu subskrypcji."""
    customer_id = subscription["customer"] if "customer" in subscription else getattr(subscription, "customer", None)
    sub_id = subscription["id"] if "id" in subscription else getattr(subscription, "id", None)
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

    res_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub_row = res_sub.scalar_one_or_none()

    sub_status = subscription["status"] if "status" in subscription else getattr(subscription, "status", None)
    if sub_status not in ("active", "trialing"):
        if user.stripe_subscription_id and sub_id and user.stripe_subscription_id != sub_id:
            logger.info("subscription.updated: non-active sub %s != user primary sub %s", sub_id, user.stripe_subscription_id)
            return
        user.plan_id = "free"
        user.stripe_subscription_id = None
        user.has_multilang_addon = False
        if sub_row:
            sub_row.plan_name = "free"
            sub_row.stripe_subscription_id = None
            sub_row.has_multilang_addon = False
        await db.commit()
        logger.info("subscription.updated: User %s downgraded to free (has_multilang_addon=False) because status is %s", user.id, sub_status)
        return

    # Ustal nowy plan i add-on na podstawie items["data"] (BEZ użycia .items!)
    items_obj = subscription["items"] if "items" in subscription else None
    items_data = items_obj["data"] if items_obj and "data" in items_obj else []
    addon_price_env = os.getenv("STRIPE_PRICE_MULTILANG_ADDON", "").strip()

    matched_plan_id: Optional[str] = None
    found_addon = False

    for item in items_data:
        price_obj = item["price"] if "price" in item else None
        if not price_obj:
            continue
        price_id = price_obj["id"] if "id" in price_obj else None
        unit_amount = price_obj["unit_amount"] if "unit_amount" in price_obj else None

        if unit_amount == 2900 or (addon_price_env and price_id == addon_price_env):
            found_addon = True

        if price_id:
            plan_result = await db.execute(
                select(Plan).where(Plan.stripe_price_id == price_id)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                matched_plan_id = plan.id

    if matched_plan_id:
        user.plan_id = matched_plan_id
        user.stripe_subscription_id = sub_id
        if matched_plan_id in ("pro", "agency"):
            user.has_multilang_addon = True
        elif found_addon:
            user.has_multilang_addon = True
    elif found_addon:
        user.has_multilang_addon = True
        if (user.plan_id or "free") == "free":
            user.plan_id = "starter"

    if sub_row:
        sub_row.plan_name = user.plan_id or "free"
        sub_row.has_multilang_addon = bool(user.has_multilang_addon)
        if sub_id:
            sub_row.stripe_subscription_id = sub_id

    await db.commit()
    logger.info(
        "User %s subscription updated: plan=%s, has_multilang_addon=%s",
        user.id,
        user.plan_id,
        user.has_multilang_addon,
    )


async def _handle_subscription_deleted(
    subscription: Any, db: AsyncSession
) -> None:
    """Po anulowaniu subskrypcji — downgrade do free i wyłączenie add-onów."""
    customer_id = subscription["customer"] if "customer" in subscription else getattr(subscription, "customer", None)
    deleted_sub_id = subscription["id"] if "id" in subscription else getattr(subscription, "id", None)
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
    if user.stripe_subscription_id and user.stripe_subscription_id != deleted_sub_id:
        logger.info(
            "subscription.deleted ignored: deleted_sub=%s != active_sub=%s",
            deleted_sub_id, user.stripe_subscription_id,
        )
        return

    user.plan_id = "free"
    user.stripe_subscription_id = None
    user.has_multilang_addon = False

    res_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub_row = res_sub.scalar_one_or_none()
    if sub_row:
        sub_row.plan_name = "free"
        sub_row.stripe_subscription_id = None
        sub_row.has_multilang_addon = False

    await db.commit()
    logger.info("User %s downgraded to free and addon disabled (subscription cancelled)", user.id)


@router.post("/verify-session")
async def verify_checkout_session(
    body: Optional[VerifySessionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Weryfikuje i synchronizuje sesję Stripe Checkout (subskrypcja lub Top-Up) oraz aktywne subskrypcje użytkownika."""
    if not STRIPE_SECRET_KEY:
        return {
            "status": "ok",
            "plan_id": current_user.plan_id or "free",
            "has_multilang_addon": bool(current_user.has_multilang_addon),
            "extra_quota_balance": int(getattr(current_user, "extra_quota_balance", 0) or 0),
            "custom_monthly_quota": getattr(current_user, "custom_monthly_quota", None),
        }

    try:
        if body and body.session_id:
            sess = stripe.checkout.Session.retrieve(body.session_id)
            sess_status = sess["status"] if "status" in sess else getattr(sess, "status", None)
            if sess_status == "complete":
                await _handle_checkout_completed(sess, db)
                await db.refresh(current_user)

        # Dodatkowa synchronizacja z aktywnymi subskrypcjami w Stripe
        customer_ids: list[str] = []
        if current_user.stripe_customer_id:
            customer_ids.append(current_user.stripe_customer_id)
        try:
            cust_list = stripe.Customer.list(email=current_user.email, limit=5)
            cust_data = cust_list["data"] if "data" in cust_list else []
            for c in cust_data:
                cid = c["id"] if "id" in c else getattr(c, "id", None)
                if cid and cid not in customer_ids:
                    customer_ids.append(cid)
        except Exception:
            pass

        plans_res = await db.execute(select(Plan))
        all_plans = {p.stripe_price_id: p.id for p in plans_res.scalars().all() if p.stripe_price_id}
        addon_price_env = os.getenv("STRIPE_PRICE_MULTILANG_ADDON", "").strip()

        found_plan: Optional[str] = None
        found_addon = False
        found_sub_id: Optional[str] = None
        found_cust_id: Optional[str] = None

        for cid in customer_ids:
            subs = stripe.Subscription.list(customer=cid, status="active", limit=10)
            subs_data = subs["data"] if "data" in subs else []
            for s in subs_data:
                sid = s["id"] if "id" in s else getattr(s, "id", None)
                items_obj = s["items"] if "items" in s else None
                items_data = items_obj["data"] if items_obj and "data" in items_obj else []
                for item in items_data:
                    price_obj = item["price"] if "price" in item else None
                    if not price_obj:
                        continue
                    pid = price_obj["id"] if "id" in price_obj else None
                    uamt = price_obj["unit_amount"] if "unit_amount" in price_obj else None
                    if pid and pid in all_plans:
                        found_plan = all_plans[pid]
                        found_sub_id = sid
                        found_cust_id = cid
                    if uamt == 2900 or (addon_price_env and pid == addon_price_env):
                        found_addon = True
                        if not found_sub_id:
                            found_sub_id = sid
                        if not found_cust_id:
                            found_cust_id = cid

        if found_plan or found_addon:
            if found_plan:
                current_user.plan_id = found_plan
            elif found_addon and (current_user.plan_id or "free") == "free":
                current_user.plan_id = "starter"
            if found_addon or current_user.plan_id in ("pro", "agency"):
                current_user.has_multilang_addon = True
            if found_cust_id:
                current_user.stripe_customer_id = found_cust_id
            if found_sub_id:
                current_user.stripe_subscription_id = found_sub_id

            res_sub = await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
            sub_row = res_sub.scalar_one_or_none()
            if sub_row is None:
                sub_row = Subscription(
                    user_id=current_user.id,
                    plan_name=current_user.plan_id or "starter",
                    has_multilang_addon=bool(current_user.has_multilang_addon),
                    stripe_customer_id=current_user.stripe_customer_id,
                    stripe_subscription_id=current_user.stripe_subscription_id,
                )
                db.add(sub_row)
            else:
                sub_row.plan_name = current_user.plan_id or "starter"
                sub_row.has_multilang_addon = bool(current_user.has_multilang_addon)
                if found_cust_id:
                    sub_row.stripe_customer_id = found_cust_id
                if found_sub_id:
                    sub_row.stripe_subscription_id = found_sub_id

            await db.commit()
    except Exception as e:
        logger.warning("verify-session error for user %s: %s", current_user.email, e)

    return {
        "status": "ok",
        "plan_id": current_user.plan_id or "free",
        "has_multilang_addon": bool(current_user.has_multilang_addon),
        "extra_quota_balance": int(getattr(current_user, "extra_quota_balance", 0) or 0),
        "custom_monthly_quota": getattr(current_user, "custom_monthly_quota", None),
    }


@router.get("/portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Tworzy Stripe Customer Portal URL."""
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
