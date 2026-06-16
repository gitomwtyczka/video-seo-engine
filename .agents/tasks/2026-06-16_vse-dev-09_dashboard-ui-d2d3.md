## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-dev-09 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet

---

# TASK: vse-dev-09 — Env Fix + D2+D3 Dashboard UI + Inject One-Click

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

1. **Fix `NEXT_PUBLIC_API_URL`** — admin panel i dashboard client-side fetch trafiają na złą ścieżkę
2. **D2** — Dashboard: zakładki Artykuł + Rozdziały (zamiast surowego JSON)
3. **D3** — Inject one-click: modal z polami WP zamiast copy-paste
4. **Jeden rebuild** na końcu
5. **Weryfikacja** admin panelu po rebuildie

---

## ETAP 1 — Fix NEXT_PUBLIC_API_URL (ZRÓB PIERWSZE)

### Diagnoza (znana, nie odkrywaj ponownie):

Agent `vse-analyst-01` zidentyfikował root cause admin panelu:

```
NEXT_PUBLIC_API_URL = "https://vse.impresjapr.pl/api"   ← ZLE
fetch → /api/v1/admin/users → 404 ❌

Powinno być:
NEXT_PUBLIC_API_URL = "https://vse.impresjapr.pl"       ← DOBRZE
fetch → /v1/admin/users → 401 (bez tokenu) ✅
```

**UWAGA:** `NEXT_PUBLIC_*` zmienne są wbudowane w build Next.js (baked at build time). Sama zmiana env w docker-compose bez rebuildu NIE wystarczy.

### Jak znaleźć gdzie jest ta zmienna:

```powershell
# Sprawdź na VPS:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker inspect vse-web | grep -i API_URL"
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cat /opt/vse/docker-compose.vse.yml | grep -A5 NEXT_PUBLIC"
```

Jak znajdziesz plik — zmień `NEXT_PUBLIC_API_URL` na `https://vse.impresjapr.pl` (bez `/api`).
Plik docker-compose zmień przez GitHub MCP, jeśli jest w repo.

---

## ETAP 2 — D2: Zakładki Artykuł + Rozdziały

Aktualnie `/dashboard` pokazuje tylko JSON-LD schema. Dodaj zakładki:

```
/dashboard — po generowaniu:
├── Zakładka: Schemat (obecny JSON-LD) ← ZOSTAJE
├── Zakładka: Artykuł [NOWE]
│   ├── Lead (lead)
│   ├── Treść artykułu (article_body)
│   ├── Cytaty (quotes[])
│   └── FAQ
├── Zakładka: Rozdziały [NOWE]
│   └── Lista: [02:15] Tytuł rozdziału
└── Akcje:
    ├── [Kopiuj JSON-LD]
    ├── [Kopiuj artykuł]
    └── [Wyślij do portalu] → D3
```

**Plik:** `web/src/app/dashboard/page.tsx`

Przed edycją przeczytaj przez GitHub MCP:
- `web/src/app/dashboard/page.tsx` — aktualny kod
- `api/routers/generate.py` — co zwraca API (jakie pola)

Użyj fetch z `BACKEND_URL` (server-side) zamiast `NEXT_PUBLIC_API_URL` (client-side) tam gdzie to możliwe. Jeśli musisz użyć client-side — użyj wzorca `fetch('/v1/...')` (relatywna ścieżka bez hosta).

---

## ETAP 3 — D3: Inject One-Click Modal

Aktualnie inject wymaga ręcznego wpisania URL+credentials przy każdym użyciu. Cel MVP:

```
Klik [Wyślij do portalu]
    ↓
Modal:
  - URL portalu WP (np. https://prawy.pl)
  - WP username
  - WP Application Password
  - [Wyślij] → POST /v1/inject
    ↓
Potwierdzenie: link do opublikowanego posta WP
```

Zapis credentials w `localStorage` na sesję = akceptowalny MVP.
Nie buduj pełnego zarządzania portalami (to Faza 5).

Przeczytaj przez GitHub MCP: `api/routers/inject.py` — jakie pola przyjmuje endpoint.

---

## ETAP 4 — Deploy i weryfikacja

```powershell
# Jeden rebuild na koniec:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"

# Sprawdź status (po ~3 min):
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker compose -f docker-compose.vse.yml ps"
```

**Weryfikacja po deploy:**
1. `https://vse.impresjapr.pl/admin` — czy panel laduje (nie spinner/error)
2. `https://vse.impresjapr.pl/dashboard` — czy zakładki Artykuł/Rozdziały się pokazują
3. `curl https://vse.impresjapr.pl/api/v1/admin/users` — czy nadal 404 czy już przechodzi

---

## ⚠️ PowerShell — wzorzec SSH dla złożonych komend

Proste komendy:
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps"
```

Złożone (SQL, zagnieżdżone cudzysłowy) → write_to_file skryptu + scp + ssh:
```powershell
# 1. write_to_file "D:/tmp/cmd.sh" z treścią
# 2. scp -i ~/.ssh/oracle-crimson.key D:/tmp/cmd.sh ubuntu@147.224.162.100:/tmp/
# 3. ssh ... "bash /tmp/cmd.sh"
```

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

*Supervisor 03 | sonic-void | 2026-06-16 19:40 | v2 — scalony z NEXT_PUBLIC_API_URL fix + admin verification*
