# Raport — D14 Image Descriptions Fix
**Data:** 2026-06-29
**Agent:** vse-dev-31

## CO
Wyeliminowano hardcoded powiązania z portalem `prawy.pl` w kodzie projektu oraz wdrożono pełną konfigurację metadanych dla obrazów przesyłanych do WordPress Media Library.

## PO CO
- Zdjęcia przesyłane do WP miały puste pola `alt_text`, `caption` i `description`, co obniżało pozycjonowanie w Google i powodowało utratę punktacji SEO w RankMath.
- Nazwa pliku miniatury (`prawy-tv-{yt_id}.jpg`) oraz fallback URL w pipeline były na sztywno powiązane z domeną `prawy.pl`, co powodowało błędy w integracji i deduplikacji na innych witrynach (np. kurier365.pl).

## JAK
1. **W `core/injector.py`:**
   - Wzbogacono aktualizację metadanych featured image (`_set_media_alt`) o przesyłanie pól `caption` i `description`.
   - Zastąpiono sztywną nazwę pliku thumbnaila dynamicznie generowaną na podstawie `wp_base_url` (np. `kurier365-pl-{yt_id}.jpg`).
   - Zmieniono domyślne klasy i nazwy funkcji JS z `prawySeek`/`prawy-chapter` na `vseSeek`/`vse-chapter`.
2. **W `api/services/pipeline.py`:**
   - Usunięto fallback URL `https://prawy.pl/` z `_resolve_site_url_from_env`. Gdy w env brak `WP_BASE_URL`, pipeline nie odpytuje SAAS o dane.
3. **Deploy:**
   - Kod został wdrożony na serwer produkcyjny VPS (147.224.162.100), kontenery zostały zrekonstruowane i poprawnie uruchomione.

**Commit SHA:**
- f807c4f85a78e4cd00266739f1b79aacdeb2e950
- ab2c9454e8d26353d2ae1e237e0c1dadc1d2e272
