# HANDOFF v2 — VSE Bugs: Zweryfikowana Analiza + Gotowe Fixy

**Agent:** sup-analyst-01 (Claude Sonnet Thinking)  
**Data:** 2026-06-30 22:38  
**Dla:** nowej sesji implementującej fixy (Gemini Pro → implementacja, Claude → weryfikacja)

> ⚠️ To jest v2 handoffu. Wcześniejszy raport Gemini (faza 1) zawierał błąd w BUG-2 — poprawiony poniżej na podstawie bezpośredniej analizy kodu.

---

## KONTEKST

- Deploy Stripe Checkout: ✅ DONE (commit 879298a, na VPS)
- Testy E2E (konto: verinarto/Agency): ujawniły 3 bugi produkcyjne
- Kod przeczytany bezpośrednio z GitHub (branch: main)

---

## BUG-1: Plan wraca do FREE po odświeżeniu / re-logowaniu

**Plik:** `api/routers/payments.py` → `_handle_subscription_deleted`

**Root cause:** Stripe przy upgrade planu wysyła `customer.subscription.deleted` na STARĄ subskrypcję. Backend dostaje event, szuka usera po `customer_id` i bezwarunkowo resetuje `plan_id = 'free'` — bez sprawdzenia czy kasowana subskrypcja to aktywna.

**Aktualny kod (błędny):**
```python
async def _handle_subscription_deleted(subscription: dict, db: AsyncSession) -> None:
    customer_id = subscription.get("customer")
    # ...
    user.plan_id = "free"
    user.stripe_subscription_id = None
    await db.commit()
```

**Fix:**
```python
async def _handle_subscription_deleted(subscription: dict, db: AsyncSession) -> None:
    customer_id = subscription.get("customer")
    deleted_sub_id = subscription.get("id")  # ID kasowanej subskrypcji
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
    # Przy upgrade Stripe kasuje starą sub — ignorujemy ten event
    if user.stripe_subscription_id != deleted_sub_id:
        logger.info(
            "subscription.deleted ignored: deleted_sub=%s != active_sub=%s (likely upgrade)",
            deleted_sub_id, user.stripe_subscription_id,
        )
        return

    user.plan_id = "free"
    user.stripe_subscription_id = None
    await db.commit()
    logger.info("User %s downgraded to free (subscription cancelled)", user.id)
```

**Dodatkowa weryfikacja przez SSH (przed fixem):**
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 `
  "docker exec vse-db psql -U postgres -d vse -c 'SELECT id, stripe_price_id FROM plans;'"
```
Sprawdź czy `stripe_price_id` jest uzupełnione dla starter/pro/agency. Jeśli NULL → webhook `subscription.updated` też nie działa.

---

## BUG-2: Nie można dodać portalu

**Plik:** `api/routers/portals.py` → `create_portal` → `_validate_profile_id`

**Root cause (inny niż podał Gemini — Gemini się mylił):**  
Backend NIE blokuje po limicie planu. Blokuje przez:
```python
def _validate_profile_id(profile_id: str):
    if not os.path.exists(f"profiles/{profile_id}.yaml"):
        raise HTTPException(status_code=400, detail=f"Profile '{profile_id}' does not exist.")
```
Jeśli user podał `profile_id` (np. "biznesciti") który nie ma pliku `profiles/biznesciti.yaml` na VPS → HTTP 400.

**Weryfikacja przez SSH:**
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 `
  "ls /home/ubuntu/video-seo-engine/profiles/"
```
Jeśli `biznesciti.yaml` nie istnieje → to jest root cause.

**Opcja A — Stwórz brakujący profil na VPS** (jeśli biznesciti to prawdziwy portal):
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 `
  "cp /home/ubuntu/video-seo-engine/profiles/default.yaml /home/ubuntu/video-seo-engine/profiles/biznesciti.yaml"
```

**Opcja B — Usuń walidację profile_id z create_portal** (jeśli profile_id jest opcjonalne):  
W `create_portal`, zamiast rzucać wyjątek gdy plik nie istnieje, po prostu zignoruj lub ustaw `profile_id = None`.

**Decyzja należy do właściciela projektu** — zapytaj przed implementacją.

---

## BUG-3: Historia pokazuje joby WSZYSTKICH użytkowników

**Plik:** `api/routers/jobs.py` → `get_job_history`

**Root cause:** Endpoint nie ma auth dependency i nie filtruje po `user_id`. Komentarz w kodzie wprost to przyznaje: *"w MVP jest jeden użytkownik"*.

**Aktualny kod (błędny):**
```python
@router.get("/history", response_model=List[HistoryJobResponse])
async def get_job_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(_get_db),   # brak current_user!
) -> List[HistoryJobResponse]:
    result = await db.execute(
        select(TranscriptJob)
        .order_by(desc(TranscriptJob.created_at))  # brak WHERE user_id!
        .offset(offset)
        .limit(limit)
    )
```

**Fix:**
```python
# KROK 1: Dodaj import
from api.auth import get_current_user
from api.models.user import User

# KROK 2: Zmień sygnaturę endpointu
@router.get("/history", response_model=List[HistoryJobResponse])
async def get_job_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),  # DODAĆ
    db: AsyncSession = Depends(_get_db),
) -> List[HistoryJobResponse]:

# KROK 3: Dodaj WHERE do query
    result = await db.execute(
        select(TranscriptJob)
        .where(TranscriptJob.user_id == current_user.id)  # DODAĆ
        .order_by(desc(TranscriptJob.created_at))
        .offset(offset)
        .limit(limit)
    )
```

**⚠️ Uwaga:** `TranscriptJob.user_id` jest nullable — stare joby (bez user_id) znikną z historii dla zwykłych userów. Admin (`is_admin=True`) powinien widzieć wszystkie — rozważ:
```python
# Dla admina — pokaż wszystko, dla zwykłego usera — filtruj
if not current_user.is_admin:
    query = query.where(TranscriptJob.user_id == current_user.id)
```

---

## KOLEJNOŚĆ IMPLEMENTACJI

| Krok | Akcja | Plik |
|------|-------|------|
| 1 | SSH: sprawdź `stripe_price_id` w DB | — |
| 2 | SSH: sprawdź `ls profiles/` | — |
| 3 | Fix BUG-1: guard w `_handle_subscription_deleted` | `api/routers/payments.py` |
| 4 | Fix BUG-2: stwórz profil lub usuń walidację | `profiles/` lub `api/routers/portals.py` |
| 5 | Fix BUG-3: filtrowanie historii po user_id | `api/routers/jobs.py` |
| 6 | Commit + deploy: `git pull && docker compose up -d --build` | VPS |
| 7 | Test E2E: zaloguj jako verinarto, sprawdź plan/portale/historię | — |

---

## INFRASTRUKTURA

- VPS: `ubuntu@147.224.162.100`
- SSH key: `~/.ssh/oracle-crimson.key`
- Repo na VPS: `/home/ubuntu/video-seo-engine`
- Docker: `vse-api`, `vse-web`, `vse-db`
- DB: PostgreSQL, container `vse-db`, user: `postgres`, db: `vse`
- Deploy: `docker compose up -d --build` w `/home/ubuntu/video-seo-engine`

---

*[sup-analyst-01 | sonic-void | 2026-06-30 22:38 | handoff v2]*
