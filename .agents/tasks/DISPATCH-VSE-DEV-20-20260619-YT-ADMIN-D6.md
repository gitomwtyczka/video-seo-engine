# DISPATCH-VSE-DEV-20-20260619-YT-ADMIN-D6

**Data:** 2026-06-19  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-20`  
**Projekt:** video-seo-engine | branch: main  
**Priorytet:** HIGH  
**Podstawa:** Raport `vse-analyst-04` — A3: YouTube Description Integration Status

---

## Cel

`core/yt_admin.py` jest kompletnym modułem (21KB) ale posiada:
1. Hardcoded wartości Prawy.pl (footer, hashtagi, categoryId, thumbnail nazwa)
2. OAuth z `os.environ` globalnie — brak per-portal
3. Brak flagi `yt_update_enabled` — każdy portal wywołuje `EnvironmentError` gdy bez OAuth
4. `batch_update_from_registry()` używa deprecated `update_video_description` zamiast `update_video_title_and_description`
5. `tools/oauth_setup.py` nie istnieje

---

## Zadanie D6 — Parametryzacja yt_admin + integracja per-portal

### D6.1 — Parametryzacja funkcji

**Plik:** `core/yt_admin.py`

Wszystkie publiczne funkcje (`update_video_title_and_description`, `update_video_description`, `build_description`, `_build_hashtags`, `update_video_*`) muszą przyjmować opcjonalny parametr `profile: dict = None`.

Logika wewnętrzna:
```python
# Przykład dla footer
footer_text = (profile or {}).get('yt_footer', YT_FOOTER)  # fallback do legacy constant
```

Hardcody które należy sparametryzować:
- `YT_FOOTER` — pole `yt_footer` w profilu (lub `display_name` + `wp_base_url` + `social.*`)
- `_build_hashtags()` — pole `yt_hashtags: []` w profilu
- `categoryId` `"25"` — pole `yt_category_id` w profilu
- thumbnail filename `prawy-tv-{yt_id}.jpg` → `{portal_id}-{yt_id}.jpg`

### D6.2 — OAuth z profilu (z fallback env)

**Plik:** `core/yt_admin.py` → `_get_access_token()`

```python
def _get_access_token(profile: dict = None) -> str:
    yt_oauth = (profile or {}).get('yt_oauth', {})
    client_id = yt_oauth.get('client_id') or os.environ.get('YT_CLIENT_ID')
    client_secret = yt_oauth.get('client_secret') or os.environ.get('YT_CLIENT_SECRET')
    refresh_token = yt_oauth.get('refresh_token') or os.environ.get('YT_REFRESH_TOKEN')
    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError("YouTube OAuth not configured for this profile")
    # ... reszta bez zmian
```

### D6.3 — Flaga `yt_update_enabled` w injector.py

**Plik:** `core/injector.py` → `inject_video()`

Aktualnie: zawsze próbuje wywołać yt_admin → EnvironmentError dla portali bez OAuth.

Fix:
```python
yt_enabled = (profile or {}).get('yt_update_enabled', False)
if yt_enabled and not dry_run and status == 200:
    try:
        from core.yt_admin import update_video_title_and_description
        yt_update_ok = update_video_title_and_description(yt_id, seo, link, profile=profile, dry_run=False)
    except EnvironmentError as exc:
        logger.info("  YT update skipped — OAuth not configured: %s", exc)
    except Exception as exc:
        logger.warning("  YT title+desc update failed for %s: %s", yt_id, exc)
```

### D6.4 — Fix batch deprecated call

**Plik:** `core/yt_admin.py` → `batch_update_from_registry()`

Zmień: `update_video_description(...)` → `update_video_title_and_description(...)`

### D6.5 — Pola profilu w template + prawy.yaml + kurier365.yaml

**Plik:** `profiles/prawy.yaml`, `profiles/kurier365.yaml`, `profiles/template.yaml` (jeśli istnieje)

Dodaj sekcję:
```yaml
yt_update_enabled: true  # prawy.yaml — ma OAuth
# yt_update_enabled: false  # kurier365.yaml — brak OAuth, domyślnie pomiń

yt_category_id: "25"  # News & Politics
yt_hashtags:
  - "#PrawyTV"
  - "#Polska"
  - "#Wiadomości"
yt_footer: |  # opcjonalnie — jeśli brak, generowany z display_name + wp_base_url + social
  ...
```

### D6.6 — tools/oauth_setup.py (narzędzie pomocnicze)

Utwórz `tools/oauth_setup.py` — skrypt do jednorazowego generowania refresh tokenu OAuth 2.0 dla YouTube:
- Wczytuje `YT_CLIENT_ID` i `YT_CLIENT_SECRET` z `.env` lub stdin
- Uruchamia OAuth flow (device flow lub loopback)
- Drukuje `refresh_token` do skopiowania do `.env`
- Minimal implementation, ~50 linii

---

## Kolejność implementacji (risk-first)

1. D6.3 (flaga enabled) — eliminuje EnvironmentError na produkcji ✅
2. D6.4 (fix deprecated) — jednoliniowy fix ✅
3. D6.1 (parametryzacja) — core refactor
4. D6.2 (OAuth z profilu) — po D6.1
5. D6.5 (pola YAML) — po D6.1 i D6.2
6. D6.6 (oauth_setup.py) — ostatnie, standalone

---

## Weryfikacja

- `kurier365` pipeline: YT update NIE jest wywoływany (flaga `False`)
- `prawy` pipeline: YT update wywoływany tylko gdy `yt_update_enabled: True` i OAuth dostępne
- `update_video_title_and_description(profile=prawy_profile)` używa prawy-specyficznych wartości
- Brak literalu `"PRAWY.PL"` ani `"#PrawyTV"` hardcoded w `yt_admin.py` (za wyjątkiem fallback stałych)
- `batch_update_from_registry()` używa `update_video_title_and_description`
- `tools/oauth_setup.py` istnieje i uruchamia się bez błędów

---

## Raportowanie

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/2026-06-19_vse-dev-20_yt-admin-d6.md`
2. Kopia do `sonic-void/.agents/reports/inbox/2026-06-19_vse-dev-20_yt-admin-d6.md`
3. Heartbeat `status: done`

---

*Supervisor 01 | video-seo-engine | 2026-06-19*
