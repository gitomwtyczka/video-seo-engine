# Raport Wdrożeniowy: KROK A+B+C — Limity 5/30/110/250, Top-Up 99/249/699 PLN, OAuth Channel Match, Instant Runner Wakeup & Blokada Anty-Konfabulacyjna

- **Data:** 2026-10-20
- **Agent:** `vse-architect-01` (we współpracy z `vse-dev-01`)
- **Projekt:** `video-seo-engine` (`main`)
- **Status:** ✅ Wdrożone na produkcję (`147.224.162.100`) i zweryfikowane E2E

---

## 1. CO i PO CO (Human-First Summary)

### CO zostało zrobione?
Wdrożono kompleksowy pakiet zmian obejmujący:
1. **KROK A — Korekta i synchronizacja limitów planów (`5 / 30 / 110 / 250`) oraz cen pakietów Top-Up (`99 / 249 / 699 PLN`):**
   - Limity miesięczne w całym systemie (PostgreSQL `plans`, backend FastAPI, wtyczka WordPress v3.0, skrypt Stripe Live, strona główna, `/cennik` oraz `/admin`):
     - **Free:** `5 filmów / mies.` (`0 PLN`)
     - **Starter:** `30 filmów / mies.` (`49 PLN`)
     - **Pro:** `110 filmów / mies.` (`149 PLN`)
     - **Agency:** `250 filmów / mies.` (`499 PLN`)
   - Pakiety jednorazowe **Top-Up** (bezterminowe kredyty `extra_quota_balance`):
     - **+50 filmów:** `99 PLN`
     - **+150 filmów:** `249 PLN`
     - **+500 filmów:** `699 PLN`
   - Baner **VIP / Enterprise (`>250 filmów / mies.`)** na stronie `/cennik`.
2. **KROK B — Niezawodność pobierania napisów (YouTube OAuth Channel Match + Multi-Track Fallback + Instant Runner Wakeup):**
   - **Dopasowanie kanału OAuth po `channel_id` filmu (`api/services/pipeline.py`):** Funkcja `_get_user_yt_access_tokens(user_id, target_channel_id)` zwraca listę tokenów OAuth użytkownika posortowaną tak, że na pierwszym miejscu znajduje się token kanału będącego właścicielem filmu (`channel_id == target_channel_id`). Eliminuje to błąd `403 Forbidden` w YouTube Data API v3 (`captions.download`), gdy użytkownik ma podpiętych wiele kanałów YouTube.
   - **Multi-Track Fallback (`core/fetcher.py`):** `fetch_transcript_api_v3()` iteruje po wszystkich ścieżkach napisów zwróconych przez `captions.list` (z priorytetem dla żądanego języka i ścieżek manualnych), zamiast przerywać po pierwszej ścieżce.
   - **Cache transkrypcji w DB (`api/services/pipeline.py`):** Przed wywołaniem zewnętrznego pobierania sprawdzane są wcześniejsze rekordy w `usage_logs` oraz `transcript_jobs` dla tego samego `video_id`.
   - **Natychmiastowe wybudzanie (`asyncio.Event`) i optymalizacja pollingu (`api/services/pipeline.py`, `api/routers/jobs.py`):**
     - Wprowadzono słownik in-memory `_JOB_EVENTS: dict[str, asyncio.Event]` — gdy Desktop Runner odsyła wynik na `POST /v1/jobs/{id}/result`, oczekujący request `/v1/generate` budzi się w `<1 ms`.
     - `LOCAL_RUNNER_POLL_INTERVAL` ustawiono na `2.0s` (fallback dla wielu workerów uvicorn — 4x mniej zapytań SQL niż przy `0.5s`), a `LOCAL_RUNNER_TIMEOUT` na `90s`.
     - Endpoint `POST /v1/jobs/{id}/result` akceptuje spóźnione wyniki również wtedy, gdy job przeszedł w stan `cloud_fallback` lub `processing`.
3. **KROK C — Twarda blokada anty-konfabulacyjna (`HTTP 422` + `0 kredytów`) oraz `clean_transcript` z korektą fonetyczną ASR (`core/generator.py`, `api/routers/generate.py`):**
   - Całkowicie usunięto niebezpieczny fallback generujący artykuł z samego tytułu i opisu filmu.
   - Gdy wszystkie warstwy pobierania napisów zawiodą, rzucany jest wyjątek `TranscriptUnavailableError`, zwracający `HTTP 422 Unprocessable Entity` z czytelną instrukcją dla użytkownika i **bez pobrania kredytu z puli (`0 credits charged`)**.
   - W `core/generator.py` dodano twarde reguły korekty fonetycznej ASR (poprawa przekręconych nazwisk, nazw własnych i interpunkcji na podstawie tytułu/opisu filmu) oraz pole wyjściowe `clean_transcript`.

---

## 2. Lista Commitów (`gitomwtyczka/video-seo-engine` @ `main`)

