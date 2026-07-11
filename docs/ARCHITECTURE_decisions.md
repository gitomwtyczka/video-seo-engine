# Architecture Decisions — Video SEO Engine

**Senior Architect:** `arch-senior-01`  
**Data:** 2026-06-16  
**Input:** 4 raporty analityczne — sec (arch-sec-01), api (arch-api-01), saas (arch-saas-01), scale (arch-scale-01)  
**Commit referencyjny:** analiza fazy D1 ukończona

---

## TL;DR (max 5 zdań)

VSE ma solidny fundament (schema SEO 8/10, architektura Docker, model planów w DB), ale trzy krytyczne dziury blokują wejście na produkcję SaaS: endpointy core pipeline (`generate`, `inject`, `process`) są publicznie dostępne bez uwierzytelnienia — każdy może zużywać Claude API kosztem właściciela. Drugim blokerem jest Local Runner jako SPOF — jeden Windows PC z jednym wątkiem nie obsłuży nawet 20 concurrent użytkowników. Trzecim jest brak rate limitingu na endpointach auth — aplikacja jest otwarta na brute-force i credential stuffing. Quick wins (auth na 3 endpointach + rate limit + 3 linie DB index) można wdrożyć w ciągu jednego sprintu i natychmiast eliminują 80% ryzyka. Skalowanie do 1000 users wymaga planu dla Local Runnera — decyzja architektoniczna, której NIE można odwrócić to wybór modelu kolejkowania jobów.

---

## Odpowiedzi na Pytania Strategiczne

### P1: Co robimy NAJPIERW? (quick wins)

**Top 3 — najwyższy ROI, najniższe ryzyko:**

1. **AUTH na generate/inject/process** — 3 linie kodu per endpoint (`Depends(check_quota)` lub `Depends(get_current_user)`). Eliminuje: darmowe AI dla anonimow, nieograniczone koszty Anthropic. Effort: 2h. Ryzyko: brak (tylko dodanie).

2. **Rate limiting na `/auth/login` + `/auth/register`** — slowapi lub nginx `limit_req_zone`. Eliminuje: brute-force, credential stuffing, account farming. Effort: 1h. Ryzyko: brak.

3. **Composite index na `usage_logs(user_id, success, created_at)`** — 3 linie kodu ORM. Eliminuje: full table scan przy każdym `check_quota` (300k rows @ 1000 users). Effort: 15 minut. Ryzyko: zero.

### P2: Co blokuje skalowanie do 1000 users?

**Diagnoza:** Local Runner — 1 Windows PC, 1 wątek, brak health check, brak cleanup stale jobs.

**Objawy przy wzroście:**
- 20 concurrent generate → kolejka rośnie, użytkownicy czekają 120s+ → timeout
- PC restart (Windows Update) → wszystkie pending joby wiszą w nieskończoność
- YouTube rate limit na jednym IP → cały pipeline zatrzymany

**Remedium (stopniowe):**
1. **Teraz (P0):** Cleanup stale jobs cron — joby pending >5min → failed. Eliminuje wisielców.
2. **Sprint 1:** Runner health check endpoint — API wie czy runner żyje, dashboard pokazuje status.
3. **Sprint 2:** `SELECT ... FOR UPDATE SKIP LOCKED` — przygotowanie na multi-runner.
4. **Faza 2:** Residential proxy lub dedykowany VPS z innym IP (nie Oracle Cloud ARM).
5. **Faza 3:** Multi-runner architecture (3+ instancji na różnych IP, PostgreSQL jako queue z SKIP LOCKED).

**Trigger do Fazy 3:** >50 aktywnych userów generujących równocześnie lub >2 zgłoszenia timeout/dzień.

### P3: Architektura multi-tenant — kiedy?

**Decyzja: ODROCZYĆ. Row-level security przez `user_id` wystarczy do ~5000 users.**

**Aktualny stan:** Poprawna izolacja danych przez `user_id` FK we wszystkich tabelach. Single-database jest architektonicznie właściwy dla tej skali.

