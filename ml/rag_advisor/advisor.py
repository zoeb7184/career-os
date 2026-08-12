"""
ml/rag_advisor/advisor.py
──────────────────────────
Node: rag_advisor

RAG-powered career advisor. Users ask natural language career questions
and get grounded, data-driven answers backed by the live job database.

Example questions:
  "What skills should I learn next to become a Senior Data Scientist?"
  "Which companies are hiring ML Engineers in Berlin right now?"
  "Why is my ATS score low for this job?"
  "What's the average salary for Python developers in Germany?"

Pipeline:
  1. Parse intent from question
  2. Retrieve relevant context (jobs, market stats, user resume)
  3. Build context-aware prompt
  4. Call LLM → stream or return response

Error codes:
  RAG_001 — User profile not found
  RAG_002 — LLM API error
  RAG_003 — Retrieval returned zero results
  RAG_004 — Context assembly failed
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from ml.shared.llm_client import get_llm_client, LLMError
from ml.shared.embedder import get_embedder

logger = get_logger("rag_advisor")


class RAGError(NodeError):
    pass


class QueryIntent(str, Enum):
    SKILL_ADVICE  = "skill_advice"    # "what should I learn?"
    JOB_MATCH     = "job_match"       # "which jobs match my profile?"
    MARKET_DATA   = "market_data"     # "what's the demand for X?"
    ATS_REASON    = "ats_reason"      # "why is my score low?"
    SALARY_INFO   = "salary_info"     # "what do ML engineers earn?"
    GENERAL       = "general"         # catch-all


SYSTEM_PROMPT = """You are a knowledgeable, honest career advisor for Data Science and Tech professionals.
You have access to live job market data — use it to give specific, data-backed advice.

Guidelines:
- Be direct and actionable. No filler text.
- Cite specific numbers and trends from the provided market data.
- If the data doesn't support a claim, say so.
- For skill recommendations, always explain WHY (market demand, salary impact, job availability).
- Keep responses focused and under 400 words unless detail is genuinely needed.
- Acknowledge gaps: if you don't have enough data to answer confidently, say so.

The user's context and relevant market data are provided below."""


@dataclass
class AdvisorResponse:
    answer:     str
    intent:     str
    sources:    list[str]    # descriptions of what data was used
    job_count:  int          # how many jobs were used as context


