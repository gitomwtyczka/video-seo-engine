# DISPATCH — vse-dev-07 | Panel Administratora (D4)

**ID:** DISPATCH-VSE-DEV-07-20260616-ADMIN-PANEL  
**Data:** 2026-06-16  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-07`  
**Priorytet:** P2 — niezależny feature  
**Scope:** `web/src/app/admin/` + `api/routers/admin.py`  
**NIE DOTYKAJ:** `local-runner/`, `api/routers/jobs.py` (pracuje tam D1/dev-06)

---

## Definicja ukończenia — Twoja sesja jest kompletna gdy

> Zanim zaczniesz — zapamiętaj co oznacza DONE.

- [ ] Heartbeat `"status": "done"` z commit SHA w `last_completed[]`
- [ ] Panel `/admin` dostępny po zalogowaniu jako agency/admin
- [ ] Lista użytkowników z edycją planu
- [ ] Raport w `video-seo-engine/.agents/reports/2026-06-16_vse-dev-07_admin-panel.md`
- [ ] Raport w `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-07_admin-panel.md`
- [ ] `project_status.json` zaktualizowany + lock zwolniony

---

## Kontekst

### Obecny problem:
Nie ma interfejsu do zarządzania użytkownikami. Teraz zmiana planu wymaga bezpośredniego SQL na VPS (jak dla `tobroz@gmail.com` → agency). To nieakceptowalne na produkcji.

### Wzorzec do implementacji:
Panel admina jak w projekcie `crimson-void` (PressAI AI Editor) — te serwisy będą połączone. Przeczytaj przez GitHub MCP jak wygląda panel admina w crimson-void:
```
gitomwtyczka/crimson-void, branch: main
Szukaj: web/src/app/admin/ lub podobne
```

### Plany użytkowników w VSE:
Sprawdź `api/models/user.py` — aktualny enum planów. Prawdopodobnie:
- `free` — podstawowy (limit 5 filmów/miesiąc)
- `pro` — średni
- `agency` — najwyższy (bez limitów)

---

## Twoje zadanie

### Krok 1 — Przeczytaj aktualny stan

Przez GitHub MCP (branch: main):
1. `api/models/user.py` — model User, enum planów, pola
2. `web/src/` — struktura frontendu
3. `web/src/app/` — strony Next.js
4. `api/routers/` — czy jest już admin router?
5. Crimson-void admin panel — jako referencja UX

### Krok 2 — Backend: admin endpoints

Stwórz `api/routers/admin.py`:

```python
# Endpointy:
GET  /v1/admin/users           # lista wszystkich users + ich plany
GET  /v1/admin/users/{id}      # szczegóły usera
PATCH /v1/admin/users/{id}/plan # zmiana planu

# Autoryzacja: only 'agency' plan lub osobna rola 'admin'
# Middleware sprawdza plan z sesji NextAuth
```

Security: admin endpoints muszą weryfikować że caller ma plan agency/admin. Nie public.

### Krok 3 — Frontend: strona /admin

Stwórz `web/src/app/admin/page.tsx`:

```
Panel Admin
├── Lista użytkowników (tabela)
│   ├── email (z OAuth)
│   ├── plan (badge: Free / Pro / Agency)
│   ├── data rejestracji  
│   ├── liczba generacji w tym miesiącu
│   └── przycisk "Zmień plan" → modal z select
└── Statystyki (opcjonalne):
    ├── Łącznie użytkowników
    ├── Generacji dzisiaj
    └── Active users (30 dni)
```

**UX referencja:** jak crimson-void admin — ciemny motyw, tabela z badge'ami planu.

### Krok 4 — Ochrona route

`web/src/middleware.ts` — dodaj że `/admin` wymaga planu agency lub roli admin:
```typescript
// Sprawdź token NextAuth — jeśli plan != 'agency' → redirect /dashboard
```

### Krok 5 — Deploy

**Sprawdź deployment_locks PRZED deploy!**

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100
cd /home/ubuntu/video-seo-engine
git pull origin main

# Tylko te kontenery — NIE dotykaj vse-api jeśli dev-06 deployuje
docker compose up -d --no-deps --force-recreate vse-web
# Jeśli dodałeś nowy router admin: też rebuild vse-api (osobny krok)
```

### Test weryfikacyjny:
1. Zaloguj jako `tobroz@gmail.com` (plan agency)
2. Wejdź na `vse.impresjapr.pl/admin`
3. Powinna być widoczna lista użytkowników
4. Zmień plan testowego userą → zapisz → odśwież → plan zmieniony

---

## Deployment Lock Protocol

Przed każdą komendą `docker compose`:
1. Pobierz `sonic-void/project_status.json` (GitHub MCP)
2. Sprawdź `deployment_locks.video-seo-engine`
3. Jeśli lock = `vse-dev-06` dla kontenera `vse-api` — poczekaj lub deployuj tylko `vse-web`
4. Po udanym deploy: zaktualizuj lock na `null` dla swojego scope

---

*Supervisor 01 | sonic-void | 2026-06-16 15:56*
