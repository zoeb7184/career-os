"""
ml/skill_extractor/extractor.py
────────────────────────────────
Node: skill_extractor

Uses GPT-4o-mini to extract structured skill data from raw job descriptions.
Runs once per job at ingestion time — results stored in job_skills table.

This is the core NLP showcase of the project:
  - Structured output extraction via JSON mode
  - Skill canonicalisation pipeline
  - Batch processing with cost tracking

Error codes:
    SKEX_001 — LLM call failed
    SKEX_002 — Response missing required fields
    SKEX_003 — Database write failed
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from ml.shared.llm_client import get_llm_client, LLMError

logger = get_logger("skill_extractor")

SYSTEM_PROMPT = """You are a technical skill extractor for job postings.
Extract ALL skills, tools, technologies, and requirements from the job description.

Return ONLY valid JSON with this exact structure:
{
    "required_skills":   ["Python", "SQL", "Docker"],
    "preferred_skills":  ["Kubernetes", "Spark"],
    "experience_years":  3,
    "education":         "Bachelor's in Computer Science or related field",
    "job_level":         "mid",
    "soft_skills":       ["communication", "teamwork"],
    "technologies":      ["AWS", "PostgreSQL", "Redis"],
    "certifications":    []
}

Rules:
- job_level must be: "junior" | "mid" | "senior" | "lead" | "unknown"
- experience_years: integer or null if not mentioned
- Use canonical names (Python not python3, TensorFlow not tensorflow)
- required_skills: MUST have, preferred_skills: nice to have
- Do not include soft skills in required/preferred_skills
- Return ONLY the JSON, no other text"""


@dataclass
class ExtractedSkills:
    required_skills:   list[str] = field(default_factory=list)
    preferred_skills:  list[str] = field(default_factory=list)
    experience_years:  int | None = None
    education:         str | None = None
    job_level:         str = "unknown"
    soft_skills:       list[str] = field(default_factory=list)
    technologies:      list[str] = field(default_factory=list)
    certifications:    list[str] = field(default_factory=list)


class SkillExtractorError(NodeError):
    pass


class SkillExtractor:
    """
    Extracts structured skill data from job descriptions using GPT-4o-mini.
    """

    def __init__(self) -> None:
        self._client = get_llm_client()

    async def extract(self, job_description: str, job_id: str | None = None) -> ExtractedSkills:
        """
        Extract skills from a single job description.

        Args:
            job_description: Raw text of the job description.
            job_id:          Optional UUID for logging.

        Returns:
            ExtractedSkills dataclass.

        Raises:
            SkillExtractorError SKEX_001: LLM call failed.
            SkillExtractorError SKEX_002: Response missing required fields.
        """
        if not job_description or len(job_description.strip()) < 50:
            logger.warning("Job description too short to extract skills", extra={"extra": {"job_id": job_id}})
            return ExtractedSkills()

        # Truncate to ~8000 chars (well within GPT-4o-mini context)
        truncated = job_description[:8000]

        try:
            result = await self._client.complete_json(
                system_prompt=SYSTEM_PROMPT,
                user_message=truncated,
                temperature=0.0,
                max_tokens=800,
            )
        except LLMError as exc:
            raise SkillExtractorError("SKEX_001", f"LLM extraction failed: {exc.message}",
                                      {"job_id": job_id, "llm_code": exc.code})

        # Validate response shape
        if "required_skills" not in result:
            raise SkillExtractorError(
                "SKEX_002",
                "LLM response missing required_skills field",
                {"job_id": job_id, "keys_returned": list(result.keys())}
            )

        logger.info(
            "Skills extracted",
            extra={"extra": {
                "job_id":         job_id,
                "required_count": len(result.get("required_skills", [])),
                "preferred_count": len(result.get("preferred_skills", [])),
                "job_level":      result.get("job_level", "unknown"),
            }}
        )

        return ExtractedSkills(
            required_skills  = result.get("required_skills", []),
            preferred_skills = result.get("preferred_skills", []),
            experience_years = result.get("experience_years"),
            education        = result.get("education"),
            job_level        = result.get("job_level", "unknown"),
            soft_skills      = result.get("soft_skills", []),
            technologies     = result.get("technologies", []),
            certifications   = result.get("certifications", []),
        )

    async def extract_batch(
        self, jobs: list[tuple[str, str]], concurrency: int = 5
    ) -> dict[str, ExtractedSkills]:
        """
        Extract skills from multiple jobs with controlled concurrency.
        Avoids hammering the OpenAI API with too many simultaneous requests.

        Args:
            jobs:        List of (job_id, description) tuples.
            concurrency: Max simultaneous LLM calls.

        Returns:
            Dict of {job_id: ExtractedSkills}
        """
        sem = asyncio.Semaphore(concurrency)
        results: dict[str, ExtractedSkills] = {}

        async def _extract_one(job_id: str, description: str) -> None:
            async with sem:
                try:
                    results[job_id] = await self.extract(description, job_id)
                except SkillExtractorError as exc:
                    logger.error(
                        f"Failed to extract skills for job {job_id}: {exc.code}",
                        extra={"extra": {"error_code": exc.code, "job_id": job_id}}
                    )
                    results[job_id] = ExtractedSkills()   # empty fallback

        await asyncio.gather(*[_extract_one(jid, desc) for jid, desc in jobs])
        logger.info(f"Batch extraction complete: {len(results)} jobs processed")
        return results
