"""Contradiction detection & claim/decision safety (P0-3/P0-4/P0-6).

Core invariant (claims AND decisions): an UNREVIEWED conflicting claim/
decision may NEVER change an ACCEPTED one. Superseding happens ONLY through
the explicit reviewer path (accept_change / accept_decision).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryStore, reflect_task  # noqa: E402
from core import transition_policy as policy  # noqa: E402

from conftest import seeded_store  # noqa: E402
from tmpdir import make_tmp  # noqa: E402

CANONICAL = "dataset:ds_mx_canonical"
SCRATCH = "scratch hypothesis note"
TOPIC = "species_ranked_accommodation"
CONFLICT_VALUE = "THREE_DISCRETE_MODES"


def test_contradictory_fact_is_not_auto_accepted():
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {TOPIC: CONFLICT_VALUE},
        source=SCRATCH, confidence="HIGH")
    out = outcomes[TOPIC]
    assert out["status"] == "CANDIDATE"
    assert out["requires_review"] is True
    assert out["conflicts"] == [TOPIC]
    assert out.get("change_id")


def test_canonical_high_confidence_no_conflict_auto_commits():
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {"mechanism_readiness": "not yet"},
        source=CANONICAL, confidence="HIGH")
    out = outcomes["mechanism_readiness"]
    assert out["status"] == "ACCEPTED"
    assert not out.get("requires_review", False)


def test_unreviewed_fact_conflict_keeps_old_accepted():
    """P0-3: conflicting LOW/scratch claim -> old stays ACCEPTED, new is a
    CANDIDATE pending change; nothing is superseded."""
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {TOPIC: CONFLICT_VALUE},
        source=SCRATCH, confidence="LOW")
    assert outcomes[TOPIC]["status"] == "CANDIDATE"
    state = store.scientific_state()
    old = state["current_conclusions"][TOPIC]
    assert old["status"] == "ACCEPTED"
    assert state["superseded_results"] == []


def test_low_confidence_fact_cannot_supersede():
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {TOPIC: "DISCRETE"}, source=SCRATCH, confidence="LOW")
    assert outcomes[TOPIC]["status"] == "CANDIDATE"


def test_noncanonical_fact_cannot_supersede():
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {TOPIC: "DISCRETE"},
        source="scratch/final_notes.txt", confidence="HIGH")
    assert outcomes[TOPIC]["status"] == "CANDIDATE"
    assert outcomes[TOPIC]["requires_review"] is True


def test_accept_change_explicitly_supersedes_old():
    """P0-3: accept_change(change_id) is the ONLY supersede path for claims."""
    store = seeded_store(make_tmp("contra"))
    outcomes = store.update_scientific_state(
        {TOPIC: CONFLICT_VALUE},
        source=SCRATCH, confidence="HIGH")
    change_id = outcomes[TOPIC]["change_id"]
    claim = store.accept_change(change_id, reviewer="human")
    assert claim["status"] == "ACCEPTED"
    assert claim["reviewed_by"] == "human"
    state = store.scientific_state()
    old = state["superseded_results"][0]
    assert old["status"] == "SUPERSEDED"
    assert old["superseded_by"] == claim["claim_id"]
    assert state["current_conclusions"][TOPIC]["value"] == CONFLICT_VALUE
    assert claim["contradictions"][0]["kind"] == "CONTRADICTION"


def test_change_id_stable():
    """P0-3: pending changes are addressed by stable change_id, never an
    array index."""
    store = seeded_store(make_tmp("contra"))
    out1 = store.update_scientific_state(
        {TOPIC: "DISCRETE"}, source=SCRATCH, confidence="HIGH")
    cid = out1[TOPIC]["change_id"]
    out2 = store.update_scientific_state(
        {"mechanism_status": "ready"}, source=SCRATCH, confidence="LOW")
    # both changes are addressable by id even after another change is appended
    store.accept_change(cid, reviewer="human")
    assert store.accept_change(out2["mechanism_status"]["change_id"],
                               reviewer="human")["status"] == "ACCEPTED"


# ------------------------------------------------------------------ decisions
def test_conflicting_low_confidence_decision_does_not_supersede_accepted():
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="B/C species regime",
        decision="Reclassify B/C as two discrete regimes",
        reason="hypothetical", source=SCRATCH, confidence="LOW")
    old = store.decisions()[0]
    assert old["status"] == "ACCEPTED"
    assert "superseded_by" not in old
    assert entry["status"] == "CANDIDATE"
    assert entry["requires_review"] is True
    contra = entry["contradictions"][0]
    assert contra["conflicting_decision_id"] == old["decision_id"]


def test_high_confidence_non_canonical_conflict_still_requires_review():
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="B/C species regime",
        decision="B/C form two robust discrete regimes",
        reason="hypothetical", source=SCRATCH, confidence="HIGH")
    assert entry["status"] == "CANDIDATE"
    assert entry["requires_review"] is True
    assert store.decisions()[0]["status"] == "ACCEPTED"


def test_reviewer_approval_supersedes_with_full_history():
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="B/C species regime",
        decision="B/C form two robust discrete regimes (reviewed)",
        reason="strong evidence", source=SCRATCH, confidence="HIGH")
    accepted = store.accept_decision(entry["decision_id"], reviewer="human")
    assert accepted["status"] == "ACCEPTED"
    assert accepted["reviewed_by"] == "human"
    old = store.decisions()[0]
    assert old["status"] == "SUPERSEDED"
    assert old["superseded_by"] == entry["decision_id"]
    review = accepted["contradictions"][-1]
    assert review["old_status"] == "ACCEPTED"
    assert review["new_status"] == "ACCEPTED"


def test_non_conflicting_eligible_decision_still_accepted():
    """P0-6: an eligible (registry-canonical + HIGH + no conflict) decision
    REQUESTED as ACCEPTED is auto-accepted; the eligible path does not
    regress. (The DEFAULT is CANDIDATE — see the direct_* tests.)"""
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="unrelated new topic", decision="record this",
        reason="r", source=CANONICAL, confidence="HIGH", status="ACCEPTED")
    assert entry["status"] == "ACCEPTED"
    assert not entry.get("requires_review", False)


def test_direct_low_confidence_decision_not_accepted():
    """P0-6: add_decision must default to CANDIDATE; LOW confidence can never
    auto-accept even if the caller asks for ACCEPTED."""
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="fresh topic", decision="d", reason="r", source=SCRATCH,
        confidence="LOW", status="ACCEPTED")
    assert entry["status"] == "CANDIDATE"
    assert entry["requires_review"] is True


def test_direct_noncanonical_decision_not_accepted():
    """P0-6: an unregistered source (even named final) cannot auto-accept."""
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="fresh topic", decision="d", reason="r",
        source="scratch/final_notes.txt", confidence="HIGH", status="ACCEPTED")
    assert entry["status"] == "CANDIDATE"
    assert entry["requires_review"] is True


def test_auto_accept_policy_single_source_of_truth():
    """P0-6: the store's decision matches the transition policy exactly."""
    store = seeded_store(make_tmp("contra"))
    entry = store.add_decision(
        topic="policy topic", decision="d", reason="r", source=CANONICAL,
        confidence="HIGH", status="ACCEPTED")
    verdict = policy.canonical_authority(
        store.data_registry().get("datasets", []), CANONICAL)
    expected = policy.can_auto_accept_decision(
        canonical=verdict.canonical, confidence="HIGH", conflict=False)
    assert (entry["status"] == "ACCEPTED") == expected


