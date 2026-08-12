"""
backend/app/models/job.py
──────────────────────────
SQLAlchemy model for the jobs table.
Every job ingested from any source goes here.
"""
from datetime import datetime
from sqlalchemy import String, Text, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id:               Mapped[str]           = mapped_column(String(36), primary_key=True)
    source:           Mapped[str]           = mapped_column(String(50), nullable=False)        # "adzuna" | "reed"
    external_id:      Mapped[str]           = mapped_column(String(255), nullable=False)
    title:            Mapped[str]           = mapped_column(String(500), nullable=False)
    company:          Mapped[str | None]    = mapped_column(String(500))
    location:         Mapped[str | None]    = mapped_column(String(500))
    country:          Mapped[str | None]    = mapped_column(String(10))
    remote_type:      Mapped[str | None]    = mapped_column(String(20))                        # "remote" | "hybrid" | "onsite"
    salary_min:       Mapped[float | None]  = mapped_column(Numeric(12, 2))
    salary_max:       Mapped[float | None]  = mapped_column(Numeric(12, 2))
    description:      Mapped[str | None]    = mapped_column(Text)
    url:              Mapped[str | None]    = mapped_column(String(1000))                      # link to original posting
    description_hash: Mapped[str | None]    = mapped_column(String(64))                        # SHA256 for dedup
    posted_at:        Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    expires_at:       Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    is_active:        Mapped[bool]          = mapped_column(Boolean, default=True)
    ingested_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding_id:     Mapped[str | None]    = mapped_column(String(100))                       # Qdrant point ID

    def __repr__(self) -> str:
        return f"<Job {self.id} | {self.title} @ {self.company} ({self.source})>"
