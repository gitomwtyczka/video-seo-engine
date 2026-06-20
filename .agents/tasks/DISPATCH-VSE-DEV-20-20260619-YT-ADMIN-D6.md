---
dispatch_id: "VSE-DEV-20-D6a-HOTFIX"
created: "2026-06-19"
updated: "2026-06-20 — rozbity z D6 na D6a (hotfix) + D6b (architektura)"
supervisor: "Supervisor 01"
assigned_to: "[vse-dev-20]"
repo: "video-seo-engine"
branch: "main"
priority: "HIGH"
status: "dispatched"
---

# DISPATCH D6a — yt_admin Hotfix (flaga enabled + deprecated fix)

## Cel

Natychmiastowy fix: każda publikacja na portalu bez OAuth (kurier365) generuje `EnvironmentError` w logach. To nie jest bug krytyczny, ale zaśmieca logi i maskuje prawdziwe błędy.

**Czas: 1-2h. Dwa punktowe fixy, zero zmian w architekturze.**

---

## Zadanie 1: Flaga `yt_update_enabled`

**Plik:** `core/injector.py` — w miejscu gdzie wywoływany jest `yt_admin`

Aktualnie: `injector.py` zawsze próbuje wywołać yt_admin po publikacji.

Fix:
```python
yt_enabled = (profile or {}).get('yt_update_enabled', False)
if yt_enabled and not dry_run:
    try:
        from core.yt_admin import update_video_title_and_description
        # ... wywołanie
    except EnvironmentError as exc:
        logger.info("  YT update skipped — OAuth not configured: %s", exc)
    except Exception as exc:
        logger.warning("  YT update failed for %s: %s", yt_id, exc)
else:
    logger.debug("  YT update disabled for portal %s", (profile or {}).get('portal_id', '?'))
```

## Zadanie 2: Fix deprecated batch call

**Plik:** `core/yt_admin.py` → `batch_update_from_registry()`

Zmień wywołanie `update_video_description(...)` na `update_video_title_and_description(...)`.

## Zadanie 3: Pola w profilach

**Pliki:** `profiles/prawy.yaml`, `profiles/kurier365.yaml`, `profiles/template.yaml`

```yaml
# prawy.yaml — ma OAuth, włącz YT update
yt_update_enabled: true

# kurier365.yaml — brak OAuth
yt_update_enabled: false

# template.yaml — domyślnie wyłączony
yt_update_enabled: false
```

---

## Weryfikacja

- [ ] `kurier365` pipeline: YT update NIE jest wywoływany, brak EnvironmentError w logach
- [ ] `prawy` pipeline: YT update wywoływany tylko gdy `yt_update_enabled: true`
- [ ] `batch_update_from_registry()` używa `update_video_title_and_description`
- [ ] Serwis działa po deploy (user weryfikuje)

---

## Raportowanie

1. `video-seo-engine/.agents/reports/2026-06-20_vse-dev-20_yt-admin-d6a-hotfix.md`
2. `sonic-void/.agents/reports/inbox/2026-06-20_vse-dev-20_yt-admin-d6a-hotfix.md`

---

*Supervisor 01 | video-seo-engine | 2026-06-20*