class RAGAdvisor:
    """
    Retrieval-augmented career advisor.
    Retrieves live job data + user context before calling the LLM.
    """

    def __init__(self) -> None:
        self._llm      = get_llm_client()
        self._embedder = get_embedder()

    def _detect_intent(self, question: str) -> QueryIntent:
        """Simple keyword-based intent detection."""
        q = question.lower()
        if any(w in q for w in ["learn", "skill", "course", "study", "should i know"]):
            return QueryIntent.SKILL_ADVICE
        if any(w in q for w in ["match", "find me", "which job", "recommend", "apply"]):
            return QueryIntent.JOB_MATCH
        if any(w in q for w in ["demand", "trend", "popular", "growing", "most needed", "hiring"]):
            return QueryIntent.MARKET_DATA
        if any(w in q for w in ["ats", "score", "low score", "rejected", "resume score"]):
            return QueryIntent.ATS_REASON
        if any(w in q for w in ["salary", "earn", "pay", "compensation", "wage"]):
            return QueryIntent.SALARY_INFO
        return QueryIntent.GENERAL

    def _retrieve_market_context(self, question: str, intent: QueryIntent, top_k: int = 8) -> tuple[list[dict], list[str]]:
        """
        Retrieve relevant job data from Qdrant based on the question.
        Returns (job_snippets, source_descriptions)
        """
        try:
            from qdrant_client import QdrantClient
            from app.config import settings

            client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)

            # Embed the question
            question_vector = self._embedder.embed_text(question)

            hits = client.search(
                collection_name = "jobs",
                query_vector    = question_vector,
                limit           = top_k,
                with_payload    = True,
            )

            snippets = []
            for hit in hits:
                p = hit.payload or {}
                snippets.append({
                    "title":      p.get("title", ""),
                    "company":    p.get("company", ""),
                    "location":   p.get("location", ""),
                    "skills":     p.get("skills", []),
                    "salary_min": p.get("salary_min"),
                    "salary_max": p.get("salary_max"),
                    "remote":     p.get("remote_type", ""),
                    "posted_at":  p.get("posted_at", ""),
                })

            sources = [f"Live job database ({len(snippets)} relevant listings retrieved)"]
            return snippets, sources

        except Exception as exc:
            logger.warning(f"Qdrant retrieval failed: {exc} — proceeding without job context")
            return [], []

    def _build_context_prompt(
        self,
        question:      str,
        intent:        QueryIntent,
        job_snippets:  list[dict],
        resume_summary: str | None,
        user_skills:   list[str],
    ) -> str:
        """Assemble the full context prompt for the LLM."""
        parts = []

        # User context
        if user_skills:
            parts.append(f"USER'S CURRENT SKILLS: {', '.join(user_skills[:20])}")
        if resume_summary:
            parts.append(f"USER'S RESUME SUMMARY:\n{resume_summary[:500]}")

        # Market data context
        if job_snippets:
            parts.append(f"\nRELEVANT JOB MARKET DATA ({len(job_snippets)} recent listings):")
            for i, job in enumerate(job_snippets[:6], 1):
                salary_str = ""
                if job.get("salary_min"):
                    salary_str = f" | Salary: {job['salary_min']:,.0f}–{job.get('salary_max', '?'):,.0f}"
                skills_str = ", ".join(job.get("skills", [])[:6])
                parts.append(
                    f"  {i}. {job['title']} @ {job.get('company','Unknown')} "
                    f"({job.get('location','?')}, {job.get('remote','?')}{salary_str})\n"
                    f"     Skills: {skills_str}"
                )
        else:
            parts.append("\nNOTE: Could not retrieve live job data for this query.")

        parts.append(f"\nUSER'S QUESTION: {question}")
        return "\n".join(parts)

    async def ask(
        self,
        question:       str,
        user_id:        str,
        resume_text:    str | None = None,
        user_skills:    list[str] | None = None,
        resume_summary: str | None = None,
    ) -> AdvisorResponse:
        """
        Answer a career question with RAG.

        Args:
            question:       The user's question.
            user_id:        For logging.
            resume_text:    Full resume text (optional but improves answers).
            user_skills:    User's canonical skill list.
            resume_summary: Short summary of user's background (faster than full text).

        Returns:
            AdvisorResponse with answer and metadata.
        """
        intent = self._detect_intent(question)
        logger.info("RAG advisor query", extra={"extra": {
            "user_id": user_id, "intent": intent, "question_len": len(question)
        }})

        # Retrieve relevant context
        job_snippets, sources = self._retrieve_market_context(question, intent)

        if not job_snippets:
            logger.warning("RAG_003: No job context retrieved", extra={"extra": {"user_id": user_id}})

        # Build prompt
        context = self._build_context_prompt(
            question       = question,
            intent         = intent,
            job_snippets   = job_snippets,
            resume_summary = resume_summary,
            user_skills    = user_skills or [],
        )

        # Call LLM
        try:
            answer = await self._llm.complete_text(
                system_prompt = SYSTEM_PROMPT,
                user_message  = context,
                temperature   = 0.5,
                max_tokens    = 600,
            )
        except LLMError as exc:
            raise RAGError("RAG_002", f"LLM call failed: {exc.message}",
                           {"user_id": user_id, "llm_code": exc.code})

        logger.info("RAG advisor response generated", extra={"extra": {
            "user_id":    user_id,
            "intent":     intent,
            "job_count":  len(job_snippets),
            "answer_len": len(answer),
        }})

        return AdvisorResponse(
            answer    = answer,
            intent    = intent.value,
            sources   = sources,
            job_count = len(job_snippets),
        )

    async def stream_ask(
        self,
        question:       str,
        user_id:        str,
        user_skills:    list[str] | None = None,
        resume_summary: str | None = None,
    ):
        """
        Streaming version of ask() — yields tokens for real-time chat UI.

        Usage in FastAPI:
            from fastapi.responses import StreamingResponse
            async def token_gen():
                async for chunk in advisor.stream_ask(question, user_id):
                    yield f"data: {chunk}\n\n"
            return StreamingResponse(token_gen(), media_type="text/event-stream")
        """
        intent = self._detect_intent(question)
        job_snippets, _ = self._retrieve_market_context(question, intent)
        context = self._build_context_prompt(
            question       = question,
            intent         = intent,
            job_snippets   = job_snippets,
            resume_summary = resume_summary,
            user_skills    = user_skills or [],
        )
        try:
            async for chunk in self._llm.stream_text(
                system_prompt = SYSTEM_PROMPT,
                user_message  = context,
                temperature   = 0.5,
            ):
                yield chunk
        except LLMError as exc:
            raise RAGError("RAG_002", f"LLM stream failed: {exc.message}")
