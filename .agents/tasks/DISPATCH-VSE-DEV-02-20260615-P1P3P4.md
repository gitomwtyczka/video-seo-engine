# DISPATCH — vse-dev-02

**Data:** 2026-06-15  
**Od:** Supervisor 01  
**Dla:** `vse-dev-02` (Worker)  
**Repo:** `gitomwtyczka/video-seo-engine` (branch: `main`)  
**Priorytet:** 🔴 WYSOKI  

---

## KONTEKST STARTOWY

Sesja `vse-dev-01` zakończyła się handoffem (2026-06-14). Frontend + auth działają produkcyjnie na https://vse.impresjapr.pl. Twoje zadanie to domknięcie 3 otwartych P-items, które blokują core feature (pipeline YT → SEO).

**OBOWIĄZKOWO przeczytaj przed pracą:**
- `.agents/handoff/2026-06-14_vse-dev-01_handoff.md` — pełny stan + 9 GOTCHA
- `AGENTS.md` w root repo — reguły projektowe + gotcha lista

---

## ZADANIE 1 — P3: Plans seed automatyczny w startup API

**Plik docelowy:** `api/main.py`  
**Problem:** Tabela `plans` musi być ręcznie seedowana SQL po każdym clean deploy. Jeśli jest pusta — rejestracja użytkownika failuje z błędem FK violation.

**Wymagana zmiana:**
W `lifespan` lub `startup` FastAPI dodaj automatyczny INSERT planów ON CONFLICT DO NOTHING:

```python
# Wykonaj przy starcie aplikacji
async def seed_plans(db: AsyncSession):
    plans = [
        {"id": "free",    "display_name": "Free",    "monthly_quota": 5,    "wp_sites_limit": 1,   "api_access": False, "price_pln": 0},
        {"id": "starter", "display_name": "Starter", "monthly_quota": 50,   "wp_sites_limit": 3,   "api_access": True,  "price_pln": 49},
        {"id": "pro",     "display_name": "Pro",     "monthly_quota": 300,  "wp_sites_limit": 10,  "api_access": True,  "price_pln": 149},
        {"id": "agency",  "display_name": "Agency",  "monthly_quota": 9999, "wp_sites_limit": 999, "api_access": True,  "price_pln": 499},
    ]
    for plan in plans:
        await db.execute(
            text("INSERT INTO plans (id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln) "
                 "VALUES (:id, :display_name, :monthly_quota, :wp_sites_limit, :api_access, :price_pln) "
                 "ON CONFLICT (id) DO NOTHING"),
            plan
        )
    await db.commit()
```

**Weryfikacja P3:**
```bash
# Po deployu — sprawdź logi startu
docker logs vse-api --tail 30
# Powinno być: "Plans seeded" lub brak błędu FK przy rejestracji

# Test rejestracji nowego usera
curl -X POST https://vse.impresjapr.pl/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test2@test.com","password":"Test1234!","name":"Test"}'
# Oczekiwany wynik: 201 Created z {"id":...,"email":...}
```

---

## ZADANIE 2 — P1: Client-side error na dashboard po wklejeniu YT URL

**Symptom:** Po wklejeniu URL YouTube i kliknięciu "Analizuj" pojawia się:
`Application error: a client-side exception has occurred`

**Diagnostyka — wykonaj NAJPIERW:**
1. Otwórz https://vse.impresjapr.pl/dashboard w przeglądarce
2. DevTools → Console → wklej URL YT i kliknij submit
3. Skopiuj pełny stack trace błędu

**Prawdopodobne przyczyny (sprawdź w kolejności):**
1. `fetch` do `/api/v1/process` zwraca błąd (np. 500, 422) — frontend nie obsługuje error state
2. Brak `try/catch` wokół `JSON.parse` lub destructuringu odpowiedzi
3. Komponent próbuje renderować `undefined` lub `null` bez guard'a
4. YouTube IP blocking na VPS → `yt-dlp` failuje → API zwraca 500 → React crasha przy próbie wyświetlenia

**Plik do sprawdzenia:** `web/src/app/dashboard/page.tsx` (lub podobny)

**Wymagane minimum — dodaj error handling:**
```typescript
// Wzorzec do zaimplementowania
const [error, setError] = useState<string | null>(null);
const [loading, setLoading] = useState(false);
const [result, setResult] = useState<any>(null);

const handleSubmit = async () => {
  setError(null);
  setLoading(true);
  try {
    const res = await fetch('/api/v1/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: ytUrl })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    setResult(data);
  } catch (e: any) {
    setError(e.message || 'Nieznany błąd');
  } finally {
    setLoading(false);
  }
};

// W JSX — zawsze renderuj error state
{error && <div className="error-box">Błąd: {error}</div>}
{loading && <div>Przetwarzanie...</div>}
{result && <ResultComponent data={result} />}
```

