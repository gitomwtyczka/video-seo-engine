# Current Tasks (Stan na 24.10.2026 — T1 Wdrożone + W1 Następne)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1, WP Plugin v3.0 + Limity 5/30/110/250 + Top-Up 99/249/699 + Niezawodność Napisów & Blokada Anty-Konfabulacyjna + UX `/ustawienia` + K4 Job Per Click + K4.1 Gaps + T1 Miniatury i ImageObject)
- [x] **Zadanie T1 — Przywrócenie miniatur WP (Featured Image), opisów SEO z PressAI Vision (D11) i schemy `ImageObject` JSON-LD (PR #8, merge `9613090` / `3c0fad0`, TAG `20261024-195131`):**
  - **PressAI Vision Aliases & Timing (`pipeline.py`):** Obsługa aliasów `PRESSAI_API_URL` i `PRESSAI_EXTERNAL_TOKEN`, przeniesienie wywołania `_describe_image_via_saas` za `generate_schema`, aby przekazać `post_title` i deduplikowane `focus_keyphrases`, zapisywanie `seo["image_data"]` i `seo["thumbnail_url"]`.
  - **HTTP fallback dla miniatur i 5 pól meta (`injector.py`):** `_upload_image_to_wp` pobiera obrazek przez HTTP (`image_url`) gdy brak pliku w `tmp_dir`, zapisuje 5 pól metadanych (`filename`, `alt_text`, `title`, `caption`, `description`). `set_youtube_thumbnail` obsługuje `image_meta` z PressAI i `wp_base_url.rstrip('/')`.
  - **Pełny `ImageObject` JSON-LD (`injector.py`):** `build_schema_jsonld` zawsze dołącza listę obiektów `@type: ImageObject` o wymiarach 1280x720 z nazwami i podpisami (ze źródeł: `uploaded_images`, `image_data`, YouTube thumbnail fallback).
  - **Przekazywanie w routerze inject (`api/routers/inject.py`):** `_inject_via_plugin_endpoint` przekazuje `thumbnail_url`, `image_meta` oraz `image_data` do endpointu `/wp-json/vse/v1/publish` i loguje `thumbnail_id`.
  - **Wtyczka WP VSE v3.0 (`vse-video-seo.php`):** Odbiór `thumbnail_url` oraz `image_meta` w `rest_external_publish`, automatyczny sideloading przez `download_url`, `media_handle_sideload`, przypisanie alt przez `_wp_attachment_image_alt` i ustawienie jako Featured Image przez `set_post_thumbnail`.
  - **Testy jednostkowe & Weryfikacja:** `tests/test_t1_thumbnails_imageobject.py` (4 testy jednostkowe), 37/37 pytest PASS na VPS w kontenerze `vse-api`, HTTP checks PASS (`/docs` 200, `/` 200), PressAI env OK (`http://172.17.0.1:8001`).
- [x] **Zadanie K4.1 — Reużycie job_id w Local Runnerze, publication_type w /historia, job_id w InjectModal (PR #7, merge `7943870`, TAG `20261024-184707`):**
- [x] **Zadanie K4 — Job per click, kolumna publication_type, scoping user_id (R1/R2) (PR #5, merge `89f24dc`, TAG `20261024-173832`):**
- [x] **Quotes — Przywrócenie sekcji Cytaty w `ArticleTab.tsx` (PR #4, merge `c3e07f9`, TAG `20261021-223954`):**
- [x] **Przebudowa UX `/ustawienia` + Język Białoruski (`be`) + Ujednolicenie limitu 50 portali WP w Agency (`3e0cb38`, `59ca091`, `c17a7a6`):**
- [x] **Wdrożenie KROK A+B+C: Limity 5/30/110/250 + Top-Up 99/249/699 PLN + OAuth Channel Match + Instant Runner Wakeup + Blokada Anty-Konfabulacyjna.**

---

## 🟡 W toku
- Brak aktywnych zadań w toku.

---

## 🔵 Następne (Master Roadmap v2.2)
- [ ] **1. W1 — Format wpisu WP (`video` zamiast `standard`) oraz wymogi Watch Page (TASK-01 do TASK-06):**
  - Rozwiązanie problemu formatu `standard` (wtyczka VSE 3.0, update_post).
  - Wymogi Watch Page: zero CLS playera (aspect-ratio 16/9), schema Article/SeekToAction, rozbudowa tekstu watching_page (150–250 słów, cytaty), linkowanie wewnętrzne.
- [ ] **2. K3'** — `POST /v1/generate` → 202 + `job_id`, background worker, polling `GET /v1/jobs/{id}`.
- [ ] **3. K5' + SEC1** — jeden silnik publikacji WP + szyfrowany `publish_secret` HMAC, usunięcie hardcode `prawy.pl`.
- [ ] **4. E2 + Komercjalizacja:** tabele `generations` + `transcript_cache`, synchronizacja dokumentacji, Stripe live, test polowy wtyczki.
