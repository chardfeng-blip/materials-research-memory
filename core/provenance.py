"""Provenance helpers.

Every scientific result that enters long-term state MUST carry:
  source   - exact path / dataset id / calculation id it came from
  date     - ISO date of the recording
  status   - OBSERVATION | CANDIDATE | VERIFIED | PROMOTED | ACCEPTED |
             REJECTED | SUPERSEDED | FROZEN
  confidence - LOW | MEDIUM | HIGH

decision_id / lesson_id / dataset_id stay stable and traceable across
compression and rollback (they are never renumbered).
"""

from __future__ import annotations

import datetime
import re
import uuid

STATUSES = {
    "OBSERVATION", "CANDIDATE", "VERIFIED", "PROMOTED",
    "ACCEPTED", "REJECTED", "SUPERSEDED", "FROZEN",
    "LEGACY", "REVIEW_BLOCKED",
}
CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
_REQUIRED_RESULT_FIELDS = ("source", "date", "status", "confidence")


def new_id(prefix: str, n: int = 8) -> str:
    """Stable-format id, e.g. ``decision_3f9c2a1b``."""
    return f"{prefix}_{uuid.uuid4().hex[:n]}"


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def now_date() -> str:
    return datetime.date.today().isoformat()


def stamp(record: dict, *, source: str, status: str,
          confidence: str = "MEDIUM", date: str | None = None,
          **extra) -> dict:
    """Fill provenance fields on a mutable record (does not overwrite ids)."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; allowed: {sorted(STATUSES)}")
    if confidence not in CONFIDENCE:
        raise ValueError(f"unknown confidence {confidence!r}; allowed: LOW/MEDIUM/HIGH")
    record.setdefault("source", source)
    record.setdefault("date", date or now_date())
    record["status"] = status
    record["confidence"] = confidence
    record.update(extra)
    return record


def ensure_provenance(record: dict, *, allow_legacy: bool = False) -> None:
    """Raise if a result record lacks a provenance field."""
    for field in _REQUIRED_RESULT_FIELDS:
        if field not in record or record[field] in (None, ""):
            raise MemoryProvenanceError(
                f"result record {record.get('id', '<no id>')} is missing "
                f"required provenance field {field!r}")
    if not allow_legacy and record.get("status") == "LEGACY":
        raise MemoryProvenanceError(
            "LEGACY-sourced records must be quarantined, not committed "
            "to canonical scientific state")


class MemoryProvenanceError(ValueError):
    """Raised when a record violates provenance rules."""
