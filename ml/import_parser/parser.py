"""
ml/import_parser/parser.py
─────────────────────────────
Node: import_parser

Smart Import — parses an uploaded .xlsx or .pdf application tracker export
into normalized application rows, using two intelligence stages instead of
naive "row 1 is the header, fuzzy-match column names" logic:

STAGE 1 — Header row detection
  Real spreadsheets routinely have title rows, subtitle rows, and blank rows
  above the real header (see e.g. a Google Sheets export with a title in A1).
  Every row near the top of the file is scored as a header candidate (are its
  cells short unique strings, not numbers/dates?) and the best-scoring row is
  used — row 1 is only a fallback when nothing scores well.

STAGE 2 — Intelligent column mapping
  Each detected header is matched against 9 canonical fields using a BLEND of
  two signals:
    (a) name semantics  — cosine similarity, via the shared fastembed model,
        between the header text and a large reference set of real-world
        column names per field (ml/import_parser/training_data.py). This
        generalizes far past exact/fuzzy string matching — "where i sent it"
        or "praktikum" both resolve correctly without ever being hardcoded.
    (b) content heuristics — do the column's actual VALUES look like the
        field they're being proposed for (dates parse as dates, a URL column
        starts with http, a status column has a small vocabulary, ...)? This
        also lets weak/contradicting content veto a strong name match — e.g.
        a "Type" column full of "Internship"/"Werkstudent" values scores near
        zero content support for "platform" even though the bare word "type"
        is a legitimate platform alias, so it correctly stays unmapped rather
        than swallowing an unrelated column.
  confidence = 0.6 * name_score + 0.4 * content_score (content_score can go
  negative when the data actively contradicts the field, which is the only
  way a near-exact name match can still lose — see _content_status/_platform).
  A column is only mapped if confidence clears CONFIDENCE_THRESHOLD, and each
  field takes the single highest-confidence unclaimed column.

Status values are normalized through a comprehensive, emoji- and
German-aware keyword matcher — see normalize_status().

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
from functools import lru_cache
from typing import Any

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from ml.import_parser.errors import ImportEmptyError, ImportFormatError, ImportParseError
from ml.import_parser.training_data import TRAINING_DATA

logger = get_logger("import_parser")

VALID_STATUSES = ("saved", "applied", "interview", "offer", "rejected")
STALE_DAYS = 30
CANONICAL_FIELDS = tuple(TRAINING_DATA.keys())

# ── Stage 2 weighting ────────────────────────────────────────────────
NAME_WEIGHT = 0.6
CONTENT_WEIGHT = 0.4
CONFIDENCE_THRESHOLD = 0.45
# Cosine similarity floor for "two unrelated short phrases" under the
# all-MiniLM-L6-v2 model — empirically ~0.30 even for unrelated text, so we
# rescale the raw similarity to [0, 1] against that floor rather than using
# it directly (see _name_score).
NAME_SIM_FLOOR = 0.30


# ── Generic emoji stripping ──────────────────────────────────────────
# Broad enough to catch anything status columns show up with in the wild
# (✅ ❌ 📋 ⏸️ ❓ 🟢 🔴 🟡 ➡️ and friends), not just a hardcoded 8-emoji list.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # symbols, pictographs, emoticons, transport, supplemental
    "\U00002600-\U000027BF"   # misc symbols + dingbats (✅❌❓➡️ live here)
    "\U00002300-\U000023FF"   # misc technical (⏰⏸⏯⏹ live here)
    "\U00002B00-\U00002BFF"   # misc symbols and arrows
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U0000FE0F"              # variation selector-16
    "\U0000200D"              # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    return _EMOJI_PATTERN.sub("", text).strip()


# ── Status normalisation ─────────────────────────────────────────────
# Checked in this order — "offer"/"rejected" before "applied"/"interview" so
# e.g. "Rejected after onsite interview" lands on rejected, not interview.
# Includes German terms since a large share of trackers this feature targets
# are for Werkstudent/Praktikum applications in Germany.
STATUS_KEYWORDS: list[tuple[str, list[str]]] = [
    ("offer", [
        "offer", "selected", "hired", "accepted",
        "angebot", "zusage", "angenommen",
    ]),
    ("rejected", [
        "reject", "declined", "decline", "unsuccessful", "not selected", "no go",
        "abgelehnt", "absage", "zurückgezogen", "withdrawn",
    ]),
    ("interview", [
        "interview", "phone screen", "assessment", "screening", "technical round",
        "onsite", "final round",
        "vorstellungsgespräch", "gespräch", "eingeladen", "invited",
    ]),
    ("applied", [
        "applied", "pending", "in progress", "in-progress", "waiting", "submitted",
        "under review", "applying",
        "beworben", "eingereicht",
    ]),
    ("saved", [
        "saved", "wishlist", "planned", "to apply", "draft", "bookmarked", "optional",
        "offen", "geplant", "queued",
    ]),
]
# bare yes/no only count once every phrase above has failed to match
_YES_NO_FALLBACK: list[tuple[str, list[str]]] = [
    ("offer", ["yes"]),
    ("rejected", ["no"]),
]


def normalize_status(raw: Any) -> tuple[str, bool]:
    """Maps a free-text (possibly emoji-prefixed, possibly German) status cell
    to one of VALID_STATUSES.

    Returns (canonical_status, was_recognized). Unrecognized/blank values
    default to "saved" — never drop the row, just flag it for the user to
    fix in the review table.
    """
    text = _clean_text(raw)
    if not text:
        return "saved", False
    text = strip_emoji(text).strip()
    if not text:
        return "saved", False
    for canonical, keywords in STATUS_KEYWORDS:
        if any(kw in text for kw in keywords):
            return canonical, True
    for canonical, keywords in _YES_NO_FALLBACK:
        if text in keywords:
            return canonical, True
    return "saved", False


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


def _is_stringy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return False
    if isinstance(v, (datetime, date)):
        return False
    return True


def _looks_numeric_or_date(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float, datetime, date))


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


# ══════════════════════════════════════════════════════════════════════
# STAGE 1 — Header row detection
# ══════════════════════════════════════════════════════════════════════

_HEADER_SCAN_LIMIT = 30  # header rows always live near the top in practice
_HEADER_SCORE_MIN = 0.35  # below this, nothing looked like a real header


def _score_header_row(row: list[Any], position_ratio: float) -> float:
    cells = [v for v in row if _cell(v) is not None]
    if len(cells) < 2:
        return 0.0
    stringy = sum(1 for v in cells if _is_stringy(v)) / len(cells)
    texts = [str(v).strip() for v in cells]
    short = sum(1 for t in texts if len(t) < 50) / len(texts)
    uniqueness = len(set(t.lower() for t in texts)) / len(texts)
    fill_ratio = len(cells) / max(len(row), 1)
    # "do they appear in the top 30% of the file?"
    position_score = 1.0 if position_ratio <= 0.30 else max(0.0, 1 - (position_ratio - 0.30) / 0.5)
    return (
        0.30 * stringy +
        0.15 * short +
        0.25 * uniqueness +
        0.15 * fill_ratio +
        0.15 * position_score
    )


def detect_header_row(matrix: list[list[Any]]) -> int:
    """Scores every near-top row as a header candidate, returns the best index.
    Falls back to row 0 (row 1 to a human) only when nothing scores well —
    e.g. a file with no title rows above the real header, where row 0 IS it."""
    if not matrix:
        return 0
    scan_limit = min(len(matrix), _HEADER_SCAN_LIMIT)
    best_idx, best_score = 0, -1.0
    for i in range(scan_limit):
        score = _score_header_row(matrix[i], i / max(len(matrix), 1))
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx if best_score >= _HEADER_SCORE_MIN else 0


def _matrix_to_columns_rows(
    matrix: list[list[Any]], header_idx: int
) -> tuple[list[str], list[dict[str, Any]]]:
    header_row = matrix[header_idx]
    width = len(header_row)
    columns: list[str] = []
    seen: dict[str, int] = {}
    for i, v in enumerate(header_row):
        name = _cell(v) or f"column_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 0
        columns.append(name)

    records: list[dict[str, Any]] = []
    for row in matrix[header_idx + 1:]:
        if all(_cell(v) is None for v in row):
            continue
        records.append({columns[i]: (row[i] if i < len(row) else None) for i in range(width)})
    return columns, records


# ══════════════════════════════════════════════════════════════════════
# File readers — return a raw matrix (Stage 1 finds the header in it)
# ══════════════════════════════════════════════════════════════════════

def _read_xlsx(file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    import pandas as pd
    try:
        # header=None: don't assume row 1 is the header — Stage 1 finds it.
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", header=None, dtype=object)
    except Exception as exc:
        raise ImportParseError("IMP_002", f"Could not read Excel file: {exc}", {"error": str(exc)}, status_code=422)
    matrix = df.values.tolist()
    if not matrix:
        raise ImportEmptyError("IMP_003", "The spreadsheet has no data rows", status_code=422)
    header_idx = detect_header_row(matrix)
    columns, records = _matrix_to_columns_rows(matrix, header_idx)
    if not records:
        raise ImportEmptyError("IMP_003", "The spreadsheet has no data rows", status_code=422)
    return columns, records


def _read_pdf(file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportParseError(
            "IMP_002", "PDF support is not installed on the server", {"error": str(exc)}, status_code=500
        )

    tables: list[list[list[Any]]] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if table:
                        tables.append(table)
    except Exception as exc:
        raise ImportParseError("IMP_002", f"Could not read PDF file: {exc}", {"error": str(exc)}, status_code=422)

    if not tables:
        raise ImportParseError(
            "IMP_002",
            "No table detected in this PDF. Export your tracker as .xlsx for best results, "
            "or make sure the PDF contains a real table (not a scanned image).",
            status_code=422,
        )

    header_idx = detect_header_row(tables[0])
    columns, records = _matrix_to_columns_rows(tables[0], header_idx)
    # Paginated exports repeat the same table across pages — stitch on if the
    # header matches exactly; otherwise leave the extra table alone rather
    # than risk corrupting good data with a mismatched shape.
    for table in tables[1:]:
        h_idx = detect_header_row(table)
        cols2, records2 = _matrix_to_columns_rows(table, h_idx)
        if cols2 == columns:
            records.extend(records2)

    if not records:
        raise ImportEmptyError("IMP_003", "The PDF table has no data rows", status_code=422)
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


# ══════════════════════════════════════════════════════════════════════
# STAGE 2 — Intelligent column mapping (name semantics + content heuristics)
# ══════════════════════════════════════════════════════════════════════

# Closed-vocabulary reference sets used by the content heuristics below.
# Deliberately does NOT include the bare word "type" as a platform signal —
# unqualified "Type" columns collide with employment-type columns
# (Internship/Werkstudent/Contract) far more often than they mean job board,
# so that ambiguity is resolved by content, not baked into the name aliases.
KNOWN_PLATFORMS = {
    "linkedin", "indeed", "xing", "stepstone", "step stone", "glassdoor",
    "monster", "ziprecruiter", "referral", "company site", "company website",
    "website", "career fair", "meetup", "handshake", "wellfound", "angellist",
    "otta", "naukri", "jobs.ch", "personal network", "networking", "recruiter",
    "agency", "university career center", "campus", "email", "direct application",
    "direct", "cold email", "cold outreach", "jobvector", "berufsstart",
}
EMPLOYMENT_TYPE_WORDS = {
    "internship", "intern", "werkstudent", "working student", "vollzeit",
    "full-time", "full time", "part-time", "part time", "contract", "permanent",
    "praktikum", "trainee", "werkstudent / intern", "internship / ws",
    "freelance", "temporary",
}
FIT_QUALITY_WORDS = {"strong", "weak", "partial", "good", "poor", "excellent", "fair", "great", "average"}
STRONG_STATUS_EMOJI = ("✅", "❌", "📋", "⏸", "❓", "➡")   # unambiguous action/outcome signals
AMBIGUOUS_TRAFFIC_EMOJI = ("🟢", "🟡", "🔴")                # also used for fit/priority ratings in the wild


def _content_job_title(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    len_score = sum(1 for t in texts if 5 <= len(t) <= 80) / len(texts)
    diversity = len(set(t.lower() for t in texts)) / len(texts)
    return 0.55 * len_score + 0.45 * diversity


def _content_company(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    len_score = sum(1 for t in texts if 2 <= len(t) <= 50) / len(texts)
    textual = sum(1 for v in values if _cell(v) is not None and not _looks_numeric_or_date(v)) / len(texts)
    return 0.5 * len_score + 0.5 * textual


def _content_location(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    len_score = sum(1 for t in texts if 2 <= len(t) <= 60) / len(texts)
    textual = sum(1 for v in values if _cell(v) is not None and not _looks_numeric_or_date(v)) / len(texts)
    return 0.5 * len_score + 0.5 * textual


def _content_date_applied(values: list[Any]) -> float:
    present = [v for v in values if _cell(v) is not None]
    if not present:
        return 0.0
    hits = sum(1 for v in present if isinstance(v, (datetime, date)) or _parse_date(v) is not None)
    return hits / len(present)


def _content_status(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    uniq = set(t.lower() for t in texts)
    vocab_score = 1.0 if len(uniq) <= 15 else max(0.0, 1 - (len(uniq) - 15) / 20)
    strong_hits = sum(1 for t in texts if any(e in t for e in STRONG_STATUS_EMOJI)) / len(texts)
    ambiguous_hits = sum(1 for t in texts if any(e in t for e in AMBIGUOUS_TRAFFIC_EMOJI)) / len(texts)
    keyword_hits = sum(1 for t in texts if normalize_status(t)[1]) / len(texts)

    score = 0.45 * vocab_score + 0.35 * keyword_hits + 0.20 * strong_hits
    if keyword_hits == 0 and strong_hits == 0 and ambiguous_hits > 0.5:
        # Traffic-light emoji with no recognizable status word — much more
        # likely a fit/priority rating column than an application status.
        score *= 0.25
    fit_hits = sum(1 for t in texts if strip_emoji(t).strip().lower() in FIT_QUALITY_WORDS) / len(texts)
    if fit_hits > 0.5 and keyword_hits == 0:
        # Actively contradicts "status" — this is a quality/fit rating.
        score = -0.6
    return score


def _content_job_url(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    hits = sum(
        1 for t in texts
        if t.lower().startswith(("http://", "https://", "www."))
        or ".com" in t.lower() or ".de" in t.lower() or ".org" in t.lower()
    )
    return hits / len(texts)


def _content_notes(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.3  # free text has no strong fingerprint either way
    diversity = len(set(t.lower() for t in texts)) / len(texts)
    substantial = sum(1 for t in texts if len(t) > 3) / len(texts)
    return 0.5 * diversity + 0.5 * substantial


def _content_salary(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    # Require actual salary-shaped formatting (currency, "k" suffix, or a
    # numeric range) — a lone bare number is just as likely to be a job ID
    # or row index, so it isn't treated as evidence on its own.
    hits = sum(
        1 for t in texts
        if re.search(r"[£$€]", t) or re.search(r"\dk\b", t, re.IGNORECASE) or re.search(r"\d\s*[-–]\s*\d", t)
    )
    return hits / len(texts)


def _content_platform(values: list[Any]) -> float:
    texts = [t for t in (_cell(v) for v in values) if t]
    if not texts:
        return 0.0
    cleaned = [strip_emoji(t).strip().lower() for t in texts]
    known_hits = sum(1 for t in cleaned if any(p in t or t in p for p in KNOWN_PLATFORMS)) / len(texts)
    employment_hits = sum(1 for t in cleaned if t in EMPLOYMENT_TYPE_WORDS) / len(texts)
    vocab_score = 1.0 if len(set(cleaned)) <= 12 else 0.3
    if known_hits > 0:
        return min(1.0, 0.5 * vocab_score + 0.7 * known_hits)
    if employment_hits > 0.5:
        # Actively contradicts "platform" — this is an employment-type column.
        return -0.7
    return 0.05


CONTENT_SCORERS = {
    "job_title": _content_job_title,
    "company": _content_company,
    "location": _content_location,
    "date_applied": _content_date_applied,
    "status": _content_status,
    "job_url": _content_job_url,
    "notes": _content_notes,
    "salary": _content_salary,
    "platform": _content_platform,
}


@lru_cache(maxsize=1)
def _reference_embeddings() -> dict[str, list[list[float]]]:
    """Embeddings for every training example, computed once per process."""
    from ml.shared.embedder import get_embedder
    embedder = get_embedder()
    return {field_name: embedder.embed_batch(examples) for field_name, examples in TRAINING_DATA.items()}


def _name_score(header_vec: list[float], field_name: str, embedder: Any) -> float:
    refs = _reference_embeddings()[field_name]
    best = max((embedder.cosine_similarity(header_vec, r) for r in refs), default=0.0)
    # Rescale so the "two unrelated phrases" noise floor -> 0 and a clean
    # match -> 1, instead of using raw cosine similarity directly.
    return max(0.0, min(1.0, (best - NAME_SIM_FLOOR) / (1.0 - NAME_SIM_FLOOR)))


def map_columns(columns: list[str], rows_by_column: dict[str, list[Any]]) -> dict[str, dict[str, Any]]:
    """Stage 2 entry point. Returns, for every canonical field:
        {"column": <source column name> | None, "confidence": float}
    A column is only assigned if its confidence clears CONFIDENCE_THRESHOLD;
    each field takes the single highest-confidence unclaimed column."""
    from ml.shared.embedder import get_embedder
    embedder = get_embedder()
    header_vecs = dict(zip(columns, embedder.embed_batch([_clean_header(c) for c in columns])))

    candidates: list[tuple[float, str, str]] = []  # (confidence, field, column)
    for field_name in TRAINING_DATA:
        content_fn = CONTENT_SCORERS[field_name]
        for col in columns:
            name_s = _name_score(header_vecs[col], field_name, embedder)
            content_s = content_fn(rows_by_column.get(col, []))
            confidence = max(0.0, min(1.0, NAME_WEIGHT * name_s + CONTENT_WEIGHT * content_s))
            candidates.append((confidence, field_name, col))
    candidates.sort(key=lambda t: t[0], reverse=True)

    mapping: dict[str, dict[str, Any]] = {f: {"column": None, "confidence": 0.0} for f in TRAINING_DATA}
    used: set[str] = set()
    for confidence, field_name, col in candidates:
        if confidence < CONFIDENCE_THRESHOLD:
            break
        if mapping[field_name]["column"] is not None or col in used:
            continue
        mapping[field_name] = {"column": col, "confidence": round(confidence, 3)}
        used.add(col)
    return mapping


# ══════════════════════════════════════════════════════════════════════
# Row shaping
# ══════════════════════════════════════════════════════════════════════

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


def _fuzzy_match(key: str, pool: dict[str, str], threshold: int = 93) -> str | None:
    """Returns the description for the best fuzzy match of `key` in `pool`, if any.
    93 (not a looser 88) because "Praktikum Strategy Consulting General" vs
    "...Operations" — two genuinely different roles at the same company —
    scores ~89 on token_sort_ratio; genuine repeats (identical strings, or
    trivial casing/whitespace differences) still land at 97-100."""
    if not key.strip("|") or not pool:
        return None
    from rapidfuzz import fuzz, process
    match = process.extractOne(key, pool.keys(), scorer=fuzz.token_sort_ratio, score_cutoff=threshold)
    return pool[match[0]] if match else None


def build_rows(
    raw_rows: list[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
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
            col = mapping.get(field_name, {}).get("column")
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
            warnings.append(f'Unrecognized status "{_cell(raw_status)}" — defaulted to Saved')
        if not applied_dt and mapping.get("date_applied", {}).get("column"):
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


def _json_safe(v: Any) -> str | int | float | bool | None:
    """Coerces a raw cell value (possibly a pandas Timestamp/NaN/numpy scalar)
    into something JSON can carry as-is, for the client-side manual remap path."""
    if v is None:
        return None
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def preview_import(
    file_bytes: bytes,
    filename: str,
    existing_applications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full upload -> preview pipeline. Raises ImportFormatError/ImportParseError/ImportEmptyError."""
    file_type, columns, raw_rows = parse_file(file_bytes, filename)
    rows_by_column: dict[str, list[Any]] = {c: [r.get(c) for r in raw_rows] for c in columns}
    mapping = map_columns(columns, rows_by_column)
    if not mapping.get("job_title", {}).get("column"):
        logger.warning("No job title column detected in import", extra={"extra": {"columns": columns}})
    rows = build_rows(raw_rows, mapping, existing_applications)
    return {
        "filename": filename,
        "file_type": file_type,
        "detected_columns": columns,
        "column_mapping": mapping,
        # Raw per-column values (JSON-safe), row-aligned with `rows` — lets the
        # frontend re-derive a field's values if the user manually remaps it
        # to a different detected column, without a second upload round-trip.
        "raw_columns": {c: [_json_safe(v) for v in vals] for c, vals in rows_by_column.items()},
        "rows": [r.to_dict() for r in rows],
        "summary": compute_summary(rows),
    }
