"""Lesson lifecycle (P0-7): CANDIDATE -> VERIFIED -> PROMOTED with INDEPENDENT
verifications. `times_verified` comes from distinct (source, task_id)
verification identities; a duplicate verification never increments it."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryStore, LessonManager  # noqa: E402

from conftest import seeded_store  # noqa: E402
from tmpdir import make_tmp  # noqa: E402


def test_candidate_lesson_does_not_touch_scientific_state():
    store = seeded_store(make_tmp("lesson"))
    before = store.scientific_state().get("current_conclusions", {})
    mgr = LessonManager(store)
    lesson = mgr.record(
        trigger="report", failure="x", root_cause="y", fix="z",
        generalizable_rule="r", scope="project",
        source="test source", confidence="MEDIUM")
    assert lesson["status"] == "CANDIDATE"
    assert store.scientific_state().get("current_conclusions", {}) == before


def test_verification_increments_and_promotes_only_when_eligible():
    store = seeded_store(make_tmp("lesson"))
    mgr = LessonManager(store)
    lesson = mgr.record(
        trigger="t", failure="f", root_cause="rc", fix="fx",
        generalizable_rule="Always split by species before correlation",
        scope="demo", source="s1", confidence="HIGH")
    mgr.verify(lesson["lesson_id"], source="s2", task_id="taskA")
    assert store.distinct_verifications(lesson["lesson_id"]) == 1
    # not eligible with only one distinct verification
    assert not any(c["lesson_id"] == lesson["lesson_id"]
                   for c in mgr.promotion_candidates())
    mgr.verify(lesson["lesson_id"], source="s3", task_id="taskB")
    candidates = mgr.promotion_candidates()
    mine = [c for c in candidates if c["lesson_id"] == lesson["lesson_id"]]
    assert len(mine) == 1 and mine[0]["times_verified"] == 2
    mgr.mark_promoted(lesson["lesson_id"], "statistical_split.md")
    assert store.find_lessons("PROMOTED")[0]["promoted_to"] == "statistical_split.md"


def test_low_confidence_lesson_never_eligible():
    store = seeded_store(make_tmp("lesson"))
    mgr = LessonManager(store)
    lesson = mgr.record(
        trigger="t", failure="f", root_cause="rc", fix="fx",
        generalizable_rule="rule", scope="demo",
        source="s1", confidence="LOW")
    mgr.verify(lesson["lesson_id"], source="s2", task_id="taskA")
    mgr.verify(lesson["lesson_id"], source="s3", task_id="taskB")
    # the LOW-confidence lesson is never a promotion candidate, even with
    # two distinct verifications (fixture lessons may be candidates)
    assert not any(c["lesson_id"] == lesson["lesson_id"]
                   for c in mgr.promotion_candidates())


def test_duplicate_verification_does_not_increment():
    """P0-7: the same (source, task_id) verification must not count twice."""
    store = seeded_store(make_tmp("lesson"))
    mgr = LessonManager(store)
    lesson = mgr.record(
        trigger="t", failure="f", root_cause="rc", fix="fx",
        generalizable_rule="rule", scope="demo",
        source="s1", confidence="HIGH")
    mgr.verify(lesson["lesson_id"], source="run1", task_id="taskA")
    updated = mgr.verify(lesson["lesson_id"], source="run1", task_id="taskA")  # duplicate
    assert updated["times_verified"] == 1
    assert len(updated["verifications"]) == 1
    assert store.distinct_verifications(lesson["lesson_id"]) == 1


def test_two_independent_tasks_do_increment():
    """P0-7: two distinct task_ids (even from one source) both count."""
    store = seeded_store(make_tmp("lesson"))
    mgr = LessonManager(store)
    lesson = mgr.record(
        trigger="t", failure="f", root_cause="rc", fix="fx",
        generalizable_rule="rule", scope="demo",
        source="s1", confidence="HIGH")
    mgr.verify(lesson["lesson_id"], source="run1", task_id="taskA")
    mgr.verify(lesson["lesson_id"], source="run1", task_id="taskB")
    assert store.find_lessons("VERIFIED")[0]["times_verified"] == 2


if __name__ == "__main__":
    test_candidate_lesson_does_not_touch_scientific_state()
    test_verification_increments_and_promotes_only_when_eligible()
    test_low_confidence_lesson_never_eligible()
    test_duplicate_verification_does_not_increment()
    test_two_independent_tasks_do_increment()
    print("lesson lifecycle OK")
