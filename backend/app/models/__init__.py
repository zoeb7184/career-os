"""
backend/app/models/__init__.py
Import all models here so Alembic can auto-detect them for migrations.
"""
from app.models.application import Application
from app.models.job import Job
from app.models.user import User

__all__ = ["Application", "Job", "User"]
