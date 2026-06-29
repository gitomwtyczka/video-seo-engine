## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

Przeczytaj protokół dispatch:
`sonic-void/.agents/protocols/dispatch-system-block.md` (GitHub MCP)

---

# DISPATCH VSE-DIAG-01 — Diagnoza generowania: prawy.pl vs kurier365

**Callsign:** vse-strateg-01  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 WYSOKI — blokuje ocenę RankMath

---

## Kontekst

Dzisiaj wykonano E2E test na dwóch portalach:
- **prawy.pl** → RankMath **68/100** — bloki renderują, artykuł widoczny
- **kurier365** → RankMath **14/100** — WSZYSTKIE bloki Gutenberga wyrzucają błąd: *"Nie można wyświetlić podglądu bloku z powodu wystąpienia błędu"*, fraza kluczowa PUSTA

D14 (image descriptions) i D15 (JSON sanitizer) są wdrożone. HTTP 200 z API był. Ale coś poszło nie tak przy zapisie do kurier365 lub generowaniu dla tego profilu.

---

## Twoje zadanie

### 1. Logi VSE API

SSH na VPS i wyciągnij logi z dzisiejszych sesji:

```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs vse-api --tail 500 2>&1 | grep -E '(generate|inject|kurier|prawy|RankMath|PATCH|REST|ERROR|WARN|focus|keyphrase|content)'"
```

Szukaj:
- Wywołania dla kurier365 — kiedy, co zwróciło
- `RankMath OK` lub `RankMath FAIL` — czy meta w ogóle trafiła
- `REST API: 200` vs błędy PATCH
- Jakiekolwiek `ERROR` lub `WARN` w kontekście kurier

### 2. Sprawdź profil kurier365

```
GitHub MCP:
owner: gitomwtyczka | repo: video-seo-engine | branch: main
path: profiles/kurier365.yaml
```

Zweryfikuj:
- Czy `wp_base_url` jest ustawiony poprawnie (nie ma placeholdera `${ENV_VAR}`)
- Czy `seo.seek_fn_name` i `seo.chapter_js_class` są zdefiniowane
- Czy `yt_update_enabled` jest ustawione

### 3. Pobierz aktualną zawartość posta kurier365

Z WP REST API kurier365 pobierz raw content posta który był testowany (ID z logów lub z UI WP):

```
GET https://kurier365.pl/wp-json/wp/v2/posts/{POST_ID}?_fields=id,content,meta
```

Sprawdź:
- Czy `content.raw` zawiera bloki Gutenberga (`<!-- wp:paragraph -->` itp.)
- Czy `content.raw` jest pusty / ma tylko tytuł
- Czy meta zawiera `rank_math_focus_keyword`

### 4. Porównaj z prawy.pl

Taki sam request dla prawy.pl posta który dał 68/100. Porównaj strukturę content.raw.

---

## Deliverable

Raport z diagnozą:
1. Co poszło nie tak dla kurier365
2. Czy to błąd profilu, błąd API, błąd generowania
3. Propozycja fixa (bez implementacji — tylko diagnoza)

**Dual-write:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-strateg-01_kurier-diagnoza.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-strateg-01_kurier-diagnoza.md`

Heartbeat `status: done` po zakończeniu.

---

*[Supervisor 01 | sonic-void 29.06.2026]*