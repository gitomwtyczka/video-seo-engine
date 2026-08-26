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

## DLA KAŻDEGO KANDYDATA:

### STRUKTURA Hook → Body → Punchline:
- **Hook (pierwsze 3-8 sekund)**: Mocne zdanie które zatrzymuje scrollowanie.
  Musi działać BEZ kontekstu — widz nie zna materiału.
  start_sec = początek tego zdania
- **Body (środek)**: Spójna narracja rozwijająca temat.
- **Punchline (ostatnie 3-8 sekund)**: Pointa, konkluzja lub zawieszenie myśli.
  `end_sec` = KONIEC ostatniego słowa punchline + 1.5 sekundy (NIE początek zdania!)
  
  PRZYKŁAD: Jeśli zdanie punchline zaczyna się o [19:01] i trwa 8 sekund:
  - POPRAWNE: end_sec = 1141 + 8 + 1.5 = 1150 
  - BŁĘDNE: end_sec = 1141 (to jest POCZĄTEK punchline, nie koniec!)

## TYTUŁ I TAGI:
- suggested_title: chwytliwy, clickbaitowy tytuł shorta (5-9 słów). Może być pytaniem lub tezą. Po polsku.
- tags: do 10 hashtagów tematycznych. Mix polskich i angielskich. Format: #słowo (bez spacji).

## ZASADY DOBORU:
- start_sec: timestamp VTT początku pierwszego słowa hooka
- end_sec: timestamp VTT OSTATNIEGO słowa punchline + 1.5s ciszy
- Długość: end_sec - start_sec musi być między 25 a 58 sekund
- Nie nakrywaj kandydatów (różne fragmenty wideo)
- score: 0.8+ = doskonały, 0.6-0.79 = dobry, <0.6 = słaby

## TRANSKRYPT Z TIMESTAMPAMI [MM:SS]:
{vtt_text}

