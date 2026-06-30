# 🚀 Raport Diagnozy Błędów: Portal Dropdowns & API Tests

Na podstawie skryptu `scripts/api_smoke_test.py` uruchomionego na produkcji oraz szczegółowej analizy logów i kodu backendu/frontendu, zidentyfikowano źródła błędów zgłoszonych w dyspozycji. 

## 1. Błąd 1: `DatatypeMismatchError` (kurier365, prawy)
**Objaw:** `500 Internal Server Error` na `POST /v1/generate` (DatatypeMismatchError portal_id INTEGER vs VARCHAR). 
**Miejsce występowania:** `api/services/pipeline.py` (funkcja `_create_transcript_job`) oraz `api/routers/generate.py` (`_save_schema_to_job`).
**Root Cause (RCA):** 
- W pliku `api/models/job.py` kolumna `TranscriptJob.portal_id` jest obecnie zadeklarowana jako typ znakowy: `String(50)`.
- W bazie PostgreSQL na produkcji, tabela `transcript_jobs` ma kolumnę `portal_id` (wcześniej ID z tabeli `wp_portals`) pozostawioną w typie `INTEGER`. 
- Kiedy framework SQLAlchemy próbuje wstawić lub zaktualizować nowy wiersz, driver PostgreSQL (asyncpg) odrzuca zapytanie z powodu niezgodności typów (nawet jeśli przekazana wartość to `NULL`, backend rzutuje ją jako `VARCHAR`, a Postgres wymusza `INTEGER`).
- Skutkuje to zablokowaniem `POST /v1/generate` (przed fetchem z YT).

## 2. Błąd 2: `Input should be a valid string` (biznesciti - nowy profil z D35)
**Objaw:** `422 Unprocessable Entity` przy kliknięciu "Generuj" lub "Opublikuj" dla nowo utworzonego w UI profilu (D35).
**Miejsce występowania:** Frontend `web/src/app/dashboard/dashboard-inner.tsx` (obsługa `handleGenerate` / `handleInject`).
**Root Cause (RCA):**
- Frontend wciąż stosuje starą konwencję konwersji ID (przed D35 profilami YAML): `portal_id: parseInt(selectedPortalId, 10)`.
- Dla nowych profili YAML, ich ID to tekst (np. `"biznesciti"`). Użycie na nim rzutowania numerycznego `parseInt("biznesciti", 10)` zwraca wartość `NaN`.
- Pod maską funkcja `JSON.stringify()` modyfikuje tak spreparowane ciało żądania, wysyłając `{"portal_id": null}` do serwera (JSON nie wspiera `NaN`).
- **Endpoint Inject (`POST /v1/inject`):** API dla tego endpointa wymaga aktualnie `site_config`, które nie jest załączane, gdy wysyłany jest stary parametr `portal_id`, w efekcie otrzymujemy błąd Pydantica dot. braku odpowiedniego typu / modelu.
- **Endpoint Generate (`POST /v1/generate`):** `portal_id` na serwerze (będąc `Optional[str] = None`) przyjmuje taką null-wartość, ale nie może wtedy zlokalizować w środowisku/bazie konfiguracji YAML by przekazać pełny `site_brand` i URL — prowadząc do niższej jakości danych SEO / błędnego powiązania profili.

## 3. Pozostałe Błędy z `api_smoke_test.py`
- **`GET /v1/portals` zwraca `401 Unauthorized`:** Endpoint zwracający wpisane wcześniej (ręcznie) portale do bazy Postgres posiada włączoną autoryzację tokenem JWT (`Depends(get_current_user)`). Dostęp przez skrypty niewskazujące prawidłowego JWT z nagłówkiem `Authorization: Bearer <TOKEN>` jest odrzucany.
- **`GET /v1/jobs` zwraca `405 Method Not Allowed`:** Router FastAPI dla `jobs.py` podpięty jest jedynie dla obsługi punktów: `POST /`, `GET /pending` oraz `GET /history` – nie posiada on generycznego roota typu `GET /`. Oczekiwany endpoint z tabelą historyczną dla Dashboardu to `GET /v1/jobs/history`.

## 🛠️ Zestawienie Wymaganych Poprawek (Next Action Steps):
1. **[Backend]** Uruchomienie skryptu SQL/Migracji (Alembic) na produkcji w celu wyprostowania schematu `transcript_jobs`. Do wykonania ręcznie lub w nowym dispatchem:
   `ALTER TABLE transcript_jobs ALTER COLUMN portal_id TYPE VARCHAR(50);`
2. **[Frontend]** Aktualizacja pliku `dashboard-inner.tsx`: Usunięcie owijania `selectedPortalId` przez `parseInt(...)` — wysyłanie jako surowy, trimowany typ `.string`.
3. **[Frontend]** Poprawa składni i wysyłki body payloadu dla przycisku "Opublikuj" `handleInject` (uzupełnienie o `site_config` wyciągany lokalnie/albo update payloadu backendu dla wstrzykiwania z profilu YAML zamiast frontu).

*Raport sporządzony dla Supervisora, zgodnie z dyrektywą braku wdrożeń (strict diag).*