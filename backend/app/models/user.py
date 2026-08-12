"""
backend/app/models/user.py
User accounts — supports email/password and Google OAuth.
"""
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id:            Mapped[str]         = mapped_column(String(36), primary_key=True)
    email:         Mapped[str]         = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None]  = mapped_column(String(255))       # null for OAuth users
    provider:      Mapped[str]         = mapped_column(String(20), default="email")  # "email" | "google"
    provider_id:   Mapped[str | None]  = mapped_column(String(255))       # Google sub id
    created_at:    Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:    Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    preferences:   Mapped[dict]        = mapped_column(JSON, default=dict)  # job prefs, location, etc.

    def __repr__(self) -> str:
        return f"<User {self.id} | {self.email} ({self.provider})>"
