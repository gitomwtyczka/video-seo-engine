import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from api.db import Base

class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    state_token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    @staticmethod
    def create_for_user(user_id):
        return OAuthState(
            user_id=user_id,
            state_token=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
        )

    def is_valid(self):
        return datetime.now(timezone.utc) < self.expires_at
