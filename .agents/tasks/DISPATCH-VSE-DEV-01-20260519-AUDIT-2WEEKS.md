# DISPATCH — VSE-DEV-01 | Supervisor → Worker
# Temat: Audit filmów 05.05–19.05.2026 + SEO inject + YT desc update

**Od:** Supervisor (sonic-void)
**Do:** vse-dev-01
**Workspace:** `/home/tobroz/projects/video-seo-engine`
**Priorytet:** 🟡 NORMALNY
**Data:** 2026-05-19

---

## Cel

Przejrzyj wszystkie filmy kanału Studio Prawy_PL z ostatnich 2 tygodni (05.05–19.05.2026).
Dla każdego: zweryfikuj czy ma WP post z pełnym SEO i zaktualizowany opis YT.

---

## Kontekst

Poprzednia sesja:
- WP#119837 i WP#119800 — inject done ✅
- `inject_video()` — zintegrowany YT desc ✅
- OAuth `prawypl5@gmail.com` — aktywny, nowe credentials w `.env` ✅
- WP#119846-119849 — posty scheduled dla premier 19-22.05 ✅
- `vse watch` — aktywny w tmux:vse-watch ✅

---

## Kroki wykonania

### 1. Pobierz listę filmów 05.05–19.05 przez OAuth
```bash
cd /home/tobroz/projects/video-seo-engine
python3 -m cli.main fetch --channel --since 2026-05-05
```
Lub bezpośrednio przez API (OAuth już skonfigurowany).

### 2. Dla każdego YT ID — sprawdź stan

| Check | Jak |
|-------|-----|
| Czy jest WP post? | `core/matcher.py` lub search WP REST |
| Czy WP ma pełne SEO? | Sprawdź `seo_results/{yt_id}.json` i content WP |
| Czy YT opis ma rozdziały? | `videos.list?part=snippet` przez OAuth |

**Znane filmy do weryfikacji:**
```
FaOOzvGWVBk | 2026-05-17 | Powstanie w getcie — Żaryn, Płużański
VtIDZ5_CBKw | 2026-05-16 | Tusk to współczesna Targowica — Żaryn, Płużański
yMynHTeuMxs | 2026-05-15 | SEKTA JEHOWY- BEZDUSZNY TWÓR — Trojanowska, Halwa
minINDFIKVg | 2026-05-14 | HISTORIA ŚWIADKÓW JEHOWY — Trojanowska, Halwa
R_QjSUkhyyI | 2026-05-14 | Pilecki: jak narodził się bohater — Żaryn, Płużański
U9HLRRXs5EU | 2026-05-12 | ŚWIADKOWIE JEHOWY- SEKTA — Trojanowska, Halwa
mqOEpSCvxCQ | 2026-05-11 | MIĘDZY SŁOWAMI — Odwaga, Orkisz
JS_3uP-0ecs | 2026-05-10 | WIARA POMAGA PROWADZIĆ BIZNES — Labowska, Halwa
hN0Lp8B0L70 | 2026-05-18 | IDEALNY KANDYDAT NA MĘŻA — Stopińska, Halwa [DONE ✅]
```

### 3. Dla każdego bez pełnego SEO — wykonaj pipeline
```bash
# Fetch VTT (Firefox cookies dla WSL2):
python3 -m cli.main fetch --video {yt_id}

# Generate SEO (Gemini):
python3 -m cli.main generate --video {yt_id} --wp-id {wp_id}

# Inject WP + RankMath + YT desc:
python3 -m cli.main inject --video {yt_id} --wp-id {wp_id}
```

### 4. Raport końcowy

Format tabeli:
```
| YT ID       | WP#    | VTT | SEO | RankMath | YT desc | Status |
|-------------|--------|-----|-----|----------|---------|--------|
| FaOOzvGWVBk | 119XXX |  ✅ |  ✅ |    ✅    |    ✅   | done   |
```

---

## Credentials (aktywne)

```bash
source /home/tobroz/projects/video-seo-engine/.env
# YT OAuth: prawypl5@gmail.com (właściciel kanału) — aktywny
# WP: prawy_admin + Application Password — aktywny
# Gemini: GEMINI_API_KEY — aktywny
# Firefox cookies dla yt-dlp: --cookies-from-browser firefox
```

---

## Deliverable

Raport: `.agents/reports/2026-05-19_vse-dev-01_audit-2weeks.md`
Format: Supervisor Decision Report (tabela + rekomendacje)

---

## Vitals embed (start sesji)

```
📊 VITALS [krok 0]:
  V1 Steps:      🟢 0/40
  V2 Width:      🟢 1 strumień (audit)
  V3 Files:      🟢 0 plików
  V4 Confidence: 🟢 jasny plan
  V5 Recovery:   🟢 ten dispatch wystarczy
```

*Supervisor | sonic-void | 2026-05-19T14:05Z*
