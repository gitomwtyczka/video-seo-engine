"""
ShortSrtPackage — przechowuje wygenerowane pliki SRT dla danego wideo YouTube lub uploadowanego audio.

CO: Model bazy danych dla pakietów SRT shortów oraz zadań transkrypcji audio (faster-whisper).
PO CO: SRT-Only workflow — użytkownicy mogą pobrać pakiet SRT bez renderowania wideo.
JAK: Przechowuje pliki SRT jako tekst + metadane o statusie transkrypcji i kandydatach.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from api.db import Base


class ShortSrtPackage(Base):
    __tablename__ = "short_srt_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_id = Column(String(100), nullable=True, index=True)
    audio_filename = Column(String(255), nullable=True)
    status = Column(String(20), default="done")  # 'pending' | 'processing' | 'done' | 'error'
    progress_pct = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    portal_id = Column(String(100), nullable=True)
    candidate_count = Column(Integer, default=0)
    pelny_film_srt = Column(Text, nullable=True)
    napisy_shortow_srt = Column(Text, nullable=True)
    shorts_markers_srt = Column(Text, nullable=True)
    youtube_chapters = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
