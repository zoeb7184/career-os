"""
ml/ats_analyzer/tests/test_analyzer.py
Tests for the ATS analyzer node.
Run: make test-node N=ats_analyzer
"""
import pytest
from ml.ats_analyzer.analyzer import ATSAnalyzer, ResumeParser, StructuralScorer, ATSError


# ── StructuralScorer tests ─────────────────────────────────────────

def test_structural_scorer_metrics():
    """Resume with quantified achievements scores higher."""
    scorer = StructuralScorer()
    good_resume = """
    Experience:
    Developed ML pipeline that reduced inference time by 40%
    Built recommendation system serving 1M+ users
    Led team of 5 engineers to deliver project 2 weeks early
    Skills: Python, TensorFlow, AWS
    Education: MSc Computer Science
    """
    score, issues = scorer.score(good_resume)
    assert score >= 12, f"Expected >= 12, got {score}"
    assert len(issues) <= 2


def test_structural_scorer_weak_resume():
    """Resume with no metrics or action verbs scores low."""
    scorer = StructuralScorer()
    weak_resume = "I worked at a company. I did some things. Python."
    score, issues = scorer.score(weak_resume)
    assert score <= 8
    assert len(issues) >= 2


def test_structural_scorer_max_20():
    """Score never exceeds 20 (the component max)."""
    scorer = StructuralScorer()
    great_resume = " ".join([
        "Developed Built Led Designed Implemented Deployed Improved Automated",
        "Reduced latency by 50%, increased revenue by $2M, trained 10 models",
        "Experience Education Skills Projects Certifications Summary",
        "Python TensorFlow PyTorch Docker Kubernetes " * 20,
    ])
    score, _ = scorer.score(great_resume)
    assert score <= 20.0


# ── ATS Analyzer integration tests ────────────────────────────────

def test_ats_high_match():
    """Resume that strongly matches a job should score >= 60."""
    analyzer = ATSAnalyzer()
    resume = """
    Senior Data Scientist with 5 years experience.
    Developed machine learning models using Python and TensorFlow.
    Built data pipelines with Apache Spark and SQL.
    Deployed models to AWS using Docker and Kubernetes.
    Improved model accuracy by 25% through feature engineering.
    Education: MSc Data Science, University of Berlin.
    Skills: Python, TensorFlow, PyTorch, SQL, Spark, AWS, Docker
    """
    job_desc = """
    We are looking for a Data Scientist with:
    - 3+ years Python experience
    - Machine learning model development (TensorFlow, PyTorch)
    - SQL and data pipeline experience
    - Cloud deployment (AWS)
    - Strong communication skills
    """
    result = analyzer.analyze(
        resume_text     = resume,
        job_description = job_desc,
        required_skills = ["Python", "TensorFlow", "SQL", "AWS"],
        job_title       = "Data Scientist",
    )
    assert result.overall_score >= 55, f"Expected >= 55, got {result.overall_score}"
    assert "Python" in result.matched_skills
    assert isinstance(result.suggestions, list)
    assert result.processing_ms > 0


def test_ats_low_match():
    """Completely irrelevant resume should score < 30."""
    analyzer = ATSAnalyzer()
    result = analyzer.analyze(
        resume_text     = "I am a chef. I cook food. I managed a kitchen for 10 years.",
        job_description = "Senior ML Engineer needed. TensorFlow, PyTorch, Python required.",
        required_skills = ["Python", "TensorFlow", "PyTorch", "MLOps", "Kubernetes"],
        job_title       = "Senior ML Engineer",
    )
    assert result.overall_score < 30
    assert len(result.missing_skills) >= 3


def test_ats_missing_skills_populated():
    """Missing skills should include skills from job not in resume."""
    analyzer = ATSAnalyzer()
    result = analyzer.analyze(
        resume_text     = "Python developer with SQL experience.",
        job_description = "Need Python, SQL, Kubernetes, and Terraform experience.",
        required_skills = ["Python", "SQL", "Kubernetes", "Terraform"],
        job_title       = "DevOps Engineer",
    )
    assert "Kubernetes" in result.missing_skills or "Terraform" in result.missing_skills


def test_ats_suggestions_not_empty():
    """Suggestions list should never be empty — always actionable feedback."""
    analyzer = ATSAnalyzer()
    result = analyzer.analyze(
        resume_text     = "I have some skills.",
        job_description = "We need Python, SQL, Docker.",
        required_skills = ["Python", "SQL", "Docker"],
        job_title       = "Backend Developer",
    )
    assert len(result.suggestions) > 0


def test_ats_breakdown_sums_to_overall():
    """Sum of breakdown components should equal overall score."""
    analyzer = ATSAnalyzer()
    result = analyzer.analyze(
        resume_text     = "Python developer. Built APIs with FastAPI. Deployed to AWS.",
        job_description = "Python developer needed. FastAPI, AWS, Docker.",
        required_skills = ["Python", "FastAPI", "AWS"],
        job_title       = "Python Developer",
    )
    expected_sum = (
        result.breakdown.skill_match +
        result.breakdown.embedding_sim +
        result.breakdown.structural +
        result.breakdown.keyword
    )
    assert abs(result.overall_score - expected_sum) < 0.5, \
        f"Overall {result.overall_score} ≠ sum {expected_sum}"


# ── Resume Parser tests ────────────────────────────────────────────

def test_parser_rejects_unknown_format():
    """Parser must raise ATS_002 for unsupported formats."""
    parser = ResumeParser()
    with pytest.raises(ATSError) as exc_info:
        parser.parse(b"some content", "resume.txt")
    assert exc_info.value.code == "ATS_002"


def test_parser_raises_ats_001_on_empty_pdf():
    """Parser raises ATS_001 when PDF has no extractable text."""
    import fitz
    # Create minimal empty PDF
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = ResumeParser()
    with pytest.raises(ATSError) as exc_info:
        parser.parse(pdf_bytes, "empty.pdf")
    assert exc_info.value.code == "ATS_001"
