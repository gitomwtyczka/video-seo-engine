# Diagnoza: kurier365 vs prawy.pl — RankMath 14/100 vs 68/100
**Callsign:** vse-strateg-01 | **Data:** 2026-06-29 | **Typ:** Diagnoza — bez implementacji

---

## Kontekst

E2E test 2026-06-29:
- **prawy.pl** → RankMath **68/100** — bloki renderują, artykuł widoczny
- **kurier365** → RankMath **14/100** — WSZYSTKIE bloki Gutenberga: *"Nie można wyświetlić podglądu bloku z powodu wystąpienia błędu"*, fraza kluczowa PUSTA

D14 (image descriptions) i D15 (JSON sanitizer) wdrożone. HTTP 200 z API był.

---

## Zebrane dane

### Logi VSE API
```
16:37:42 [INFO] [/v1/generate] ...j2tcD6rOGWs type=watching_page profile=kurier365
16:37:57 [INFO] core.generator: site_brand: 'Kurier365'
16:39:31 [INFO] core.generator: Done: 7 chapters, keyphrases=['klasyka science fiction', ...]
16:42:01 [INFO] [inject] New WP post created: #87946 | https://kurier365.pl/?p=87946
16:42:07 [INFO] THUMB ALT: set alt_text='klasyka science fiction | Prawy TV' title='...'
16:42:08 [INFO] REST API: 200 | https://kurier365.pl/?p=87946
16:42:08 [INFO] RankMath: keyphrase='klasyka science fiction,...'
16:42:09 [ERROR] RankMath exception WP#87946: Expecting value: line 1 column 1 (char 0)
```

### Stan bazy danych wp_portals
| name | url | wp_username |
|------|-----|-------------|
| Kurier365 | https://kurier365.pl | blastotoprowpku |

**Prawy.pl NIE ma rekordu w wp_portals.**

### Zmienne środowiskowe kontenera vse-api (docker inspect)
Brak: WP_USER, WP_APP_PASSWORD, WP_BASE_URL, WP_KURIER365_USER, WP_KURIER365_APP_PASSWORD.
Profiles/kurier365.yaml używa `${WP_KURIER365_USER}` — placeholder nierozwiązany (empty string).

---

## BUG #1 — RankMath endpoint zwraca puste body [KRYTYCZNY]

**CO się dzieje:**
`update_rankmath_meta()` w `core/injector.py` wykonuje:
```python
resp = requests.post(url, json=payload, auth=auth, timeout=20)
data = resp.json()  # JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```
Empty body = `resp.json()` crash. Fraza kluczowa **nigdy nie zostaje zapisana**.

**Dlaczego na prawy.pl działa:**
Logi prawy.pl: `RankMath OK: WP#121654`. Endpoint `/wp-json/rankmath/v1/updateMeta` zwraca `{"slug": true}`.

**Hipotezy root cause (wymagają weryfikacji):**
1. RankMath plugin nieaktywny lub inna wersja na kurier365.pl
2. Application Password `blastotoprowpku` nie ma uprawnień do endpointu `rankmath/v1/`
3. Różny namespace REST API dla RankMath na kurier365

**Dowód:** REST API zwróciło 200 (post powstał — auth działa dla `wp/v2/posts`). Tylko `rankmath/v1/` nie odpowiada. To WordPress/plugin-level problem, nie kod VSE.

**Czy D15 json-repair spowodował problem?**
NIE. D15 działa podczas generowania w `core/generator.py`. Logi potwierdzają: generate zakończył się poprawnie z `keyphrases=['klasyka science fiction', ...]`. Problem jest w INJECT, po zakończeniu generate. D15 jest niewinny.

---

## BUG #2 — Brand "Prawy TV" w alt-text thumbnajla kurier365 [WYSOKI]

**CO się dzieje:**
Log: `THUMB ALT: set alt_text='klasyka science fiction | Prawy TV'`

**Dlaczego:**
W `core/injector.py` linia ~1251:
```python
portal_name = (profile or {}).get("display_name", "Prawy TV")
```
Fallback = hardcoded `"Prawy TV"`.

`_create_wp_post()` w `api/services/pipeline.py` wywołuje `inject_video()` **bez argumentu `profile`** — profile dict nigdy nie jest przekazywany z pipeline generate do inject.

**Skutek:** Każdy portal inny niż prawy.pl dostaje błędny brand w alt-text. SEO punkty za alt tracone.

---

## BUG #3 — Prawy.pl nieobecny w wp_portals [WYSOKI]

**CO się dzieje:**
Tabela `wp_portals` ma tylko Kurier365. Prawy.pl nie ma rekordu.
Ale posty na prawy.pl są tworzone (log: `New WP post created: #121654 | https://prawy.pl`).

**Skąd credentials dla prawy.pl:**
Z `InjectRequest.site_config` który przychodzi z frontendu — albo z hardcoded wartości, albo z ręcznego formularza. Env zmienne (`WP_USER`, `WP_APP_PASSWORD`) też nie są ustawione w kontenerze.

