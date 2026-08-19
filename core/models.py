"""Shared cross-module data structures (P0-4). Typed dicts only — no logic.

One claim model everywhere: every long-term scientific claim is a
ClaimRecord carrying value + source + date + status + confidence (+ review
provenance). Pending gated claims are PendingChange records with a stable
change_id (never an array index).
"""

from __future__ import annotations

from typing import TypedDict


class ClaimRecord(TypedDict, total=False):
    claim_id: str
    topic: str
    value: object
    source: str
    date: str
    status: str            # ACCEPTED | CANDIDATE | REJECTED | SUPERSEDED
    confidence: str        # LOW | MEDIUM | HIGH
    reviewed_by: str
    reviewed_at: str
    superseded_by: str
    requires_review: bool
    contradictions: list   # list of CONTRADICTION dicts
    migrated: bool         # set by migrate_v011_claims() on legacy primitives


class PendingChange(TypedDict, total=False):
    change_id: str
    topic: str
    value: object
    source: str
    date: str
    status: str            # CANDIDATE until accepted
    confidence: str
    requires_review: bool
    conflicts: list        # topics that conflicted
    reviewed_by: str
    reviewed_at: str
    superseded_by: str


class VerificationRecord(TypedDict, total=False):
    verification_id: str
    source: str
    task_id: str
    date: str
    confirmation: str


class DecisionRecord(TypedDict, total=False):
    decision_id: str
    timestamp: str
    topic: str
    decision: str
    alternatives: list
    reason: str
    evidence: str
    source: str
    confidence: str
    status: str
    requires_review: bool
    reviewed_by: str
    reviewed_at: str
    superseded_by: str
    contradictions: list


class LessonRecord(TypedDict, total=False):
    lesson_id: str
    trigger: str
    failure: str
    root_cause: str
    fix: str
    generalizable_rule: str
    scope: str
    confidence: str
    times_verified: int
    status: str            # CANDIDATE | VERIFIED | PROMOTED
    source: str
    date: str
    verifications: list    # VerificationRecord
    promoted_to: str
