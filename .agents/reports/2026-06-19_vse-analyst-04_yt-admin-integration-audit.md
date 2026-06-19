# A3: YouTube Description Integration Status — Audit

**Callsign:** `vse-analyst-04`  
**Data:** 2026-06-19  
**Audytowany moduł:** `core/yt_admin.py`  
**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## Status integracji

### A3.1 — Czy yt_admin jest wywoływany w pipeline?

**TAK — częściowo.** `injector.py` wywołuje `yt_admin` w funkcji `inject_video()`, ale z istotnymi ograniczeniami.

#### Gdzie jest wywołanie (injector.py → inject_video):

```python
# core/injector.py — inject_video() — po update_post() + rankmath:
if not dry_run and status == 200:
    try:
        from core.yt_admin import update_video_title_and_description  # type: ignore
        yt_update_ok = update_video_title_and_description(yt_id, seo, link, dry_run=False)
    except EnvironmentError as exc:
        logger.info("  YT update skipped — OAuth not configured: %s", exc)
    except Exception as exc:
        logger.warning("  YT title+desc update failed for %s: %s", yt_id, exc)
```

#### Problemy z obecną integracją:

| Problem | Opis |
|---|---|
| **Brak flagi `yt_update` per portal** | Nie ma sposobu wyłączenia YT update dla portali bez OAuth (np. kurier365) — skończy się zawsze EnvironmentError |
| **Profil NIE jest przekazywany do yt_admin** | OAuth czytany z `os.environ` globalnie — `yt_admin.py` nie przyjmuje `profile` arg |
| **`wp_url` = `link` z update_post** | Przekazywany `link` z WP REST response — OK, ale może być niestabilny (`/?p=ID` zamiast permalinku) |
| **`batch_update_from_registry()` używa deprecated** | Ta funkcja wywołuje `update_video_description()` (tylko opis, bez tytułu) — nie `update_video_title_and_description()` |
| **`oauth_setup.py`** | Brak — nie istnieje w repo. Wspomniany w docstringu yt_admin.py jako sposób generowania tokenu. Brak narzędzia do konfiguracji OAuth |

#### Diagram przepływu (obecny):
```
inject_video()
  → update_post()      ← WP content + slug + title
  → update_rankmath_meta()  ← RankMath SEO meta
  → update_video_title_and_description()  ← YT (BRAK profilu → czyta env globalnie)
```

#### Diagram przepływu (docelowy):
```
inject_video(profile=profile)
  → update_post()
  → update_rankmath_meta()
  → IF profile.get('yt_oauth') AND profile.get('yt_update_enabled', True):
       update_video_title_and_description(yt_id, seo, link, profile=profile)
```

---

### A3.2 — OAuth credentials

#### `.env.api.example`:

```ini
# Optional: YouTube OAuth (for updating YT titles/descriptions)
# YT_CLIENT_ID=...
# YT_CLIENT_SECRET=...
# YT_REFRESH_TOKEN=...
```

**Status:** Zakomentowane — **opcjonalne**, nie wymagane.  
Bez konfiguracji OAuth: `yt_admin._get_access_token()` rzuca `EnvironmentError` → `inject_video()` łapie go i loguje INFO (nie crash).

#### `profiles/prawy.yaml`:

```yaml
yt_oauth:
  client_id: "${YT_CLIENT_ID}"
  client_secret: "${YT_CLIENT_SECRET}"
  refresh_token: "${YT_REFRESH_TOKEN}"
```

**Problem:** Profil MA sekcję `yt_oauth`, ale `yt_admin.py` **nie używa profilu** — czyta tylko `os.environ.get("YT_CLIENT_ID")` globalnie.  
Dla multi-portalu (kurier365 + prawy) niemożliwe zarządzanie oddzielnymi tokenami OAuth.

#### `oauth_setup.py` / `oauth_server.py`:
**NIE ISTNIEJE** w repo. Docstring `yt_admin.py` wspomina `oauth_setup.py / oauth_server.py` jako źródło refresh tokenu — plik nie jest dostarczony. Dev musi go stworzyć lub obsłużyć manualnie.

---

### A3.3 — Hardcody do przepisania na profil

#### KRYTYCZNE hardcody w `yt_admin.py`:

