# Raport: D4 External Links — vse-dev-18

**Data:** 2026-06-20  
**Agent:** vse-dev-18  
**Dispatch:** DISPATCH-VSE-DEV-18-20260619-EXTERNAL-LINKS-D4  
**Status:** ✅ DONE

---

## Co zrobiono

Implementacja Opcji A (stały link zewnętrzny per profil) zgodnie z dispatchem.

### 1. Profile YAML — nowe pole `seo_external_link`

| Profil | URL | Anchor |
|---|---|---|
| `profiles/prawy.yaml` | `https://www.youtube.com/@PrawyTV` | Kanał Prawy TV na YouTube |
| `profiles/kurier365.yaml` | `https://www.youtube.com` | Źródło wideo na YouTube |

### 2. `core/injector.py` — zmiany

- **Nowa funkcja:** `_build_external_link_block(profile)` — helper budujący blok WP z linkiem zewnętrznym
  - Czyta `seo_external_link.url` + `.anchor` z profilu
  - Generuje `<p>Więcej informacji: <a href="..." target="_blank" rel="noopener noreferrer">...</a></p>`
  - Graceful skip gdy pole nieobecne (zwraca pusty string)
  - Pełny docstring CO/PO CO/JAK

- **Integracja w `build_post_content()`:** 
  - Wywołanie `_build_external_link_block(profile)` po `body_rest_block`
  - Dodany do listy `parts[]` między `body_rest_block` a `quotes_section`
  - Zaktualizowany docstring i komentarz article order

- **Zaktualizowany module docstring:** Dodany blok D4 z dokumentacją CO/PO CO/JAK

### 3. Kolejność artykułu (po D4)

```
lead → first_p → embed → chapters → rest_body → external_link → Podsumowanie → FAQ → JSON-LD → JS
```

---

## Weryfikacja

| Kryterium | Status |
|---|---|
| `seo_external_link` obecny w YAML i parsowany | ✅ |
| Link w `post_content` w odpowiednim miejscu (po body, przed quotes) | ✅ |
| `target="_blank" rel="noopener noreferrer"` | ✅ |
| Graceful skip gdy pole nieobecne w profilu | ✅ |
| Backward compat (profile=None nie crashuje) | ✅ |

---

## Commity

| Commit | Opis |
|---|---|
| `5e5dda6` | D4: add seo_external_link to prawy.yaml |
| `513a5e1` | D4: add seo_external_link to kurier365.yaml |
| `6cccc21` | D4: external link block in build_post_content() + _build_external_link_block() |

---

## Uwagi

- Opcja B (LLM-generated external links) pozostaje jako follow-up — nie realizowana w tej sesji
- Link zewnętrzny jest **stały per profil** — można go zmienić edytując YAML bez zmian w kodzie
- Istn. artykuły nie zostaną zmienione — link pojawi się dopiero przy następnym inject/re-inject

---

*vse-dev-18 | video-seo-engine | 2026-06-20*