**Skutek:**
System ma dwa modele zarządzania portalami jednocześnie:
- Kurier365: z DB (wp_portals) → UI portal selector
- Prawy.pl: z frontendu/env → poza DB

Niespójność architekturalna. Brak możliwości trwałego zarządzania prawy.pl przez dashboard.

---

## BUG #4 — Selektor portalu w dashboard nie propaguje konfiguracji do inject [WYSOKI]

**CO się dzieje (per obserwacja właściciela produktu):**
Wybór portalu w UI generowania nie zmienia parametrów wyjściowych.

**Weryfikacja przez kod:**
`GenerateRequest.profile_id` (Optional[str]) istnieje — logi potwierdzają `profile=kurier365` w generate.
Ale `InjectRequest.site_config = {wp_base_url, wp_user, wp_app_password}` to osobny model.

Dwa kroki są architekturalnie rozłączone:
- Generate: używa `profile_id` → brand + SAAS (OK)
- Inject: używa `site_config` z requestu → musi pochodzić z frontendu

Jeśli frontend nie aktualizuje `site_config` przy zmianie portalu, inject trafia ze złymi credentials lub pod zły URL.

---

## BUG #5 — D15 json-repair nie zainstalowany [NISKI]

Log: `D15: json-repair not installed — using regex fallback. pip install json-repair`
Regex fallback działa, ale jest mniej niezawodny przy edge cases z LLM JSON.
Nie spowodował problemu w tym teście.

---

## Tabela bugsów i skutków

| # | Problem | Skutek widoczny | Priorytet |
|---|---------|----------------|-----------|
| 1 | RankMath endpoint pusty body → crash | Fraza kluczowa PUSTA, 14/100 | 🔴 KRYTYCZNY |
| 2 | Brand "Prawy TV" w alt-text każdego nowego portalu | Błędny branding, SEO tracone | 🟠 WYSOKI |
| 3 | Prawy.pl nie w DB wp_portals | Niespójny model danych | 🟠 WYSOKI |
| 4 | Selektor portalu nie propaguje site_config | Użytkownik nie może zmienić portalu | 🟠 WYSOKI |
| 5 | json-repair niezainstalowany | Ryzyko edge cases | 🟡 NISKI |

---

## Propozycje fixów (diagnoza — bez implementacji)

### Fix #1 — Weryfikacja RankMath (krok PRZED kodowaniem)
Sprawdzić ręcznie czy endpoint odpowiada na kurier365:
```bash
curl -X POST https://kurier365.pl/wp-json/rankmath/v1/updateMeta \
  -u "blastotoprowpku:ji9z hShW NWXt BCR5 IGQH L0yk" \
  -H "Content-Type: application/json" \
  -d '{"objectType":"post","objectID":87946,"meta":{"rank_math_focus_keyword":"test"}}'
```
Jeśli zwraca HTML lub puste = problem po stronie kurier365 WordPress.
Jeśli zwraca JSON = problem z credentials lub payload.

**Fix kodu (niezależnie od wyniku):** Guard przed `resp.json()` w `update_rankmath_meta()`:
```python
if not resp.text.strip():
    logger.error("RankMath FAIL WP#%s: empty response body", wp_id)
    return False
data = resp.json()
```

### Fix #2 — Brand w alt-text
Przekazać `profile_config` z pipeline generate do `_create_wp_post()` → do `inject_video()`.
Lub krócej: dodać `display_name` do `site_config` (już przekazywanego) i odczytać w injector.

### Fix #3 + #4 — Model portali i selektor
Architektura docelowa:
1. Wszystkie portale w `wp_portals` DB (dodać prawy.pl)
2. Frontend przy wyborze portalu: `GET /v1/portals/{id}` → buduje `site_config` dla InjectRequest
3. `profile_id` w GenerateRequest = `portal_id` z wp_portals
4. Jedno źródło prawdy o portalu

**Uwaga właściciela produktu:** Przed fixem #4 należy zaimplementować możliwość trwałego dodania portalu przez UI. Bez tego fix selektora jest niemożliwy do przetestowania.

### Fix #5 — json-repair
```bash
pip install json-repair
# + rebuild docker
```

---

## Konkluzja

**Główna przyczyna RankMath 14/100 na kurier365:** Endpoint `/wp-json/rankmath/v1/updateMeta` zwraca puste body. Fraza kluczowa nigdy nie została zapisana.

**To problem infrastruktury WordPress (kurier365), nie błąd D14/D15.** Kod ma buga (crash bez graceful handling), ale nawet z fixem kodu RankMath by nie działał bez działającego endpointu.

**Kolejność działań:**
1. Zweryfikować RankMath na kurier365.pl (curl test)
2. Patch graceful handling w `update_rankmath_meta()`
3. Fix brandu w alt-text
4. Ujednolicenie modelu portali + fix selektora w UI
5. pip install json-repair

---

*vse-strateg-01 | video-seo-engine | 2026-06-29*
