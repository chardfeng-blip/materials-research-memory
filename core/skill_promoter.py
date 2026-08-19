"""Skill promotion (P0-8).

Generates SKILL_PROMOTION_PROPOSAL.md from eligible VERIFIED lessons; the
actual skill file is written ONLY after human/agent approval.

v0.1.2 hardening:
  * `validation_count` is NEVER caller-supplied — it is computed live from the
    lesson store's DISTINCT verification identities;
  * promotion is atomic: ALL origin lessons are validated first
    (status VERIFIED, confidence HIGH, distinct verifications >= threshold,
    generalizable rule non-empty); only then is the skill file written, and
    only after the write succeeds are lessons marked PROMOTED. A failed
    validation leaves NO skill file behind;
  * the promoted skill lands in the INDEXED skill location (P0-9): the active
    profile's skills dir when a profile is active, otherwise skills/core —
    never in a non-indexed location;
  * the write goes through core/storage (atomic), not ad-hoc file IO.
"""

from __future__ import annotations

import datetime
import os

from . import storage
from .lesson_manager import (LessonManager,
                             PROMOTION_THRESHOLD_VERIFICATIONS)
from .memory_manager import MemoryStore

SKILL_SECTIONS = [
    "Purpose", "When to use", "Inputs", "Definitions", "Procedure",
    "QA", "Common failures", "Blocking conditions", "Outputs",
    "Provenance requirements",
]


def _skill_filename(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.lower())
    return safe.strip("_") + ".md"


def _skill_target_dir(store: MemoryStore) -> str:
    """Indexed skill location (P0-9): active profile first, else core."""
    return store.profile_skills_dir or store.core_skills_dir


class SkillPromoter:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.lessons = LessonManager(store)

    def propose(self) -> str:
        """Write SKILL_PROMOTION_PROPOSAL.md from eligible lessons."""
        candidates = self.lessons.promotion_candidates()
        store = self.store
        store.ensure_layout()
        path = os.path.join(store.outputs_dir, "SKILL_PROMOTION_PROPOSAL.md")
        lines = [
            "# SKILL_PROMOTION_PROPOSAL",
            "",
            f"generated: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"eligible lessons: {len(candidates)}",
            "",
        ]
        if not candidates:
            lines.append("No lesson currently meets promotion criteria "
                         "(VERIFIED + distinct verifications >= "
                         f"{PROMOTION_THRESHOLD_VERIFICATIONS} + HIGH + generalizable).")
        for lesson in candidates:
            target = _skill_target_dir(store)
            lines.append(f"## Candidate: {lesson['lesson_id']} — "
                         f"{lesson.get('scope', '')}")
            lines.append(f"- generalizable rule: {lesson.get('generalizable_rule')}")
            lines.append(f"- distinct verifications: {lesson.get('times_verified')}")
            lines.append(f"- confidence: {lesson.get('confidence')}")
            lines.append(f"- source: {lesson.get('source')}")
            lines.append(f"- proposed skill file: "
                         f"{os.path.relpath(os.path.join(target, _skill_filename(lesson.get('scope') or 'lesson')), store.root)}")
            lines.append("")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return path

    def _validate_origin_lessons(self, origin_lessons: list[str]) -> int:
        """Validate ALL origin lessons for promotion eligibility. Returns the
        minimum distinct-verification count across them. Raises on the first
        ineligible lesson (validation happens BEFORE any write, P0-8)."""
        by_id = {l["lesson_id"]: l for l in self.store.lessons()}
        counts: list[int] = []
        for lesson_id in origin_lessons:
            lesson = by_id.get(lesson_id)
            if lesson is None:
                raise ValueError(f"origin lesson {lesson_id} not found")
            rule = (lesson.get("generalizable_rule") or "").strip()
            distinct = self.store.distinct_verifications(lesson_id)
            problems = []
            if lesson.get("status") not in ("VERIFIED", "PROMOTED"):
                problems.append(f"status={lesson.get('status')}")
            if lesson.get("confidence") != "HIGH":
                problems.append(f"confidence={lesson.get('confidence')}")
            if distinct < PROMOTION_THRESHOLD_VERIFICATIONS:
                problems.append(f"distinct_verifications={distinct}")
            if not rule:
                problems.append("generalizable_rule empty")
            if problems:
                raise ValueError(
                    f"lesson {lesson_id} is not promotable: {', '.join(problems)}")
            counts.append(distinct)
        return min(counts) if counts else 0

    def promote(self, *, name: str, purpose: str, when_to_use: str,
                inputs: str, definitions: str, procedure: str,
                qa: str, common_failures: str, blocking_conditions: str,
                outputs: str, provenance_requirements: str,
                origin_lessons: list[str], reviewer: str) -> str:
        """Write a real skill file (approval assumed: this is the approval
        path). `validation_count` is computed from the lesson store — the
        caller cannot inflate it."""
        store = self.store
        store.ensure_layout()
        validation_count = self._validate_origin_lessons(origin_lessons)
        body = {
            "Purpose": purpose, "When to use": when_to_use, "Inputs": inputs,
            "Definitions": definitions, "Procedure": procedure, "QA": qa,
            "Common failures": common_failures,
            "Blocking conditions": blocking_conditions, "Outputs": outputs,
            "Provenance requirements": provenance_requirements,
        }
        lines = [
            "---",
            f"name: {name}",
            f"description: {purpose[:300]}",
            "version: 1",
            f"origin_lessons: {', '.join(origin_lessons)}",
            f"validation_count: {validation_count}",
            f"last_reviewed: {datetime.date.today().isoformat()}",
            f"reviewed_by: {reviewer}",
            "---",
            "",
        ]
        for section in SKILL_SECTIONS:
            lines.append(f"## {section}")
            lines.append(body[section].strip())
            lines.append("")
        filename = _skill_filename(name)
        target_dir = _skill_target_dir(store)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)
        # validate-first is done; now write the skill, then mark lessons.
        storage.atomic_write_text(path, "\n".join(lines))
        for lesson_id in origin_lessons:
            self.lessons.mark_promoted(lesson_id, filename)
        return path
