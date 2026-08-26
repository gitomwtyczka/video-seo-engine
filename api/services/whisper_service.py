"""VSE Whisper Transcription Service using faster-whisper.

CO: Lokalna transkrypcja audio na VPS za pomocą faster-whisper.
PO CO: Niezależność od YouTube i zewnętrznych API. Obsługa uploadu własnego MP3/WAV/M4A.
JAK: Lazy loading modeli (small/base) z compute_type="int8", cpu_threads=4, vad_filter=True.
     Konwersja segmentów do formatu WebVTT i SRT.
"""
import logging
import os
import re
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

_loaded_models: Dict[str, Any] = {}


def get_whisper_model(model_name: str = "small", cpu_threads: int = 4):
    """Lazy loader dla modeli faster-whisper.

    Model jest pobierany i ładowany do pamięci dopiero przy pierwszym żądaniu.
    Cache modeli w pamięci procesu.
    """
    global _loaded_models
    if model_name not in _loaded_models:
        from faster_whisper import WhisperModel
        logger.info(
            "[whisper] Loading model %s (device=cpu, compute_type=int8, threads=%d)...",
            model_name,
            cpu_threads,
        )
        _loaded_models[model_name] = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
        )
        logger.info("[whisper] Model %s loaded successfully", model_name)
    return _loaded_models[model_name]


def seconds_to_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def seconds_to_vtt_time(seconds: float) -> str:
    """Format seconds to WebVTT timestamp (HH:MM:SS.mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d}.000"


def transcribe_audio(
    audio_path: str,
    quality: str = "default",
    lang: Optional[str] = "pl",
    cpu_threads: int = 4,
) -> Tuple[str, str, dict]:
    """Transkrybuje plik audio za pomocą faster-whisper.

    Args:
        audio_path: Ścieżka do pliku audio na dysku.
        quality: 'default' (model small) lub 'fast' (model base).
        lang: Kod języka (np. 'pl', 'en') lub None dla auto-detekcji.
        cpu_threads: Liczba wątków CPU (domyślnie 4).

    Returns:
        (srt_text, vtt_text, info_dict)
    """
    model_name = "base" if quality == "fast" else "small"
    model = get_whisper_model(model_name=model_name, cpu_threads=cpu_threads)

    logger.info(
        "[whisper] Starting transcription: file=%s, model=%s, lang=%s",
        audio_path,
        model_name,
        lang,
    )

    segments_generator, info = model.transcribe(
        audio_path,
        language=lang if lang else None,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    srt_entries = []
    vtt_entries = ["WEBVTT", ""]

    counter = 1
    for seg in segments_generator:
        start_sec = seg.start
        end_sec = seg.end
        text = seg.text.strip()
        if not text:
            continue

        # SRT entry
        srt_start = seconds_to_srt_time(start_sec)
        srt_end = seconds_to_srt_time(end_sec)
        srt_entries.append(f"{counter}\n{srt_start} --> {srt_end}\n{text}")

        # WebVTT entry
        vtt_start = seconds_to_vtt_time(start_sec)
        vtt_end = seconds_to_vtt_time(end_sec)
        vtt_entries.append(str(counter))
        vtt_entries.append(f"{vtt_start} --> {vtt_end}")
        vtt_entries.append(text)
        vtt_entries.append("")

        counter += 1

    srt_text = "\n\n".join(srt_entries) + ("\n" if srt_entries else "")
    vtt_text = "\n".join(vtt_entries)

    info_dict = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments_count": counter - 1,
        "model": model_name,
    }
    logger.info(
        "[whisper] Transcription finished: %d segments, duration=%.1fs, lang=%s",
        counter - 1,
        info.duration,
        info.language,
    )

    return srt_text, vtt_text, info_dict
