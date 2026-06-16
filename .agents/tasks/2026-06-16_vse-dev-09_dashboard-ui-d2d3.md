## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-dev-09 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet

---

# TASK: vse-dev-09 — Env Fix + D2+D3 Dashboard + UX Fixes

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Priorytet:** 🔴 PILNE

---

## 📚 KROK 0b — Przeczytaj kontekst projektu (OBOWIĄZKOWE)

Przed czymkolwiek przeczytaj przez GitHub MCP:
1. `docs/ARCHITECTURE.md` — stack, kontenery, porty
2. `ROADMAP.md` — co zrobione, co w toku

---

## Twój deliverable:

1. Fix `NEXT_PUBLIC_API_URL` (naprawia admin panel)
2. D2 — Dashboard: zakładki Artykuł + Rozdziały z prawdziwymi czasami
3. D3 — Panel WP widoczny od razu (nie dopiero po obróbce)
4. Inject one-click modal
5. Historia z bazy danych (nie localStorage/cache)
6. Historia i Ustawienia klikalne
7. Jeden rebuild + weryfikacja

---

## ETAP 1 — Fix NEXT_PUBLIC_API_URL (ZRÓB PIERWSZE)

**Problem (znany, nie odkrywaj ponownie):**
```
NEXT_PUBLIC_API_URL = "https://vse.impresjapr.pl/api"  ← ZLE
fetch → /api/v1/admin/users → 404 ❌

Powinno być:
NEXT_PUBLIC_API_URL = "https://vse.impresjapr.pl"      ← DOBRZE
fetch → /v1/admin/users → poprawnie ✅
```

Znajdź zmienną w docker-compose lub `.env`, zmień przez GitHub MCP.
`NEXT_PUBLIC_*` jest wbudowane w build — sama zmiana bez rebuildu NIE wystarczy.

---

## ETAP 2 — Rozdzialy z prawidłowymi czasami (VTT fix diagnoza)

**Problem:** Użytkownik zgadza, że timestamps rozdziałów nadal = 0, wpisy puste.

DEV-06 miał to naprawić (format `__VTT__\n[MM:SS] tekst`). Zbadaj:

1. Sprawdź `api/services/pipeline.py` przez GitHub MCP — czy parser `__VTT__` jest poprawny
2. Sprawdź `api/routers/jobs.py` — czy sanitize zachowuje timestamps
3. Sprawdź co zwraca API w polu `schema_data.chapters` dla przetworzonego joba — SSH:
   ```powershell
   ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker exec [API_CONTAINER] curl -s http://localhost:8085/v1/jobs/[JOB_ID] | python3 -m json.tool | grep -A5 chapter"
   ```
4. Jeśli backend zwraca poprawne czasy — problem jest w renderowaniu frontend (`page.tsx`)
5. Jeśli backend zwraca 0 — problem w pipeline, napraw tam

**Cel:** Użytkownik widzi `[02:15] Tytuł rozdziału` a nie `[00:00] `

---

## ETAP 3 — D3: Panel WP od razu widoczny

**Problem:** Panel logowania do portalu WP pojawia się dopiero po obróbce linka.
**Oczekiwanie:** Formularz z polami URL+credentials powinien być widoczny od początku (domyślnie otwarty lub jako boczny panel).

Implementacja MVP:
```
/dashboard:
  Po lewej lub na dole — panel stały:
    [ URL portalu WP      ]
    [ WP Username         ]
    [ WP App Password     ]
    [Wyślij do portalu] ← aktywny dopiero gdy jest wygenerowane schema
```

Zapis credentials w `localStorage` = akceptowalny MVP.

---

## ETAP 4 — D2: Zakładki Artykuł + Rozdziały

```
/dashboard — po generowaniu:
├── Zakładka: Schemat (obecny JSON-LD) ← ZOSTAJE
├── Zakładka: Artykuł [NOWE]
│   ├── Lead, Treść, Cytaty, FAQ
├── Zakładka: Rozdziały [NOWE]
│   └── [02:15] Tytuł — z prawdziwymi czasami
└── Akcje: Kopiuj / Wyślij
```

---

## ETAP 5 — Historia: baza danych (KRYTYCZNE)

**Zasada architektoniczna (nienaruszalna):**
> Historia procesowania musi być pobierana z bazy danych PostgreSQL.
> NIE z localStorage, NIE z sessionStorage, NIE z żadnego lokalnego cache.

**Dlaczego:** localStorage = traci się po wylogowaniu, nie działa między urządzeniami, nie działa w trybie incognito. To był znany bloker w poprzednim projekcie SaaS.

**Implementacja:**
- Historia = tabela `transcript_jobs` + `usage_logs` w PostgreSQL
- Endpoint: `GET /v1/jobs/history?user_id=...` lub `GET /v1/jobs/` z filtrem po user
- Sprawdź czy endpoint historii istnieje w `api/routers/jobs.py`
- Jeśli nie ma — dodaj endpoint zwracający historię jobów zalogowanego usera
- Frontend `/historia` czyta z API, nie z cache

---

## ETAP 6 — Historia i Ustawienia klikalne

**Problem:** Linki "Historia" i "Ustawienia" w sidebarze są nieklikalne (prawdopodobnie `href="#"` lub brak routingu).

**Minimum viable:**
- `/historia` — strona z listą przetworzonych linków (z bazy, patrz Etap 5)
- `/ustawienia` — placeholder z informacją "W trakcie budowy" (nie musi być pełne)

Sprawdź w `web/src/app/` czy te katalogi/pliki istnieją.

---

## ETAP 7 — Deploy i weryfikacja

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
```

Build ~3 min. Weryfikacja:
1. `/admin` — tabela userów ładuje się
2. `/dashboard` — zakładki Artykuł/Rozdziały widoczne, panel WP od razu
3. `/historia` — strona istnieje i ładuje z API
4. Czasy rozdziałów != 0

---

## ⚠️ Kolejność implementacji

1. Przeczytaj ARCHITECTURE.md + ROADMAP.md
2. Przeczytaj kluczowe pliki (jobs.py, pipeline.py, page.tsx, middleware.ts)
3. Fix NEXT_PUBLIC_API_URL
4. Diagnoza VTT timestamps (backend najpierw)
5. Historia endpoint (jeśli brak)
6. Frontend: zakładki + panel WP + historia + ustawienia placeholder
7. Jeden rebuild
8. Weryfikacja

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **FILE BRIDGE / Wetty: ZAKAZ**

---

## Raport po wykonaniu

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-09_dashboard-d2d3.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-09_dashboard-d2d3.md`

**Dual-write OBOWIĄZKOWY.**

---

## Protokół callsign

```
[vse-dev-09 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-09 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

---

*Supervisor 03 | sonic-void | 2026-06-16 19:48 | v3 — dodane: VTT diagnoza, panel WP od razu, historia z DB, Historia/Ustawienia klikalne*
