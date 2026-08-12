"""ml/ats_analyzer/errors.py — Error codes for the ATS analyzer node."""
from app.errors import NodeError

class ATSParseError(NodeError):
    """ATS_001: Resume file could not be parsed."""
    pass

class ATSFormatError(NodeError):
    """ATS_002: Unsupported file format."""
    pass

class ATSJobNotFoundError(NodeError):
    """ATS_003: Job ID not found in database."""
    pass

class ATSEmbeddingError(NodeError):
    """ATS_004: Embedding computation failed."""
    pass

class ATSScoringError(NodeError):
    """ATS_005: Unexpected error during scoring."""
    pass
