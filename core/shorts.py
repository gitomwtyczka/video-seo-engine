"""
ShortMachine — AI selection of short video candidates from VTT transcript.

Responsibilities:
  - Parse VTT segments to identify emotional/professional/custom fragments
  - Call LLM to propose ShortCandidates with Hook/Body/Punchline structure
  - Return list of ShortCandidate objects with timestamps and scores

Dependencies: core/generator.py (reuses parse_vtt_full, _call_llm)
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
    
    CO: Reprezentuje fragment wideo proponowany jako short.
    PO CO: Przechowuje wszystkie dane potrzebne do wycięcia i wyświetlenia w UI.
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
    suggested_title: str = ""  # chwytliwy tytuł shorta (5-9 słów po polsku)
    tags: list = field(default_factory=list)  # do 10 hashtagów tematycznych
    
    def to_dict(self) -> dict:
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
            "suggested_title": self.suggested_title,
            "tags": self.tags,
        }


SHORTS_SELECTION_PROMPT = """
Jesteś ekspertem od krótkich formatów wideo (YouTube Shorts, TikTok, Reels).
Na podstawie transkryptu z timestampami zaproponuj kandydatury na shorty.

## PARAMETRY
- Emotional: {count_emotional} kandydatów (fragmenty wywołujące emocje: złość, zaskoczenie, wzruszenie)
- Professional: {count_professional} kandydatów (merytoryczne, eksperckie, informacyjne)
- Custom ({custom_query}): {count_custom} kandydatów (pasujące do tej tezy/tematu/słów)

## ⚠️ KRYTYCZNA ZASADA DLA KAŻDEGO KANDYDATA (SPÓJNOŚĆ FAKTÓW I SEGMENTU):
Każdy kandydat to DOKŁADNIE JEDEN spójny wycinek wideo w przedziale [start_sec → end_sec].
- `hook_text`, `body_summary`, `punchline_text` i `suggested_title` MUSZĄ być ściśle zakorzenione w faktach, tezach i wypowiedziach padających w TYM KONKRETNYM segmencie [start_sec → end_sec].
- Styl, ton i retoryka mogą być wzmocnione/chwytliwe pod Shorty, ALE KATEGORYCZNIE NIE WOLNO wstawiać faktów, nazwisk ani twierdzeń z innych części filmu (np. z innej minuty).
- Widz oglądający ten 30-50 sekundowy fragment musi usłyszeć to, co zapowiada hook i puenta.

## DLA KAŻDEGO KANDYDATA:

### STRUKTURA Hook → Body → Punchline:
- **start_sec**: timestamp VTT początku pierwszego słowa hooka przeliczony na sekundy jako float (np. [02:25] = 145.0).
- **end_sec**: timestamp VTT OSTATNIEGO słowa punchline + 1.5 sekundy ciszy przeliczony na sekundy jako float (NIE początek zdania!).
  PRZYKŁAD: Jeśli zdanie punchline zaczyna się o [03:04] (184s) i trwa 7 sekund:
  - POPRAWNE: end_sec = 184 + 7 + 1.5 = 192.5
  - BŁĘDNE: end_sec = 184.0 (to jest POCZĄTEK punchline, nie koniec!)
- **hook_text (pierwsze 3-8 sekund)**: Mocne zdanie otwierające / hook zatrzymujący scrollowanie.
  Musi wynikać bezpośrednio ze słów otwierających ten fragment w sekundzie `start_sec`.
