"""
ml/ats_analyzer/health.py
Health check for the ATS analyzer node.
Tests: embedding model loadable, PDF parser importable.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger

logger = get_logger("ats_analyzer")


def check() -> dict:
    """Return health status of the ATS analyzer node."""
    issues = []

    # Check 1: embedding model
    try:
        from ml.shared.embedder import get_embedder
        emb = get_embedder()
        test_vec = emb.embed_text("test")
        assert len(test_vec) == 384
    except Exception as exc:
        issues.append(f"Embedder: {exc}")

    # Check 2: PDF parser
    try:
        import fitz  # noqa
    except ImportError:
        issues.append("PyMuPDF (fitz) not installed — PDF parsing unavailable")

    # Check 3: DOCX parser
    try:
        import docx  # noqa
    except ImportError:
        issues.append("python-docx not installed — DOCX parsing unavailable")

    if issues:
        return {"status": "degraded", "detail": "; ".join(issues)}
    return {"status": "ok", "detail": "Embedder ready, PDF+DOCX parsers available"}
