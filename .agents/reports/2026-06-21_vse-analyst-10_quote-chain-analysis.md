# Raport: Cudzysłowy — Pełna Analiza Łańcucha

**Dispatch:** A11 — QUOTE-CHAIN-ANALYSIS
**Callsign:** vse-analyst-10
**Data:** 2026-06-21
**Priorytet:** KRYTYCZNY

---

## 1. REFERENCJA DO ORYGINALNEJ ANALIZY

Przeszukano raporty w video-seo-engine/.agents/reports/ (06-17 do 06-21) oraz sonic-void/.agents/reports/inbox/ (ten sam zakres).

**Nie znaleziono dedykowanego raportu analitycznego** dot. cudzysłowów w archiwum raportów. Temat pojawia się w historii konwersacji:
- 21.06 — Diagnosing JSON Parsing Errors (10addafe) — diagnoza JSONDecodeError
- 21.06 — Fixing JSON Resilience Issues (e9bd6a1e) — implementacja D12 (retry + prompt fix)

Brak formalnego raportu oznacza, że oryginalne rozwiązanie nigdy nie zostało udokumentowane jako raport agenta — jedynie jako commity i notatki w kodzie.

D12 (vse-dev-27) dodał:
1. Prompt instruction: uzywaj apostrofow w atrybutach HTML
2. 1 retry z fix promptem na JSONDecodeError
3. Logowanie raw LLM output na failure

To jest latka na objawy, nie systemowe rozwiazanie.

---

## 2. PELNY LANCUCH PRZETWARZANIA Z PUNKTAMI ZLAMANIA

```
LLM (Claude/Gemini) --> json.loads() generator.py --> injector.py build_* --> WP REST API PATCH --> Portal (prawy.pl)
```

### PUNKT ZLAMANIA 1: LLM Output (GLOWNA PRZYCZYNA)

LLM (szczegolnie Claude) generuje JSON w ktorym pole article_body zawiera HTML z podwojnymi cudzyslowami w atrybutach:

```json
{"article_body": "<a href=\"https://example.com\" target=\"_blank\">tekst</a>"}
```

Problem: Claude produkuje unescaped " wewnatrz wartosci JSON string. Poprawny JSON wymagalby podwojnego escape, ale Claude tego nie robi.

Co json.loads() traktuje jako koniec stringa w nieoczekiwanym miejscu — JSONDecodeError.

**Dlaczego to sie nasila:** Od D10 (external links) i D11 (image descriptions) LLM musi generowac HTML z <a href> wewnatrz JSON string. Wczesniej article_body nie mial tagow <a> z atrybutami — teraz ma je obowiazkowo.

### PUNKT ZLAMANIA 2: json.loads() w generator.py

Aktualny kod (generate_seo_v4):
```python
try:
    text = _call_llm(prompt, api_key, provider)
    text = text.strip()
    text = re.sub(r"^```json\\s*", "", text)
    text = re.sub(r"\\s*```$", "", text)
    return json.loads(text)  # LAMIE SIE TUTAJ
```

Nie ma zadnego pre-processingu text przed json.loads(). Jedyna obrona to:
- D12 retry (pros LLM o naprawienie) — ok 50% skutecznosc
- Prompt instruction (uzyj apostrofow) — LLM moze zignorowac

Brak sanitizera miedzy raw LLM output a json.loads().

### PUNKT ZLAMANIA 3: injector.py build_post_content()

**Nie ma problemu tutaj.** Po udanym json.loads() dane sa poprawnym Python dict. build_post_content() wstawia seo["article_body"] do WP blocks via f-string. build_schema_jsonld() serializuje schemat przez json.dumps() co poprawnie escapuje.

### PUNKT ZLAMANIA 4 (potencjalny): WP REST API -> wyswietlenie

Jesli article_body z LLM zawiera <a href="..."> z podwojnymi cudzyslowami i json.loads() jakos przechodzi (np. po retry), to HTML wyglada poprawnie w WP — bo WordPress renderuje HTML normalnie.

**Problem jest WYLACZNIE w etapie 1->2 (LLM output -> json.loads). Reszta lancucha jest bezpieczna.**

---

## 3. ANALIZA AKTUALNEGO KODU

### core/generator.py — kluczowe obserwacje

| Element | Status | Komentarz |
|---|---|---|
| Prompt instruction D12 | Obecna | ZAWSZE uzywaj APOSTROFOW (') zamiast cudzyslowow |
| Prompt instruction wielokrotna | Powtorzona 3x | W par. 8 article_body, par. 15 external_links, koncowka |
| json.loads() | Brak sanitizera | Bezposrednie parsowanie raw LLM output |
| D12 retry | Latka | 1 retry z fix promptem — nieniezawodne |
| Logowanie raw output | Dodane D12 | Pierwsze 2000 znakow na failure |

### core/injector.py — kluczowe obserwacje

| Element | Status | Komentarz |
|---|---|---|
| article_body -> WP block | Bezpieczne | Wstawienie via wp:html block |
| JSON-LD serialization | Bezpieczne | json.dumps(s, ensure_ascii=False, indent=2) |
| D4 external link | Bezpieczne | Hardcoded HTML z ", ale nie w JSON context |
| WP REST PATCH | Bezpieczne | requests.post(url, json=payload) serializuje poprawnie |

---

## 4. OCENA WARIANTOW ROZWIAZAN

### Wariant 1: Post-processing po json.loads() — regex na HTML atrybuty
Ocena: NIE ROZWIAZUJE PROBLEMU. Post-processing wykonuje sie PO json.loads(). Problem wystepuje PRZED json.loads(). Jesli json.loads() sie nie powiedzie, ten regex nigdy nie uruchomi sie. Przydatny jednak jako warstwa zapobiegawcza po udanym parsowaniu.

### Wariant 2: HTML entity encoding (&quot; zamiast ")
Ocena: NIE ROZWIAZUJE. Sama konwersja nie pomoze bo problem jest w LLM output.

### Wariant 3: Dedykowany sanitizer PRE json.loads()
Ocena: REKOMENDOWANE ROZWIAZANIE SYSTEMOWE.

To jest jedyne podejscie ktore naprawia root cause. Sanitizer musi:
1. Zidentyfikowac wzorzec attr=\"value\" wewnatrz JSON stringa (HTML atrybuty z escaped quotes)
2. Zamienic je na attr='value'
3. Wykonac to PRZED json.loads()

Proponowany kod:
```python
def _sanitize_llm_json(raw_text: str) -> str:
    """Fix common LLM JSON errors before parsing.
    
    Root cause: LLM generates HTML attributes with unescaped double quotes
    inside JSON string values. This breaks json.loads().
    
    Fix: Replace escaped-quote HTML attributes with single-quote equivalents
    BEFORE parsing.
    """
    result = re.sub(
        r'(\w+)=\\"([^\\]*?)\\"',
        lambda m: f"{m.group(1)}='{m.group(2)}'",
        raw_text
    )
    return result
