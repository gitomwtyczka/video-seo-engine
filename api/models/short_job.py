"""
ShortJob model — baza danych dla zadań ShortMachine.

CO: Model SQLAlchemy dla tabeli short_jobs.
PO CO: Przechowuje stan zadań wycinania wideo dla Local Runnera.
JAK: Wzorzec polling — Local Runner pobiera pending, przetwarza, raportuje result.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from api.db import Base


class ShortJob(Base):
    __tablename__ = "short_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default="pending")  # pending|processing|done|error
    
    # Źródło wideo
    youtube_url = Column(String(500), nullable=True)
    local_path = Column(String(1000), nullable=True)  # ścieżka na PC użytkownika
    
    # Czasy wycięcia
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    
    # Dane kandydata (z propose_shorts)
    candidate_data = Column(JSONB, nullable=True)  # ShortCandidate.to_dict()
    
    # Konfiguracja renderowania
    render_config = Column(JSONB, nullable=True)  # format, subtitles, output_dir
    
    # Wyniki
    result_paths = Column(JSONB, nullable=True)   # {raw: path, social: path, srt: path}
    error_message = Column(Text, nullable=True)
    
    # Metadane
    portal_id = Column(String(100), nullable=True)
    youtube_id = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
