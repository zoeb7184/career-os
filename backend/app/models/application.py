"""
backend/app/models/application.py
Job applications tracked by the user (the Kanban board data).
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id:         Mapped[str]        = mapped_column(String(36), primary_key=True)
    user_id:    Mapped[str]        = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id:     Mapped[str]        = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    status:     Mapped[str]        = mapped_column(String(30), default="saved")  # saved|applied|interview|offer|rejected
    ats_score:  Mapped[float|None] = mapped_column(Float)
    notes:      Mapped[str | None] = mapped_column(Text)
    # Smart Import fields — null for jobs saved the normal way from /jobs
    applied_at: Mapped[date | None]  = mapped_column(Date)                  # when the user actually applied (from the import file, or set manually)
    platform:   Mapped[str | None]   = mapped_column(String(100))           # LinkedIn / Indeed / Stepstone / ... — where the application came from
    import_id:  Mapped[str | None]   = mapped_column(String(36), ForeignKey("imports.id", ondelete="SET NULL"))
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Application {self.id} | user={self.user_id} job={self.job_id} status={self.status}>"