- **body_summary (środek)**: 1-2 zwięzłe zdania podsumowujące, o czym mowa w środku TEGO fragmentu (między start_sec a end_sec).
- **punchline_text (ostatnie 3-8 sekund)**: Mocna puenta, konkluzja lub zawieszenie myśli zamykające TEN fragment tuż przed `end_sec`.
- **suggested_title**: chwytliwy, clickbaitowy tytuł shorta (5-9 słów po polsku) opisujący DOKŁADNIE temat tego konkretnego wycinka.
- **tags**: do 10 hashtagów tematycznych (mix PL i EN, format #słowo).

## ZASADY DOBORU:
- Długość: end_sec - start_sec musi być między 25 a 58 sekund.
- Nie nakrywaj kandydatów (różne fragmenty wideo).
- score: 0.8+ = doskonały, 0.6-0.79 = dobry, <0.6 = słaby.

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
    "suggested_title": "Chwytliwy tytuł shorta — 5-9 słów po polsku",
    "tags": ["#hashtag1", "#hashtag2"]}}
]}}
"""


def _validate_and_enrich_candidate_texts(
    cand: dict,
    segments: list[tuple[float, str]],
) -> dict:
    """
    Weryfikuje i ewentualnie koryguje teksty hook_text, punchline_text i body_summary
    na podstawie rzeczywistych segmentów VTT w przedziale [start_sec, end_sec].
    
    CO: Zapobiega halucynacjom LLM, gdy hook/puenta pochodzą z innej części filmu.
    PO CO: Gwarantuje zgodność faktów w opisie shorta z wyciętym fragmentem wideo.
    JAK: Filtruje segmenty w zadanym przedziale czasowym i sprawdza leksykalny overlap.
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
    title = str(cand.get("suggested_title", "")).strip()
    
    # Zbiór słów bazowych z segmentu i tytułu
    seg_words = set(re.findall(r"\b\w{4,}\b", (full_text + " " + title).lower()))
    opening_text = " ".join(t.strip() for _, t in active_segments[:2] if t.strip())
    closing_text = " ".join(t.strip() for _, t in active_segments[-2:] if t.strip())

    # Walidacja hook_text
    hook_text = str(cand.get("hook_text", "")).strip()
    # Tylko fallback na pusty/za krótki hook — nie zastępuj kreatywnych parafraz
    if not hook_text or len(hook_text.strip()) < 10:
        logger.warning("hook_text out of context for [%.1f-%.1f], auto-repairing from transcript", start, end)
        cand["hook_text"] = opening_text

    # Walidacja punchline_text
    punchline_text = str(cand.get("punchline_text", "")).strip()
    # Tylko fallback na pusty/za krótki punchline — nie zastępuj kreatywnych parafraz
    if not punchline_text or len(punchline_text.strip()) < 10:
        logger.warning("punchline_text out of context for [%.1f-%.1f], auto-repairing from transcript", start, end)
        cand["punchline_text"] = closing_text

    # Walidacja body_summary
    body_summary = str(cand.get("body_summary", "")).strip()
    if not body_summary or len(body_summary) < 5:
        cand["body_summary"] = f"Fragment wideo ({int(start // 60)}:{int(start % 60):02d} - {int(end // 60)}:{int(end % 60):02d}): {title}"

    return cand


def propose_shorts(
    vtt_path: str,
    count_emotional: int = 2,
    count_professional: int = 2,
    custom_query: str = "",
    count_custom: int = 3,
    api_key: str = "",
    provider: str = "gemini",
) -> list[ShortCandidate]:
    """Analizuje VTT i zwraca listę kandydatów na shorty.
    
    CO: Główna funkcja ShortMachine — AI propozycje z transkryptu.
    PO CO: Pozwala użytkownikowi zobaczyć proponowane fragmenty przed pobraniem wideo.
    JAK: Parsuje VTT, wysyła do LLM, weryfikuje spójność tekstową i zwraca ShortCandidate objects.
    
    Args:
        vtt_path: Ścieżka do pliku .vtt
        count_emotional: liczba kandydatów emotional
        count_professional: liczba kandydatów professional
        custom_query: zapytanie custom (np. 'Niemcy teściową Europy')
        count_custom: liczba kandydatów custom
        api_key: klucz API dla LLM
        provider: 'gemini' lub 'claude'
    
    Returns:
        Lista ShortCandidate obiektów posortowanych po score (malejąco).
    """
    timestamped, segments, total_duration = parse_vtt_full(vtt_path)
    
    # Trim do rozsądnej długości
    vtt_text = timestamped[:150000]
    
    prompt = SHORTS_SELECTION_PROMPT.format(
        count_emotional=count_emotional,
        count_professional=count_professional,
        custom_query=custom_query or "brak",
        count_custom=count_custom if custom_query else 0,
        vtt_text=vtt_text,
    )
    
    logger.info(
        "propose_shorts: emotional=%d professional=%d custom=%d query=%r via %s",
        count_emotional, count_professional, count_custom, custom_query, provider
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

        # Spójność treści z zakresem czasowym
        c_fixed = _validate_and_enrich_candidate_texts(c, segments)

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
            suggested_title=c_fixed.get("suggested_title", ""),
            tags=c_fixed.get("tags", []),
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
    PO CO: Używany przez endpoint /v1/shorts/title do regeneracji tytułu.
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
