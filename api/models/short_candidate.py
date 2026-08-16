"""
ShortCandidate model — persystencja kandydatów AI w bazie danych.

CO: Przechowuje kandydatów wygenerowanych przez propose_shorts dla danego youtube_id.
PO CO: Kandydaci nie znikają po przełączeniu zakładki lub re-logowaniu.
JAK: Zapis przy pierwszej analizie, odczyt przy powrocie na zakładkę ShortMachine.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from api.db import Base

class ShortCandidateSet(Base):
    __tablename__ = "short_candidate_sets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_id = Column(String(20), nullable=False, index=True)
    youtube_url = Column(String(500), nullable=True)
    portal_id = Column(String(100), nullable=True)
    custom_query = Column(Text, nullable=True)
    candidates = Column(JSONB, nullable=False, default=list)  # list[ShortCandidate.to_dict()]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Wersjonowanie: można mieć wiele setów dla jednego youtube_id
    version = Column(Integer, default=1)