**Co to oznacza:**
- Schema-per-tenant: NIE potrzeba (overhead bez korzyści)
- Separate database per tenant: NIE potrzeba (kosztowne, złożone)
- Row-level security: WYSTARCZY — ale wymaga 100% konsekwencji (audyt IDOR w jobs.py!)

**Trigger do multi-tenant:** Klient enterprise z wymogiem data isolation w umowie (typowo >500 USD/miesiąc kontrakt), lub audit compliance (GDPR data residency requirement).

**Red flag:** IDOR w `/v1/jobs/{id}` — jeśli nie weryfikuje `job.user_id == current_user.id`, to row-level security jest dziurawa. Naprawić natychmiast razem z auth na generate/inject.

### P4: Local Runner — jak długo?

**Rekomendacja: utrzymaj architekturę (PostgreSQL queue) ale zastąp transport do 3 miesięcy.**

**Uzasadnienie:**
- Obecny design (DB jako queue, SELECT pending, POST result) jest dobry — nie przepisywać
- Problem jest w *poziomie absorbcji* (1 wątek, 1 IP, 1 PC) — nie w *protokole*
- `SELECT ... FOR UPDATE SKIP LOCKED` to wystarczająca baza dla multi-runner bez Redis/Celery

**Plan zastąpienia:**
- 0-30 dni: Cleanup stale jobs + runner health check (konieczne niezależnie)
- 30-60 dni: SKIP LOCKED + dodanie 2. runnera na innym IP (VPS z innym ASN niż Oracle)
- 60-90 dni: Residential proxy jako opcja fallback lub usługa `youtube-transcript-api` przez proxy pool

**Czego NIE robić:** Nie zastępować Celery/Redis na tym etapie — overhead bez proporcjonalnych korzyści przy <100 users.

### P5: Jakich decyzji NIE można odwrócić?

Są 4 decyzje które jeśli podjęte źle — zamknęłyby drogę do SaaS:

1. **Model kolejkowania jobów** — `transcript_jobs` jako PostgreSQL queue z SKIP LOCKED to słuszna droga. Migracja do Celery/Redis po wdrożeniu 100+ runnerów byłaby kosztowna. **Decyzja: zostajemy przy PostgreSQL queue + implementujemy SKIP LOCKED.** Rewersja trudna po skalowaniu.

2. **Format tokenu / auth model** — HS256 JWT dla users + API keys dla M2M. Zmiana algorytmu JWT po GA = forced logout wszystkich userów. **Decyzja: zostajemy przy HS256 JWT ale fail-fast przy braku `JWT_SECRET_KEY`.** Migracja do RS256 tylko jeśli pojawią się zewnętrzne serwisy weryfikujące tokeny.

3. **Response envelope** — Obecny brak spójnego envelope = tech debt który rośnie. Zmiana formatu po GA = breaking change v2 + praca po stronie crimson-void. **Decyzja: standaryzacja envelope w v1.1 (przed integracją z crimson-void) lub kontrakt adapter po stronie crimson-void.** Nie odwracalna po publicznym GA.

4. **Billing: Stripe webhook jako jedyne źródło prawdy** — Jeśli admin PATCH zmieni plan poza Stripe, subskrypcje w Stripe i DB będą rozsynchronizowane. **Decyzja: po wdrożeniu Stripe, `PATCH /v1/admin/users/{id}/plan` musi być wyłączony lub tylko dla override z logiem.** Trudno naprawić po zaległych błędach w billing data.

---

## Decyzje Architektoniczne (ADR)

### ADR-01: Auth na endpointach core pipeline

- **Status:** 🔴 Do natychmiastowego wdrożenia
- **Kontekst:** `POST /v1/generate`, `POST /v1/inject`, `POST /v1/process`, `POST /v1/sitemap` — 4 główne endpointy biznesowe — nie wymagają żadnego uwierzytelnienia. Każdy anonimowy klient może wywoływać Claude API kosztem właściciela VSE (koszt: ~$0.01-0.10 per generacja × unlimited calls).
- **Decyzja:** Dodać `Depends(check_quota)` na `/v1/generate` i `/v1/process` (auth + quota w jednej zależności). Dodać `Depends(get_current_user)` na `/v1/inject` i `/v1/sitemap` + sprawdzenie uprawnień planu (`plan.wp_sites_limit > 0` dla inject).
- **Skutki:** Wyciek kosztów zatrzymany. Quota enforcement aktywny. Izolacja danych per-user. Drobne ryzyko: istniejące integracje (jeśli jakieś są) przestaną działać — ale przy obecnym stanie (publiczne) to jest pożądane zachowanie.
- **Priorytet:** P0 — przed jakimkolwiek skalowaniem.

