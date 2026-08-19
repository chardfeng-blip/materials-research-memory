"""Single source of truth for scientific-state transitions (P0-3/P0-5/P0-6).

Every auto-accept eligibility check and every conflict classification goes
through this module — MemoryStore, reflection, and the CLI must never re-derive
the rule "canonical and confidence == HIGH and not conflict".

P0-5: canonical WRITE authority comes ONLY from DATA_REGISTRY resolution
(`dataset:<id>` exact, or normalized exact path, or a basename that is unique
in the registry). The filename heuristic is never a write authorization; it
exists only as a read-only legacy hint for display/migration warnings.
"""

from __future__ import annotations

from dataclasses import dataclass

CANONICAL_STATUSES = {"CANONICAL", "FROZEN", "FINAL", "ACCEPTED"}
NON_CANONICAL_STATUSES = {
    "NON_CANONICAL", "LEGACY", "SUPERSEDED", "TEMP", "REJECTED",
    "REFERENCE", "WORK_IN_PROGRESS", "REVIEW_BLOCKED",
}
ALLOWED_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_STATUSES = {
    "OBSERVATION", "CANDIDATE", "VERIFIED", "PROMOTED", "ACCEPTED",
    "REJECTED", "SUPERSEDED", "FROZEN", "LEGACY", "REVIEW_BLOCKED",
}


@dataclass(frozen=True)
class CanonicalVerdict:
    """Outcome of resolving a source against DATA_REGISTRY."""
    canonical: bool
    reason: str  # 'registered-ok' | 'registered-denied' | 'unregistered'


def _norm(path: str) -> str:
    return (path or "").lower().replace("\\", "/").strip().strip("/")


def registry_status_for(datasets: list, source: str) -> str | None:
    """Resolve `source` to a REGISTERED dataset's status.

    Strict resolution (no loose substring matching that would mis-hit on
    duplicate basenames across directories):
      1. `dataset:<dataset_id>` — explicit, unambiguous.
      2. normalized exact path equality.
      3. basename equality ONLY when that basename is unique in the registry.
    Returns the dataset status, or None when unresolvable/ambiguous.
    """
    if not datasets or not source:
        return None
    s = _norm(source)
    if s.startswith("dataset:"):
        dsid = s[len("dataset:"):]
        for d in datasets:
            if str(d.get("dataset_id", "")).strip().lower() == dsid:
                return str(d.get("status", "")).upper()
        return None
    exact = [d for d in datasets if _norm(str(d.get("path", ""))) == s]
    if len(exact) == 1:
        return str(exact[0].get("status", "")).upper()
    if len(exact) > 1:
        return None  # duplicate registered paths -> unresolvable
    basename = s.rsplit("/", 1)[-1]
    by_basename = [
        d for d in datasets
        if _norm(str(d.get("path", ""))).rsplit("/", 1)[-1] == basename
    ]
    if len(by_basename) == 1:
        return str(by_basename[0].get("status", "")).upper()
    return None


def canonical_authority(datasets: list, source: str) -> CanonicalVerdict:
    """DATA_REGISTRY is the authority. Unregistered sources are NEVER
    canonical (write-side)."""
    status = registry_status_for(datasets, source)
    if status is None:
        return CanonicalVerdict(False, "unregistered")
    if status in CANONICAL_STATUSES:
        return CanonicalVerdict(True, "registered-ok")
    return CanonicalVerdict(False, "registered-denied")


def legacy_canonical_hint(source: str) -> bool:
    """READ-ONLY hint for display/migration warnings only. NEVER used for
    write authorization (P0-5). Matches the old filename heuristic so legacy
    data can be flagged, not trusted."""
    s = source.lower()
    return any(k in s for k in ("canonical", "frozen", "final", "results/",
                                "r3_3", "r3_2", "paper_ready", "master"))


def can_auto_accept_claim(*, canonical: bool, confidence: str,
                          auto_commit: bool, conflict: bool) -> bool:
    """The ONLY auto-accept rule for scientific claims."""
    return bool(auto_commit and canonical and confidence == "HIGH" and not conflict)


def can_auto_accept_decision(*, canonical: bool, confidence: str,
                             conflict: bool) -> bool:
    """The ONLY auto-accept rule for decisions. A conflicting decision can
    never auto-accept (it requires explicit review)."""
    return bool(canonical and confidence == "HIGH" and not conflict)


def classify_conflict(old_value, new_value, old_status: str) -> bool:
    """Same-topic claim conflict: the value changed on an existing claim."""
    if old_status in ("SUPERSEDED", "REJECTED"):
        return False
    return str(old_value) != str(new_value)


def decision_conflicts(prior_rows: list, entry: dict) -> tuple[list[dict], bool]:
    """Detect conflicts between a new decision and prior ledger rows.

    PURE — never mutates prior rows (and does not mutate `entry`). Returns
    (contradiction_records, conflicted). An unreviewed conflicting decision
    can never auto-accept: `can_auto_accept_decision(conflict=True)` is False
    regardless of source/confidence, so the caller's ACCEPTED request is
    forced to CANDIDATE by the policy — the same rule claims follow.
    """
    records: list[dict] = []
    conflicted = False
    for prior in prior_rows:
        if prior.get("status") in ("SUPERSEDED", "REJECTED"):
            continue
        if (prior.get("topic") == entry.get("topic")
                and prior.get("decision") != entry.get("decision")):
            conflicted = True
            records.append({
                "kind": "CONTRADICTION",
                "conflicting_decision_id": prior["decision_id"],
                "old_decision": prior.get("decision"),
                "new_decision": entry.get("decision"),
                "source": entry.get("source"),
                "confidence": entry.get("confidence"),
                "old_status": prior.get("status"),
                "new_status": "CANDIDATE",
                "requires_review": True,
                "note": "conflicting decision requires explicit reviewer "
                        "approval before superseding the accepted one",
            })
    return records, conflicted


def validate_confidence(confidence: str) -> str:
    value = str(confidence).upper()
    if value not in ALLOWED_CONFIDENCE:
        raise ValueError(f"confidence must be one of {sorted(ALLOWED_CONFIDENCE)}, "
                         f"got {confidence!r}")
    return value
