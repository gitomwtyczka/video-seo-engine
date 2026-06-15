"""TranscriptJob ORM model — Local Transcript Runner.

CO: SQLAlchemy model tabeli transcript_jobs.

PO CO: Kolejka zadań dla Local Runner’a (Windows Service na PC Usera).
YouTube blokuje youtube-transcript-api z Oracle Cloud VPS IP.
Rozwiązaniem jest przeniesienie fetchowania transkryptów na lokalne PC,
które ma normalne IP domowe/biurowe. Ta tabela to szyna komunikacji
między VPS (API) a lokalnym PC (runner).

JAK:
- VPS tworzy job ze statusem 'pending'
- Local Runner polluje /v1/jobs/pending, pobiera transkrypt, POST-uje wynik
- Pipeline czeka na status 'fetched', potem kontynuuje
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from api.db import Base


class TranscriptJob(Base):
    """Kolejka zadań transkrypcji dla Local Runner’a.

    Lifecycle:
        pending  → runner pobrał z /v1/jobs/pending
        fetched  → runner zwrócił transkrypt przez /v1/jobs/{id}/result
        processing → pipeline w trakcie generowania SEO
        done    → pipeline zakończony
        failed  → błąd (runner lub pipeline)
    """
    __tablename__ = "transcript_jobs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    video_url = Column(String(500), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )  # pending | fetched | processing | done | failed
    transcript = Column(Text, nullable=True)  # NULL do czasu zwrotu przez runner
    error = Column(Text, nullable=True)  # NULL jeśli OK
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
    # FK do usera który zlecił — opcjonalne (może być None dla internal calls)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