---

### ADR-02: Rate Limiting — Dwuwarstwowy Model

- **Status:** 🔴 Do natychmiastowego wdrożenia (warstwa 1)
- **Kontekst:** Brak rate limiting na auth endpoints umożliwia brute-force, credential stuffing i account farming. Brak throttlingu na `/v1/generate` umożliwia DDoS rachunku Anthropic.
- **Decyzja:**
  - **Warstwa 1 (infrastruktura):** nginx `limit_req_zone` per IP na auth endpoints (5/min login, 3/hour register). Implementacja bez zmian w kodzie Python — tylko nginx config.
  - **Warstwa 2 (aplikacja):** `slowapi` per API key / per user na generate (10/min). Implementacja po dodaniu auth (ADR-01).
  - **NIE używamy** Cloudflare rate limiting jako primary — nie kontrolujemy konfiguracji i może nie być dostępny przy self-hosted.
- **Skutki:** Auth endpoints chronione przed atakami. Generate endpoint chroniony przed kosztami. Legitymujący użytkownicy nie odczują różnicy przy normalnym użyciu.
- **Priorytet:** P0.

---

### ADR-03: OAuth Security — Tokeny w URL

- **Status:** 🔴 Do wdrożenia (CRITICAL, OWASP A02)
- **Kontekst:** `GET /v1/auth/google/callback` przekierowuje z `access_token` i `refresh_token` w query string URL. Tokeny trafiają do: nginx access logs, Cloudflare logs, browser history, `document.referrer`.
- **Decyzja:** Zamień token-in-URL na **one-time code pattern**: backend generuje UUID w Redis/DB z TTL 60s, redirect do frontendu z `?code=UUID`. Frontend wymienia code → tokeny przez `POST /v1/auth/exchange`. Tokeny nigdy nie są w URL.
- **Skutki:** Eliminacja OWASP A02. Drobny overhead: 1 dodatkowy request per OAuth flow. Wymaga Redis lub tabeli `auth_codes` w DB.
- **Priorytet:** P0 — naprawić przed otwarciem rejestracji na szerszą skalę.

---

### ADR-04: JWT Secret — Fail-Fast

- **Status:** 🔴 Do natychmiastowego wdrożenia
- **Kontekst:** `SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")` — aplikacja startuje z literal kluczem jeśli env nie jest ustawiony. Każdy może podpisać dowolny JWT.
- **Decyzja:** Zmienić na fail-fast: `SECRET_KEY = os.getenv("JWT_SECRET_KEY") or raise RuntimeError(...)`. Sprawdzić produkcyjny `.env` na VPS czy klucz jest ustawiony i czy jest silny (min. 32 chars).
- **Skutki:** Aplikacja nie startuje bez klucza — to pożądane zachowanie (bezpieczne domyślne).
- **Priorytet:** P0 — 5-minutowy fix.

---

### ADR-05: PostgreSQL jako Job Queue — Zostajemy

- **Status:** ✅ Zaakceptowana
- **Kontekst:** `transcript_jobs` tabela działa jako message queue dla Local Runnera. arch-scale-01 rozważał Redis/Celery jako alternatywę.
- **Decyzja:** Zostajemy przy PostgreSQL queue. Implementujemy `SELECT ... FOR UPDATE SKIP LOCKED` dla bezpiecznego multi-runner pickup. NIE migrujemy do Redis/Celery na tym etapie.
- **Uzasadnienie:** PostgreSQL queue jest prostszy w operacjach (backup, monitoring, debugowanie). SKIP LOCKED eliminuje race condition. Overhead Redis/Celery bez uzasadnienia przy <100 runnerów. Pattern znany jako "Transactional Outbox" — uznany w branży.
- **Trigger do rewizji:** >100 runnerów lub >10 000 jobów/dzień — wtedy ARQ (async Redis Queue).
- **Skutki:** Dodatkowa praca: implementacja SKIP LOCKED w `GET /v1/jobs/pending`. Multi-runner gotowy bez przepisywania architektury.
- **Priorytet:** P1.

