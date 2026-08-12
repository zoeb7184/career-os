"""
ml/shared/llm_client.py
────────────────────────
Single shared LLM client for the entire project.
Uses Groq (free) — OpenAI-compatible API, no credit card needed.
All ML nodes import from here — never instantiate the client directly.

Provider: Groq (https://console.groq.com) — FREE tier
Models used:
  - Extraction: llama-3.1-8b-instant  (fast, cheap, great for structured output)
  - Advisor:    llama-3.3-70b-versatile (smarter, for RAG Q&A responses)

Why centralised:
  - One place to swap providers/models
  - Consistent error handling → LLM_001 error code everywhere
  - Easy to mock in tests

Usage:
    from ml.shared.llm_client import get_llm_client
    client = get_llm_client()

    # Structured JSON output (skill extraction, etc.)
    result = await client.complete_json(
        system_prompt="Extract skills from job descriptions. Return JSON only.",
        user_message=job_description,
    )

    # Plain text (advisor responses)
    text = await client.complete_text(
        system_prompt="You are a career advisor.",
        user_message="What skills should I learn next?",
    )
"""
from __future__ import annotations
import json
import time
from functools import lru_cache
from typing import Any
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError

logger = get_logger("llm_client")


class LLMError(NodeError):
    """LLM_001: API call failed. LLM_002: Response not valid JSON. LLM_003: Rate limit."""
    pass


class LLMClient:
    """
    Thin wrapper around the Groq API (OpenAI-compatible).
    Groq is free — sign up at https://console.groq.com
    """

    # Groq base URL — this is the only difference from OpenAI
    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self) -> None:
        try:
            import openai
            from app.config import settings

            if not settings.groq_api_key:
                raise LLMError("LLM_000", "GROQ_API_KEY not set in .env — get a free key at https://console.groq.com")

            # Groq uses the OpenAI SDK — just point base_url to Groq
            self._client = openai.AsyncOpenAI(
                api_key  = settings.groq_api_key,
                base_url = self.GROQ_BASE_URL,
            )
            self._extraction_model = settings.groq_model_extraction
            self._advisor_model    = settings.groq_model_advisor

            logger.info("LLM client initialised (Groq)", extra={"extra": {
                "provider":         "groq",
                "extraction_model": self._extraction_model,
                "advisor_model":    self._advisor_model,
            }})
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError("LLM_000", f"Failed to initialise Groq client: {exc}")

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """
        Call the LLM and parse the response as JSON.
        temperature=0.0 for deterministic extraction tasks.

        Returns:
            Parsed dict from the LLM's JSON response.

        Raises:
            LLMError LLM_001: API call failed.
            LLMError LLM_002: Response was not valid JSON.
            LLMError LLM_003: Rate limit exceeded.
        """
        model = model or self._extraction_model
        start = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},   # forces JSON output
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
            )
        except Exception as exc:
            error_str = str(exc)
            code = "LLM_003" if "rate_limit" in error_str.lower() else "LLM_001"
            logger.error(f"LLM API call failed: {exc}", extra={"extra": {"error_code": code, "model": model}})
            raise LLMError(code, f"LLM API call failed: {exc}", {"model": model})

        elapsed_ms = round((time.perf_counter() - start) * 1000)
        raw = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        logger.info("LLM call complete", extra={"extra": {
            "model":      model,
            "tokens":     tokens,
            "elapsed_ms": elapsed_ms,
        }})

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"LLM returned invalid JSON: {raw[:200]}", extra={"extra": {"error_code": "LLM_002"}})
            raise LLMError("LLM_002", "LLM response was not valid JSON", {"raw_response": raw[:500]})

    async def complete_text(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Call the LLM and return plain text response.
        temperature=0.7 for creative/advisory responses.

        Returns:
            String response from the model.
        """
        model = model or self._advisor_model
        start = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
            )
        except Exception as exc:
            error_str = str(exc)
            code = "LLM_003" if "rate_limit" in error_str.lower() else "LLM_001"
            raise LLMError(code, f"LLM API call failed: {exc}", {"model": model})

        elapsed_ms = round((time.perf_counter() - start) * 1000)
        tokens = response.usage.total_tokens if response.usage else 0
        logger.info("LLM text call complete", extra={"extra": {
            "model": model, "tokens": tokens, "elapsed_ms": elapsed_ms
        }})

        return response.choices[0].message.content or ""

    async def stream_text(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.7,
    ):
        """
        Stream LLM response token by token.
        Used by the RAG advisor for real-time chat responses.

        Usage:
            async for chunk in client.stream_text(system, user):
                yield chunk   # send to frontend via SSE
        """
        model = model or self._advisor_model
        try:
            stream = await self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=1500,
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError("LLM_001", f"LLM stream failed: {exc}", {"model": model})


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Get the shared LLMClient singleton."""
    return LLMClient()
