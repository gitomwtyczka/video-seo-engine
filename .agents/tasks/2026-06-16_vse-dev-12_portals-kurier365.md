## ⚡ KROK 0

**Callsign:** `[vse-dev-12 | video-seo-engine]` | Model: Claude Sonnet

---

# TASK: vse-dev-12 — Portal Management MVP + Kurier365 Setup

**Data:** 2026-06-16 | **Dispatch:** Supervisor 03

---

## 📚 KROK 0b — Kontekst projektu (OBOWIĄZKOWE)

Przeczytaj przez GitHub MCP przed startem:
1. `docs/ARCHITECTURE.md`
2. `ROADMAP.md`

---

## Twój deliverable:

System zapisu portalów WP do bazy danych (nie hardcode) + kurier365.pl jako pierwszy portal dla użytkownika `tobroz@gmail.com`.

---

## Kontekst biznesowy

Użytkownik chce móc:
1. Zapisać portal WP (URL + credentials) do konta
2. Przy inject wybrać portal z listy zamiast wpisywać ręcznie
3. Móc usunąć portal (NIE hardcode)

Kurier365 to pierwszy portal testowy który Supervisor przygotowuje. Użytkownik doda prawy.pl i biznescity sam przez UI.

---

## ETAP 1 — Model bazy danych: tabela `wp_portals`

Dodaj migrację lub `CREATE TABLE` do `api/models/` (wzoruj się na istn. modelach):

```sql
CREATE TABLE wp_portals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,          -- np. "Kurier365"
    url VARCHAR(512) NOT NULL,           -- np. "https://kurier365.pl"
    wp_username VARCHAR(255) NOT NULL,   -- wp user
    wp_app_password TEXT NOT NULL,       -- WP Application Password (nie plain password)
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Zapisywanie credentials w DB = akceptowalne dla MVP. Docelowo szyfrowanie (P2).

---

## ETAP 2 — API: CRUD endpoints dla portalów

Nowy plik `api/routers/portals.py`:

```
GET  /v1/portals          — lista portalów zalogowanego usera
POST /v1/portals          — dodaj portal
DELETE /v1/portals/{id}   — usuń portal
PATCH /v1/portals/{id}    — edytuj (opcjonalne)
```

Zarejestruj router w `api/main.py`.

---

## ETAP 3 — Wpisz kurier365 do DB

Po stworzeniu tabeli i deploy API — wstaw kurier365 dla `tobroz@gmail.com`:

```powershell
# Znajdź nazwy kontenerów:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}}'"

# Pobierz user_id tobroz@gmail.com:
# docker exec [DB] psql -U [USER] -d [DB] -c "SELECT id FROM users WHERE email='tobroz@gmail.com';"

# Wstaw portal:
# docker exec [DB] psql -U [USER] -d [DB] -c "
# INSERT INTO wp_portals (user_id, name, url, wp_username, wp_app_password, is_default)
# VALUES ('[USER_ID]', 'Kurier365', 'https://kurier365.pl', 'blastotoprowpku', 'ji9z hShW NWXt BCR5 IGQH L0yk', true);
# "
```

**Credentials kurier365 (używaj tych wartości — nie wpisuj ich do repo/raportów!):**
- URL: `https://kurier365.pl`
- User: `blastotoprowpku`
- App Password: `ji9z hShW NWXt BCR5 IGQH L0yk`

⚠️ NIE commituj credentials do repo. Wstaw bezpośrednio do DB przez psql na VPS.

---

## ETAP 4 — Frontend: WpQuickPane z listą portalów

Zmodyfikuj `web/src/app/dashboard/page.tsx` — sekcja WpQuickPane:

```
Zamiast: pola URL + username + password ręcznie
Powinno być:
  [Dropdown: Kurier365 | Dodaj nowy...]
  └─ Jeśli wybrany z listy: credentials auto-fill
  └─ Jeśli "Dodaj nowy": pola do wpisania
  [Wyślij] [Usuń portal] (dla zapisanych)
```

Fetch portali z `GET /v1/portals` przy mount komponenty.

---

## ETAP 5 — Deploy i weryfikacja

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web"
```

Weryfikacja:
1. `GET /v1/portals` — zwraca kurier365 dla zalogowanego usera
2. Dashboard WpQuickPane — dropdown pokazuje "Kurier365"
3. `DELETE /v1/portals/{id}` — działa (można usunąć)

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **Credentials: tylko do DB przez psql — NIE do repo ani raportów**
- **FILE BRIDGE/Wetty: ZAKAZ**

---

## Raport (dual-write):

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-12_portals-kurier365.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-12_portals-kurier365.md`

⚠️ W raporcie NIE wpisuj credentials — tylko potwierdź "kurier365 dodany do DB" bez wartości.

```
[vse-dev-12 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-12 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

*Supervisor 03 | sonic-void | 2026-06-16 22:38*