---

### ADR-06: Local Runner — Plan Zastąpienia

- **Status:** 📋 Do zatwierdzenia przez Supervisora
- **Kontekst:** 1 Windows PC = SPOF. Brak health check, brak cleanup stale jobs, brak multi-instance. Limit: ~20 concurrent users.
- **Decyzja:** 3-fazowy plan (szczegóły w P4 powyżej). Kluczowe: NIE przepisywać protokołu, zastąpić transport. Cel: 2. runner na innym IP w ciągu 60 dni.
- **Otwarte pytanie do Supervisora:** Czy możemy dedykować 1 VPS z innym ASN niż Oracle Cloud ARM jako runner host? Koszt: ~$5-10/miesiąc. Alternatywnie: residential proxy pool (~$20-50/miesiąc).
- **Skutki:** Po wdrożeniu: eliminacja SPOF, obsługa 50+ concurrent users w trybie LOCAL_RUNNER.
- **Priorytet:** P1.

---

### ADR-07: API Keys dla M2M (crimson-void integracja)

- **Status:** 📋 Do wdrożenia — Sprint 2
- **Kontekst:** crimson-void potrzebuje dostępu M2M do VSE API. JWT user tokens nie nadają się dla M2M (wygasają, refresh wymaga browser flow). Tabela `api_keys` w DB już istnieje, ale brak endpointów CRUD i brak auth dependency obsługującej `X-API-Key` header.
- **Decyzja:** Implementacja API key auth: `POST /v1/api-keys` (create), `GET /v1/api-keys` (list), `DELETE /v1/api-keys/{id}` (revoke). Rozszerzenie `get_current_user` o `X-API-Key` header. Format klucza: `vse_live_[32 hex chars]`. Plan enforcement: `api_access=True` wymagany.
- **Skutki:** Odblokowanie M2M integracji z crimson-void. Klienci SaaS (plan starter+) mogą korzystać z API bez przeglądarki.
- **Priorytet:** P1 — Sprint 2.

---

### ADR-08: Billing — Stripe Webhook jako Jedyne Źródło Prawdy

- **Status:** 📋 Decyzja strategiczna — Faza 2
- **Kontekst:** DB schema ma pola `stripe_customer_id` i `stripe_subscription_id`, ale brak biblioteki Stripe i brak endpointów. Aktualnie plan można zmienić tylko przez admin PATCH.
- **Decyzja:** Po wdrożeniu Stripe: webhook `POST /v1/billing/webhook` = jedyne źródło zmian planu. Admin PATCH nie zmienia planu bezpośrednio — może tylko flagować override z logiem. Stripe subscription = source of truth.
- **Uzasadnienie:** Bez tej zasady DB i Stripe będą się rozsynchronizowywać po każdym anulowaniu subskrypcji, chargeback, refund.
- **Skutki:** Wymaga starannej implementacji webhook handlera. Admin traci możliwość ręcznej zmiany planu (pożądane przy scale).
- **Priorytet:** P2 — przed uruchomieniem monetyzacji.

---

### ADR-09: Response Envelope — Standaryzacja w v1.1

- **Status:** 📋 Decyzja odroczona — przed GA lub integracją crimson-void
- **Kontekst:** Brak spójnego envelope API (generate zwraca inny format niż auth, inne niż admin). Parsowanie po stronie crimson-void wymaga dedykowanego adaptera.
- **Decyzja:** Opcja A (rekomendowana): Standaryzacja envelope w v1.1 PRZED integracją crimson-void. Format: `{ok: bool, data: {...}, meta: {processing_time_s}}` dla sukcesu, `{ok: false, error: {code, message, context}}` dla błędów. Opcja B: Adapter po stronie crimson-void + dokumentacja kontraktu w `docs/INTEGRATION_crimson-void.md`. Opcja B jest wolniejsza ale bezpieczniejsza jeśli już są klienci zewnętrzni.
- **Otwarte pytanie do Supervisora:** Czy są już zewnętrzni klienci API (poza crimson-void)? Jeśli nie — Opcja A. Jeśli tak — Opcja B.
- **Priorytet:** P1 — decyzja musi być podjęta przed pierwszą integracją M2M.

