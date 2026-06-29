"""
SQLAlchemy ORM model: WpPortal.

CO: Model portalu WordPress powiązanego z kontem użytkownika.
PO CO: Użytkownik zapisuje portale WP w bazie danych zamiast wpisywać
       credentials ręcznie przy każdym injeccie. Dropdown w InjectModal
       pobiera listę z GET /v1/portals.
JAK: Tabela wp_portals z FK do users(id), CASCADE delete.
     Credentials (wp_app_password) przechowywane jako plaintext (MVP).
     Docelowo szyfrowanie AES-256 (Faza 5+).
"""
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.db import Base


class WpPortal(Base):
    """WordPress portal saved by user for quick inject."""
    __tablename__ = "wp_portals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)            # np. "Kurier365"
    url = Column(String(512), nullable=False)             # np. "https://kurier365.pl"
    wp_username = Column(String(255), nullable=False)     # WP user login
    wp_app_password = Column(Text, nullable=False)        # WP Application Password
    profile_id = Column(String(100), nullable=True)       # np. "prawy", "kurier365"
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="portals")
