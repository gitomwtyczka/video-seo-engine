"""
AppSettings model: klucz-wartość dla ustawień systemowych.

CO: Tabela app_settings — prosty store klucz/wartość dla ustawień aplikacji.
PO CO: Pozwala przechowywać flagi systemowe (np. debug_mode) bez osobnych kolumn
       na każde ustawienie. Admin może włączać/wyłączać tryb debug przez panel UI
       bez SSH na VPS i bez restartu kontenera.
JAK: Prosta tabela PRIMARY KEY (key VARCHAR). Nie ma FK. CREATE TABLE IF NOT EXISTS
     wywołane automatycznie przez Base.metadata.create_all() na starcie API.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from api.db import Base


class AppSettings(Base):
    """System-wide key/value settings store."""
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(1000), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