---

### ADR-10: Multi-Tenancy — Row-Level Security Wystarczy

- **Status:** ✅ Zaakceptowana
- **Kontekst:** arch-saas-01 analizował alternatywę schema-per-tenant.
- **Decyzja:** Row-level security przez `user_id` FK — wystarczające do ~5000 users. Schema-per-tenant lub separate DB per tenant = NIE implementować.
- **Warunek:** 100% konsekwencja — każdy endpoint musi filtrować po `user_id`. Audyt IDOR konieczny (patrz ADR-01).
- **Trigger do rewizji:** Enterprise kontrakt z wymogiem contractual data isolation lub GDPR data residency.

---

### ADR-11: Auth na /v1/inject (2026-07-11)

**Status:** Accepted  
**Kontekst:** POST /v1/inject nie miał `Depends(get_current_user)`. Dowolny anonimowy request mógł publikować na cudzym portalu WordPress. Odkryte podczas audytu izolacji kont przed wdrożeniem YT Publishing.  
**Decyzja:** Dodano JWT auth + weryfikację ownership (`WpPortal.user_id == current_user.id`) do inject endpoint.  
**Konsekwencje:** Wszystkie callery /v1/inject MUSZĄ przekazywać Bearer token. Dashboard (Next.js) przekazuje token przez NextAuth — bez zmian frontend. Zewnętrzne integracje (jeśli istnieją) wymagają tokena.  
**Commit:** `7174fb1cdc847e4dfcbbc9941bb1e02d87e82427`

---

## Priorytetowany Roadmap Techniczny

| Faza | Co | Effort | Blokuje co? |
|------|-----|--------|-------------|
| **P0 (teraz, 1-2 dni)** | Auth na generate/inject/process/sitemap | 2h | Koszty LLM |
| P0 | Fail-fast JWT_SECRET_KEY | 5 min | Security Critical |
| P0 | Rate limit na auth endpoints (nginx) | 1h | Brute-force |
| P0 | IDOR fix w jobs.py | 1h | Wyciek danych |
| P0 | Cleanup stale jobs (background task) | 2h | Runner stability |
| **P1 (Sprint 1, tydzień 1)** | OAuth one-time code (tokeny z URL) | 4h | OWASP Critical |
| P1 | Composite index usage_logs | 15 min | DB performance @ scale |
| P1 | SKIP LOCKED w jobs pickup | 1h | Multi-runner readiness |
| P1 | Runner health check endpoint | 3h | Monitoring |
| P1 | Uvicorn workers 2→4 | 5 min | Throughput |
| P1 | DB pool hardening (pre_ping, recycle) | 15 min | Stability |
| P1 | LLM timeout + retry (tenacity) | 2h | Reliability |
| **P2 (Sprint 2, tydzień 2)** | API key CRUD + X-API-Key auth | 6h | crimson-void M2M |
| P2 | Quota enforcement + UsageLog fix | 3h | SaaS business logic |
| P2 | Response envelope standaryzacja | 4h | API kontraktu stabilność |
| P2 | CORS hardening (env-based origins) | 1h | Security Medium |
| P2 | SSRF fix — YouTube URL validator | 1h | Security Medium |
| **P3 (Sprint 3-4, tygodnie 3-4)** | Stripe billing (checkout + webhook + portal) | 16h | Monetyzacja |
| P3 | Email verification (Resend/SendGrid) | 6h | User onboarding |
| P3 | Dashboard UI: Upgrade plan CTA | 8h | Self-service |
| P3 | 2. runner na innym IP | 4h | Scale >20 users |
| **P4 (kwartalnie)** | Redis cache LLM wyników | 16h+ | Cost reduction |
| P4 | PgBouncer | 8h | Scale >500 users |
| P4 | WP credentials w DB (nie inline) | 8h | Security/UX |
| P4 | Data retention cron | 4h | DB size control |
| P4 | Webhook infrastructure | 12h | Automation crimson-void |

