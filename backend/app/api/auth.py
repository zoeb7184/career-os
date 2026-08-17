"""
backend/app/api/auth.py
────────────────────────
Authentication endpoints.

POST /api/v1/auth/register  — create account
POST /api/v1/auth/login     — get JWT token
GET  /api/v1/auth/me        — get current user (protected)
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logger import get_logger

logger = get_logger("auth")
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


_PASSWORD_NUMBER_OR_SPECIAL_RE = re.compile(r"[0-9!@#$%^&*]")


def _validate_password(password: str) -> str | None:
    """Server-side mirror of the frontend's minimum bar — the strength meter
    is advisory UX, this is the actual gate. Returns an error message if the
    password fails validation, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not _PASSWORD_NUMBER_OR_SPECIAL_RE.search(password):
        return "Password must contain at least one number or special character (!@#$%^&*)."
    return None


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency — validates JWT and returns user dict. Use in protected endpoints."""
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key,
                             algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(text("SELECT id, email FROM users WHERE id = :id"), {"id": user_id})
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": user[0], "email": user[1]}


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    password_error = _validate_password(request.password)
    if password_error:
        return JSONResponse(status_code=400, content={
            "data": None, "error": {"code": "AUTH_003", "message": password_error, "detail": {}}
        })
    # Check email not taken
    existing = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": request.email})
    if existing.fetchone():
        return JSONResponse(status_code=400, content={
            "data": None, "error": {"code": "AUTH_001", "message": "Email already registered", "detail": {}}
        })
    user_id = str(uuid.uuid4())
    hashed = pwd_context.hash(request.password)
    await db.execute(text("""
        INSERT INTO users (id, email, password_hash, provider)
        VALUES (:id, :email, :hash, 'email')
    """), {"id": user_id, "email": request.email, "hash": hashed})
    await db.commit()
    token = create_token(user_id)
    logger.info("User registered", extra={"extra": {"user_id": user_id, "email": request.email}})
    return JSONResponse(content={"data": {"token": token, "user_id": user_id, "email": request.email}, "error": None})


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, password_hash FROM users WHERE email = :e"), {"e": request.email}
    )
    row = result.fetchone()
    if not row or not pwd_context.verify(request.password, row[1]):
        return JSONResponse(status_code=401, content={
            "data": None, "error": {"code": "AUTH_002", "message": "Invalid email or password", "detail": {}}
        })
    token = create_token(row[0])
    logger.info("User logged in", extra={"extra": {"user_id": row[0]}})
    return JSONResponse(content={"data": {"token": token, "user_id": row[0], "email": request.email}, "error": None})


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return JSONResponse(content={"data": current_user, "error": None})
