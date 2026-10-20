# Raport zadania H0: Hotfix bezpieczeństwa SEC2 — usunięcie cross-domain fallbacku kluczy API

**Callsign:** vse-dev-h0  
**Data:** 2026-10-20 22:42 CET (20:42 UTC)  
**Status:** ZAKOŃCZONE SUKCESEM ✅  
**Commit:** `2593a92270a226cbe878c5469be912ac3e4f0eee`

---

## 1. WYNIK PRE-CHECKU BAZY DANYCH (Postgres vse)

Przed modyfikacją kodu zweryfikowano wszystkie portale w tabeli `wp_portals` oraz klucze w `api_keys`:

| Portal ID | Nazwa | URL | Tryb auth | App PW? | Powiązany `api_key_id` | Status klucza | Dopasowanie po domenie | Rezultat po usunięciu fallbacku |
|---|---|---|---|---|---|---|---|---|
| `2b047d7d-15a1-4d2f-8463-f89c2275bb73` | Prawy.pl | `https://prawy.pl` | `plugin_token` | Tak | `20de351c-5370-4377-adc3-246016610446` | `is_active = true` (WordPress Plugin v3.0) | `prawy.pl` (zgodna) | ✅ **BEZPIECZNY** (`KEY_VIA_API_KEY_ID` + `KEY_VIA_DOMAIN`) |
| `dc49d944-188a-4e64-8465-f0a5d6a0221a` | kurier365.pl | `https://kurier365.pl` | `app_password` | Tak | `NULL` | N/D | N/D | ✅ Pomija ścieżkę wtyczki (REST App Password) |
| `3bf77e55-26ba-4f0b-b7dc-a79d91d2f4b1` | Biznesciti | `https://biznesciti.com` | `app_password` | Tak | `NULL` | N/D | N/D | ✅ Pomija ścieżkę wtyczki (REST App Password) |

**Wniosek:** Żaden portal nie traci dostępu do publikacji. Prawy.pl posiada zarówno bezpośrednie powiązanie `api_key_id`, jak i pasujący klucz domeny `prawy.pl`.

---

## 2. MODYFIKACJA KODU (GitHub MCP)

- **Plik:** `api/routers/inject.py`
- **Operacja:** Usunięcie niebezpiecznego fallbacku `if api_key_obj is None and all_keys: api_key_obj = all_keys[0]` (linie 81-82).
- **Commit SHA:** `2593a92270a226cbe878c5469be912ac3e4f0eee`
- **Weryfikacja post-action:**
  - Weryfikacja newlines i składni AST (`ast.parse`) powiodła się.
  - Liczba linii przed zmianą: 397, po zmianie: 395. Reszta pliku nienaruszona.

---

## 3. ANALIZA BACKUPU ORAZ INFRASTRUKTURA SNAPSHOT / ROLLBACK

### A. Analiza `/home/ubuntu/scripts/backup_pre_deploy.sh`
- Skrypt uruchamia `/home/ubuntu/scripts/backup_db.sh`.
- Co backupuje:
  1. Dump bazy `crimson_saas` z kontenera `crimson-postgres` (`pg_saas_${DATE}.sql.gz`)
  2. Dump bazy `vse` z kontenera `vse-postgres` (`pg_vse_${DATE}.sql.gz` — z flagami `--if-exists --clean`)
  3. Dump bazy `content_radar` z kontenera `cr-postgres` (`pg_cr_${DATE}.sql.gz`)
  4. Plik SQLite `/home/ubuntu/crimson-void/backend/saas_database.db` (`saas_database_${DATE}.db.gz`)
- Gdzie zapisuje: `/home/ubuntu/backups/db/` (retencja: 7 dni, logi w `/home/ubuntu/backups/backup.log`).
- **Czego NIE backupuje:** Plików aplikacji, kodu i konfiguracji `.env` (backup dotyczy wyłącznie baz danych).

### B & C. Implementacja skryptów snapshot i rollback na VPS
- **`/home/ubuntu/scripts/vse_snapshot.sh`**:
  - Wywołuje `backup_pre_deploy.sh` (awaria = natychmiastowe przerwanie deployu).
  - Tworzy unikalny tag `YYYYMMDD-HHMMSS`.
  - Tworzy tagi Docker: `video-seo-engine-vse-api:rollback-$TAG` oraz `video-seo-engine-vse-web:rollback-$TAG`.
  - Zapisuje commit git `git rev-parse HEAD` do `/home/ubuntu/rollback/$TAG/commit.txt`.
  - Automatycznie rotuje punkty rollbacku (utrzymuje max 10 ostatnich, starsze usuwa z dysku i z rejestru Dockera).
- **`/home/ubuntu/scripts/vse_rollback.sh`**:
  - Obsługuje `vse_rollback.sh --list` (wypisuje tabelę dostępnych punktów z tagiem, datą, commit sha i opisem).
  - Obsługuje `vse_rollback.sh [TAG]` (przywraca obrazy Docker bez przebudowywania i restartuje `vse-api` oraz `vse-web`).
  - Opcjonalna flaga `--code` wykonuje `git reset --hard <commit>` na repozytorium.
  - Wykonuje healthcheck `curl /docs`.

---

## 4. DEPLOY I WERYFIKACJA

1. Wykonano snapshot: punkt `20261020-203832` (commit bazowy `74e52187e05d08bfe2cc24f7b2b8101d41e310cc`).
2. Sprawdzono brak współbieżnych procesów `docker compose`.
3. Wykonano `git pull origin main` — potwierdzono brak obcych zmian w kodzie (jedyny diff w `api/`, `core/`, `web/` to zmiana w `api/routers/inject.py`).
4. Przebudowano i uruchomiono kontener:
   `docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api`
5. Weryfikacja:
   - Logi `vse-api`: brak tracebacków, `INFO: Application startup complete.`, serwer nasłuchuje na 8085.
   - Endpoint dokumentacji: `https://vse.impresjapr.pl/docs` -> **HTTP 200 OK**.
   - Test `vse_rollback.sh --list` zwrócił poprawnie zarejestrowany punkt:
     `20261020-203832 | 2026-10-20T20:38:32Z | 74e52187 | 74e5218 chore(heartbeat): status=handoff with complete v2.2 commit history [vse-dev-01]`

---

## 5. ONE-CLICK ROLLBACK (Komenda PowerShell)

W razie potrzeby natychmiastowego cofnięcia deployu z poziomu lokalnego PowerShell:

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/vse_rollback.sh 20261020-203832 --code"
```
*(Bez flagi `--code` przywracane są wyłącznie obrazy Docker bez dotykania kodu git).*
