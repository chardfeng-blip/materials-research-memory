"""Lesson lifecycle management: CANDIDATE -> VERIFIED -> PROMOTED.

Safety: a CANDIDATE lesson never affects hard scientific rules; only
repeat-verified, generalizable, HIGH-confidence lessons may be promoted (and
even then promotion requires human/agent approval).

v0.1.2 (P0-7): `times_verified` is NEVER maintained by the caller. It is
recomputed from distinct verification identities (source, task_id), and an
exact duplicate verification does not increment the count.
"""

from __future__ import annotations

from .memory_manager import MemoryStore
from .provenance import new_id, now_date

PROMOTION_THRESHOLD_VERIFICATIONS = 2


class LessonManager:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def record(self, *, trigger: str, failure: str, root_cause: str,
               fix: str, generalizable_rule: str, scope: str,
               source: str, confidence: str = "MEDIUM") -> dict:
        return self.store.add_lesson(
            trigger=trigger, failure=failure, root_cause=root_cause, fix=fix,
            generalizable_rule=generalizable_rule, scope=scope, source=source,
            confidence=confidence, status="CANDIDATE")

    def verify(self, lesson_id: str, *, source: str, task_id: str | None = None,
               confirmation: str = "") -> dict:
        """Independent confirmation; a duplicate (source, task_id) does not
        increment `times_verified` (P0-7)."""
        return self.store.verify_lesson(lesson_id, source=source,
                                        task_id=task_id, confirmation=confirmation)

    def promotion_candidates(self) -> list[dict]:
        """Lessons eligible for SKILL promotion: VERIFIED, >= threshold
        DISTINCT verifications, HIGH confidence, generalizable rule present."""
        out = []
        for lesson in self.store.find_lessons():
            rule = (lesson.get("generalizable_rule") or "").strip()
            verified = lesson.get("times_verified", 0)
            if (lesson.get("status") in ("VERIFIED", "PROMOTED")
                    and verified >= PROMOTION_THRESHOLD_VERIFICATIONS
                    and lesson.get("confidence") == "HIGH"
                    and rule):
                out.append(lesson)
        return out

    def mark_promoted(self, lesson_id: str, skill_name: str) -> dict:
        return self.store.mark_lesson_promoted(lesson_id, skill_name)
