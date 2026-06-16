## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-dev-09 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet

---

# TASK: vse-dev-09 — D2 + D3: Dashboard UI Artykuł + Inject One-Click

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Priorytet:** 🔴 PILNE — główny bloker operacyjny produktu

---

## Twój deliverable:

Użytkownik po wygenerowaniu SEO widzi **gotowy artykuł z rozdziałami** (nie suchy JSON) i może go wysłać do WordPressa **jednym kliknięciem** (nie copy-paste).

---

## D2 — Dashboard: Zakładka Artykuł + Rozdziały

Aktualnie `/dashboard` pokazuje tylko JSON-LD schema. Dodaj zakładki:

```
/dashboard — po generowaniu:
├── Zakładka: Schemat (obecny JSON-LD) ← ZOSTAJE bez zmian
├── Zakładka: Artykuł [NOWE]
│   ├── Lead / wstęp
│   ├── Treść artykułu (article_body)
│   ├── Cytaty (quotes[])
│   └── FAQ
├── Zakładka: Rozdziały [NOWE]
│   └── Lista: [02:15] Tytuł rozdziału (z VTT timestamps)
└── Akcje:
    ├── [Kopiuj JSON-LD]
    ├── [Kopiuj artykuł]
    └── [Wyślij do portalu] → D3
```

**Plik:** `web/src/app/dashboard/page.tsx`

Przed edycją — sprawdź przez GitHub MCP jak wygląda obecna odpowiedź API (`/v1/generate`) i jakie pola zwraca. Renderuj to co jest w response.

---

## D3 — Inject Flow: One-Click do WordPressa

Aktualnie inject wymaga ręcznego wpisania URL + credentials przy każdym użyciu. Cel MVP:

```
Klik [Wyślij do portalu]
    ↓
Modal: 
  - Pole URL portalu WP (np. https://prawy.pl)
  - Pole WP username
  - Pole WP Application Password
  - [Wyślij] → POST /v1/inject
    ↓
Potwierdzenie: link do opublikowanego posta WP
```

**Uwaga MVP:** Nie buduj pełnego zarządzania portalami (to Faza 5). Wystarczy modal z polami. Zapis credentials w localStorage na sesję jest akceptowalny jako MVP.

**Plik:** `web/src/app/dashboard/` + zweryfikuj `api/routers/inject.py`

---

## Jak czytać kod

Repo: `gitomwtyczka/video-seo-engine`, branch: `main`
Użyj GitHub MCP `get_file_contents` do odczytu. Kluczowe pliki:
- `web/src/app/dashboard/page.tsx` — główny cel edycji
- `web/src/app/dashboard/` — sprawdź cały katalog
- `api/routers/generate.py` — co zwraca API
- `api/routers/inject.py` — jak wygląda inject endpoint

---

## Deploy po zmianach

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
```

Build trwa ~2-3 min. Sprawdź:
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker compose -f docker-compose.vse.yml ps"
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

## Protokół callsign (OBOWIĄZKOWE)

```
[vse-dev-09 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-09 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

---

*Supervisor 03 | sonic-void | 2026-06-16 19:15*
