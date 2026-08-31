"""
ShortMachine — AI selection of short video candidates from VTT transcript.

Responsibilities:
  - Parse VTT segments to identify emotional/professional/custom fragments
  - Call LLM to propose ShortCandidates with Hook/Body/Punchline structure
  - Generate 2025/2026 YouTube Shorts best practice metadata:
    * optimized_title: max 45 chars, front-loaded, NO #Shorts, curiosity gap
    * description: 1-3 sentences (150-350 chars), keywords, @channel mention CTA, NO URLs, 3-5 hashtags
    * hashtags: 3-5 thematic tags, NO #Shorts
    * pinned_comment: polarizing question based on punchline + CTA to related long-form video, NO URLs
    * related_video_id: parent long video YouTube ID
  - Return list of ShortCandidate objects with timestamps, scores and metadata

Dependencies: core/generator.py (reuses parse_vtt_full, _call_llm, _sanitize_llm_json)
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .generator import parse_vtt_full, _call_llm, _sanitize_llm_json

logger = logging.getLogger(__name__)


@dataclass
class ShortCandidate:
    """Pojedynczy kandydat na short video.
    
    CO: Reprezentuje fragment wideo proponowany jako short z pełnymi metadanymi.
    PO CO: Przechowuje wszystkie dane potrzebne do wycięcia, wyświetlenia w UI oraz publikacji na YT.
    """
    type: str               # 'emotional' | 'professional' | 'custom'
    start_sec: float        # sekunda początku (Hook)
    end_sec: float          # sekunda końca (Punchline)
    duration_sec: float     # czas trwania w sekundach
    hook_text: str          # pierwsze słowa / hook (widoczne w UI)
    punchline_text: str     # ostatnie słowa / puenta (widoczne w UI)
    body_summary: str       # krótkie streszczenie środka
    score: float            # 0.0–1.0 jakość kandydata
    rationale: str          # uzasadnienie wyboru przez AI
    query_match: str = ""   # jak pasuje do custom query
    suggested_title: str = ""  # chwytliwy tytuł shorta (max 45 zn, backward compat)
    optimized_title: str = ""  # zoptymalizowany tytuł shorta (max 45 zn, front-loaded, bez #Shorts)
    description: str = ""   # opis shorta (150-350 zn, słowa kluczowe, @mention CTA, bez URL)
    tags: list = field(default_factory=list)  # 3-5 hashtagów tematycznych (backward compat)
    hashtags: list = field(default_factory=list)  # 3-5 hashtagów tematycznych (bez #Shorts)
    pinned_comment: str = ""  # emoji + pytanie polaryzujące + CTA do powiązanego filmu
    related_video_id: str = ""  # ID długiego wideo-rodzica
    
    def to_dict(self) -> dict:
        title = self.optimized_title or self.suggested_title
        tag_list = self.hashtags if self.hashtags else self.tags
        return {
            "type": self.type,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "hook_text": self.hook_text,
            "punchline_text": self.punchline_text,
            "body_summary": self.body_summary,
            "score": self.score,
            "rationale": self.rationale,
            "query_match": self.query_match,
            "suggested_title": title,
            "optimized_title": title,
            "tags": tag_list,
            "hashtags": tag_list,
            "description": self.description,
            "pinned_comment": self.pinned_comment,
            "related_video_id": self.related_video_id,
        }


SHORTS_SELECTION_PROMPT = """
Jesteś ekspertem od krótkich formatów wideo (YouTube Shorts, TikTok, Reels) wg standardów 2025/2026.
Na podstawie transkryptu z timestampami zaproponuj kandydatury na shorty wraz z kompletnymi, zoptymalizowanymi metadanymi.

## PARAMETRY
- Emotional: {count_emotional} kandydatów (fragmenty wywołujące emocje: złość, zaskoczenie, wzruszenie)
- Professional: {count_professional} kandydatów (merytoryczne, eksperckie, informacyjne)
- Custom ({custom_query}): {count_custom} kandydatów (pasujące do tej tezy/tematu/słów)
- Kanał: {channel_mention}