Odpowiedź TYLKO JSON (bez markdown):
{{\"candidates\": [
  {{\"type\": \"emotional\", \"start_sec\": 0.0, \"end_sec\": 0.0,\n    \"hook_text\": \"...\", \"punchline_text\": \"...\", \"body_summary\": \"...\",\n    \"score\": 0.0, \"rationale\": \"...\", \"query_match\": \"\",\n    \"suggested_title\": \"Chwytliwy tytuł shorta — 5-9 słów po polsku, bez hashtag\",\n    \"tags\": [\"#hashtag1\", \"#hashtag2\"]}}\n]}}\n\"\"\"\n\n\ndef propose_shorts(\n    vtt_path: str,\n    count_emotional: int = 2,\n    count_professional: int = 2,\n    custom_query: str = \"\",\n    count_custom: int = 3,\n    api_key: str = \"\",\n    provider: str = \"gemini\",\n) -> list[ShortCandidate]:\n    \"\"\"Analizuje VTT i zwraca listę kandydatów na shorty.\n    \n    CO: Główna funkcja ShortMachine — AI propozycje z transkryptu.\n    PO CO: Pozwala użytkownikowi zobaczyć proponowane fragmenty przed pobraniem wideo.\n    JAK: Parsuje VTT, wysyła do LLM, zwraca ShortCandidate objects.\n    \n    Args:\n        vtt_path: Ścieżka do pliku .vtt\n        count_emotional: liczba kandydatów emotional\n        count_professional: liczba kandydatów professional\n        custom_query: zapytanie custom (np. 'Niemcy teściową Europy')\n        count_custom: liczba kandydatów custom\n        api_key: klucz API dla LLM\n        provider: 'gemini' lub 'claude'\n    \n    Returns:\n        Lista ShortCandidate obiektów posortowanych po score (malejąco).\n    \"\"\"\n    timestamped, segments, total_duration = parse_vtt_full(vtt_path)\n    \n    # Trim do rozsądnej długości\n    vtt_text = timestamped[:150000]\n    \n    prompt = SHORTS_SELECTION_PROMPT.format(\n        count_emotional=count_emotional,\n        count_professional=count_professional,\n        custom_query=custom_query or \"brak\",\n        count_custom=count_custom if custom_query else 0,\n        vtt_text=vtt_text,\n    )\n    \n    logger.info(\n        \"propose_shorts: emotional=%d professional=%d custom=%d query=%r via %s\",\n        count_emotional, count_professional, count_custom, custom_query, provider\n    )\n    \n    try:\n        raw = _call_llm(prompt, api_key, provider)\n    except Exception as llm_err:\n        logger.error(\"propose_shorts: LLM error: %s\", llm_err)\n        raise ValueError(f\"LLM call failed: {llm_err}\")\n\n    raw = raw.strip()\n    raw = re.sub(r\"^```json\\s*\", \"\", raw)\n    raw = re.sub(r\"\\s*```$\", \"\", raw)\n    raw = _sanitize_llm_json(raw)\n    \n    try:\n        data = json.loads(raw)\n    except json.JSONDecodeError as e:\n        logger.error(\"propose_shorts: JSON parse error: %s | raw[:200]=%s\", e, raw[:200])\n        raise ValueError(f\"LLM returned invalid JSON: {e}\")\n    candidates_raw = data.get(\"candidates\", [])\n    \n    candidates: list[ShortCandidate] = []\n    for c in candidates_raw:\n        start = float(c.get(\"start_sec\", 0))\n        end = float(c.get(\"end_sec\", 0))\n        if end <= start:\n            logger.warning(\"Skipping candidate: end_sec <= start_sec (%s→%s)\", start, end)\n            continue\n        duration = end - start\n        if duration < 10 or duration > 90:\n            logger.warning(\"Skipping candidate: duration=%.1fs out of range\", duration)\n            continue\n        candidates.append(ShortCandidate(\n            type=c.get(\"type\", \"custom\"),\n            start_sec=start,\n            end_sec=end,\n            duration_sec=round(duration, 1),\n            hook_text=c.get(\"hook_text\", \"\"),\n            punchline_text=c.get(\"punchline_text\", \"\"),\n            body_summary=c.get(\"body_summary\", \"\"),\n            score=float(c.get(\"score\", 0.5)),\n            rationale=c.get(\"rationale\", \"\"),\n            query_match=c.get(\"query_match\", \"\"),\n            suggested_title=c.get(\"suggested_title\", \"\"),\n            tags=c.get(\"tags\", []),\n        ))\n    \n    candidates.sort(key=lambda x: x.score, reverse=True)\n    logger.info(\"propose_shorts: %d valid candidates returned\", len(candidates))\n    return candidates\n\n\ndef get_vtt_segments_for_candidate(\n    vtt_path: str,\n    start_sec: float,\n    end_sec: float,\n    context_sec: float = 60.0,\n) -> list[dict]:\n    \"\"\"\n    Zwraca segmenty VTT dla kandydata z kontekstem.\n    \n    CO: Wyodrębnia segmenty transkryptu dla zakresu start_sec-end_sec +/- context_sec.\n    PO CO: Transcript Editor Panel — wyświetla klikalny transkrypt w UI.\n    JAK: Parsuje VTT, filtruje segmenty w zakresie, zwraca listę {ts, text, in_range}.\n    \n    Returns:\n        Lista dictów: [{\"ts\": float, \"time_str\": \"MM:SS\", \"text\": str, \"in_range\": bool}]\n    \"\"\"\n    try:\n        _, segments, _ = parse_vtt_full(vtt_path)\n    except Exception as e:\n        logger.warning(\"get_vtt_segments: parse failed: %s\", e)\n        return []\n    \n    context_start = max(0.0, start_sec - context_sec)\n    context_end = end_sec + context_sec\n    \n    result = []\n    for ts, text in segments:\n        if context_start <= ts <= context_end:\n            mins = int(ts // 60)\n            secs = int(ts % 60)\n            result.append({\n                \"ts\": round(ts, 1),\n                \"time_str\": f\"{mins}:{secs:02d}\",\n                \"text\": text.strip(),\n                \"in_range\": start_sec <= ts <= end_sec,\n            })\n    \n    return result\n\n\ndef get_segments_for_range(\n    vtt_path: str,\n    start_sec: float,\n    end_sec: float,\n    context_sec: float = 3.0,\n) -> list[dict]:\n    \"\"\"\n    Zwraca segmenty VTT dla zakresu start_sec-end_sec z małym kontekstem.\n    \n    CO: Alias do get_vtt_segments_for_candidate z mniejszym domyślnym kontekstem.\n    PO CO: Używany przez endpoint /v1/shorts/title do regeneracji tytułu.\n    JAK: Parsuje VTT, filtruje segmenty w zakresie +/- context_sec.\n    \n    Returns:\n        Lista dictów: [{\"ts\": float, \"time_str\": \"MM:SS\", \"text\": str, \"in_range\": bool}]\n    \"\"\"\n    return get_vtt_segments_for_candidate(\n        vtt_path=vtt_path,\n        start_sec=start_sec,\n        end_sec=end_sec,\n        context_sec=context_sec,\n    )\n\n\ndef extract_srt_segment(\n    segments: list[tuple[float, str]],\n    start_sec: float,\n    end_sec: float,\n    output_path: str,\n) -> str:\n    \"\"\"Generuje plik .srt dla fragmentu start_sec–end_sec z segmentów VTT.\n    \n    CO: Tworzy plik napisów .srt pasujący do wyciętego fragmentu.\n    PO CO: Użytkownik może zaimportować .srt do Premiere/FinalCut lub użyć ffmpeg.\n    JAK: Filtruje segmenty VTT w przedziale, resetuje timestampy do 0.\n    \n    Returns:\n        Ścieżka do zapisanego pliku .srt\n    \"\"\"\n    filtered = [(ts, text) for ts, text in segments if start_sec <= ts <= end_sec]\n    \n    srt_lines = []\n    for i, (ts, text) in enumerate(filtered, 1):\n        relative_start = ts - start_sec\n        relative_end = min(relative_start + 3.0, end_sec - start_sec)\n        \n        def fmt(s: float) -> str:\n            h = int(s // 3600)\n            m = int((s % 3600) // 60)\n            sec = int(s % 60)\n            ms = int((s % 1) * 1000)\n            return f\"{h:02d}:{m:02d}:{sec:02d},{ms:03d}\"\n        \n        srt_lines.append(f\"{i}\")\n        srt_lines.append(f\"{fmt(relative_start)} --> {fmt(relative_end)}\")\n        srt_lines.append(text)\n        srt_lines.append(\"\")\n    \n    with open(output_path, \"w\", encoding=\"utf-8\") as f:\n        f.write(\"\\n\".join(srt_lines))\n    \n    logger.info(\"extract_srt_segment: %d lines → %s\", len(filtered), output_path)\n    return output_path\n