| Commit SHA | Opis |
|---|---|
| `a63cb06` | `feat(plugin): set PLAN_LIMITS to 5/30/110/250 [vse-dev-01]` |
| `5196757` | `feat(payments): update Top-Up prices to 99 / 249 / 699 PLN [vse-dev-01]` |
| `3a62af9` | `feat(admin): set DEFAULT_PLAN_QUOTAS to 5/30/110/250 [vse-dev-01]` |
| `c3fac7c` | `feat(stripe): add scripts/setup_stripe_live.py with 30/110/250 quotas [vse-dev-01]` |
| `581f232` | `feat(cennik): set quotas to 30/110/250, Top-Up to 99/249/699 PLN and >250 Enterprise banner [vse-dev-01]` |
| `d43c544` | `feat(landing): set plan quotas to 5/30/110/250 on landing page [vse-dev-01]` |
| `a480164` | `feat(admin-ui): set PLAN_QUOTA and PLAN_OPTIONS to 5/30/110/250 [vse-dev-01]` |
| `a3e1e56` | `docs(roadmap): update ROADMAP.md to v2.2 (quotas 5/30/110/250, Top-Up 99/249/699, WP plugin v3.0, Admin panel) [vse-dev-01]` |
| `aaf0085` | `docs(handoff): update .agents/handoff/handoff.md on GitHub to v2.2 [vse-dev-01]` |
| `2009f30` | `fix(fetcher): multi-track fallback in fetch_transcript_api_v3 and log channel_id [vse-dev-01]` |
| `64e83e2` | `fix(pipeline): match video channel_id for YT OAuth, add DB transcript cache, 90s/0.5s runner polling, and hard anti-confabulation block [vse-dev-01]` |
| `3d651cd` | `fix(jobs): accept transcript results on cloud_fallback/processing jobs [vse-dev-01]` |
| `4d0ed16` | `fix(generate): return HTTP 422 with 0 credits charged on missing transcript and reuse existing transcript job [vse-dev-01]` |
| `87e21a3` | `fix(generator): hard anti-confabulation block on missing transcript, ASR phonetic correction instructions, and clean_transcript field [vse-dev-01]` |
| `93cf930` | `perf(pipeline): set LOCAL_RUNNER_POLL_INTERVAL=2.0s + in-memory asyncio.Event instant wakeup [vse-dev-01]` |
| `212c588` | `perf(jobs): trigger in-memory asyncio.Event wakeup on POST /v1/jobs/{id}/result [vse-dev-01]` |
| `e7de509` | `docs(tasks): mark KROK A+B+C complete in current.md [vse-architect-01]` |

---

## 3. Weryfikacja E2E na VPS (`147.224.162.100`)

1. **Backup Pre-Deploy (`/home/ubuntu/scripts/backup_pre_deploy.sh`):**
   - Wykonany przed deployem (`=== PRE-DEPLOY BACKUP COMPLETE ===`, exit code `0`).
2. **Sekwencyjny Build & Deploy (`vse-api` -> `vse-web`):**
   - `vse-api`: zbudowany z `212c588` i uruchomiony (`Plans seeded/updated with Stripe prices and accurate quotas (5 / 30 / 110 / 250)`).
   - `vse-web`: zbudowany (19 stron statycznych/dynamicznych Next.js 14) i uruchomiony (`Ready in 84ms` na porcie `3001`).
3. **Tabela `plans` w PostgreSQL:**
   - `free`: `monthly_quota = 5`, `price_pln = 0`
   - `starter`: `monthly_quota = 30`, `price_pln = 49` (`price_1To7dAQpm4UmxYABGIq9xztn`)
   - `pro`: `monthly_quota = 110`, `price_pln = 149` (`price_1To7dAQpm4UmxYABJDZg6rRE`)
   - `agency`: `monthly_quota = 250`, `price_pln = 499` (`price_1To7dBQpm4UmxYAB8x6Guqcf`)
4. **Dopasowanie kanału YouTube OAuth + Pobieranie VTT dla `lAdOs4IcHvY` (`Studio Prawy_PL` / `UCoH2G9By4OX3kcLsc8lHgDw`):**
   - `_get_user_yt_access_tokens` poprawnie dopasowało i odświeżyło token kanału `UCoH2G9By4OX3kcLsc8lHgDw` jako pierwszy na liście.
   - `fetch_transcript_api_v3("lAdOs4IcHvY", lang="pl", oauth_token=tokens[0])` pobrało pełną polską transkrypcję VTT: **`lang='pl'`, `len=154983` znaków**.
5. **Endpointy HTTP:**
   - `GET /cennik` -> `HTTP 200 OK` (zwraca `30 filmów`, `110 filmów`, `250 filmów` oraz pakiety Top-Up `99 zł`, `249 zł`, `699 zł`).
   - `HEAD /v1/plugin/download` -> `HTTP 200 OK` (`content-disposition: attachment; filename="vse-video-seo.zip"`).
   - `GET /v1/users/desktop-runner-package` -> `HTTP 401 Unauthorized` bez tokenu (endpoint aktywny i chroniony autoryzacją).
