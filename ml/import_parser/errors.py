"""ml/import_parser/errors.py — Error codes for the Smart Import parser node."""
from app.errors import NodeError


class ImportFormatError(NodeError):
    """IMP_001: Unsupported file format (not .xlsx or .pdf)."""
    pass


class ImportParseError(NodeError):
    """IMP_002: File could not be parsed (corrupted, empty, or no table found)."""
    pass


class ImportEmptyError(NodeError):
    """IMP_003: File parsed but contained no data rows."""
    pass
