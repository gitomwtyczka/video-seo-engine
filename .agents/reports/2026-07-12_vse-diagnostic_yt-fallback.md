# Raport: vse-diagnostic — YT description fallback + re-inject

**Wynik diagnostyki:** SAAS API i PressAI działają poprawnie ze strony VSE. Problem leży gdzie indziej (prawdopodobnie w logice wstrzykiwania na YouTube po stronie VSE, np. z powodu `partial=True`).

### 1. Czy SAAS_API_TOKEN był w .env?
**TAK**. Token oraz `SAAS_API_URL` były obecne w `.env` przed jakimikolwiek modyfikacjami. Nie trzeba było ich dodawać.

### 2. Co pokazały logi (fragment)
Logi z `docker logs vse-api --tail 500` pokazują, że zapytanie do PressAI **powiodło się**, a nie zakończyło błędem:

```
2026-07-12 17:37:03,950 [WARNING] core.fetcher: [fetcher] No transcript available for cGnRMArpjIw
(...)
2026-07-12 17:37:26,295 [WARNING] api.services.pipeline: [generate] FIX A: No transcript available for cGnRMArpjIw — continuing without (partial_result=True)
2026-07-12 17:37:26,296 [INFO] core.generator: Processing video: cGnRMArpjIw (WP#0) via claude [type=full_analysis]
2026-07-12 17:37:26,296 [WARNING] core.generator: [FIX A] vtt_path=None for cGnRMArpjIw — calling generate_schema_without_transcript()
(...)
2026-07-12 17:37:58,540 [INFO] api.services.pipeline: [pipeline] PressAI YT description received for cGnRMArpjIw
2026-07-12 17:37:58,540 [INFO] api.services.pipeline: [pipeline] PressAI YT fields merged into schema_data
2026-07-12 17:37:58,541 [INFO] api.services.pipeline: [generate] done: video_id=cGnRMArpjIw [...] has_transcript=False partial=True
```

Logika VSE poprawnie pobrała wynik z PressAI (`PressAI YT description received for cGnRMArpjIw`), jednak YouTube otrzymał wersję fallback (być może przez to, że poleciał na YouTube przed zakończeniem PressAI lub z powodu flagi `partial=True`).

### 3. HTTP status PressAI z VPS
**200 OK**. Wykonano bezpośredni curl z prawidłowym payloadem z VPS i status był 200, co dowodzi, że endpoint jest dostępny i token jest prawidłowy.

### 4. Czy po poprawkach restart się powiódł
Nie było potrzeby wprowadzania poprawek (token był już na miejscu), zatem restart nie został wykonany (środowisko jest w pełni zdrowe pod kątem env).
