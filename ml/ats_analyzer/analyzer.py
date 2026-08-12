"""
ml/ats_analyzer/analyzer.py
─────────────────────────────
Node: ats_analyzer

The flagship feature. Computes an ATS score (0-100) for a resume against a job.

Score breakdown (total 100 pts):
  40 pts — Skill match:       how many required skills appear in the resume
  30 pts — Embedding sim:     semantic similarity between resume and job description
  20 pts — Structural score:  does resume have measurable achievements, action verbs, sections?
  10 pts — Keyword density:   does the job title / key terms appear in the resume?

Error codes:
  ATS_001 — Resume parse failed (corrupted or unsupported file)
  ATS_002 — Unsupported file format (not PDF or DOCX)
  ATS_003 — Job not found in database
  ATS_004 — Embedding timeout or failure
  ATS_005 — Unexpected scoring error
"""
from __future__ import annotations
import re
import time
from dataclasses import dataclass, field

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from ml.shared.embedder import get_embedder

logger = get_logger("ats_analyzer")


# ── Error types ────────────────────────────────────────────────────
class ATSError(NodeError):
    pass


# ── Data models ────────────────────────────────────────────────────
@dataclass
class ATSBreakdown:
    skill_match:    float = 0.0    # 0-40
    embedding_sim:  float = 0.0    # 0-30
    structural:     float = 0.0    # 0-20
    keyword:        float = 0.0    # 0-10


@dataclass
class ATSResult:
    overall_score:    float                  # 0-100
    breakdown:        ATSBreakdown
    missing_skills:   list[str]              # required skills not found in resume
    matched_skills:   list[str]              # required skills found in resume
    suggestions:      list[str]              # actionable improvement tips
    processing_ms:    int = 0
    resume_id:        str | None = None
    job_id:           str | None = None


