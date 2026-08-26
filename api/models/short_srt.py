"""
ShortSrtPackage — przechowuje wygenerowane pliki SRT dla danego wideo YouTube.

CO: Model bazy danych dla pakietów SRT shortmów.
PO CO: SRT-Only workflow — użytkownicy free mogą pobrać pakiet SRT bez renderowania wideo.
JAK: Przechowuje 3 pliki SRT jako tekst + metadane o kandydatach (ile, zakresy).
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from api.db import Base


class ShortSrtPackage(Base):
    __tablename__ = "short_srt_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_id = Column(String(20), nullable=False, index=True)
    portal_id = Column(String(100), nullable=True)
    candidate_count = Column(Integer, default=0)
    pelny_film_srt = Column(Text, nullable=True)
    napisy_shortow_srt = Column(Text, nullable=True)
    shorts_markers_srt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
