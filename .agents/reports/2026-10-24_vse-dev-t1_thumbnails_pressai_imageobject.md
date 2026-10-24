# Raport z wdrożenia zadania T1: Miniatury WP Featured Image, PressAI Vision (D11) i ImageObject JSON-LD

**Data:** 2026-10-24 21:55  
**Callsign:** `vse-dev-t1`  
**Status zadania:** ✅ ZAKOŃCZONE  
**Repozytorium:** `gitomwtyczka/video-seo-engine` (branch: `main`)  
**Pull Request:** PR #8 (merge `9613090`, commit testów `3c0fad0`)  
**Punkt rollbacku (VPS Snapshot):** `TAG=20261024-195131` (commit bazowy `7943870d7711b92c92911d43ef87012b70d92044`)

---

## 1. Cel zadania (CO i PO CO)
Przywrócenie pełnego flow miniatur WordPress Featured Image oraz opisów SEO z PressAI Vision (D11), a także wygenerowanie kompletnej schemy `@type: ImageObject` w JSON-LD.
Po refactorze asynchronicznym generatora miniatury i opisy z PressAI Vision nie były wpinane do postów WordPress (zarówno w ścieżce REST API Basic Auth, jak i we wtyczce VSE WP Plugin v3.0), a schema `VideoObject` nie zawierała pełnych obiektów `ImageObject`.

---

## 2. Rozwiązane root causes i zrealizowane zmiany (JAK)

### 2.1. Obsługa aliasów env i właściwy timing generowania opisów (`api/services/pipeline.py`)
- **Obsługa aliasów:** `_describe_image_via_saas()` uwzględnia `PRESSAI_API_URL` oraz `PRESSAI_EXTERNAL_TOKEN` (obok legacy `SAAS_API_URL` i `EXTERNAL_API_TOKEN`).
- **Timing:** Przeniesiono pętlę opisów kadrów za `generate_schema()`. Dzięki temu do PressAI Vision przekazywany jest pełny wygenerowany kontekst artykułu: `post_title` oraz deduplikowane `focus_keyphrases`.
- **Propagacja danych:** Zapisano `seo["image_data"]` oraz `seo["thumbnail_url"]`.

### 2.2. HTTP fallback oraz 5 pól metadanych w WP (`core/injector.py`)
- **Problem:** Po wyjściu z bloku `with tempfile.TemporaryDirectory() as tmp_dir:` w generatorze lokalne pliki zrzutów są usuwane. Gdy użytkownik wywoływał `POST /v1/inject`, lokalna ścieżka `img["path"]` nie istniała i injection pomijał upload obrazków.
- **Fix:** `_upload_image_to_wp()` sprawdza obecność `image_url` – w przypadku braku pliku lokalnego pobiera bajty obrazu przez HTTP (`requests.get`).
- **5 pól SEO:** W WordPress Media Library zapisywane jest pełne 5 pól metadanych: `filename`, `alt_text`, `title`, `caption`, `description`.
- **Miniatury:** `set_youtube_thumbnail()` przyjmuje `image_meta` z PressAI i sanityzuje URL portalu przez `wp_base_url.rstrip('/')`.
- **ImageObject JSON-LD:** `build_schema_jsonld()` zawsze generuje listę obiektów `@type: ImageObject` o wymiarach 1280x720 ze źródeł:
  1) `uploaded_images` (z WP Media Library),
  2) `image_data` (z PressAI Vision / LLM),
  3) Fallback miniatury YouTube (`thumbnail_url` / `maxresdefault.jpg`).

### 2.3. Przekazywanie danych w routerze wtyczki (`api/routers/inject.py`)
- W `_inject_via_plugin_endpoint()` wyciągnięto `thumbnail_url`, `image_meta` (z `image_data[0]`) oraz `image_data` i dołączono je do payloadu wysyłanego do `/wp-json/vse/v1/publish`.
- Dodano logowanie zwrotnego `thumbnail_id`.

### 2.4. Wtyczka WordPress VSE v3.0 (`plugins/vse-video-seo/vse-video-seo.php`)
- W metodzie REST endpointu `rest_external_publish` dodano obsługę `thumbnail_url` oraz `image_meta`.
- Zaimplementowano bezpieczny sideloading miniatury do WP Media Library: `download_url()`, `media_handle_sideload()`, sanityzację nazwy pliku, aktualizację tekstu alternatywnego `update_post_meta($attach_id, '_wp_attachment_image_alt', $img_alt)` oraz powiązanie z postem jako Featured Image: `set_post_thumbnail($post_id, $attach_id)`.
- W odpowiedzi JSON zwracany jest `thumbnail_id`.

### 2.5. Testy jednostkowe (`tests/test_t1_thumbnails_imageobject.py`)
- `test_describe_image_via_saas_aliases`: weryfikacja aliasów zmiennych środowiskowych PressAI oraz przekazywania kontekstu.
- `test_upload_image_to_wp_via_http_url`: weryfikacja pobierania obrazka przez HTTP i aktualizacji 5 pól metadanych.
- `test_set_youtube_thumbnail_image_meta`: weryfikacja zapisu metadanych miniatury z PressAI.
- `test_build_schema_jsonld_imageobject`: weryfikacja generowania ImageObject ze wszystkich trzech źródeł fallbacku.

---

## 3. Weryfikacja wdrożenia na serwerze produkcyjnym (VPS)

- **Mandatory Backup:** `/home/ubuntu/scripts/vse_snapshot.sh` utworzył migawkę `TAG=20261024-195131`.
- **Git pull:** Zaktualizowano kod do commita `3c0fad0` na gałęzi `main`.
- **Docker rebuild:** Kontener `vse-api` przebudowany i uruchomiony bez błędów.
- **Pytest:** `docker exec vse-api pytest tests/test_generator.py tests/test_k4_job_per_click.py tests/test_d15_sanitizer.py tests/test_t1_thumbnails_imageobject.py -v`
  - Wynik: **37 passed, 6 warnings in 2.98s** (100% testów zaliczonych).
- **Smoke checks:**
  - `http://localhost:8085/docs`: HTTP 200 OK
  - `http://localhost:3001/`: HTTP 200 OK
- **Weryfikacja środowiska PressAI w kontenerze:**
  - `PRESSAI/SAAS URL`: `http://172.17.0.1:8001`
  - `TOKEN SET`: `True`