| Linia (approx) | Zmienna/Element | Wartość hardcoded | Pole z profilu |
|---|---|---|---|
| `YT_FOOTER` constant (~L32) | Nazwa portalu | `"PRAWY.PL — Niezależne media"` | `profile['display_name']` + `profile['site_brand']` |
| `YT_FOOTER` constant | Site URL | `"https://prawy.pl"` | `profile['wp_base_url']` lub `profile['site_url']` |
| `YT_FOOTER` constant | Facebook | `"https://www.facebook.com/PortalPrawy/"` | `profile['social']['facebook']` (TODO) |
| `YT_FOOTER` constant | Twitter/X | `"https://twitter.com/prawypl"` | `profile['social']['twitter']` (TODO) |
| `YT_FOOTER` constant | YouTube link | `"https://www.youtube.com/user/portalprawypl"` | `profile['social']['youtube_channel_url']` (TODO) |
| `YT_FOOTER` constant | Fundacja SOS | `"Fundacja S.O.S. Obrony Poczętego Życia"` | `profile['footer_extra']` (opcjonalne, prawy-specific) |
| `YT_FOOTER` constant | Numer konta | `"32 1140 1010 0000 4777 8600 1001"` | `profile['footer_extra']` |
| `YT_FOOTER` constant | KRS | `"KRS: 0000215438"` | `profile['footer_extra']` |
| `_build_hashtags()` (~L140) | Domyślne hashtagi | `["#PrawyTV", "#Prawy", "#Polska"]` | `profile['yt_hashtags']` (TODO) |
| `build_description()` docstring | wp_url | `"prawy.pl"` | bez zmiany (docstring tylko) |
| `update_video_description()` | categoryId fallback | `"25"` (News & Politics) | `profile['yt_category_id']` (opcjonalne) |
| `update_video_title_and_description()` | categoryId fallback | `"25"` (News & Politics) | `profile['yt_category_id']` (opcjonalne) |
| `set_youtube_thumbnail()` (injector) | filename prefix | `"prawy-tv-{yt_id}.jpg"` | `f"{profile['portal_id']}-{yt_id}.jpg"` |
| `set_youtube_thumbnail()` (injector) | dedup search | `"prawy-tv-{yt_id}"` | `f"{profile['portal_id']}-{yt_id}"` |
| `inject_video()` (injector) | `portal_name` fallback | `"Prawy TV"` | `profile['site_brand']` lub `profile['display_name']` |

**Uwaga:** `injector.py` częściowo obsługuje profil (`portal_name = (profile or {}).get("display_name", "Prawy TV")`), ale filename thumbnail i dedup search są wciąż hardcoded `prawy-tv-*`.

#### Pola wymagane w profilu (template):

```yaml
# Do dodania do profiles/template.yaml:
yt_hashtags:           # Domyślne hashtagi, max 3 (reszta z SEO)
  - "#PrawyTV"
  - "#Polska"
yt_category_id: "25"  # YouTube category (25 = News & Politics)
yt_update_enabled: true  # Czy YT update jest włączony dla tego portalu
footer_extra: ""       # Opcjonalny dodatkowy blok (SOS, KRS itp.)
social:
  facebook: ""
  twitter: ""
  youtube_channel_url: ""
```

---

### A3.4 — Registry

**Liczba plików:** 11 plików JSON (+ brak .gitkeep — katalog czysty)

**Struktura pliku registry (dwa formaty obserwowane):**

Format A — zinjektowane (`M1pmpDJUyAA.json`, 384B):
```json
{
  "yt_id": "M1pmpDJUyAA",
  "wp_id": 119846,
  "title": "IDEALNA KANDYDATKA...",
  "pub_date": "2026-05-19",
  "status": "pending",
  "wp_status": "future",
  "created": "2026-05-19T13:56Z",
  "video_id": "M1pmpDJUyAA",
  "wp_post_id": 119959,
  "injected_at": "2026-05-19T16:00:32.280052+00:00",
  "agent": "vse-architect-01"
}
```

Format B — pending SEO (`vXRShHvIbSA.json`, 254B):
```json
{
  "yt_id": "vXRShHvIbSA",
  "wp_id": 119848,
  "title": "TUSK UKRADŁ...",
  "pub_date": "2026-05-21",
  "status": "pending_seo",
  "wp_status": "future",
  "created": "2026-05-19T13:56Z"
}
```

**`yt_desc_updated` obecne:** ❌ NIE — żaden z 11 plików nie zawiera tego pola.  
**`wp_post_id` obecne:** Tylko w Format A (pliki zinjektowane przez `inject_video()`).  
**`injected_at` obecne:** Tylko w Format A.  
**`agent` pole:** Obecne w Format A — śledzi kto zinjektował.

**Problem z `batch_update_from_registry()`:** Funkcja używa `reg.get("wp_post_id")` do budowania URL `/?p={wp_id}` — ale w Format B (`pending_seo`) `wp_post_id` nie istnieje. Efekt: batch skończy się na `{wp_base_url}` bez ID.

---

## Plan dla dev (D6 dispatch)

### Priorytet 1 — Parametryzacja yt_admin.py (KRYTYCZNE)

**Plik:** `core/yt_admin.py`

**Co:** Przepisać `YT_FOOTER` i `_build_hashtags()` tak, żeby akceptowały `profile` dict zamiast hardcode.

```python
# ZAMIAST globalnego YT_FOOTER — funkcja build_footer(profile):
def _build_footer(profile: dict) -> str:
    name = profile.get('display_name', 'Portal')
    url = profile.get('wp_base_url', '')
    social = profile.get('social', {})
    footer_extra = profile.get('footer_extra', '')
    # ...buduj footer dynamicznie
```

