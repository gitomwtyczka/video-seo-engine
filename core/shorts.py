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
    hook_text: str          # pierwsze słowa (widoczne w UI)
    punchline_text: str     # ostatnie słowa (widoczne w UI)
    body_summary: str       # krótkie streszczenie środka
    score: float            # 0.0–1.0 jakość kandydata
    rationale: str          # uzasadnienie wyboru przez AI
    query_match: str = ""   # jak pasuje do custom query
    
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
        }


SHORTS_SELECTION_PROMPT = """
Jesteś ekspertem od krótkich formatów wideo (YouTube Shorts, TikTok, Reels).
Na podstawie transkryptu z timestampami zaproponuj kandydatury na shorty.

## PARAMETRY
- Emotional: {count_emotional} kandydatów (fragmenty wywołujące emocje: złość, zaskoczenie, wzruszenie)
- Professional: {count_professional} kandydatów (merytoryczne, eksperckie, informacyjne)
- Custom ({custom_query}): {count_custom} kandydatów (pasujące do tej tezy/tematu/słów)

## DLA KAŻDEGO KANDYDATA:

### STRUKTURA Hook → Body → Punchline:
- **Hook (pierwsze 3-8 sekund)**: Mocne zdanie które zatrzymuje scrollowanie.
  Musi działać BEZ kontekstu — widz nie zna materiału.
  start_sec = początek tego zdania
- **Body (środek)**: Spójna narracja rozwijająca temat.
- **Punchline (ostatnie 3-8 sekund)**: Pointa, konkluzja lub zawieszenie myśli.
  end_sec = koniec tego zdania

## ZASADY DOBORU:
- Długość kandydata: 25-58 sekund (SHORT MUSI BYĆ KRÓTKI)
- Granice cięcia: dopasuj do przerw między zdaniami (nie ucinaj słów)
- Nie nakrywaj kandydatów (różne fragmenty wideo)
- score: 0.8+ = doskonały, 0.6-0.79 = dobry, <0.6 = słaby

## TRANSKRYPT Z TIMESTAMPAMI [MM:SS]:
{vtt_text}

Odpowiedź TYLKO JSON (bez markdown):
{{"candidates": [
  {{"type": "emotional", "start_sec": 0.0, "end_sec": 0.0,
    "hook_text": "...", "punchline_text": "...", "body_summary": "...",
    "score": 0.0, "rationale": "...", "query_match": ""}}
]}}
"""


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
    JAK: Parsuje VTT, wysyła do LLM, zwraca ShortCandidate objects.
    
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
        candidates.append(ShortCandidate(
            type=c.get("type", "custom"),
            start_sec=start,
            end_sec=end,
            duration_sec=round(duration, 1),
            hook_text=c.get("hook_text", ""),
            punchline_text=c.get("punchline_text", ""),
            body_summary=c.get("body_summary", ""),
            score=float(c.get("score", 0.5)),
            rationale=c.get("rationale", ""),
            query_match=c.get("query_match", ""),
        ))
    
    candidates.sort(key=lambda x: x.score, reverse=True)
    logger.info("propose_shorts: %d valid candidates returned", len(candidates))
    return candidates


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
