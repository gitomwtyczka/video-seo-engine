# DISPATCH VSE-DEV-36 — API tests + bug analysis (test-first, no premature fix)

**Callsign:** vse-dev
**Data:** 2026-06-30
**Zlecający:** Supervisor 01
**Priorytet:** 🔴 KRYTYCZNY
**Model:** Gemini Pro
**Workspace:** video-seo-engine

> ⚠️ PODEJŚCIE: Test-first. NIE łataj niczego z palca.
> Napisz testy, uruchom, zbierz pełne logi, zrób diagnozę, wyślij raport.
> Fix będzie w osobnym dispatchu po analizie wyników.

---

## Znane objawy (zgłoszone przez Usera)

### Objaw 1 — nowy profil (biznesciti): `Input should be a valid string`
- Przy próbie generowania na nowo utworzonym portalu (D35 inline creation)
- Błąd natychmiastowy, przed fetch YT
- Pydantic validation error — jakieś pole jest None zamiast string

### Objaw 2 — istniejący portal (kurier365): DatatypeMismatchError
- Błąd po fetch YT, przy zapisie do DB
- `column "portal_id" is of type integer but expression is of type character varying`
- `INSERT INTO transcript_jobs (..., portal_id, ...) VALUES (..., $6::VARCHAR, ...)`
- `parameters: (..., None, None, None, None, None)` — wartości None w parametrach!

---

## Zadanie

### Krok 1: Napisz skrypt testowy

Utwórz `scripts/api_smoke_test.py` uruchamiany jako:
```bash
python scripts/api_smoke_test.py https://vse.impresjapr.pl
```

**Testy do pokrycia:**

```
[HEALTH]
✔ GET /health → 200

[PROFILES — filesystem]
✔ GET /v1/profiles → 200 + lista zawiera prawy + kurier365
✔ POST /v1/profiles (valid) → 201
✔ POST /v1/profiles (duplikat) → 409
✔ POST /v1/profiles (zły default_type) → 422
✔ POST /v1/profiles (zły portal_id: spacje/wielkie litery) → 422
✔ Cleanup: usuń testowy YAML po teście (SSH lub DELETE endpoint jeśli istnieje)

[PORTALS — DB-backed]
✔ GET /v1/portals → 200 + sprawdź typy pól (zwłaszcza portal_id: int czy string?)
✔ Zbadaj różnicę między Profile (YAML) a Portal (DB)

[GENERATE — główny flow]
✔ POST /v1/generate z prawy → nie rzuca błędu natychmiastowego
✔ POST /v1/generate z kurier365 → nie rzuca DatatypeMismatchError
✔ POST /v1/generate z biznesciti (nowy profil) → nie rzuca "Input should be a valid string"
✔ POST /v1/generate z nieistniejącym portalem → sensowny błąd (nie 500)

[TRANSCRIPT JOBS — DB schema]
✔ Sprawdź GET endpoint na jobs — co zwraca portal_id: int czy string?
✔ Porównaj z tym co idzie w INSERT
```

**Format wyjścia:**
```
[PASS] GET /health → 200
[FAIL] POST /v1/generate (kurier365) → 500: DatatypeMismatchError
       RAW ERROR: ...
[SKIP] DELETE /v1/profiles (brak endpointu)
```

### Krok 2: Uruchom testy na produkcji

Przez SSH:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && python scripts/api_smoke_test.py https://vse.impresjapr.pl"
```
Albo lokalnie z zewnętrz — jak wolisz, ważny pełny output.

### Krok 3: Diagnoza z kodu (bez modyfikacji)

Dla każdego FAIL:
1. Wskaż dokładne miejsce w kodzie (plik + linia)
2. Wytłumacz root cause
3. Opisz fix który należy zastosować (ale NIE implementuj)
4. Określ ryzyko: czy fix wymaga migracji DB?

### Krok 4: Raport

Raport dual-write z:
- Pełnymi wynikami testów (PASS/FAIL/SKIP)
- Root cause analysis per FAIL
- Proponowane fixy (bez implementacji)
- Czy `portal_id` w transcript_jobs jest INTEGER — jaki typ, jaka wartość powinna tam trafić
- Czy to regression z D34/D35 czy istniało wcześniej

---

## Deliverable

- [ ] `scripts/api_smoke_test.py` napisany i działa
- [ ] Testy uruchomione na produkcji — pełny output
- [ ] Raport dual-write: video-seo-engine + sonic-void inbox
- [ ] ŻADNEGO kodu fixującego — tylko diagnoza

---

*[Supervisor 01 | sonic-void 30.06.2026]*
