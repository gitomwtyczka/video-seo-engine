# Raport: vse-dev-21 — D6b BLOCKED by D6a

**Callsign:** vse-dev-21  
**Data:** 2026-06-20  
**Dispatch:** VSE-DEV-21-D6b-ARCHITECTURE  
**Status:** 🛑 BLOCKED  

---

## Co zrobiłem

1. Pobrałem i przeczytałem dispatch D6b (architektura kanał/witryna/typy publikacji)
2. Sprawdziłem bloker D6a — warunek: flaga `yt_update_enabled` w `profiles/prawy.yaml`
3. **Flaga NIE ISTNIEJE** — D6a nie został wykonany
4. Potwierdziłem sprawdzając dispatch D6a (`DISPATCH-VSE-DEV-20-20260619-YT-ADMIN-D6.md`) — status: `dispatched`, przypisany do `vse-dev-20`
5. Heartbeat zaktualizowany ze statusem `blocked`

---

## Stan blokera D6a

| Element | Status |
|---|---|
| Flaga `yt_update_enabled` w `profiles/prawy.yaml` | ❌ Brak |
| Flaga `yt_update_enabled` w `profiles/kurier365.yaml` | ❌ Brak |
| Guard w `core/injector.py` | ❌ Nie zaimplementowany |
| Fix deprecated call w `core/yt_admin.py` | ❓ Nie zweryfikowany |
| Dispatch D6a assigned to | `vse-dev-20` |
| Dispatch D6a status | `dispatched` (nie `done`) |
| Ostatni heartbeat przed moim | `vse-dev-19` — D5 complete |

---

## Scope D6a (prerequisite)

D6a to prosty hotfix (~30 min):
1. **Profil prawy.yaml** — dodać `yt_update_enabled: true`
2. **Profil kurier365.yaml** — dodać `yt_update_enabled: false`
3. **Profil template.yaml** — dodać `yt_update_enabled: false`
4. **core/injector.py** — guard: sprawdzać flagę przed wywołaniem yt_admin
5. **core/yt_admin.py** — fix deprecated `update_video_description()` → `update_video_title_and_description()`

---

## Rekomendacja

🚦 **ZAMIAR:** Wykonać D6a sam (jako vse-dev-21) aby odblokować D6b.  
D6a to 3 punktowe fixy, zero zmian architektonicznych, ryzyko minimalne.

**Alternatywa:** Czekać na vse-dev-20 — ale nie wiadomo kiedy wystartuje.

---

## Następne kroki (po odblokowaniu D6a)

D6b kolejność:
1. D6b.1 — `channels/prawy-tv.yaml` (nowy katalog)
2. D6b.2 — refaktor profili (usunięcie danych kanału)
3. D6b.3 — `core/channel.py` (channel loader)
4. D6b.4 — parametryzacja `yt_admin.py`
5. D6b.5 — cytaty z timestamps → opis YT
6. D6b.6 — typ publikacji w generatorze
7. D6b.7 — CLI/API override
8. D6b.8 — `tools/oauth_setup.py`

---

*vse-dev-21 | video-seo-engine | 2026-06-20T18:17+02:00*
