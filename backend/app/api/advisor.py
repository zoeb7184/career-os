"""
backend/app/api/advisor.py
────────────────────────────
RAG Career Advisor API endpoints.

POST /api/v1/advisor/ask        — Single Q&A response
POST /api/v1/advisor/stream     — Streaming response (Server-Sent Events)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logger import get_logger

logger = get_logger("api_advisor")
router = APIRouter()


class AskRequest(BaseModel):
    question:       str
    user_id:        str
    resume_summary: str | None = None
    user_skills:    list[str] | None = None


@router.post("/ask", summary="Ask the career advisor a question")
async def ask_advisor(request: AskRequest):
    """
    Ask a career question. Returns a complete answer.

    Examples:
    - "What skills should I learn next to become a Senior Data Scientist?"
    - "Which companies in Germany are hiring ML engineers right now?"
    - "What's the average salary for Python developers in the UK?"
    """
    from ml.rag_advisor.advisor import RAGAdvisor

    advisor  = RAGAdvisor()
    response = await advisor.ask(
        question       = request.question,
        user_id        = request.user_id,
        user_skills    = request.user_skills or [],
        resume_summary = request.resume_summary,
    )

    return JSONResponse(content={
        "data": {
            "answer":    response.answer,
            "intent":    response.intent,
            "sources":   response.sources,
            "job_count": response.job_count,
        },
        "error": None,
    })


@router.post("/stream", summary="Ask the career advisor (streaming response)")
async def stream_advisor(request: AskRequest):
    """
    Streaming version — tokens arrive in real time for the chat UI.
    Uses Server-Sent Events (SSE) format.

    Frontend usage:
        const evtSource = new EventSource('/api/v1/advisor/stream');
        evtSource.onmessage = (e) => appendToChat(e.data);
    """
    from ml.rag_advisor.advisor import RAGAdvisor
    advisor = RAGAdvisor()

    async def token_generator():
        try:
            async for chunk in advisor.stream_ask(
                question       = request.question,
                user_id        = request.user_id,
                user_skills    = request.user_skills or [],
                resume_summary = request.resume_summary,
            ):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            logger.error(f"Stream error: {exc}")
            yield f"data: [ERROR] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
