"""
SQLAlchemy ORM model: WpPortal.

CO: Model portalu WordPress powiązanego z kontem użytkownika.
PO CO: Użytkownik zapisuje portale WP w bazie danych zamiast wpisywać
       credentials ręcznie przy każdym injeccie. Dropdown w InjectModal
       pobiera listę z GET /v1/portals. Obsługuje również auto-parowanie
       wtyczki WordPress v3.0 przez token (auth_mode="plugin_token").
JAK: Tabela wp_portals z FK do users(id), CASCADE delete oraz opcjonalnym
     FK api_key_id do api_keys(id).
"""
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.db import Base


class WpPortal(Base):
    """WordPress portal saved by user for quick inject or paired via VSE WP Plugin v3.0."""
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
    wp_username: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    wp_app_password: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    auth_mode: Mapped[str] = mapped_column(
        String(32), default="app_password", server_default="app_password", nullable=False
    )  # "app_password" | "plugin_token"
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_id = Column(String(100), nullable=True)       # np. "prawy", "kurier365"
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="portals")