## ⚠️ KRYTYCZNA ZASADA DLA KAŻDEGO KANDYDATA (SPÓJNOŚĆ FAKTÓW I SEGMENTU):
Każdy kandydat to DOKŁADNIE JEDEN spójny wycinek wideo w przedziale [start_sec → end_sec].
- `hook_text`, `body_summary`, `punchline_text`, `optimized_title`, `description` i `pinned_comment` MUSZĄ być ściśle zakorzenione w faktach, tezach i wypowiedziach padających w TYM KONKRETNYM segmencie [start_sec → end_sec].
- Styl, ton i retoryka mogą być chwytliwe pod Shorty, ALE KATEGORYCZNIE NIE WOLNO wstawiać faktów, nazwisk ani twierdzeń z innych części filmu.
- Widz oglądający ten 25-58 sekundowy fragment musi usłyszeć to, co zapowiada hook i puenta.

## WYMAGANIA METADANYCH YOUTUBE SHORTS (2025/2026 BEST PRACTICES):

1. **optimized_title** (oraz `suggested_title`):
   - **TWARDE OGRANICZENIE: MAX 45 ZNAKÓW** (optymalnie 28-42 znaki).
   - **KATEGORYCZNY ZAKAZ wstawiania `#Shorts` w tytule** — YouTube klasyfikuje szorty automatycznie.
   - **Front-loading:** kluczowe słowa i esencja w pierwszych 30 znakach (widoczne na mobile feed).
   - Emocja + luka ciekawości (curiosity gap), np. "Dlaczego banki to ukrywają?", "To zniszczy Twój zysk!".

2. **description**:
   - 1–3 zwięzłe zdania (łącznie 150–350 znaków wraz z hashtagami).
   - Zawiera naturalne słowa kluczowe z transkrypcji pod kątem indeksacji AI YouTube.
   - CTA z mentionem kanału: `{channel_mention}` (np. "Więcej analiz na {channel_mention}").
   - 3–5 hashtagów umieszczonych na samym końcu opisu.
   - **KATEGORYCZNY ZAKAZ wklejania URL/linków** (linki w Shorts są nieklikalne od 31.08.2023).

