"""Snapshot / rollback (P1-12): rollback accepts ONLY snapshots inside
store.snapshots_dir, restores ONLY the durable-memory allowlist, and always
takes a `pre_rollback_<timestamp>` snapshot first so a failed restore never
leaves half-state.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryError, MemoryStore, SnapshotManager  # noqa: E402

from conftest import seeded_store  # noqa: E402
from tmpdir import make_tmp  # noqa: E402


def test_snapshot_then_rollback():
    store = seeded_store(make_tmp("snap"))
    mgr = SnapshotManager(store)
    snap = mgr.create("milestone_demo")
    assert os.path.isdir(snap)
    # LOW-confidence conflicting claim -> pending change, never ACCEPTED
    store.update_scientific_state(
        {"species_ranked_accommodation": "THREE_DISCRETE_MODES"},
        source="scratch note", confidence="LOW")
    text = str(store.scientific_state())
    assert "THREE_DISCRETE_MODES" in text
    assert "连续尺度依赖响应演化" in text  # ACCEPTED claim untouched
    mgr.rollback(snap)
    after = str(store.scientific_state())
    assert "连续尺度依赖响应演化" in after
    assert "THREE_DISCRETE_MODES" not in after


def test_rollback_rejects_external_directory():
    """P1-12: a snapshot directory outside store.snapshots_dir is refused —
    even a plausible one placed right next to it."""
    store = seeded_store(make_tmp("snapx"))
    external = os.path.join(store.root, "sneaky_snapshot")
    os.makedirs(external, exist_ok=True)
    with open(os.path.join(external, "SCIENTIFIC_STATE.yaml"), "w",
              encoding="utf-8") as fh:
        fh.write("meta: {initialized: true}\n")
    raised = False
    try:
        store.rollback(external)
    except MemoryError:
        raised = True
    assert raised, "rollback must refuse directories outside snapshots_dir"
    # and a missing directory is refused too
    raised = False
    try:
        store.rollback(os.path.join(store.snapshots_dir, "does_not_exist"))
    except MemoryError:
        raised = True
    assert raised, "rollback must refuse a missing snapshot directory"


def test_pre_rollback_snapshot_created():
    """P1-12: before restoring, a pre_rollback_* snapshot of the CURRENT
    memory is created automatically."""
    store = seeded_store(make_tmp("snappre"))
    mgr = SnapshotManager(store)
    snap = mgr.create("before_tamper")
    store.update_scientific_state(
        {"species_ranked_accommodation": "TAMPERED"},
        source="scratch note", confidence="LOW")
    mgr.rollback(snap)
    pres = [d for d in os.listdir(store.snapshots_dir)
            if "pre_rollback_" in d]
    assert pres, "a pre_rollback_* snapshot must exist after rollback"
    pre_dir = os.path.join(store.snapshots_dir, pres[0])
    assert os.path.isfile(os.path.join(pre_dir, "SCIENTIFIC_STATE.yaml"))
    assert os.path.isfile(os.path.join(pre_dir, "DATA_REGISTRY.json"))


def test_failed_rollback_restores_entire_pre_state():
    """P0-3: if a rollback write fails mid-way (e.g. on the SECOND durable
    file), the ENTIRE durable memory — including files already replaced
    earlier in the loop — must be restored to the pre-rollback state. A
    half-applied mix of snapshot and live content is never left behind."""
    import core.storage as storage

    store = seeded_store(make_tmp("snapfail"))
    mgr = SnapshotManager(store)
    snap = mgr.create("before_tamper")

    # live (post-tamper) content differs from the snapshot
    live_project = "# LIVE PROJECT MEMORY\nlive marker project\n"
    store.write_project_memory(live_project)
    store.update_scientific_state(
        {"live_marker": "LIVE_STATE_MARKER"},
        source="dataset:ds_mx_canonical", confidence="HIGH")
    live_state = str(store.scientific_state())
    assert "LIVE_STATE_MARKER" in live_state
    # every durable file carries live content now
    live_ledger = store.decisions()
    live_lessons = store.lessons()
    live_registry = store.data_registry()
    live_methods = store.method_registry()
    live_questions = store.open_questions()

    original = storage.atomic_write_text
    state_path = os.path.join(store.memory_dir, "SCIENTIFIC_STATE.yaml")
    fault_injected = {"done": False}

    def flaky(path, text, **kwargs):
        # fail on the SECOND durable file being restored into memory
        if (os.path.abspath(path) == os.path.abspath(state_path)
                and not fault_injected["done"]):
            fault_injected["done"] = True
            raise OSError("injected fault on second durable file")
        return original(path, text, **kwargs)

    storage.atomic_write_text = flaky
    try:
        raised = False
        try:
            mgr.rollback(snap)
        except MemoryError:
            raised = True
        assert raised, "rollback must raise when a restore write fails"
    finally:
        storage.atomic_write_text = original

    # ENTIRE durable memory is back to the pre-rollback (live) state —
    # including PROJECT_MEMORY.md, which was already replaced before the fault
    assert store.project_memory() == live_project
    assert str(store.scientific_state()) == live_state
    assert store.decisions() == live_ledger
    assert store.lessons() == live_lessons
    assert store.data_registry() == live_registry
    assert store.method_registry() == live_methods
    assert store.open_questions() == live_questions


def test_rollback_restores_allowlist_only():
    """P1-12: only the durable-memory allowlist is restored; stray files in a
    snapshot are never copied into memory."""
    store = seeded_store(make_tmp("snapal"))
    mgr = SnapshotManager(store)
    snap = mgr.create("base")
    # plant a stray non-allowlisted file in the snapshot
    with open(os.path.join(snap, "EVIL.txt"), "w", encoding="utf-8") as fh:
        fh.write("should never be restored")
    # mutate a durable file, then roll back
    store.update_scientific_state(
        {"species_ranked_accommodation": "OTHER_VALUE"},
        source="scratch note", confidence="LOW")
    mgr.rollback(snap)
    assert not os.path.exists(os.path.join(store.memory_dir, "EVIL.txt"))
    assert "OTHER_VALUE" not in str(store.scientific_state())


def test_ids_stable_across_rewrites():
    store = seeded_store(make_tmp("snap"))
    first = store.decisions()[0]["decision_id"]
    store.add_decision(topic="t", decision="d", reason="r", source="s")
    assert store.decisions()[0]["decision_id"] == first


if __name__ == "__main__":
    test_snapshot_then_rollback()
    test_rollback_rejects_external_directory()
    test_pre_rollback_snapshot_created()
    test_rollback_restores_allowlist_only()
    test_ids_stable_across_rewrites()
    print("snapshot OK")