---

## Czerwone Linie (Czego NIE Robić)

1. **NIE otwierać rejestracji na szerokim froncie zanim nie ma auth na generate/inject.** Każde nowe konto = potencjalny anonimowy koszt LLM. Priorytet P0 musi być wdrożony zanim jakakolwiek kampania user acquisition.

2. **NIE migrować do Redis/Celery dla job queue** na etapie <100 runnerów. PostgreSQL z SKIP LOCKED obsłuży do 50+ runnerów. Migracja = przepisywanie bez korzyści.

3. **NIE zmieniać formatu URL versioning (`/v1/`)** — każda zmiana = breaking change dla istniejących integracji. URL path versioning zostaje.

4. **NIE pozwolić admin PATCH na zmianę planu po wdrożeniu Stripe** — tylko webhook. Każdy wyjątek = desynch billing.

5. **NIE przechowywać WP App Passwords w logach** — upewnij się że FastAPI nie loguje request body na poziomie INFO (tylko ERROR dla exception context).

6. **NIE implementować schema-per-tenant** bez enterprise kontraktu — overhead O(N) gdzie N = liczba klientów, bez proporcjonalnych korzyści przy row-level security.

7. **NIE uruchamiać Kubernetes** przed >500 paying users — overhead infrastrukturalny zabije produktywność małego zespołu.

---

## Otwarte Pytania do Supervisora

1. **Czy są zewnętrzni klienci API (poza crimson-void)?** — Decyduje o wyborze między ADR-09 Opcja A (standaryzacja envelope teraz) vs Opcja B (adapter). Jeśli brak zewnętrznych klientów — Opcja A jest tańsza długoterminowo.

2. **Czy możemy dedykować VPS z innym ASN niż Oracle Cloud ARM jako 2. runner?** (~$5-10/miesiąc) — Bez tego skalowanie Local Runnera do 2+ instancji jest niemożliwe (ten sam IP = te same YouTube rate limity). Decyzja blokuje Fazę 2 runnera.

3. **Kiedy planujemy otworzyć monetyzację (Stripe)?** — Billing (P3) to ~16h pracy i wymaga decyzji o pricing (PLN/EUR, VAT). Jeśli monetyzacja planowana w ciągu 30 dni — billing powinien przeskoczyć do P1.

---

## Matryca Ryzyk — Top 5

| # | Ryzyko | Prawdopodobieństwo | Wpływ | Mitygacja |
|---|--------|-------------------|-------|----------|
| R1 | Ktoś odkryje publiczne endpointy → rack up Claude bill | 🔴 Wysokie (publiczne API, znane URL) | 🔴 Krytyczny ($$$) | ADR-01 — auth na endpoints (P0) |
| R2 | Runner PC restart → pipeline zatrzymany | 🟠 Wysokie (Windows Updates) | 🟠 Duży (SLA breach) | Cleanup stale jobs + health check (P0/P1) |
| R3 | Brute-force na login → konta przejęte | 🟠 Średnle | 🔴 Krytyczny (reputacja) | ADR-02 — rate limit auth (P0) |
| R4 | LLM 429 → wszystkie generate failują | 🟡 Średnle (przy >50 RPM) | 🟠 Duży | Retry z tenacity + timeout (P1) |
| R5 | DB quota scan → timeout przy 1000 users | 🟡 Średnle | 🟠 Duży | Composite index usage_logs (P1) |

---

*arch-senior-01 | video-seo-engine | 2026-06-16 — Architecture Decisions v1.0*  
*Synteza: ANALYSIS_security.md + ANALYSIS_api_design.md + ANALYSIS_saas_patterns.md + ANALYSIS_scalability.md*  
*[vse-dev | 2026-07-11] — ADR-11 dodane: auth + user_id isolation na /v1/inject*