3. **hashtags** (oraz `tags`):
   - Dokładnie 3–5 hashtagów tematycznych/niszowych (mix PL/EN, format #slowo).
   - **KATEGORYCZNY ZAKAZ używania `#Shorts` lub `#shorts`** — zastąp tagiem niszowym/branżowym.

4. **pinned_comment**:
   - Przypięty komentarz pod shortem budujący dyskusję i konwersję.
   - **KATEGORYCZNY ZAKAZ linków/URLi** (brak klikalności).
   - Zamiast linku: mocne pytanie polaryzujące oparte na punchline/temacie fragmentu.
   - + CTA kierujące do powiązanego pełnego odcinka: „całą rozmowę znajdziesz w powiązanym filmie poniżej”.
   - Format z emoji: "💬 [Pytanie polaryzujące]? 👇\\n\\n🎬 Całą rozmowę znajdziesz w powiązanym filmie poniżej!"

## DLA KAŻDEGO KANDYDATA:
- **start_sec**: timestamp VTT początku pierwszego słowa hooka przeliczony na sekundy jako float (np. [02:25] = 145.0).
- **end_sec**: timestamp VTT OSTATNIEGO słowa punchline + 1.5 sekundy ciszy przeliczony na sekundy jako float.
- **hook_text (pierwsze 3-8 sekund)**: Mocne zdanie otwierające zatrzymujące scrollowanie.
- **body_summary (środek)**: 1-2 zwięzłe zdania podsumowujące środek tego fragmentu.
- **punchline_text (ostatnie 3-8 sekund)**: Mocna puenta, konkluzja lub zawieszenie myśli zamykające ten fragment.
- **score**: 0.8+ = doskonały, 0.6-0.79 = dobry, <0.6 = słaby.
- **rationale**: dlaczego ten fragment ma wysoki potencjał viralowy.
- Długość: end_sec - start_sec musi wynosić między 25 a 58 sekund.

## TRANSKRYPT Z TIMESTAMPAMI [MM:SS]:
{vtt_text}

Odpowiedź TYLKO JSON (bez markdown):
{{"candidates": [
  {{"type": "emotional", "start_sec": 145.0, "end_sec": 192.5,
    "hook_text": "Mocny cytat lub hook otwierający ze start_sec...",
    "punchline_text": "Pointa lub konkluzja zamykająca z end_sec...",
    "body_summary": "1-2 zdania streszczenia środka tego fragmentu...",
    "score": 0.85, "rationale": "Dlaczego ten fragment jest świetnym shortem",
    "query_match": "",
    "optimized_title": "Tytuł max 45 znaków z emocją",
    "suggested_title": "Tytuł max 45 znaków z emocją",
    "description": "Krótkie podsumowanie z kluczowymi słowami. Subskrybuj {channel_mention}! #tag1 #tag2 #tag3",
    "hashtags": ["#temat1", "#temat2", "#nisza"],
    "tags": ["#temat1", "#temat2", "#nisza"],
    "pinned_comment": "💬 Pytanie polaryzujące do widzów? 👇\\n\\n🎬 Całą rozmowę znajdziesz w powiązanym filmie poniżej!"}}
]}}
"""


def _sanitize_short_title(title: str, max_len: int = 45) -> str:
    """Oczyszcza tytuł shorta: usuwa #Shorts, trymuje do max_len na granicy słowa."""
    if not title:
        return ""
    # Usuń wszelkie warianty #shorts
    clean = re.sub(r"#shorts\b|#short\b", "", title, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= max_len:
        return clean
    # Przytnij do granicy słowa
    trimmed = clean[:max_len].rsplit(" ", 1)[0].strip()
    return trimmed if trimmed else clean[:max_len]


def _sanitize_hashtags(tags: list) -> list[str]:
    """Usuwa #Shorts i duplikaty, ogranicza do max 5 tagów."""
    if not tags:
        return []
    clean_tags = []
    for t in tags:
        if not isinstance(t, str):
            continue
        tag = t.strip()
        if not tag.startswith("#"):
            tag = f"#{tag}"
        tag_lower = tag.lower()
        if tag_lower in ["#shorts", "#short"]:
            continue
        if tag not in clean_tags and len(clean_tags) < 5:
            clean_tags.append(tag)
    return clean_tags


def _validate_and_enrich_candidate_texts(
    cand: dict,
    segments: list[tuple[float, str]],
    channel_mention: str = "@Kanal",
) -> dict:
    """
    Weryfikuje i ewentualnie koryguje teksty hook_text, punchline_text, body_summary,
    optimized_title, description, hashtags i pinned_comment.
    """
    start = float(cand.get("start_sec", 0))
    end = float(cand.get("end_sec", 0))
    if end <= start or not segments:
        return cand

    clip_segments = [seg for seg in segments if (start - 2.0) <= seg[0] <= (end + 2.0)]
    in_range_segments = [seg for seg in clip_segments if start <= seg[0] <= end]
    active_segments = in_range_segments if in_range_segments else clip_segments

    if not active_segments:
        return cand

    full_text = " ".join(t.strip() for _, t in active_segments if t.strip())
    raw_title = str(cand.get("optimized_title") or cand.get("suggested_title", "")).strip()
    title = _sanitize_short_title(raw_title, max_len=45)
    cand["optimized_title"] = title
    cand["suggested_title"] = title
    
    opening_text = " ".join(t.strip() for _, t in active_segments[:2] if t.strip())
    closing_text = " ".join(t.strip() for _, t in active_segments[-2:] if t.strip())

    # Walidacja hook_text
    hook_text = str(cand.get("hook_text", "")).strip()
    if not hook_text or len(hook_text.strip()) < 10:
        logger.warning("hook_text out of context for [%.1f-%.1f], auto-repairing from transcript", start, end)
        cand["hook_text"] = opening_text

    # Walidacja punchline_text
    punchline_text = str(cand.get("punchline_text", "")).strip()
    if not punchline_text or len(punchline_text.strip()) < 10:
        logger.warning("punchline_text out of context for [%.1f-%.1f], auto-repairing from transcript", start, end)
        cand["punchline_text"] = closing_text

    # Walidacja body_summary
    body_summary = str(cand.get("body_summary", "")).strip()
    if not body_summary or len(body_summary) < 5:
        cand["body_summary"] = f"Fragment ({int(start // 60)}:{int(start % 60):02d} - {int(end // 60)}:{int(end % 60):02d}): {title}"

    # Walidacja i sanityzacja tagów
    raw_tags = cand.get("hashtags") or cand.get("tags") or []
    clean_tags = _sanitize_hashtags(raw_tags)
    cand["hashtags"] = clean_tags
    cand["tags"] = clean_tags

    # Walidacja description (usuwanie ewentualnych URLi)
    desc = str(cand.get("description", "")).strip()
    desc = re.sub(r"https?://\S+", "", desc).strip()
    if not desc or len(desc) < 20:
        tag_str = " ".join(clean_tags[:4])
        desc = f"{cand['body_summary']} Sprawdź więcej na {channel_mention}. {tag_str}".strip()
    cand["description"] = desc[:350]

    # Walidacja pinned_comment (usuwanie ewentualnych URLi, format z emoji)
    p_comment = str(cand.get("pinned_comment", "")).strip()
    p_comment = re.sub(r"https?://\S+", "", p_comment).strip()
    if not p_comment or len(p_comment) < 15:
        p_comment = f"💬 Co sądzisz o tej opinii? Podziel się w komentarzu! 👇\n\n🎬 Całą rozmowę znajdziesz w powiązanym filmie poniżej!"
    cand["pinned_comment"] = p_comment

    return cand


def propose_shorts(
    vtt_path: str,
    count_emotional: int = 2,
    count_professional: int = 2,
    custom_query: str = "",
    count_custom: int = 3,
    api_key: str = "",
    provider: str = "gemini",
    channel_name: str = "",
    related_video_id: str = "",
) -> list[ShortCandidate]:
    """Analizuje VTT i zwraca listę kandydatów na shorty wg standardów 2025/2026.
    
    CO: Główna funkcja ShortMachine — AI propozycje z transkryptu.
    PO CO: Zwraca wycinki z tytułami max 45 znaków, opisami bez linków, tagami bez #Shorts i przypiętym komentarzem.
    JAK: Parsuje VTT, wysyła do LLM, weryfikuje spójność i zwraca ShortCandidate objects.
    """
    timestamped, segments, total_duration = parse_vtt_full(vtt_path)
    
    # Trim do rozsądnej długości
    vtt_text = timestamped[:150000]
    channel_mention = f"@{channel_name.lstrip('@')}" if channel_name else "@naszym kanale"
    
    prompt = SHORTS_SELECTION_PROMPT.format(
        count_emotional=count_emotional,
        count_professional=count_professional,
        custom_query=custom_query or "brak",
        count_custom=count_custom if custom_query else 0,
        channel_mention=channel_mention,
        vtt_text=vtt_text,
    )
    
    logger.info(
        "propose_shorts: emotional=%d professional=%d custom=%d query=%r channel=%s via %s",
        count_emotional, count_professional, count_custom, custom_query, channel_mention, provider
    )
    
    try:
        raw = _call_llm(prompt, api_key, provider)
    except Exception as llm_err:
        logger.error("propose_shorts: LLM error: %s", llm_err)
        raise ValueError(f"LLM call failed: {llm_err}")

    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = _sanitize_llm_json(raw)
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("propose_shorts: JSON parse error: %s | raw[:200]=%s", e, raw[:200])
        raise ValueError(f"LLM returned invalid JSON: {e}")
    candidates_raw = data.get("candidates", [])
    logger.info("propose_shorts: LLM returned %d raw candidate entries", len(candidates_raw))
    
    candidates: list[ShortCandidate] = []
    for c in candidates_raw:
        start = float(c.get("start_sec", 0))
        end = float(c.get("end_sec", 0))
        if end <= start:
            logger.warning("Skipping candidate: end_sec <= start_sec (%s→%s)", start, end)
            continue
        duration = end - start
        if duration < 10 or duration > 90:
            logger.warning("Skipping candidate: duration=%.1fs out of range", duration)
            continue

        # Spójność treści z zakresem czasowym i formatowanie 2025/2026
        c_fixed = _validate_and_enrich_candidate_texts(c, segments, channel_mention=channel_mention)

        title = c_fixed.get("optimized_title") or c_fixed.get("suggested_title", "")
        tags = c_fixed.get("hashtags") or c_fixed.get("tags", [])

        candidates.append(ShortCandidate(
            type=c_fixed.get("type", "custom"),
            start_sec=start,
            end_sec=end,
            duration_sec=round(duration, 1),
            hook_text=c_fixed.get("hook_text", ""),
            punchline_text=c_fixed.get("punchline_text", ""),
            body_summary=c_fixed.get("body_summary", ""),
            score=float(c_fixed.get("score", 0.5)),
            rationale=c_fixed.get("rationale", ""),
            query_match=c_fixed.get("query_match", ""),
            suggested_title=title,
            optimized_title=title,
            tags=tags,
            hashtags=tags,
            description=c_fixed.get("description", ""),
            pinned_comment=c_fixed.get("pinned_comment", ""),
            related_video_id=related_video_id or c_fixed.get("related_video_id", ""),
        ))
    
    candidates.sort(key=lambda x: x.score, reverse=True)
    logger.info("propose_shorts: %d valid candidates returned", len(candidates))
    return candidates


def get_vtt_segments_for_candidate(
    vtt_path: str,
    start_sec: float,
    end_sec: float,
    context_sec: float = 60.0,
) -> list[dict]:
    """
    Zwraca segmenty VTT dla kandydata z kontekstem.
    
    CO: Wyodrębnia segmenty transkryptu dla zakresu start_sec-end_sec +/- context_sec.
    PO CO: Transcript Editor Panel — wyświetla klikalny transkrypt w UI.
    JAK: Parsuje VTT, filtruje segmenty w zakresie, zwraca listę {ts, text, in_range}.
    
    Returns:
        Lista dictów: [{"ts": float, "time_str": "MM:SS", "text": str, "in_range": bool}]
    """
    try:
        _, segments, _ = parse_vtt_full(vtt_path)
    except Exception as e:
        logger.warning("get_vtt_segments: parse failed: %s", e)
        return []
    
    context_start = max(0.0, start_sec - context_sec)
    context_end = end_sec + context_sec
    
    result = []
    for ts, text in segments:
        if context_start <= ts <= context_end:
            mins = int(ts // 60)
            secs = int(ts % 60)
            result.append({
                "ts": round(ts, 1),
                "time_str": f"{mins}:{secs:02d}",
                "text": text.strip(),
                "in_range": start_sec <= ts <= end_sec,
            })
    
    return result


def get_segments_for_range(
    vtt_path: str,
    start_sec: float,
    end_sec: float,
    context_sec: float = 3.0,
) -> list[dict]:
    """
    Zwraca segmenty VTT dla zakresu start_sec-end_sec z małym kontekstem.
    
    CO: Alias do get_vtt_segments_for_candidate z mniejszym domyślnym kontekstem.
    PO CO: Używany przez endpoint /v1/shorts/title oraz /v1/shorts/describe.
    JAK: Parsuje VTT, filtruje segmenty w zakresie +/- context_sec.
    
    Returns:
        Lista dictów: [{"ts": float, "time_str": "MM:SS", "text": str, "in_range": bool}]
    """
    return get_vtt_segments_for_candidate(
        vtt_path=vtt_path,
        start_sec=start_sec,
        end_sec=end_sec,
        context_sec=context_sec,
    )


def extract_srt_segment(
    segments: list[tuple[float, str]],
    start_sec: float,
    end_sec: float,
    output_path: str,
) -> str:
    """Generuje plik .srt dla fragmentu start_sec–end_sec z segmentów VTT.
    
    CO: Tworzy plik napisów .srt pasujący do wyciętego fragmentu.
    PO CO: Użytkownik może zaimportować .srt do Premiere/FinalCut lub użyć ffmpeg.
    JAK: Filtruje segmenty VTT w przedziale, resetuje timestampy do 0.
    
    Returns:
        Ścieżka do zapisanego pliku .srt
    """
    filtered = [(ts, text) for ts, text in segments if start_sec <= ts <= end_sec]
    
    srt_lines = []
    for i, (ts, text) in enumerate(filtered, 1):
        relative_start = ts - start_sec
        relative_end = min(relative_start + 3.0, end_sec - start_sec)
        
        def fmt(s: float) -> str:
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            ms = int((s % 1) * 1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        
        srt_lines.append(f"{i}")
        srt_lines.append(f"{fmt(relative_start)} --> {fmt(relative_end)}")
        srt_lines.append(text)
        srt_lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    
    logger.info("extract_srt_segment: %d lines → %s", len(filtered), output_path)
    return output_path
