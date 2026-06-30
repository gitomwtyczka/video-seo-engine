# DISPATCH VSE-DEV-35 — Inline profile creation w Add Portal modal

**Callsign:** vse-dev
**Data:** 2026-06-30
**Zlecający:** Supervisor 01
**Priorytet:** 🟠 PILNY (user request)
**Model rekomendowany:** Claude Opus
**Workspace:** video-seo-engine

---

## Kontekst

Aktualnie "Dodaj nowy portal" wymaga osobnego pliku YAML w `profiles/` na serwerze.
User chce tworzyć profil **w trakcie dodawania portalu** — w jednym flow.

### Typy publikacji — UNIWERSALNE (nie per-portal)

Typy dotyczą WSZYSTKICH portali i nie zawierają odniesień do konkretnego:

| Typ w systemie | Display name | Opis |
|---|---|---|
| `watching_page` | Film | Krótki artykuł z embedem + chaptery |
| `discover` | Discover | Format Google Discover |
| `full_analysis` | Full Analysis | Rozbudowany artykuł SEO |

> ⚠️ Profile YAML zawierają teraz `default_type` per source_channel.
> Nowy system: profil wybiera **domyślny typ** z tych trzech, ale typ NIE jest specyficzny per portal.

---

## Zadanie

### Krok 1: Backend — POST /v1/profiles

Utwórz endpoint do tworzenia profili:

```python
# POST /v1/profiles
# Body:
{
    "portal_id": "biznesciti",
    "display_name": "BiznesCiti.com",
    "site_brand": "BiznesCiti",
    "wp_base_url": "https://biznesciti.com",
    "default_type": "full_analysis",  # watching_page | discover | full_analysis
    "seo_language": "pl",
    "seo_external_link_url": "https://youtube.com",
    "seo_external_link_anchor": "Źródło wideo"
}
# Response: 201 Created + profile object
```

Endpoint powinien:
1. Walidować `default_type` ∈ {`watching_page`, `discover`, `full_analysis`}
2. Generować plik `profiles/{portal_id}.yaml` z template
3. Ustawić `active: true`
4. Source channels na razie puste (dodawane później)

Sprawdź istniejący router w `core/` lub `api/` — dodaj endpoint tam gdzie są inne `/v1/*`.

### Krok 2: Frontend — rozszerzenie AddPortalModal

Aktualnie modal ma:
- Nazwa portalu
- URL WordPress
- Użytkownik WP + App Password
- Profil treści (dropdown: prawy / kurier365 / brak profilu)

**Nowy flow gdy user wybiera `(brak profilu)` LUB `+ Utwórz nowy profil`:**

Pokazać dodatkowe pola:
- **Site brand** (text input, placeholder: np. "BiznesCiti")
- **Domyślny typ publikacji** (dropdown: Film / Discover / Full Analysis)
- **Język SEO** (dropdown: pl / en, default: pl)
- **Link zewnętrzny SEO** (url input, opcjonalnie)
- **Anchor linku** (text, opcjonalnie)

Przy Submit:
1. Jeśli profil wybrany z listy → użyj istniejącego (jak teraz)
2. Jeśli nowy profil → POST /v1/profiles NAJPIERW, potem dodaj portal z nowym profilem

### Krok 3: Refactor profile YAML — publication types

Typy publikacji (`watching_page`, `discover`, `full_analysis`) są **uniwersalne**.
W profilu `default_type` określa domyślny typ — ale nie powinien zawierać logiki specyficznej per portal.

Sprawdź `profiles/prawy.yaml` i `profiles/kurier365.yaml`:
- `source_channels[].default_type` — to jest OK, to jest per-channel, nie per-portal
- `seo.chapter_js_class: "prawy-chapter"` — to IS per-portal i to jest OK (customization)

---

## Pliki do modyfikacji

| Plik | Zmiana |
|---|---|
| `api/` lub `core/` router | Nowy endpoint POST /v1/profiles |
| `profiles/template.yaml` | Wzorzec do generowania nowych profili |
| `web/src/app/dashboard/dashboard-inner.tsx` | Rozszerzenie AddPortalModal |
| `web/src/app/dashboard/use-profiles.ts` | Dodanie createProfile mutation |

---

## Deliverable

- [ ] POST /v1/profiles endpoint działający
- [ ] AddPortalModal z inline profile creation
- [ ] Walidacja 3 typów publikacji
- [ ] Deploy na produkcję
- [ ] Raport dual-write

---

## Zasady

- Nie zmieniaj istniejących profili (prawy.yaml, kurier365.yaml)
- Publication types to STAŁA lista: watching_page, discover, full_analysis
- UI powinien być spójny z istniejącym designem modala
- TypeScript build MUSI przejść bez błędów

---

*[Supervisor 01 | sonic-void 30.06.2026]*
