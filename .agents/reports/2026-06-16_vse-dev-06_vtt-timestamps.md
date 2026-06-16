# Raport: VTT Timestamps Fix (D1)

**Agent:** `vse-dev-06`  
**Data:** 2026-06-16  
**Status:** ✅ DONE  
**Dispatch:** DISPATCH-VSE-DEV-06-20260616-VTT-TIMESTAMPS  

---

## CO zostało zrobione

Naprawiono brakujące timestampy w rozdziałach (chaptery pokazywały `time=0`
zamiast rzeczywistych czasów np. `02:15`, `07:43`).

## Root Cause

Local Runner posyłał transkrypt jako **plain text bez timestampów**:
```
text = " ".join(s.text for s in segments if s.text)  # straciło start/duration!
```

Dodatkowo `sanitize_transcript()` w `jobs.py` niszczył newlines:
```python
clean = ' '.join(clean.split())  # zapłaszczało wieloliniowy format!
```

Efekt: `generator.parse_vtt_full()` dostało plain text, nie mógł sparsować
timestampów → wszystkie chaptery `time=0`.

## Implementacja

### Commit 1 — `827e5b0` runner.py

**Plik:** `local-runner/runner.py`

- Nowa funkcja `_format_segments_as_vtt(segments)` konwertuje listę
  `[{text, start, duration}]` do formatu `[MM:SS] tekst\n[MM:SS] tekst...`
- `fetch_transcript()` wysyła transkrypt z prefixem `__VTT__\n`
- Zachowuje timestamp `start` z każdego segmentu (w sekundach)

### Commit 2 — `81ac779` jobs.py

**Plik:** `api/routers/jobs.py`

- `sanitize_transcript()` wykrywa prefix `__VTT__`
- Jeśli VTT: przetwarza linię po linii (NIE `' '.join(split())`!)
- Zachowuje newlines i markery `[MM:SS]`
- `MAX_TRANSCRIPT_LENGTH` zwiększony z 50k do 100k (VTT ma overhead ~20%)

### Commit 3 — `6612d36` pipeline.py

**Plik:** `api/services/pipeline.py`

- Nowa funkcja `_vtt_runner_to_webvtt(vtt_runner_text)` konwertuje
  format `__VTT__` do prawdziwego WebVTT:
  ```
  Input:  '__VTT__\n[02:15] Tekst\n[07:43] Kolejny'
  Output: 'WEBVTT\n\n1\n00:02:15.000 --> 00:07:43.000\nTekst\n\n...'
  ```
- W `run_generate()`: gdy `transcript_text.startswith("__VTT__")` →
  konwertuje do WebVTT i zapisuje jako `.vtt` (nie `.txt`)
- Fallback dla starych runnerów (plain text): zachowany z warning w logach

## Weryfikacja

### Test jednostkowy (na kontenerze `vse-api`):

```
=== TEST 1: sanitize_transcript VTT format ===
IS_VTT: True
HAS_NEWLINES: True
HAS_02_15: True

=== TEST 2: __VTT__ -> WebVTT conversion ===
IS_WEBVTT: True
HAS_ARROW: True
HAS_TIME: True
RESULT: 'WEBVTT\n\n1\n00:00:00.000 --> 00:02:15.000\nDzien dobry witam\n\n2\n00:02:15.000 --> 00:07:43.000\n...'

=== TEST 3: parse_vtt_full parses converted WebVTT ===
SEGMENTS: 3
SECOND_SEGMENT_TIME: 135.0 (expected: 135 = 2*60+15)
HAS_TIMESTAMPS: True

ALL TESTS PASSED - VTT timestamps fix WORKS!
```

### Status infrastruktury:
- `vse-api`: Up (zrestartowany przez DEV-07 z oboma zestawami zmian)
- Logi: `GET /v1/jobs/pending 200 OK` co ~10s (runner aktywny)
- Git log na VPS: wszystkie 3 commity DEV-06 obecne

## Uwaga dla użytkownika

Local Runner na Windows PC wymaga aktualizacji:
```bat
git pull origin main
nssm restart VSELocalRunner
```

Lub jeśli nie używasz NSSM:
```bat
git pull origin main
python local-runner\runner.py
```

Po aktualizacji runner będzie wysyłał transkrypt z timestamp'ami →
rozdziahy na VSE będą pokazywać rzeczywiste czasy.

## Commity VSE-DEV-06

| SHA | Plik | Zmiana |
|-----|------|--------|
| `827e5b0` | local-runner/runner.py | `_format_segments_as_vtt()` + `__VTT__` format |
| `81ac779` | api/routers/jobs.py | VTT-aware `sanitize_transcript()` |
| `6612d36` | api/services/pipeline.py | `_vtt_runner_to_webvtt()` converter |

---

*vse-dev-06 | video-seo-engine | 2026-06-16 16:35*
