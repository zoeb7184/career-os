"""
backend/app/main.py
────────────────────
FastAPI application — all routers registered, all middleware wired.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.logger import get_logger
from app.errors import NodeError
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.error_handler import (
    node_error_handler, validation_error_handler, unhandled_error_handler,
)

from app.api.health      import router as health_router
from app.api.auth        import router as auth_router
from app.api.jobs        import router as jobs_router
from app.api.ats         import router as ats_router
from app.api.recommend   import router as recommend_router
from app.api.advisor     import router as advisor_router
from app.api.analytics   import router as analytics_router
from app.api.resumes     import router as resumes_router
from app.api.applications import router as applications_router

logger = get_logger("career_os")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Career OS API starting", extra={"extra": {"environment": settings.environment}})
    try:
        await _ensure_qdrant_collections()
        logger.info("Qdrant collections ready")
    except Exception as exc:
        logger.warning(f"Qdrant setup failed at startup: {exc}")
    yield
    logger.info("Career OS API shutting down")


async def _ensure_qdrant_collections():
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=10)
    existing = {c.name for c in client.get_collections().collections}
    for name in ("jobs", "resumes"):
        if name not in existing:
            client.create_collection(name, vectors_config=VectorParams(size=384, distance=Distance.COSINE))
            logger.info(f"Created Qdrant collection: {name}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Career OS API",
        description="AI-powered Career Operating System",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(NodeError, node_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    # Routes
    app.include_router(health_router)
    app.include_router(auth_router,         prefix=f"{settings.api_prefix}/auth",         tags=["Auth"])
    app.include_router(jobs_router,         prefix=f"{settings.api_prefix}/jobs",         tags=["Jobs"])
    app.include_router(ats_router,          prefix=f"{settings.api_prefix}/ats",          tags=["ATS"])
    app.include_router(recommend_router,    prefix=f"{settings.api_prefix}/recommend",    tags=["Recommend"])
    app.include_router(advisor_router,      prefix=f"{settings.api_prefix}/advisor",      tags=["Advisor"])
    app.include_router(analytics_router,    prefix=f"{settings.api_prefix}/analytics",    tags=["Analytics"])
    app.include_router(resumes_router,      prefix=f"{settings.api_prefix}/resumes",      tags=["Resumes"])
    app.include_router(applications_router, prefix=f"{settings.api_prefix}/applications", tags=["Applications"])

    @app.get("/", tags=["Root"])
    async def root():
        return {"app": "Career OS API", "version": "1.0.0",
                "docs": "/docs", "health": "/health"}

    return app


app = create_app()
