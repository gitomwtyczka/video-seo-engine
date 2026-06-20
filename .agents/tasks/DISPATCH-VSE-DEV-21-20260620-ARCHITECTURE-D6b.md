---
dispatch_id: "VSE-DEV-21-D6b-ARCHITECTURE"
created: "2026-06-20"
supervisor: "Supervisor 01"
assigned_to: "[vse-dev-21]"
repo: "video-seo-engine"
branch: "main"
priority: "HIGH"
status: "dispatched"
blocked_by: "D6a musi być wykonane i zdeployowane zanim rozpoczniesz D6b"
---

# DISPATCH D6b — Architektura kanał/witryna/typy publikacji

## Kontekst

Aktualny model VSE: profil = witryna + kanał YT razem (1:1).  
Docelowy model: jeden kanał YT → wiele witryn, każda z własnym typem publikacji.

**Decyzje usera (zatwierdzone 2026-06-20):**
- Format kanałów: osobne pliki `channels/*.yaml` + mapowanie w profilach witryn
- Typ publikacji: domyślny per profil + override per request (CLI/API)
- Cytaty → opis YT: te same timestamps z JSON-LD (hasPart/Clip)
- Relacja: jeden kanał → wiele witryn, każda witryna MOŻE mieć swój kanał

---

## Architektura docelowa

```
channels/prawy-tv.yaml     ← dane kanału YT (OAuth, hashtags, footer, category)
profiles/prawy.yaml        ← witryna + source_channels: ["prawy-tv"] + default_type
profiles/kurier365.yaml    ← witryna + source_channels: ["prawy-tv"] + default_type
```

### Typy publikacji

| Typ | Opis | Content |
|---|---|---|
| `watching_page` | Krótki artykuł z embedem | Lead + embed + chaptery (bez rozbudowanego body) |
| `full_analysis` | Pełny artykuł SEO (jak teraz) | Lead + body + podsumowanie + FAQ |
| `discover` | Format pod Google Discover | Hook, duży obraz, krótkie paragrafy |

---

## Zadania

### D6b.1 — Katalog `channels/` + format pliku

Utwórz `channels/prawy-tv.yaml`:
```yaml
channel_id: "prawy-tv"
display_name: "Prawy TV"
yt_channel_id: "${CHANNEL_ID}"

yt_oauth:
  client_id: "${YT_CLIENT_ID}"
  client_secret: "${YT_CLIENT_SECRET}"
  refresh_token: "${YT_REFRESH_TOKEN}"

yt_api_key: "${YT_API_KEY}"
yt_category_id: "25"
yt_hashtags:
  - "#PrawyTV"
  - "#Polska"
  - "#Wiadomości"
yt_footer: |
  PRAWY.PL — Niezależne media
  https://prawy.pl
  Facebook: https://facebook.com/PrawyPL
  Twitter: https://twitter.com/PrawyPL
```

### D6b.2 — Refaktor profili witryn

Usuwa dane kanału z profili. Dodaje mapowanie:
```yaml
# profiles/prawy.yaml
portal_id: prawy
display_name: "Prawy.pl"
site_brand: "Prawy TV"
active: true

source_channels:
  - channel: "prawy-tv"
    default_type: "full_analysis"  # watching_page | full_analysis | discover

wp_base_url: "${WP_BASE_URL}"
wp_user: "${WP_USER}"
wp_app_password: "${WP_APP_PASSWORD}"

# yt_oauth, yt_api_key, channel_ids — USUNIĘTE (teraz w channels/)
```

```yaml
# profiles/kurier365.yaml
source_channels:
  - channel: "prawy-tv"
    default_type: "watching_page"
```

### D6b.3 — Channel loader

**Plik:** `core/channel.py` (NOWY)

```python
def load_channel(channel_id: str) -> dict:
    """Load channel config from channels/{channel_id}.yaml"""
    path = Path(f"channels/{channel_id}.yaml")
    ...
```

**Plik:** `core/profile.py` — rozszerz o `get_channel_for_profile(profile, channel_id=None)`

### D6b.4 — Parametryzacja yt_admin.py

**Plik:** `core/yt_admin.py`

Wszystkie publiczne funkcje przyjmują `channel: dict` zamiast czytać z env:
- `build_description(seo, link, channel)` — używa `channel['yt_footer']`, `channel['yt_hashtags']`
- `_get_access_token(channel)` — używa `channel['yt_oauth']`
- `update_video_title_and_description(yt_id, seo, link, channel)` — używa `channel['yt_category_id']`
- Thumbnail: `{channel['channel_id']}-{yt_id}.jpg` zamiast `prawy-tv-{yt_id}.jpg`

**Zero hardcodów Prawy.pl w kodzie** (stare stałe można zostawić jako fallback z deprecation warning).

### D6b.5 — Cytaty z timestamps → opis YT

**Plik:** `core/yt_admin.py` → `build_description()`

SEO output zawiera `hasPart` (Clip schema) z timestampami. Dodaj sekcję w opisie YT:

```
⏰ KLUCZOWE MOMENTY
00:03:15 — „Nie pozwolimy na to, żeby...”
00:12:40 — „To jest moment przełomowy...”
```

Dane z `seo['hasPart']` lub `seo['quotes']` (te same timestamps co w JSON-LD na stronie).

### D6b.6 — Typ publikacji w generatorze

**Plik:** `core/generator.py`

Parametr `publication_type: str = "full_analysis"` wpływa na prompt LLM:
- `full_analysis`: pełny artykuł jak teraz
- `watching_page`: krótszy prompt, skupiony na lead + chaptery, bez rozbudowanego body
- `discover`: prompt pod Discover (hook, krótkie akapity, duży obraz)

### D6b.7 — CLI/API override

CLI:
```bash
vse process --video ABC123 --site kurier365 --type full_analysis
```

API endpoint:
```json
{"video_id": "ABC123", "portal_id": "kurier365", "publication_type": "full_analysis"}
```

Jeśli `--type` nie podany → użyj `default_type` z `source_channels` mapowania.

### D6b.8 — tools/oauth_setup.py

Skrypt do jednorazowego OAuth flow:
- Wczytuje `client_id` i `client_secret`
- Uruchamia device flow lub loopback
- Drukuje `refresh_token`
- ~50 linii

---

## Kolejność implementacji

1. D6b.1 — channels/ katalog + prawy-tv.yaml
2. D6b.2 — refaktor profili
3. D6b.3 — channel loader
4. D6b.4 — parametryzacja yt_admin
5. D6b.5 — cytaty → opis YT
6. D6b.6 — typ publikacji w generatorze
7. D6b.7 — CLI/API override
8. D6b.8 — oauth_setup.py

**Po każdym kroku:** deploy + weryfikacja usera.

---

## Weryfikacja

- [ ] `channels/prawy-tv.yaml` istnieje i jest parsowany
- [ ] Profile NIE zawierają danych kanału
- [ ] `yt_admin.py` nie ma hardcodów Prawy.pl
- [ ] Cytaty z timestamps pojawiają się w opisie YT
- [ ] `--type watching_page` produkuje krótszy artykuł
- [ ] `--type discover` produkuje format Discover
- [ ] Brak `--type` → używa default_type z profilu
- [ ] `tools/oauth_setup.py` działa
- [ ] Serwis działa po każdym deploy (user weryfikuje)

---

## Raportowanie

1. `video-seo-engine/.agents/reports/2026-06-20_vse-dev-21_architecture-d6b.md`
2. `sonic-void/.agents/reports/inbox/2026-06-20_vse-dev-21_architecture-d6b.md`

---

*Supervisor 01 | video-seo-engine | 2026-06-20*
