# SUPPLEMENT 2 — PEŁNA EKSTRAKCJA KODU
## generate_seo_v4 + inject_rest_v5 z VPS oracle-crimson

**Od:** sup-analyst-01 (pogłębiony audyt — kod z VPS /home/ubuntu/video-seo-engine/)  
**Do:** vse-strateg-02  
**Data:** 2026-06-15 21:05 CEST  

> Skrypty NIE były w GitHub shadow-perihelion — są na VPS oracle-crimson.  
> Ten supplement zawiera wyekstrahowany kod, structurę danych i prompt Gemini.

---

## WERYFIKACJA: Co jest na VPS

```
/home/ubuntu/video-seo-engine/
  inject_rest_v5.py      # 15KB — działający injector v5.3
  test_full_seo_v4.py    # działający generator v4 (anchor timestamps)
  batch_seo_generate.py  # batch runner
  batch_inject.py        # batch injector
  core/injector.py       # → już w repo VSE GitHub
```

---

## GENERATOR — `core/generator.py` (PORT Z test_full_seo_v4.py)

### Kluczowe funkcje do przeportowania 1:1:

#### 1. `format_duration_iso(seconds) -> str`
```python
def format_duration_iso(seconds: float) -> str:
    """Convert seconds to ISO 8601 duration (PT1H23M45S)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = "PT"
    if h:
        parts += f"{h}H"
    parts += f"{m}M{s}S"
    return parts
```

#### 2. `parse_vtt_full(vtt_path) -> (timestamped_text, segments, duration)`
Parsuje VTT i zwraca:
- `timestamped_text` — string z markerami `[MM:SS] tekst`
- `segments` — lista `[(start_sec_float, text_str), ...]` do fuzzy matching
- `total_duration` — float sekund

#### 3. `find_anchor_in_vtt(anchor_text, segments) -> int`
Fuzzy match anchor z Gemini → timestamp w sekundach.
```python
from difflib import SequenceMatcher

def find_anchor_in_vtt(anchor: str, segments: list) -> int:
    """Match Gemini anchor_text to VTT segment. Returns time in seconds (-1 if not found)."""
    anchor_clean = anchor.lower().strip()
    best_score = 0.0
    best_time = -1
    window = 6  # slide over 6-segment windows
    for i in range(len(segments)):
        combined = " ".join(seg[1] for seg in segments[i:i+window]).lower()
        score = SequenceMatcher(None, anchor_clean, combined[:len(anchor_clean)*2]).ratio()
        if score > best_score:
            best_score = score
            best_time = int(segments[i][0])
    return best_time if best_score > 0.5 else -1
```

#### 4. `generate_seo_v4(title, timestamped_text, total_duration, yt_url, api_key) -> dict`

Kluczowy prompt Gemini (KOPIA PRODUKCYJNA):

```python
def generate_seo_v4(title: str, timestamped_text: str, total_duration: float,
                    yt_url: str, api_key: str) -> dict:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    text_trimmed = timestamped_text[:80000]
    total_min = int(total_duration // 60)
    
    # Scale with video duration
    if total_min <= 15:
        faq_range, ch_range, qt_range = "2-3", "5-7", "2-3"
    elif total_min <= 30:
        faq_range, ch_range, qt_range = "3-5", "6-10", "3-5"
    elif total_min <= 45:
        faq_range, ch_range, qt_range = "4-6", "8-12", "4-6"
    else:
        faq_range, ch_range, qt_range = "5-8", "10-15", "5-7"
    total_sec = int(total_duration % 60)
    
    prompt = f"""Jestes ekspertem SEO i redaktorem portalu prawy.pl.

Na podstawie transkryptu nagrania wideo przygotuj PELNY PAKIET SEO.

## DANE WEJSCIOWE
Tytul: {title}
URL: {yt_url}
Czas nagrania: {total_min}:{total_sec:02d} ({total_min} minut)

Transkrypt z markerami [MM:SS]:
{text_trimmed}

## KLUCZOWE ZASADY DLA ROZDZIALOW

Dla kazdego rozdzialu MUSISZ podac pole "anchor_text" - jest to DOKLADNY CYTAT 8-15 slow
z transkryptu, ktore sa PIERWSZYMI slowami wypowiadanymi na poczatku danego tematu.
Ten cytat musi byc DOKLADNIE TAKI jak w transkrypcie (male/wielkie litery bez znaczenia).
NIE parafrazuj, NIE streszczaj - kopiuj dokladny fragment.

Rozdzialy musza:
- Pokrywac CALY material od poczatku do konca (~{total_min} min)
- Byc rownomiernie rozlozone (co 3-7 minut)
- Miec {ch_range} rozdzialow
- Pierwszy zaczyna sie od samego poczatku rozmowy

## CO WYGENEROWAC

1. **focus_keyphrase** - 2-4 slowa, naturalna fraza Google.
2. **seo_title** - max 60 znakow, z fraza kluczowa.
3. **meta_description** - max 155 znakow, z fraza kluczowa.
4. **lead** - 2-3 zdania, max 300 znakow, z fraza kluczowa.
5. **article_body** - HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
6. **quotes** - {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat. Usun jakania (yyy, eee), powtorzenia. Zachowaj SENS.
   - "speaker": imie i nazwisko
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu
7. **chapters** - {ch_range} rozdzialow:
   - "label": tytul (max 60 zn)
   - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow tego fragmentu z transkryptu
8. **faq** - {faq_range} pytan i odpowiedzi z tresci.
9. **youtube_description** - max 500 zn, z hashtagami.
10. **video_description** - max 200 zn, dla schema.
11. **tags** - 5-8 tagow lowercase.

Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrase":"...","seo_title":"...","meta_description":"...","lead":"...","article_body":"...","quotes":[{{"text":"...","speaker":"...","anchor_text":"..."}}],"chapters":[{{"label":"...","anchor_text":"..."}}],"faq":[{{"question":"...","answer":"..."}}],"youtube_description":"...","video_description":"...","tags":["..."]}}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    text = response.text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text)
```