**WAŻNE:** Nawet jeśli pipeline failuje (P7 — YouTube IP blocking), dashboard NIE może crashować. Error musi być wyświetlony jako komunikat, nie jako Application Error.

**Weryfikacja P1:**
- Wklej URL YT → strona NIE crashuje
- Widać albo wyniki, albo czytelny komunikat błędu
- Brak `Application error: a client-side exception has occurred`

---

## ZADANIE 3 — P4: Weryfikacja pipeline /v1/process end-to-end

**UWAGA:** Zadanie P4 jest zależne od P7 (YouTube IP blocking). Jeśli YouTube jest zablokowany na VPS, pipeline nie zwróci wyników. **Mimo to wykonaj test diagnostyczny.**

**Test diagnostyczny pipeline:**
```bash
# Na VPS (przez FILE BRIDGE lub SSH)
# Test 1 — czy API w ogóle odpowiada
curl -X POST https://vse.impresjapr.pl/api/v1/process \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Test 2 — czy yt-dlp na VPS działa
docker exec vse-api yt-dlp --version
docker exec vse-api yt-dlp --dump-json --no-download \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | head -50
```

**Scenariusze i akcje:**

| Wynik | Akcja |
|---|---|
| API zwraca 200 + JSON SEO | ✅ Pipeline działa — udokumentuj w raporcie |
| API zwraca 200 ale puste/błędne dane | 🔧 Napraw logikę generacji w `api/processor.py` |
| yt-dlp: HTTP 403 / blocked | ⚠️ Potwierdź IP blocking — raportuj do Supervisora (P7 dla stratega) |
| yt-dlp nie znaleziony | 🔧 Dodaj `yt-dlp` do `api/requirements.txt` i rebuild |
| API zwraca 500 | 🔧 Debug logi, napraw |

**Minimalny wynik:** Zdiagnozuj co blokuje pipeline i udokumentuj w raporcie. Fix jeśli możliwy bez rozwiązania P7.

---

## DEPLOY WORKFLOW (skrócony runbook)

```bash
# Na VPS przez FILE BRIDGE stellar-relay
# target: oracle-crimson, method: execute_command

# Po każdej zmianie kodu — git pull + rebuild
cd /home/ubuntu/video-seo-engine
git fetch origin main && git reset --hard origin/main

# Rebuild tylko zmienionego serwisu
docker compose -f docker-compose.vse.yml build api
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate api

# Dla frontendu
docker compose -f docker-compose.vse.yml build web
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate web

# Weryfikacja
docker ps --filter name=vse
curl https://vse.impresjapr.pl/health
curl https://vse.impresjapr.pl/api/auth/csrf  # musi zwrócić JSON z csrfToken
```

**KRYTYCZNE GOTCHA — zawsze sprawdź po rebuild frontu:**
- G8: brak rewrites `/api/*` w `next.config.mjs`
- G9: nginx blok `/api/auth/` → 3001 (NIE ruszaj nginx jeśli nie musisz)

---

## RAPORTOWANIE

Po zakończeniu każdego P-item — dual write:

**Repo projektu:**
```
gitomwtyczka/video-seo-engine
branch: main
path: .agents/reports/2026-06-15_vse-dev-02_[temat].md
```

**Supervisor inbox:**
```
gitomwtyczka/sonic-void
branch: master  
path: .agents/reports/inbox/2026-06-15_vse-dev-02_[temat].md
```

**Format raportu:**
```markdown
# Raport — [P-item] [temat]
**Agent:** vse-dev-02
**Data:** 2026-06-15
**Status:** ✅ done / ⚠️ partial / ❌ blocked

## Co zrobiono
...

## Wynik weryfikacji
...

## Commit SHA
...

## Blokery / niezakończone
...
```

---

## KOLEJNOŚĆ WYKONANIA

1. **P3 najpierw** — prerequisit dla P1 (register musi działać)
2. **P1** — dodaj error handling dashboard (niezależny od P7)
3. **P4** — test diagnostyczny pipeline, raport
4. **Raport zbiorczy** → dual write

---

## LINKI OPERACYJNE

- Repo: https://github.com/gitomwtyczka/video-seo-engine/tree/main
- Site: https://vse.impresjapr.pl
- Swagger: https://vse.impresjapr.pl/docs
- Nginx config: `/home/ubuntu/crimson-void/nginx/default.conf` (VPS)
- .env: `/home/ubuntu/video-seo-engine/.env` (VPS, NIE w repo)
- VPS: `147.224.162.100` (Oracle ARM)
- Docker compose: `docker-compose.vse.yml`

---

*Dispatch: Supervisor 01 | 2026-06-15 | video-seo-engine*
