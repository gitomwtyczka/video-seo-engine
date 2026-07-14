# Raport sesji — Supervisor-01 | VTT Diagnosis + Fix
**Data:** 2026-07-14  
**Sesja:** Diagnoza urwanego VTT + naprawa limitu generatora  
**Status:** ✅ ZAMKNIĘTA

---

## CO ZOSTAŁO ZBADANE

Zgłoszenie: plik `Xcfh_fxyiHE (1).vtt` (materiał 83 min) urywa się na 32 minucie.  
Wideo: https://www.youtube.com/watch?v=Xcfh_fxyiHE

---

## DIAGNOZA — 3 WARSTWY

### Warstwa 1 — Plik źródłowy był niekompletny (główna przyczyna)

Plik `Xcfh_fxyiHE (1).vtt` dostarczony przez właściciela projektu to **stary, niekompletny zapis**:

| Parametr | Wartość |
|---|---|
| Rozmiar | 149 604 bajtów |
| Segmentów | 1 615 |
| Zasięg czasowy | 00:00 → 32:08 |
| Zakończenie | Urwane w połowie zdania, brak terminalnej pustej linii |

Pełny VTT pobrany lokalnie przez `yt-dlp` w tej samej sesji:

| Parametr | Wartość |
|---|---|
| Rozmiar | **691 391 bajtów** |
| Segmentów | **4 281** |
| Zasięg czasowy | 00:00 → **1:23:30** |

**Wniosek:** YouTube MA pełne auto-generated napisy dla tego wideo (potwierdzone screenshotem CC na 53:52 oraz pobraniem). Stary plik był po prostu niepełny.

Pełny VTT zapisany lokalnie:  
`C:\Users\tomas2\.gemini\antigravity\brain\b8a7119c-f1a1-4dbc-bce6-f6654fc8901b\scratch\vtt_test\Xcfh_fxyiHE.pl.vtt`

---

### Warstwa 2 — Oracle VPS zablokowany przez YouTube (bloker systemowy)

Test na VPS:
```
youtube_transcript_api._errors.RequestBlocked
YouTube is blocking requests from your IP (Oracle Cloud)
```

`youtube-transcript-api` i `yt-dlp` nie mogą pobierać transkryptów z VPS. Oracle Cloud IP jest na blocklist YouTube.

**Implikacja:** Pipeline VSE na VPS nie może samodzielnie pobrać VTT — użytkownik musi uploadować plik ręcznie.

**Opcje rozwiązania (do decyzji właściciela — NIE zaimplementowano):**
1. Webshare rotating proxies
2. Cookie auth (ryzyko banu konta)
3. Lokalny worker uploading VTT do API (rekomendowane)
4. yt-dlp z proxy

Dispatch z analizą zapisany: `.agents/tasks/2026-07-14_Supervisor-01_vse-dev_vtt-truncation-fix.md`

---

### Warstwa 3 — Limit 80k znaków w generator.py (bug systemowy — NAPRAWIONY)

W `core/generator.py`, funkcja `generate_seo_v4()`:
```python
# PRZED:
text_trimmed = timestamped_text[:80000]   # pokrywało ~36-40 min

# PO:
text_trimmed = timestamped_text[:200000]  # pokrywa ~90 min
```

**Kalkulacja:**
- Rozmowa po parse_vtt_full: ~2 200 znaków/min (po deduplikacji)
- 80 000 znaków ≈ 36–40 minut
- 200 000 znaków ≈ 90 minut
- Gemini 2.5 Flash (1M token ctx) i Claude Sonnet (200k token ctx) obsługują bezpiecznie

---

## ZMIANY WDROŻONE

| Zmiana | Commit | Status |
|---|---|---|
| `core/generator.py` limit 80k → 200k | `9c116257` | ✅ na main |
| Docker rebuild `vse-api` na VPS | — | ✅ deployed |
| `vse-api` restart | — | ✅ running |

---

## DISPATCHYE WYSTAWIONE

| Plik | Dla kogo | Treść |
|---|---|---|
| `2026-07-14_Supervisor-01_vse-dev_vtt-truncation-fix.md` | vse-dev | Diagnoza VTT + opcje proxy dla VPS |
| `2026-07-14_Supervisor-01_strateg_roadmap-ludzki-opis.md` | Strateg / Właściciel | Roadmapa VSE z ludzkimi opisami |

---

## BŁĘDY DIAGNOSTYCZNE SUPERVISORA (do wyciągnięcia wniosków)

1. **Fałszywe `yt-dlp --list-subs`** — komenda zwróciła `has no subtitles` dla wideo które MA napisy auto-generated. yt-dlp w trybie `--list-subs` nie zawsze pokazuje ścieżki auto-generated gdy brak manual subs. Właściwa weryfikacja: `--write-auto-sub` z próbą pobrania.

2. **Wczesne wnioski bez weryfikacji źródła** — Supervisor założył że plik VTT użytkownika jest kompletny i że problem leży w kodzie VSE. Właściwy flow: najpierw zweryfikuj integralność źródłowego pliku (porównaj rozmiar z oczekiwanym przy danej długości materiału).

---

## ROADMAP — CO DALEJ (do decyzji właściciela)

| Priorytet | Temat | Opis |
|---|---|---|
| 🔴 Systemowe | Lokalne pobieranie VTT | VPS zablokowany — potrzebny proxy lub lokalny klient |
| 🟡 Średnioterminowe | Transmisje >90 min | Limit 200k = ~90 min. Dla 8h potrzeba chunkowania LLM |
| 🟡 Średnioterminowe | Refactor dashboard-inner.tsx | 7865 linii → modularyzacja (InjectModal, TabBar) |
| 🟢 Gotowe | Roadmapa ludzka | Dispatch wystawiony — czeka na wykonanie |

---

## HEARTBEAT KOŃCOWY

```json
{
  "callsign": "Supervisor-01",
  "status": "done",
  "current_task": "Sesja zamknięta",
  "timestamp": "2026-07-14T17:27:00Z",
  "last_completed": [
    "Diagnoza VTT urwanego: root cause = stary niekompletny plik (2026-07-14)",
    "Fix generator.py limit 80k → 200k — commit 9c116257 (2026-07-14)",
    "Deploy vse-api na VPS po zmianie limitu (2026-07-14)",
    "Dispatch vtt-truncation-fix dla vse-dev (2026-07-14)",
    "Dispatch roadmapa-ludzki-opis dla stratega (2026-07-14)",
    "Pobranie pełnego VTT lokalnie: 691KB, 4281 seg, 0:00-1:23:30 (2026-07-14)"
  ],
  "pending": [
    "Decyzja: proxy/lokalny worker dla VTT na VPS",
    "Wykonanie dispatchu roadmapy",
    "Chunking dla transmisji >90 min"
  ]
}
```

---

*Supervisor-01 | video-seo-engine | 2026-07-14*