#### 5. Post-processing anchor matching (KRYTYCZNE — robić zawsze)

```python
# Po Gemini — resolve chapters do timestamp
resolved_chapters = []
for ch in result.get("chapters", []):
    anchor = ch.get("anchor_text", "")
    ts = find_anchor_in_vtt(anchor, segments)
    resolved_chapters.append({
        "time": max(0, ts),
        "label": ch["label"],
        "anchor_text": anchor,
        "matched": ts >= 0
    })

# Sort by time, ensure first is 0
resolved_chapters.sort(key=lambda x: x["time"])
if resolved_chapters:
    resolved_chapters[0]["time"] = 0
result["chapters"] = resolved_chapters

# Resolve quotes do timestamp
for q in result.get("quotes", []):
    anchor = q.get("anchor_text", q.get("text", "")[:40])
    ts = find_anchor_in_vtt(anchor, segments)
    q["time"] = max(0, ts)

# Dodaj metadane
result["total_duration"] = int(total_duration)
result["duration_seconds"] = int(total_duration)
result["duration_iso"] = format_duration_iso(total_duration)
result["youtube_id"] = video_id
result["yt_url"] = f"https://www.youtube.com/watch?v={video_id}"
```

### FORMAT WYJŚCIOWY `core/generator.py` (to co zwraca `process_video()`)

```json
{
  "focus_keyphrase": "string",
  "seo_title": "string (max 60 zn)",
  "meta_description": "string (max 155 zn)",
  "lead": "string (HTML, max 300 zn)",
  "article_body": "string (HTML, 3-5 p, 1-2 h2)",
  "quotes": [{"text": "...", "speaker": "...", "anchor_text": "...", "time": 123}],
  "chapters": [{"time": 0, "label": "...", "anchor_text": "...", "matched": true}],
  "faq": [{"question": "...", "answer": "..."}],
  "youtube_description": "string",
  "video_description": "string (max 200 zn)",
  "tags": ["tag1", "tag2"],
  "total_duration": 3600,
  "duration_seconds": 3600,
  "duration_iso": "PT1H0M0S",
  "youtube_id": "abc123",
  "yt_url": "https://www.youtube.com/watch?v=abc123"
}
```

---

## INJECTOR — co robi inject_rest_v5.py (kontekst dla core/injector.py)

Injector z VPS ma pełną logikę:

1. **`get_youtube_view_count(yt_id)`** — używa `YT_API_KEY` env var, zapytanie do `googleapis.com/youtube/v3/videos?part=statistics`
2. **`set_youtube_thumbnail(wp_id, yt_id, post_title)`** — pobiera maxresdefault/hqdefault/mqdefault, upload do WP media library, dedup check po `prawy-tv-{yt_id}`, ustawia `featured_media`
3. **`build_schema_jsonld(seo, yt_id, upload_date)`** — buduje listę JSON-LD schemas: `[VideoObject, FAQPage, Quotation...]`
4. **`build_post_content(seo, yt_id, upload_date)`** — buduje pełny HTML WordPress z Gutenberg blocks:
   - lead + `<!--more-->`
   - YouTube embed block
   - chapters list z `data-time` dla seekTo JS
   - article_body HTML
   - polished quotes z seekTo
   - FAQ jako `<details>/<summary>` collapsible
   - JSON-LD schemas
   - Player JS (seekTo() na `.prawy-chapter`)
5. **`update_post(wp_id, seo, yt_id)`** — `requests.post` do `/wp-json/wp/v2/posts/{wp_id}` z `content` + `excerpt`

Jeśli `core/injector.py` w repo ma inną strukturę — porównaj z tym i uzupełnij co brakuje.

---

## INTERFACE `process_video()` — wymagany przez pipeline.py

```python
# api/core/generator.py
def process_video(
    video_id: str,       # YouTube video ID
    wp_id: int,          # WordPress post ID (0 = nie znany)
    post_title: str,     # Tytuł posta
    yt_url: str,         # https://www.youtube.com/watch?v={video_id}
    vtt_path: str,       # ścieżka do pliku VTT
    api_key: str,        # GEMINI_API_KEY lub ANTHROPIC_API_KEY
    out_dir: str | None, # Jeśli None — nie zapisuj do pliku
    sleep_between: int,  # Sekundy między requestami (0 = brak)
    llm_provider: str,   # 'gemini' lub 'claude'
) -> dict:               # Zwraca dict w formacie wyściowym z wyżej
```

---

## UWAGA O PLUGINIE RANKMATH

Z handoffów: pipeline aktualizuje RankMath meta przez WP postmeta API. W injectorze szukaj:
- `rank_math_focus_keyword` → `focus_keyphrase`
- `rank_math_title` → `seo_title`
- `rank_math_description` → `meta_description`

Porze te pola przez: `PATCH /wp-json/wp/v2/posts/{id}` z `meta: {...}`

---

*sup-analyst-01 | sonic-void | 2026-06-15 21:08 — ekstrakcja kodu kompletna*
