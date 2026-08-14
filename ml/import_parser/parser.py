"""
ml/import_parser/parser.py
─────────────────────────────
Node: import_parser

Smart Import — parses an uploaded .xlsx or .pdf application tracker export,
fuzzy-matches its columns against the fields Career OS understands, normalises
status values, and flags duplicates / stale applications — all before a
single row touches the database. The API layer (app/api/import_router.py)
calls `preview_import()` for the upload step and reuses `normalize_status()`
to re-validate rows on confirm.

Error codes:
  IMP_001 — Unsupported file format (not .xlsx or .pdf)
  IMP_002 — File could not be parsed (corrupted, unreadable, or no table found)
  IMP_003 — File parsed but contained no data rows
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from ml.import_parser.errors import ImportEmptyError, ImportFormatError, ImportParseError

logger = get_logger("import_parser")

VALID_STATUSES = ("saved", "applied", "interview", "offer", "rejected")
STALE_DAYS = 30

# ── Fuzzy column matching ───────────────────────────────────────────
# canonical field -> phrases a real spreadsheet header is likely to use.
# Matched against the *cleaned* header (lowercased, punctuation collapsed).
COLUMN_ALIASES: dict[str, list[str]] = {
    "job_title":    ["job title", "title", "position", "role", "job", "position title", "job role", "job position"],
    "company":      ["company", "employer", "organisation", "organization", "company name", "hiring company"],
    "location":     ["location", "city", "office location", "job location", "place", "region"],
    "date_applied": ["date applied", "application date", "applied date", "date", "applied on", "submission date", "apply date"],
    "status":       ["status", "application status", "stage", "state", "result", "outcome"],
    "job_url":      ["job url", "url", "link", "job link", "posting url", "listing url", "job posting"],
    "notes":        ["notes", "comments", "comment", "remarks", "note", "feedback"],
    "salary":       ["salary", "compensation", "pay", "salary range", "expected salary", "comp", "wage"],
    "platform":     ["source", "platform", "job board", "found via", "applied via", "channel", "site"],
}
MATCH_THRESHOLD = 62  # rapidfuzz score (0-100) below which a column is left unmapped

# ── Status normalisation ─────────────────────────────────────────────
# Checked in this order — "offer"/"rejected" before "applied"/"interview" so
# e.g. "Rejected after onsite interview" lands on rejected, not interview.
STATUS_KEYWORDS: list[tuple[str, list[str]]] = [
    ("offer",     ["offer", "selected", "hired", "accepted"]),
    ("rejected",  ["reject", "declined", "decline", "unsuccessful", "not selected", "no go"]),
    ("interview", ["interview", "phone screen", "assessment", "screening", "technical round", "onsite", "final round"]),
    ("applied",   ["applied", "pending", "in progress", "in-progress", "waiting", "submitted", "under review", "applying"]),
    ("saved",     ["saved", "wishlist", "planned", "to apply", "draft", "bookmarked"]),
]
# bare yes/no only count once every phrase above has failed to match
_YES_NO_FALLBACK: list[tuple[str, list[str]]] = [
    ("offer", ["yes"]),
    ("rejected", ["no"]),
]


def normalize_status(raw: Any) -> tuple[str, bool]:
    """Maps a free-text status cell to one of VALID_STATUSES.

    Returns (canonical_status, was_recognized). Unrecognized/blank values
    default to "applied" — a row in an application tracker export is
    presumed at least applied-to unless it clearly says otherwise.
    """
    text = _clean_text(raw)
    if not text:
        return "applied", False
    for canonical, keywords in STATUS_KEYWORDS:
        if any(kw in text for kw in keywords):
            return canonical, True
    for canonical, keywords in _YES_NO_FALLBACK:
        if text in keywords:
            return canonical, True
    return "applied", False


# ── Cell / header cleanup helpers ────────────────────────────────────

def _clean_text(value: Any) -> str:
    """Lowercased, whitespace-trimmed string form of a cell, '' for empty/NaN."""
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in ("", "nan", "none", "nat", "-", "n/a"):
        return ""
    return text.lower()


def _cell(value: Any) -> str | None:
    """Display string for a cell, or None if empty/NaN."""
    text = _clean_text(value)
    if not text:
        return None
    return str(value).strip()


def _clean_header(s: Any) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[_\-/]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def map_columns(columns: list[str]) -> dict[str, str | None]:
    """Greedy best-match assignment of source columns to canonical fields."""
    from rapidfuzz import fuzz

    cleaned = {c: _clean_header(c) for c in columns}
    candidates: list[tuple[float, str, str]] = []  # (score, field, original_column)
    for field_name, aliases in COLUMN_ALIASES.items():
        for col in columns:
            c = cleaned[col]
            if not c:
                continue
            score = max(fuzz.token_sort_ratio(c, alias) for alias in aliases)
            if c in aliases:
                score = 100.0
            candidates.append((score, field_name, col))
    candidates.sort(key=lambda t: t[0], reverse=True)

    mapping: dict[str, str | None] = {f: None for f in COLUMN_ALIASES}
    used: set[str] = set()
    for score, field_name, col in candidates:
        if score < MATCH_THRESHOLD:
            break
        if mapping[field_name] is not None or col in used:
            continue
        mapping[field_name] = col
        used.add(col)
    return mapping


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _cell(value)
    if not text:
        return None
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(text, fuzzy=True).date()
    except Exception:
        return None


_NUM_RE = re.compile(r"[\d][\d,]*(?:\.\d+)?")


def _parse_salary(value: Any) -> tuple[float | None, float | None, str | None]:
    """Best-effort numeric range from free text like '$90k - $110k' or '85000'."""
    text = _cell(value)
    if not text:
        return None, None, None
    multiplier = 1000.0 if re.search(r"\dk\b", text, re.IGNORECASE) else 1.0
    nums = [float(n.replace(",", "")) * multiplier for n in _NUM_RE.findall(text)]
    if not nums:
        return None, None, text
    if len(nums) == 1:
        return nums[0], nums[0], text
    return min(nums), max(nums), text


def _dedup_key(title: str | None, company: str | None) -> str:
    return f"{_clean_header(title or '')}|{_clean_header(company or '')}"


# ── File readers ──────────────────────────────────────────────────────

def _read_xlsx(file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    import pandas as pd
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", dtype=object)
    except Exception as exc:
        raise ImportParseError("IMP_002", f"Could not read Excel file: {exc}", {"error": str(exc)}, status_code=422)
    df = df.dropna(how="all")
    if df.empty:
        raise ImportEmptyError("IMP_003", "The spreadsheet has no data rows", status_code=422)
    columns = [str(c) for c in df.columns]
    return columns, df.to_dict("records")


def _read_pdf(file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportParseError(
            "IMP_002", "PDF support is not installed on the server", {"error": str(exc)}, status_code=500
        )

    columns: list[str] | None = None
    records: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table:
                        continue
                    header_row, *body = table
                    header = [(_cell(h) or f"column_{i}") for i, h in enumerate(header_row)]
                    if columns is None:
                        columns = header
                    for row in body:
                        if [(_cell(v) or "") for v in row] == [(_cell(h) or "") for h in header_row]:
                            continue  # repeated header row on a later page
                        if all(_cell(v) is None for v in row):
                            continue
                        records.append({
                            (columns[i] if columns and i < len(columns) else f"column_{i}"): v
                            for i, v in enumerate(row)
                        })
    except ImportParseError:
        raise
    except Exception as exc:
        raise ImportParseError("IMP_002", f"Could not read PDF file: {exc}", {"error": str(exc)}, status_code=422)

    if columns is None or not records:
        raise ImportParseError(
            "IMP_002",
            "No table detected in this PDF. Export your tracker as .xlsx for best results, "
            "or make sure the PDF contains a real table (not a scanned image).",
            status_code=422,
        )
    return columns, records


def parse_file(file_bytes: bytes, filename: str) -> tuple[str, list[str], list[dict[str, Any]]]:
    ext = (filename or "").lower().rsplit(".", 1)[-1] if "." in (filename or "") else ""
    if ext == "xlsx":
        columns, rows = _read_xlsx(file_bytes)
        return "xlsx", columns, rows
    if ext == "pdf":
        columns, rows = _read_pdf(file_bytes)
        return "pdf", columns, rows
    raise ImportFormatError(
        "IMP_001", f"Unsupported file format: .{ext or '?'}. Upload a .xlsx or .pdf file.", status_code=422
    )


# ── Row shaping ───────────────────────────────────────────────────────

@dataclass
class ParsedRow:
    row_index: int
    job_title: str | None
    company: str | None
    location: str | None
    date_applied: str | None  # ISO date, or None
    status: str
    status_recognized: bool
    job_url: str | None
    notes: str | None
    salary_text: str | None
    salary_min: float | None
    salary_max: float | None
    platform: str | None
    days_since_applied: int | None
    is_stale: bool
    is_duplicate: bool
    duplicate_reason: str | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_index": self.row_index,
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "date_applied": self.date_applied,
            "status": self.status,
            "status_recognized": self.status_recognized,
            "job_url": self.job_url,
            "notes": self.notes,
            "salary_text": self.salary_text,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "platform": self.platform,
            "days_since_applied": self.days_since_applied,
            "is_stale": self.is_stale,
            "is_duplicate": self.is_duplicate,
            "duplicate_reason": self.duplicate_reason,
            "warnings": self.warnings,
            # rows default to "keep" — the frontend pre-unchecks duplicates
            "skip": self.is_duplicate,
        }


def _fuzzy_match(key: str, pool: dict[str, str], threshold: int = 88) -> str | None:
    """Returns the description for the best fuzzy match of `key` in `pool`, if any."""
    if not key.strip("|") or not pool:
        return None
    from rapidfuzz import fuzz, process
    match = process.extractOne(key, pool.keys(), scorer=fuzz.token_sort_ratio, score_cutoff=threshold)
    return pool[match[0]] if match else None


def build_rows(
    raw_rows: list[dict[str, Any]],
    mapping: dict[str, str | None],
    existing_applications: list[dict[str, Any]] | None = None,
) -> list[ParsedRow]:
    """Shapes raw parsed cells into ParsedRow objects: normalizes status, computes
    days-since-applied / staleness, and flags duplicates against both the rest of
    this file and the user's existing tracker."""
    existing_applications = existing_applications or []
    existing_pool: dict[str, str] = {}
    for app in existing_applications:
        key = _dedup_key(app.get("title"), app.get("company"))
        if key.strip("|"):
            existing_pool[key] = f"Already in your tracker (status: {app.get('status') or 'saved'})"

    today = date.today()
    seen_pool: dict[str, str] = {}
    parsed: list[ParsedRow] = []

    for i, raw in enumerate(raw_rows):
        def get(field_name: str) -> Any:
            col = mapping.get(field_name)
            return raw.get(col) if col else None

        title = _cell(get("job_title"))
        company = _cell(get("company"))
        location = _cell(get("location"))
        job_url = _cell(get("job_url"))
        notes = _cell(get("notes"))
        platform = _cell(get("platform"))
        applied_dt = _parse_date(get("date_applied"))
        raw_status = get("status")
        status, recognized = normalize_status(raw_status)
        salary_min, salary_max, salary_text = _parse_salary(get("salary"))

        warnings: list[str] = []
        if not title:
            warnings.append("Missing job title")
        if not recognized and _cell(raw_status):
            warnings.append(f'Unrecognized status "{_cell(raw_status)}" — defaulted to Applied')
        if not applied_dt and mapping.get("date_applied"):
            warnings.append("Could not parse a date in the Date Applied column")

        days_since = (today - applied_dt).days if applied_dt else None
        is_stale = status == "applied" and days_since is not None and days_since >= STALE_DAYS

        key = _dedup_key(title, company)
        duplicate_reason = _fuzzy_match(key, seen_pool) or _fuzzy_match(key, existing_pool)
        is_duplicate = duplicate_reason is not None
        if key.strip("|") and key not in seen_pool:
            seen_pool[key] = f"Duplicate of row {i + 1} in this file"

        parsed.append(ParsedRow(
            row_index=i,
            job_title=title,
            company=company,
            location=location,
            date_applied=applied_dt.isoformat() if applied_dt else None,
            status=status,
            status_recognized=recognized,
            job_url=job_url,
            notes=notes,
            salary_text=salary_text,
            salary_min=salary_min,
            salary_max=salary_max,
            platform=platform,
            days_since_applied=days_since,
            is_stale=is_stale,
            is_duplicate=is_duplicate,
            duplicate_reason=duplicate_reason,
            warnings=warnings,
        ))

    return parsed


def compute_summary(rows: list[ParsedRow]) -> dict[str, Any]:
    total = len(rows)
    counts = {s: 0 for s in VALID_STATUSES}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    duplicate_count = sum(1 for r in rows if r.is_duplicate)
    stale_count = sum(1 for r in rows if r.is_stale)
    responded = counts.get("interview", 0) + counts.get("offer", 0)
    return {
        "total": total,
        **counts,
        "duplicate_count": duplicate_count,
        "stale_count": stale_count,
        "response_rate": round(responded / total, 4) if total else 0.0,
    }


def preview_import(
    file_bytes: bytes,
    filename: str,
    existing_applications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full upload -> preview pipeline. Raises ImportFormatError/ImportParseError/ImportEmptyError."""
    file_type, columns, raw_rows = parse_file(file_bytes, filename)
    mapping = map_columns(columns)
    if not mapping.get("job_title"):
        logger.warning("No job title column detected in import", extra={"extra": {"columns": columns}})
    rows = build_rows(raw_rows, mapping, existing_applications)
    return {
        "filename": filename,
        "file_type": file_type,
        "detected_columns": columns,
        "column_mapping": mapping,
        "rows": [r.to_dict() for r in rows],
        "summary": compute_summary(rows),
    }
