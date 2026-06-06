"""
Full SEO v5.3 — ANCHOR timestamps + polished quotes + uploadDate + duration_iso

Key changes:
  1. Gemini identifies chapters by quoting FIRST WORDS of each topic
  2. Python programmatically matches those quotes to VTT → exact timestamps
  3. Chapters use JavaScript seekTo() instead of YouTube links
  4. Output includes duration_seconds and duration_iso for VideoObject schema
"""
import re
import json
import sys
import os
import time
from difflib import SequenceMatcher


def format_duration_iso(seconds):
    """Convert seconds to ISO 8601 duration (PT1H23M45S)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = "PT"
    if h:
        parts += f"{h}H"
    parts += f"{m}M{s}S"
    return parts

SUBS_DIR = r"D:\Biblioteki\prawy.pl\subs"
OUT_DIR = r"D:\Biblioteki\prawy.pl\seo_results_v5"

TEST_VIDEOS = [
    {
        "youtube_id": "01vhWvog9gQ",
        "wp_id": 16318,
        "post_title": "Antoni Macierewicz: Bezczelne ataki Tuska na prawdę (NA ŻYWO)",
        "slug": "tylko-u-nas-antoni-macierewicz-bezczelne-ataki-tuska-na-prawde-na-zywo",
        "yt_url": "https://www.youtube.com/watch?v=01vhWvog9gQ"
    },
    {
        "youtube_id": "FqinFJiFZeg",
        "wp_id": 17074,
        "post_title": "Przemysław Czarnek: Trwa walka ideologii (WIDEO)",
        "slug": "przemyslaw-czarnek-nie-gryzie-sie-w-jezyk-trwa-walka-ideologii",
        "yt_url": "https://www.youtube.com/watch?v=FqinFJiFZeg"
    },
    {
        "youtube_id": "bK2bEhoKu-o",
        "wp_id": 17838,
        "post_title": "Marek Jakubiak: Tusk chce oddać Polskę Niemcom (WIDEO)",
        "slug": "marek-jakubiak-tusk-chce-oddac-polske-niemcom-wideo",
        "yt_url": "https://www.youtube.com/watch?v=bK2bEhoKu-o"
    }
]


# ============================================================
# VTT PARSER — returns both marked text AND searchable segments
# ============================================================
def parse_vtt_full(vtt_path: str):
    """Returns (timestamped_text, segments_list, total_duration)
    segments_list = [(start_sec, text), ...] for anchor matching
    """
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    segments = []
    current_time = 0.0
    max_time = 0.0
    
    for line in content.split('\n'):
        line = line.strip()
        ts_match = re.match(r'^(\d{2}):(\d{2}):(\d{2}[\.\,]\d+)\s*-->', line)
        if ts_match:
            h, m, s = ts_match.groups()
            s = s.replace(',', '.')
            current_time = int(h) * 3600 + int(m) * 60 + float(s)
            if current_time > max_time:
                max_time = current_time
            continue
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        if re.match(r'^\d+$', line):
            continue
        clean = re.sub(r'<[^>]+>', '', line)
        clean = clean.replace('&gt;&gt;', '').strip()
        if clean and len(clean) > 3:
            segments.append((current_time, clean))
    
    # Deduplicate keeping first occurrence
    seen = set()
    unique = []
    for ts, text in segments:
        if text not in seen:
            seen.add(text)
            unique.append((ts, text))
    
    # Build marked text with 30s markers for more precision
    parts = []
    last_marker = -30
    for ts, text in unique:
        if ts - last_marker >= 30:
            minutes = int(ts // 60)
            seconds = int(ts % 60)
            parts.append(f"\n[{minutes:02d}:{seconds:02d}] ")
            last_marker = ts
        parts.append(text + ' ')
    
    return ''.join(parts), unique, max_time


def find_anchor_in_vtt(anchor_text: str, segments: list) -> int:
    """Find the VTT timestamp where anchor_text appears.
    Uses fuzzy matching to handle speech-to-text variations.
    Returns timestamp in seconds, or -1 if not found.
    """
    anchor_clean = anchor_text.lower().strip()
    
    # Build sliding windows of text from segments
    best_score = 0
    best_time = -1
    
    # Try matching against windows of 3-5 consecutive segments
    for window_size in [3, 5, 2, 1]:
        for i in range(len(segments) - window_size + 1):
            window_text = ' '.join(seg[1] for seg in segments[i:i+window_size]).lower()
            
            # Check if anchor is a substring
            if anchor_clean in window_text:
                return int(segments[i][0])
            
            # Fuzzy match
            score = SequenceMatcher(None, anchor_clean, window_text[:len(anchor_clean)*2]).ratio()
            if score > best_score:
                best_score = score
                best_time = int(segments[i][0])
    
    # Accept if fuzzy match is good enough (>0.5)
    if best_score > 0.5:
        return best_time
    
    return -1


# ============================================================
# GEMINI v4 — anchor-based chapters
# ============================================================
def generate_seo_v4(title: str, timestamped_text: str, total_duration: float, yt_url: str, api_key: str) -> dict:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    text_trimmed = timestamped_text[:80000]
    total_min = int(total_duration // 60)
    
    # Scale counts with video duration
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

Dla kazdego rozdzialu MUSISZ podac pole "anchor_text" — jest to DOKLADNY CYTAT 8-15 slow z transkryptu, ktore sa PIERWSZYMI slowami wypowiadanymi na poczatku danego tematu/rozdzialu.
Ten cytat musi byc DOKLADNIE TAKI jak w transkrypcie powyzej (dokladny tekst, male/wielkie litery bez znaczenia).
NIE parafrazuj, NIE streszczaj — kopiuj dokladny fragment.

Rozdzialy musza:
- Pokrywac CALY material od poczatku do konca (~{total_min} min)
- Byc rownomiernie rozlozone (co 3-7 minut)
- Miec {ch_range} rozdzialow (skaluj z dlugoscia materialu)
- Pierwszy zaczyna sie od samego poczatku rozmowy

## CO WYGENEROWAC

1. **focus_keyphrase** — 2-4 slowa, naturalna fraza Google.
2. **seo_title** — max 60 znakow, z fraza kluczowa.
3. **meta_description** — max 155 znakow, z fraza kluczowa.
4. **lead** — 2-3 zdania, max 300 znakow, z fraza kluczowa.
5. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
6. **quotes** — {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat (1-3 zdania). Usun jąkania (yyy, eee), powtórzenia, urwane zdania. Zachowaj SENS i STYL mówcy ale napisz to poprawną, płynną polszczyzną. Cytat musi brzmieć jak profesjonalny wywiad w prasie — nie jak surowy transkrypt.
   - "speaker": imie i nazwisko
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu (surowe, bez edycji!) z tego fragmentu — potrzebne do odnalezienia momentu w nagraniu
7. **chapters** — 6-10 rozdzialow:
   - "label": tytul (max 60 zn)
   - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow tego fragmentu z transkryptu
8. **faq** — {faq_range} pytan i odpowiedzi z tresci.
9. **youtube_description** — max 500 zn, z hashtagami.
10. **video_description** — max 200 zn, dla schema.
11. **tags** — 5-8 tagow lowercase.

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


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("Uzycie: python test_full_seo_v4.py YOUR_GEMINI_API_KEY")
        sys.exit(1)
    
    os.makedirs(OUT_DIR, exist_ok=True)
    
    for i, video in enumerate(TEST_VIDEOS):
        vid = video["youtube_id"]
        vtt_path = os.path.join(SUBS_DIR, f"{vid}.pl.vtt")
        
        if not os.path.exists(vtt_path):
            print(f"[{i+1}/3] BRAK VTT: {vid}")
            continue
        
        print(f"\n{'='*60}")
        print(f"[{i+1}/3] {video['post_title']}")
        print(f"{'='*60}")
        
        # Parse full VTT
        timestamped, segments, duration = parse_vtt_full(vtt_path)
        dur_min = int(duration // 60)
        dur_sec = int(duration % 60)
        print(f"    Transkrypt: {len(timestamped)} zn | {len(segments)} segmentow | {dur_min}:{dur_sec:02d}")
        
        # Generate with Gemini
        print(f"    Gemini...")
        result = generate_seo_v4(video["post_title"], timestamped, duration, video["yt_url"], api_key)
        
        # ANCHOR MATCHING — resolve chapters to exact timestamps
        print(f"\n    MATCHING CHAPTERS:")
        resolved_chapters = []
        for ch in result.get("chapters", []):
            anchor = ch.get("anchor_text", "")
            ts = find_anchor_in_vtt(anchor, segments)
            m = ts // 60 if ts >= 0 else -1
            s = ts % 60 if ts >= 0 else 0
            status = f"{int(m):02d}:{int(s):02d}" if ts >= 0 else "NOT FOUND"
            print(f"      [{status}] {ch['label']}")
            print(f"               anchor: \"{anchor[:60]}...\"")
            resolved_chapters.append({
                "time": max(0, ts),
                "label": ch["label"],
                "anchor_text": anchor,
                "matched": ts >= 0
            })
        
        # Sort by time, ensure first is 0
        resolved_chapters.sort(key=lambda x: x["time"])
        if resolved_chapters and resolved_chapters[0]["time"] != 0:
            resolved_chapters[0]["time"] = 0
        
        result["chapters"] = resolved_chapters
        
        # ANCHOR MATCHING — resolve quotes
        print(f"\n    MATCHING QUOTES:")
        for q in result.get("quotes", []):
            anchor = q.get("anchor_text", q.get("text", "")[:40])
            ts = find_anchor_in_vtt(anchor, segments)
            q["time"] = max(0, ts)
            m = ts // 60 if ts >= 0 else -1
            s = ts % 60 if ts >= 0 else 0
            status = f"{int(m):02d}:{int(s):02d}" if ts >= 0 else "APPROX"
            print(f"      [{status}] {q['speaker']}: \"{q['text'][:50]}...\"")
        
        # Add metadata
        result["wp_id"] = video["wp_id"]
        result["youtube_id"] = vid
        result["original_title"] = video["post_title"]
        result["slug"] = video["slug"]
        result["yt_url"] = video["yt_url"]
        result["total_duration"] = int(duration)
        result["duration_seconds"] = int(duration)
        result["duration_iso"] = format_duration_iso(duration)
        
        # Save
        out_path = os.path.join(OUT_DIR, f"{vid}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Summary
        last_ch = resolved_chapters[-1]["time"] if resolved_chapters else 0
        matched = sum(1 for c in resolved_chapters if c.get("matched"))
        print(f"\n    FRAZA: {result.get('focus_keyphrase')}")
        print(f"    CHAPTERS: {len(resolved_chapters)} szt, {matched}/{len(resolved_chapters)} matched")
        print(f"    Pokrycie: 0 -> {int(last_ch//60):02d}:{int(last_ch%60):02d} / {dur_min}:{dur_sec:02d}")
        print(f"    Zapisano: {out_path}")
        
        if i < len(TEST_VIDEOS) - 1:
            print(f"\n    Czekam 5s...")
            time.sleep(5)
    
    print(f"\n{'='*60}")
    print(f"GOTOWE! Wyniki w: {OUT_DIR}")