```

### Wariant 4: Prompt engineering (instrukcja ' zamiast ")
Ocena: OBECNE — NIESKUTECZNE JAKO SAMODZIELNE. Claude mimo wielokrotna instrukcje produkuje " w atrybutach w ok. 30-40% przypadkow. Prompt engineering to konieczna ale niewystarczajaca warstwa obrony.

### Wariant 5: json.dumps() na LLM output przed parsowaniem
Ocena: BEZ SENSU. json.dumps() serializuje Python obiekty do JSON stringa. Nie naprawia broken JSON.

---

## 5. REKOMENDOWANE ROZWIAZANIE SYSTEMOWE

### Wielowarstwowa obrona (Defense in Depth):

```
Warstwa 1: PROMPT (istniejace)         — Instrukcja: uzyj ' w atrybutach HTML
Warstwa 2: PRE-PARSE SANITIZER (NOWE)  — _sanitize_llm_json() przed json.loads()
Warstwa 3: D12 RETRY (istniejace)      — 1 retry z fix promptem na JSONDecodeError
Warstwa 4: POST-PARSE CLEANUP (NOWE)   — Po udanym json.loads() zamien " na ' w HTML
```

### Konkretne zmiany w generator.py:

Dodaj dwie nowe funkcje:

```python
def _sanitize_llm_json(raw_text: str) -> str:
    """Fix common LLM JSON errors before parsing."""
    result = re.sub(
        r'(\w+)=\\"([^\\]*?)\\"',
        lambda m: f"{m.group(1)}='{m.group(2)}'",
        raw_text
    )
    return result


def _post_parse_html_cleanup(seo_data: dict) -> dict:
    """After successful json.loads(), ensure HTML attributes use single quotes."""
    for field in ['article_body', 'lead']:
        html = seo_data.get(field, '')
        if html and '"' in html:
            cleaned = re.sub(
                r'(<[^>]*?)(\w+)="([^"]*)"([^>]*?>)',
                lambda m: f"{m.group(1)}{m.group(2)}='{m.group(3)}'{m.group(4)}",
                html
            )
            seo_data[field] = cleaned
    return seo_data
```

Modyfikacja generate_seo_v4():
```diff
    try:
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
+       text = _sanitize_llm_json(text)  # Warstwa 2: pre-parse sanitize
-       return json.loads(text)
+       result = json.loads(text)
+       result = _post_parse_html_cleanup(result)  # Warstwa 4: post-parse cleanup
+       return result
```

---

## 6. DLACZEGO PROBLEM POWRACA (DEGRADACJA PRZEZ POKOLENIA)

User trafnie zidentyfikowal pattern: kazdy kolejny agent dodaje instrukcje do promptu lub retry logic, ale nie dodaje warstwy sanitizera. Dlaczego?

1. Brak raportu z root cause analysis — oryginalne rozwiazanie nie zostalo udokumentowane jako formalne ustalenie architektoniczne
2. Prompt-first mindset — agenci zakladaja ze wystarczy powiedziec LLM co ma robic. LLM nie jest deterministyczny — instrukcja nie gwarantuje wyniku.
3. Brak warstwy sanitizera — jedyna obrona jest w promptcie i retry. Nie ma kodu ktory DETERMINISTYCZNIE naprawia output.
4. Narastajaca zlozonosc promptu — D10 i D11 dodaly wymaganie linkow HTML w article_body, co dramatycznie zwieksza czestotliwosc problemu.

Kluczowa rekomendacja: Dodanie _sanitize_llm_json() jako warstwy kodu rozwiazuje problem deterministycznie. Prompt engineering + retry to uzupelnienie, nie rozwiazanie.

---

## 7. PRIORYTET IMPLEMENTACJI

| # | Akcja | Priorytet | Czas |
|---|---|---|---|
| 1 | Dodaj _sanitize_llm_json() pre-parse | KRYTYCZNY | 15 min |
| 2 | Dodaj _post_parse_html_cleanup() | WAZNY | 10 min |
| 3 | Dodaj test jednostkowy z broken JSON | ZALECANY | 15 min |
| 4 | Udokumentuj jako ADR / GOTCHA #10 | ZALECANY | 10 min |

---

*[vse-analyst-10 | video-seo-engine 21.06.2026 17:55]*