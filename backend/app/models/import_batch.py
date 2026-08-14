"""
backend/app/models/import_batch.py
Smart Import — one row per uploaded file, tracking how many applications
it produced. Populated by POST /api/v1/import/confirm.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportBatch(Base):
    __tablename__ = "imports"

    id:               Mapped[str]        = mapped_column(String(36), primary_key=True)
    user_id:          Mapped[str]        = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename:         Mapped[str]        = mapped_column(String(500))
    file_type:        Mapped[str]        = mapped_column(String(10))   # "xlsx" | "pdf"
    total_rows:       Mapped[int]        = mapped_column(Integer, default=0)    # rows detected in the file
    imported_rows:    Mapped[int]        = mapped_column(Integer, default=0)    # rows actually inserted
    skipped_rows:     Mapped[int]        = mapped_column(Integer, default=0)    # rows the user excluded (dupes etc.)
    duplicate_count:  Mapped[int]        = mapped_column(Integer, default=0)
    status_counts:    Mapped[dict]       = mapped_column(JSON, default=dict)    # {"applied": 8, "interview": 4, ...}
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<ImportBatch {self.id} | {self.filename} ({self.imported_rows}/{self.total_rows})>"
