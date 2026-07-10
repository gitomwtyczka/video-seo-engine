"""
SQLAlchemy ORM model: YouTubeChannel.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime,
    ForeignKey, Text, LargeBinary, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.db import Base
from api.services.crypto import encrypt_token, decrypt_token


class YouTubeChannel(Base):
    """YouTube channel authorized via OAuth."""
    __tablename__ = "youtube_channels"
    __table_args__ = (
        UniqueConstraint("user_id", "youtube_channel_id", name="uq_user_yt_channel"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    youtube_channel_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    refresh_token_encrypted = Column(LargeBinary, nullable=True)
    footer_text = Column(Text, default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="youtube_channels")

    @property
    def refresh_token(self):
        if self.refresh_token_encrypted is None:
            return None
        return decrypt_token(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value):
        self.refresh_token_encrypted = encrypt_token(value) if value else None