**Co przepisać:**
- `build_description()` → dodać `profile: Optional[dict] = None`
- `update_video_description()` → dodać `profile: Optional[dict] = None`
- `update_video_title_and_description()` → dodać `profile: Optional[dict] = None`
- `_build_hashtags(seo)` → `_build_hashtags(seo, profile=None)` — default hashtags z `profile['yt_hashtags']`
- `batch_update_from_registry()` → dodać `profile: Optional[dict] = None`

### Priorytet 2 — OAuth z profilu zamiast z env (WAŻNE)

**Plik:** `core/yt_admin.py`

**Co:** `_get_access_token()` powinien przyjąć `profile` i wyciągać credentials z `profile['yt_oauth']`, z fallbackiem do `os.environ`.

```python
def _get_access_token(profile: Optional[dict] = None) -> str:
    yt_oauth = (profile or {}).get('yt_oauth', {})
    client_id = yt_oauth.get('client_id') or os.environ.get('YT_CLIENT_ID', '')
    client_secret = yt_oauth.get('client_secret') or os.environ.get('YT_CLIENT_SECRET', '')
    refresh_token = yt_oauth.get('refresh_token') or os.environ.get('YT_REFRESH_TOKEN', '')
```

**Uwaga:** Jeśli wartości w YAML to `${YT_CLIENT_ID}` (niezastąpione), trzeba najpierw rozwiązać template (przez `os.environ.get`).

### Priorytet 3 — Flaga `yt_update_enabled` w profilu

**Plik:** `core/injector.py` → `inject_video()`

**Co:** Zamiast ślepego wywołania YT update dla każdego portalu:

```python
# inject_video() — przed YT update:
yt_enabled = (profile or {}).get('yt_update_enabled', False)  # domyślnie FALSE — opt-in
if not dry_run and status == 200 and yt_enabled:
    yt_update_ok = update_video_title_and_description(yt_id, seo, link, profile=profile)
```

**Dlaczego domyślnie `False`:** Prawy.pl to jedyny portal z OAuth teraz. Kurier365 nie ma tokenu — guard przed EnvironmentError.

### Priorytet 4 — Fix `batch_update_from_registry()` (DEPRECATED call)

**Plik:** `core/yt_admin.py` → `batch_update_from_registry()`

**Co:** Zamienić wywołanie `update_video_description()` → `update_video_title_and_description()`.

```python
# BEFORE:
ok = update_video_description(video_id, seo, wp_url, dry_run)
# AFTER:
ok = update_video_title_and_description(video_id, seo, wp_url, dry_run, profile=profile)
```

Także: zmiana URL building — użyć `reg.get('wp_post_id') or reg.get('wp_id')` z fallbackiem na `wp_base_url`.

### Priorytet 5 — `oauth_setup.py` (helper dla konfiguracji)

**Plik:** `tools/oauth_setup.py` (NOWY)

**Co:** Prosty skrypt do uzyskania `YT_REFRESH_TOKEN` przez OAuth 2.0 flow (consent screen).  
**Dlaczego:** Bez tego wdrożenie YT update wymaga manualnego OAuth poza pipeline.

```python
# Minimalny oauth_setup.py:
# 1. Otwiera URL do Google consent screen
# 2. User klika, dostaje code
# 3. Wymienia code na refresh_token
# 4. Drukuje token do .env
```

### Priorytet 6 — Pola profilu do dodania do template.yaml

**Plik:** `profiles/template.yaml` (UPDATE) + `profiles/prawy.yaml` (UPDATE)

Dodać:
```yaml
yt_update_enabled: true     # opt-in per portal
yt_category_id: "25"        # YouTube category
yt_hashtags:                # default hashtags (max 3)
  - "#PrawyTV"
  - "#Polska"
footer_extra: ""            # dodatkowy blok footer (SOS etc)
social:
  facebook: "https://www.facebook.com/PortalPrawy/"
  twitter: "https://twitter.com/prawypl"
  youtube_channel_url: "https://www.youtube.com/user/portalprawypl"
```

---

## Podsumowanie statusu

| Aspekt | Status | Uwagi |
|---|---|---|
| Wywołanie w pipeline | ✅ JEST | `inject_video()` → `update_video_title_and_description()` |
| Przekazanie profilu | ❌ BRAK | `yt_admin` nie akceptuje `profile` arg |
| OAuth konfiguracja | ⚠️ OPCJONALNE | `.env.api.example` — zakomentowane, graceful skip |
| Multi-tenant OAuth | ❌ BRAK | Jeden globalny env — nie per portal |
| Flaga `yt_update_enabled` | ❌ BRAK | Każdy portal próbuje YT update |
| `oauth_setup.py` | ❌ NIE ISTNIEJE | Wspomniany w docstringu, brak w repo |
| Registry `yt_desc_updated` | ❌ NIE MA | Żaden z 11 plików nie ma tego pola |
| `batch_update_from_registry()` | ⚠️ BUG | Wywołuje deprecated `update_video_description()` |
| Hardcody Prawy.pl w yt_admin | 🔴 KRYTYCZNE | YT_FOOTER, hashtagi, category — wszystko hardcoded |

---

*vse-analyst-04 | video-seo-engine | 2026-06-19*
