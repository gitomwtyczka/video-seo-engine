# HANDOFF — VSE Bugs Investigation
**Agent:** sup-analyst-01 | **Data:** 2026-06-30 22:14 | **Przekazuje do:** nowej sesji Gemini Pro

---

## KONTEKST SESJI

Deploy Stripe Checkout zakończony sukcesem. Testy E2E (konto: verinarto) ujawniły 3 bugi produkcyjne w video-seo-engine.

## 3 BUGI DO NAPRAWY (priorytet: wszystkie CRITICAL)

### BUG-1: Plan wraca do FREE po odświeżeniu strony
- **Objaw:** Po opłaceniu Agency plan widoczny → po refresh/re-login znowu FREE
- **Dotyczy:** konto verinarto (nowe) i tobroz (admin)
- **Znana przyczyna (z wcześniejszej analizy):**
  - `stripe_price_id` był NULL w DB → webhook `subscription.updated` nie matchował planu
  - Race condition: `customer.subscription.deleted` resetuje plan przed `checkout.session.completed`
  - **UWAGA:** agent vse-dev-stripe twierdzi że wpisał stripe_price_id do DB — wymaga weryfikacji czy rzeczywiście są w DB i czy są poprawne
- **Pliki do zbadania:** `api/routers/payments.py`, `api/routers/auth.py`

### BUG-2: Nie można dodać portalu (ale profil można)
- **Objaw:** Dodawanie portalu zwraca błąd. Dodawanie profilu działa. Testowane na koncie Agency.
- **Możliwa przyczyna:** Limit portali sprawdzany po planie — ale jeśli plan = FREE (BUG-1), limit wynosi 0
- **Pliki do zbadania:** `api/routers/portals.py` (szczególnie check limitu wp_sites_limit)

### BUG-3: Historia pokazuje joby WSZYSTKICH użytkowników
- **Objaw:** Nowy user (verinarto) widzi w /historia joby innych użytkowników
- **Znana przyczyna (z kodu):** `GET /v1/jobs/history` — w kodzie jest komentarz "w MVP jest jeden użytkownik — nie filtruje po user_id"
- **Pliki do zbadania:** `api/routers/jobs.py` endpoint `get_job_history`

---

## ZNANE FAKTY Z KODU

### VSE — Model User (`api/models/user.py`)
- Tabela `users` z `plan_id` FK → `plans`
- `plans` ma kolumnę `stripe_price_id` (nullable)
- `plans`: free / starter / pro / agency
- `WpPortal` linked FK `user_id` → `users.id`
- `TranscriptJob` ma opcjonalny FK `user_id` (nullable!)

### Stripe Price IDs (wpisane przez agenta, wymagają weryfikacji w DB)
- Starter: `price_1To7dAQpm4UmxYABGIq9xztn` (49 PLN)
- Pro: `price_1To7dAQpm4UmxYABJDZg6rRE` (149 PLN)
- Agency: `price_1To7dBQpm4UmxYAB8x6Guqcf` (499 PLN)

### Infrastructure
- VPS: `ubuntu@147.224.162.100`
- SSH key: `~/.ssh/oracle-crimson.key`
- Docker containers: `vse-api`, `vse-web`, `vse-db` (PostgreSQL)
- DB: PostgreSQL, container `vse-db`, user: postgres, db: vse

---

## INSTRUKCJA DLA NOWEJ SESJI

1. **FAZA 1 (Gemini Pro):** Zbierz kod 3 bugów przez GitHub MCP (owner: gitomwtyczka, repo: video-seo-engine, branch: main)
2. **FAZA 2 (Claude Sonnet):** Analiza + plan naprawy
3. **FAZA 3 (Gemini Pro):** Implementacja zatwierdzonych fixów
4. **Weryfikacja DB:** SSH → sprawdź `SELECT id, stripe_price_id FROM plans;`

---

*[sup-analyst-01 | sonic-void | 2026-06-30 22:14]*