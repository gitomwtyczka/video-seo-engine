"""
SQLAlchemy ORM model: YouTubeChannel.
"""
from datetime import datetime
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime,
    ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.db import Base


class YouTubeChannel(Base):
    """YouTube channel authorized via OAuth."""
    __tablename__ = "youtube_channels"

    id = Column(String(255), primary_key=True)  # YouTube Channel ID
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=True)  # Channel Title
    refresh_token = Column(String(1024), nullable=False)
    footer_text = Column(Text, default="", nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="youtube_channels")