def test_import_accepted_decision_records_reviewer():
    """P0-6: the migration/import path requires an explicit reviewer."""
    store = seeded_store(make_tmp("contra"))
    entry = store.import_accepted_decision(
        topic="historic", decision="old result", reason="history",
        source="legacy path", reviewer="migration", confidence="HIGH")
    assert entry["status"] == "ACCEPTED"
    assert entry["reviewed_by"] == "migration"
    assert entry["imported"] is True


def test_reflection_decision_requires_review_split():
    store = seeded_store(make_tmp("contra"))
    path = reflect_task(
        store, task_id="t_rev", task_summary="s",
        new_decisions=[{
            "topic": "B/C species regime",
            "decision": "Reclassify B/C as two discrete regimes",
            "reason": "hypothetical", "source": SCRATCH,
            "confidence": "HIGH"}],
        canonical_source=None)
    text = open(path, encoding="utf-8").read()
    assert "requires_review" in text
    rows = store.decisions()
    assert rows[0]["status"] == "ACCEPTED"
    assert rows[-1]["status"] == "CANDIDATE"


if __name__ == "__main__":
    test_contradictory_fact_is_not_auto_accepted()
    test_canonical_high_confidence_no_conflict_auto_commits()
    test_unreviewed_fact_conflict_keeps_old_accepted()
    test_low_confidence_fact_cannot_supersede()
    test_noncanonical_fact_cannot_supersede()
    test_accept_change_explicitly_supersedes_old()
    test_change_id_stable()
    test_conflicting_low_confidence_decision_does_not_supersede_accepted()
    test_high_confidence_non_canonical_conflict_still_requires_review()
    test_reviewer_approval_supersedes_with_full_history()
    test_non_conflicting_eligible_decision_still_accepted()
    test_direct_low_confidence_decision_not_accepted()
    test_direct_noncanonical_decision_not_accepted()
    test_auto_accept_policy_single_source_of_truth()
    test_import_accepted_decision_records_reviewer()
    test_reflection_decision_requires_review_split()
    print("contradiction detection OK")