# ── Resume parser ──────────────────────────────────────────────────
class ResumeParser:
    """Extracts plain text from PDF and DOCX resume files."""

    def parse_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            if not text.strip():
                raise ATSError("ATS_001", "PDF text extraction returned empty — may be image-based PDF",
                               status_code=422)
            return text
        except ATSError:
            raise
        except Exception as exc:
            raise ATSError("ATS_001", f"PDF parse failed: {exc}", {"error": str(exc)}, status_code=422)

    def parse_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX bytes using python-docx."""
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise ATSError("ATS_001", f"DOCX parse failed: {exc}", {"error": str(exc)}, status_code=422)

    def parse(self, file_bytes: bytes, filename: str) -> str:
        """
        Parse resume file. Auto-detects format from filename.

        Returns:
            Extracted plain text.

        Raises:
            ATSError ATS_001: Parse failed.
            ATSError ATS_002: Unsupported format.
        """
        ext = filename.lower().split(".")[-1]
        if ext == "pdf":
            return self.parse_pdf(file_bytes)
        elif ext in ("docx", "doc"):
            return self.parse_docx(file_bytes)
        else:
            raise ATSError("ATS_002", f"Unsupported file format: .{ext}. Upload PDF or DOCX.",
                           {"extension": ext}, status_code=422)


# ── Structural scorer ─────────────────────────────────────────────
class StructuralScorer:
    """
    Scores resume on structural quality signals.
    No ML — pure rule-based signals that correlate with strong resumes.
    """
    ACTION_VERBS = {
        "developed", "built", "led", "designed", "implemented", "deployed",
        "improved", "optimised", "optimized", "reduced", "increased", "created",
        "launched", "managed", "architected", "automated", "trained", "researched",
        "analysed", "analyzed", "delivered", "shipped", "published", "achieved"
    }
    SECTION_KEYWORDS = {"experience", "education", "skills", "projects", "certifications", "summary"}
    METRIC_PATTERN   = re.compile(r'\d+[%x\+]|\$[\d,]+|[\d,]+ (users|customers|requests|jobs|models|papers)', re.I)

    def score(self, resume_text: str) -> tuple[float, list[str]]:
        """
        Score resume structure. Returns (score_out_of_20, issues_list).
        """
        text_lower = resume_text.lower()
        words      = set(text_lower.split())
        score      = 0.0
        issues: list[str] = []

        # Signal 1: Has measurable achievements (numbers, %)  → up to 8 pts
        metrics = self.METRIC_PATTERN.findall(resume_text)
        metric_score = min(len(metrics) * 2, 8)
        score += metric_score
        if metric_score < 4:
            issues.append("Add quantified achievements (e.g. 'Reduced model inference time by 40%')")

        # Signal 2: Uses action verbs → up to 6 pts
        found_verbs = self.ACTION_VERBS.intersection(words)
        verb_score = min(len(found_verbs) * 1.5, 6)
        score += verb_score
        if verb_score < 3:
            issues.append("Start bullet points with strong action verbs (Built, Designed, Deployed...)")

        # Signal 3: Has clear sections → up to 4 pts
        found_sections = self.SECTION_KEYWORDS.intersection(words)
        section_score = min(len(found_sections) * 0.8, 4)
        score += section_score
        if section_score < 2:
            issues.append("Ensure resume has clear sections: Experience, Education, Skills, Projects")

        # Signal 4: Appropriate length (400–1500 words) → 2 pts
        word_count = len(resume_text.split())
        if 400 <= word_count <= 1500:
            score += 2
        elif word_count < 400:
            issues.append("Resume seems short — add more detail to your experience and projects")
        else:
            issues.append("Resume may be too long — aim for 1-2 pages (400-1500 words)")

        return min(score, 20.0), issues


# ── Main ATS Analyzer ─────────────────────────────────────────────
class ATSAnalyzer:
    """
    Main ATS scoring engine.
    Combines skill matching, embedding similarity, structural scoring, and keyword density.
    """

    def __init__(self) -> None:
        self._parser    = ResumeParser()
        self._struct    = StructuralScorer()
        self._embedder  = get_embedder()

    def analyze(
        self,
        resume_text: str,
        job_description: str,
        required_skills: list[str],
        job_title: str = "",
        resume_id: str | None = None,
        job_id: str | None = None,
    ) -> ATSResult:
        """
        Compute ATS score given resume text and job info.

        Args:
            resume_text:      Parsed plain text of the resume.
            job_description:  Full job description text.
            required_skills:  List of required skills from skill_extractor.
            job_title:        Job title for keyword scoring.

        Returns:
            ATSResult with overall score and breakdown.
        """
        start = time.perf_counter()
        logger.info("ATS analysis starting", extra={"extra": {"resume_id": resume_id, "job_id": job_id}})

        resume_lower = resume_text.lower()

        # ── Skill match score (40 pts) ───────────────────────────
        matched: list[str] = []
        missing: list[str] = []
        for skill in required_skills:
            # Simple presence check — skill name anywhere in resume
            if skill.lower() in resume_lower:
                matched.append(skill)
            else:
                missing.append(skill)

        skill_score = 0.0
        if required_skills:
            skill_score = (len(matched) / len(required_skills)) * 40

        # ── Embedding similarity (30 pts) ────────────────────────
        try:
            resume_vec = self._embedder.embed_chunks(resume_text)[0]
            job_vec    = self._embedder.embed_chunks(job_description)[0]
            cosine_sim = self._embedder.cosine_similarity(resume_vec, job_vec)
            # Map cosine sim [0,1] → [0,30] pts (values below 0.3 are very low)
            embedding_score = max(0.0, (cosine_sim - 0.2) / 0.8) * 30
        except Exception as exc:
            logger.error(f"Embedding failed: {exc}", extra={"extra": {"error_code": "ATS_004"}})
            raise ATSError("ATS_004", f"Embedding failed: {exc}", status_code=503)

        # ── Structural score (20 pts) ────────────────────────────
        structural_score, structural_issues = self._struct.score(resume_text)

        # ── Keyword density (10 pts) ─────────────────────────────
        title_words = set(re.findall(r'\b\w+\b', job_title.lower()))
        title_words -= {"and", "or", "the", "a", "an", "in", "for", "with", "of"}
        keyword_hits = sum(1 for w in title_words if w in resume_lower)
        keyword_score = min((keyword_hits / max(len(title_words), 1)) * 10, 10)

        # ── Total ────────────────────────────────────────────────
        overall = skill_score + embedding_score + structural_score + keyword_score

        # ── Generate suggestions ─────────────────────────────────
        suggestions: list[str] = list(structural_issues)
        if missing:
            top_missing = missing[:5]
            suggestions.append(f"Add missing skills to your resume: {', '.join(top_missing)}")
        if embedding_score < 15:
            suggestions.append(
                "Your resume and the job description have low semantic overlap. "
                "Tailor your summary and bullet points to mirror the job's language."
            )
        if keyword_score < 5:
            suggestions.append(f"Include the job title keywords in your resume: '{job_title}'")

        elapsed_ms = round((time.perf_counter() - start) * 1000)

        result = ATSResult(
            overall_score  = round(overall, 1),
            breakdown      = ATSBreakdown(
                skill_match   = round(skill_score, 1),
                embedding_sim = round(embedding_score, 1),
                structural    = round(structural_score, 1),
                keyword       = round(keyword_score, 1),
            ),
            missing_skills = missing,
            matched_skills = matched,
            suggestions    = suggestions,
            processing_ms  = elapsed_ms,
            resume_id      = resume_id,
            job_id         = job_id,
        )

        logger.info(
            "ATS analysis complete",
            extra={"extra": {
                "resume_id":    resume_id,
                "job_id":       job_id,
                "overall":      result.overall_score,
                "skill_match":  result.breakdown.skill_match,
                "embedding_sim": result.breakdown.embedding_sim,
                "structural":   result.breakdown.structural,
                "missing_count": len(missing),
                "elapsed_ms":   elapsed_ms,
            }}
        )
        return result

    def analyze_from_file(
        self,
        file_bytes: bytes,
        filename: str,
        job_description: str,
        required_skills: list[str],
        job_title: str = "",
        resume_id: str | None = None,
        job_id: str | None = None,
    ) -> ATSResult:
        """
        Parse a resume file and then run analysis.
        Convenience wrapper for the API endpoint.
        """
        resume_text = self._parser.parse(file_bytes, filename)
        return self.analyze(
            resume_text     = resume_text,
            job_description = job_description,
            required_skills = required_skills,
            job_title       = job_title,
            resume_id       = resume_id,
            job_id          = job_id,
        )
