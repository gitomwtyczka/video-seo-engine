#!/usr/bin/env python3
"""
CO: Skrypt automatycznego wdrożenia produktów i cen Stripe (Live lub Test) oraz kuponu retencyjnego LOYALTY20.
PO CO: Pozwala jednym poleceniem przełączyć komercjalizację VSE na klucze produkcyjne (sk_live_...),
       utworzyć 4 plany cykliczne w PLN (Starter 49 zł, Pro 149 zł, Agency 499 zł, Add-on 8 Języków 29 zł),
       zaktualizować tabelę `plans` w PostgreSQL oraz skonfigurować ukryty kupon retencyjny LOYALTY20
       (-20% na 3 kolejne miesiące przy próbie anulowania lub oferty przedłużenia subskrypcji).
JAK:
  docker exec vse-api python3 /app/scripts/setup_stripe_live.py
"""
import asyncio
import os
import sys

import stripe
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.db import AsyncSessionLocal  # noqa: E402


PRODUCTS_SPEC = [
    {
        "plan_id": "starter",
        "name": "PressAI VSE — Plan Starter",
        "description": "30 filmów/mies., 3 portale WordPress, Cross-Language SEO, VSE Desktop Runner",
        "amount_grosze": 4900,
        "monthly_quota": 30,
        "wp_sites_limit": 3,
        "api_access": True,
        "env_var": "STRIPE_PRICE_STARTER",
    },
    {
        "plan_id": "pro",
        "name": "PressAI VSE — Plan Pro",
        "description": "110 filmów/mies., 10 portali WordPress, Pakiet Wielojęzyczny (8 języków) w cenie, API Access",
        "amount_grosze": 14900,
        "monthly_quota": 110,
        "wp_sites_limit": 10,
        "api_access": True,
        "env_var": "STRIPE_PRICE_PRO",
    },
    {
        "plan_id": "agency",
        "name": "PressAI VSE — Plan Agency",
        "description": "250 filmów/mies., 50 portali WordPress, Multi-Language 8 języków, moduł ShortMachine AI",
        "amount_grosze": 49900,
        "monthly_quota": 250,
        "wp_sites_limit": 50,
        "api_access": True,
        "env_var": "STRIPE_PRICE_AGENCY",
    },
    {
        "plan_id": "multilang_addon",
        "name": "PressAI VSE — Pakiet Wielojęzyczny (Add-on 8 języków)",
        "description": "Dodatek do planu Starter: generowanie i adaptacja zakładek w 8 językach (PL, EN, DE, ES, FR, IT, UK, PT)",
        "amount_grosze": 2900,
        "monthly_quota": None,
        "wp_sites_limit": None,
        "api_access": None,
        "env_var": "STRIPE_PRICE_MULTILANG_ADDON",
    },
]


def ensure_price(spec: dict) -> str:
    """Find existing active recurring PLN price or create product + price in Stripe."""
    plan_id = spec["plan_id"]
    amount = spec["amount_grosze"]

    prices = stripe.Price.list(active=True, currency="pln", limit=100)
    for p in prices.data:
        meta_plan = p.metadata["vse_plan_id"] if (p.metadata and "vse_plan_id" in p.metadata) else None
        if (
            p.unit_amount == amount
            and p.recurring
            and p.recurring["interval"] == "month"
            and meta_plan == plan_id
        ):
            print(f"[Stripe] Znaleziono istniejącą cenę dla {plan_id}: {p.id} ({amount / 100:.2f} PLN)")
            return p.id

    product = stripe.Product.create(
        name=spec["name"],
        description=spec["description"],
        metadata={"vse_plan_id": plan_id},
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount,
        currency="pln",
        recurring={"interval": "month"},
        metadata={"vse_plan_id": plan_id},
    )
    print(f"[Stripe] Utworzono nową cenę dla {plan_id}: {price.id} ({amount / 100:.2f} PLN)")
    return price.id


def ensure_retention_coupon() -> str:
    """Ensure retention-only coupon LOYALTY20 (-20% for 3 months on renewal/cancellation save) exists."""
    coupon_id = "LOYALTY20"
    try:
        c = stripe.Coupon.retrieve(coupon_id)
        print(f"[Stripe] Kupon retencyjny {c.id} już istnieje (-{c.percent_off}% na {c.duration_in_months} mies.)")
    except Exception:
        c = stripe.Coupon.create(
            id=coupon_id,
            name="Retencja VSE -20% (3 mies.)",
            percent_off=20,
            duration="repeating",
            duration_in_months=3,
            metadata={"purpose": "retention_renewal_only"},
        )
        print(f"[Stripe] Utworzono kupon retencyjny {c.id} (-20% na 3 mies.)")

    # Optional promotion code creation (Coupon LOYALTY20 can be applied directly via Customer Portal or API)
    try:
        promos = stripe.PromotionCode.list(code="LOYALTY20", limit=5)
        if not promos.data:
            stripe.PromotionCode.create(coupon=coupon_id, code="LOYALTY20")
            print("[Stripe] Utworzono kod promocyjny retencji: LOYALTY20")
    except Exception as exc:
        print(f"[Stripe] Kupon LOYALTY20 aktywny w Customer Portal / API (info: {exc})")
    return coupon_id


async def update_db_plans(created_prices: dict[str, str]) -> None:
    """Sync commercial quotas into PostgreSQL `plans` table."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE plans SET monthly_quota = 5, wp_sites_limit = 1 WHERE id = 'free'")
        )
        for spec in PRODUCTS_SPEC:
            pid = spec["plan_id"]
            if pid == "multilang_addon":
                continue
            await db.execute(
                text(
                    """
                    UPDATE plans
                    SET monthly_quota = :q,
                        wp_sites_limit = :w,
                        api_access = :a
                    WHERE id = :id
                    """
                ),
                {
                    "q": spec["monthly_quota"],
                    "w": spec["wp_sites_limit"],
                    "a": spec["api_access"],
                    "id": pid,
                },
            )
        await db.commit()
    print("[PostgreSQL] Zaktualizowano tabelę `plans` (limity 5 / 30 / 110 / 250).")


async def main() -> None:
    api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not api_key:
        print("BŁĄD: Brak STRIPE_SECRET_KEY w zmiennych środowiskowych.")
        sys.exit(1)

    stripe.api_key = api_key
    mode = "LIVE (PRODUKCJA)" if api_key.startswith("sk_live_") else "TEST (SANDBOX)"
    print(f"=== Konfiguracja Stripe VSE — Tryb: {mode} ===")

    created_prices: dict[str, str] = {}
    for spec in PRODUCTS_SPEC:
        created_prices[spec["plan_id"]] = ensure_price(spec)

    ensure_retention_coupon()
    await update_db_plans(created_prices)

    print("\n=== Podsumowanie zmiennych do .env ===")
    for spec in PRODUCTS_SPEC:
        env_name = spec["env_var"]
        val = created_prices[spec["plan_id"]]
        print(f"{env_name}={val}")


if __name__ == "__main__":
    asyncio.run(main())
