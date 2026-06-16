## ⚡ KROK 0

**Callsign:** `[vse-dev-12 | video-seo-engine]` | Model: Claude Sonnet

> ⚠️ Poprzednia sesja padła po heartbeat. Zacznij od nowa.

---

# TASK: vse-dev-12 — Portal Management MVP + Kurier365 + Format wpisu

**Data:** 2026-06-16 | **Dispatch:** Supervisor 03

---

## 📚 KROK 0b — Kontekst projektu (OBOWIĄZKOWE)

1. `docs/ARCHITECTURE.md` przez GitHub MCP
2. `ROADMAP.md` przez GitHub MCP

---

## Deliverables:

1. Tabela `wp_portals` w DB + API CRUD
2. Kurier365 wpisany do DB bezpośrednio przez psql
3. Modal inject: dropdown z zapisanymi portalami
4. Modal inject: pole "Format wpisu" (domyślnie **Film**)
5. Jeden rebuild + weryfikacja

---

## ETAP 1 — Model bazy: tabela `wp_portals`

Wzoruj się na istniejących modelach w `api/models/` (GitHub MCP).

```sql
CREATE TABLE wp_portals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    wp_username VARCHAR(255) NOT NULL,
    wp_app_password TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## ETAP 2 — API: CRUD endpoints

Nowy plik `api/routers/portals.py`:
```
GET    /v1/portals        — lista portalów zalogowanego usera
POST   /v1/portals        — dodaj portal
DELETE /v1/portals/{id}   — usuń portal
```
Zarejestruj w `api/main.py`.

---

## ETAP 3 — Wstaw Kurier365 do DB (przez psql, NIE do repo)

**Wzór działania — użyj pliku dla złożonego SQL:**
```
1. write_to_file "C:/tmp/insert_kurier.sh" z treścią skryptu bash
2. run_command: scp -i ~/.ssh/oracle-crimson.key C:/tmp/insert_kurier.sh ubuntu@147.224.162.100:/tmp/
3. run_command: ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "bash /tmp/insert_kurier.sh"
```

Credentials kurier365 są w tasku — wstaw do DB, NIE do repo ani raportów:
- URL: `https://kurier365.pl`
- User: `blastotoprowpku`
- App Password: `ji9z hShW NWXt BCR5 IGQH L0yk`

---

## ETAP 4 — Frontend: modal inject z dropdownem portalów + format wpisu

**Plik:** `web/src/app/dashboard/page.tsx` (lub `InjectModal` jeśli wydzielony)

### Dropdown portalów:
```
[Dropdown: Kurier365 ▼ | + Dodaj nowy portal]
└─ wybór z listy → auto-fill URL + credentials
└─ "Dodaj nowy" → puste pola do wpisania + przycisk [Zapisz portal]
[Usuń portal] (tylko dla zapisanych)
```
Fetch z `GET /v1/portals` przy otwarciu modala.

### Format wpisu (NOWE):
```
Format wpisu: [Film ▼]  (opcje: Film | Standard | Cytat | Obrazek | Odnośnik)
Domyślny: Film
```
Wartość trafia do `POST /v1/inject` jako pole `post_format` (np. `"video"`).
Sprawdź `api/routers/inject.py` czy to pole jest obsługiwane — jeśli nie, dodaj.

---

## ETAP 5 — Deploy + weryfikacja

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web"
```

Weryfikacja:
1. `GET /v1/portals` → zwraca Kurier365
2. Modal inject → dropdown z "Kurier365"
3. Modal inject → pole Format wpisu z domyślnym "Film"
4. Dodanie nowego portalu przez UI działa
5. Usunięcie portalu działa

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **Credentials: tylko psql na VPS, NIE do repo**
- **FILE BRIDGE/Wetty: ZAKAZ**
- **Złożone SSH/SQL → write_to_file + scp + ssh**

---

## Raport (dual-write):

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-12_portals-kurier365.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-12_portals-kurier365.md`

⚠️ Credentials w raporcie: tylko "kurier365 dodany" — bez wartości.

```
[vse-dev-12 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-12 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

*Supervisor 03 | sonic-void | 2026-06-17 00:25 | v2 — dodany format wpisu domyślnie Film*
