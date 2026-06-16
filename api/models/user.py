"""
SQLAlchemy ORM models: User, Plan, UsageLog, ApiKey.
"""
from datetime import datetime
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer,
    ForeignKey, Enum, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.db import Base


class PlanName(str, PyEnum):
    free = "free"
    starter = "starter"
    pro = "pro"
    agency = "agency"


class Plan(Base):
    """Subscription plan definition with quota limits."""
    __tablename__ = "plans"

    id = Column(String(50), primary_key=True)  # e.g. 'free', 'starter'
    display_name = Column(String(100), nullable=False)
    monthly_quota = Column(Integer, nullable=False)  # -1 = unlimited
    wp_sites_limit = Column(Integer, nullable=False, default=0)
    api_access = Column(Boolean, default=False)
    price_pln = Column(Integer, nullable=False, default=0)  # grosz (PLN * 100)
    stripe_price_id = Column(String(200), nullable=True)

    users = relationship("User", back_populates="plan")


class User(Base):
    """User account with auth and subscription info."""
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # None if OAuth-only
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    # OAuth
    google_id = Column(String(255), nullable=True, unique=True)

    # Subscription
    plan_id = Column(String(50), ForeignKey("plans.id"), default="free")
    plan = relationship("Plan", back_populates="users")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Verification
    verification_token = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    usage_logs = relationship("UsageLog", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
    portals = relationship("WpPortal", back_populates="user", cascade="all, delete-orphan")


class UsageLog(Base):
    """Records each pipeline execution for quota tracking."""
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint = Column(String(100), nullable=False, default="/v1/process")
    youtube_id = Column(String(50), nullable=True)
    success = Column(Boolean, default=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="usage_logs")


class ApiKey(Base):
    """API key for Pro/Agency users (programmatic access)."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    name = Column(String(100), nullable=False, default="Default")
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="api_keys")
