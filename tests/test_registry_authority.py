"""Registry authority (P0-5): the write authority for scientific state is
decided EXCLUSIVELY by resolution against DATA_REGISTRY, never by filename
heuristics or loose substring matching. Resolution order: dataset:<id> exact
match -> normalized exact path -> unique basename. Unregistered sources can
never be canonical (auto-accepted) and are never silently accepted.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryError, MemoryStore  # noqa: E402
from core import transition_policy as policy  # noqa: E402

from conftest import copy_fixture  # noqa: E402
from tmpdir import make_tmp  # noqa: E402

REGISTERED_PATH = "data/material_x/master_clean.csv"
REGISTERED_BASENAME = "master_clean.csv"


def _store(name="reg"):
    root = make_tmp(name)
    copy_fixture(root)
    return MemoryStore(root, active_profile="materialx")


def _datasets(store):
    return store.data_registry().get("datasets", [])


def test_dataset_id_resolution_is_canonical():
    store = _store()
    assert store.is_canonical_source("dataset:ds_mx_canonical") is True
    assert policy.registry_status_for(_datasets(store),
                                      "dataset:ds_mx_canonical") == "FROZEN"
    assert policy.canonical_authority(
        _datasets(store), "dataset:ds_mx_canonical").canonical is True


def test_exact_path_resolution_is_canonical():
    store = _store()
    assert store.is_canonical_source(REGISTERED_PATH) is True
    assert store.is_canonical_source(
        "data\\material_x\\master_clean.csv") is True  # normalized
    assert policy.registry_status_for(_datasets(store),
                                      REGISTERED_PATH) == "FROZEN"


def test_unique_basename_resolution_is_canonical():
    store = _store()
    # the basename of the registered path is unique in the registry
    assert store.is_canonical_source(REGISTERED_BASENAME) is True
    assert policy.registry_status_for(_datasets(store),
                                      REGISTERED_BASENAME) == "FROZEN"


def test_unregistered_source_never_canonical():
    store = _store()
    for source in (
        "scratch/final_notes.txt",
        "conclusions.md",
        "memory/SCIENTIFIC_STATE.yaml",   # file exists on disk but unregistered
        "SCIENTIFIC_STATE",               # loose partial of a registered name
        "notes",
        "",
    ):
        assert store.is_canonical_source(source) is False, source
        assert policy.registry_status_for(_datasets(store), source) is None, source
        verdict = policy.canonical_authority(_datasets(store), source)
        assert verdict.canonical is False, source
        assert verdict.reason != "registered-ok", source


def test_ambiguous_basename_not_canonical():
    store = _store()
    store.register_dataset(
        dataset_id="ds_second", name="second master", path="scratch/master_clean.csv",
        version="1", status="FROZEN", scope="demo", rows=1,
        columns=["x"], definition="duplicate basename", source="fixture")
    # "master_clean.csv" now matches two registered paths -> ambiguous -> no authority
    assert store.is_canonical_source(REGISTERED_BASENAME) is False
    assert policy.registry_status_for(_datasets(store), REGISTERED_BASENAME) is None
    # the explicit dataset: id still resolves unambiguously
    assert store.is_canonical_source("dataset:ds_mx_canonical") is True
    assert store.is_canonical_source("dataset:ds_second") is True


def test_unregistered_source_never_auto_accepted():
    store = _store()
    outcomes = store.update_scientific_state(
        {"mechanism_status": "ready"},
        source="scratch/final_notes.txt", confidence="HIGH")
    assert outcomes["mechanism_status"]["status"] == "CANDIDATE"
    assert outcomes["mechanism_status"]["requires_review"] is True


def test_register_dataset_validates_status():
    store = _store()
    store.register_dataset(
        dataset_id="ds_ref", name="reference set", path="scratch/ref.csv",
        version="1", status="REFERENCE", scope="demo", rows=2,
        columns=["a"], definition="reference but not canonical", source="fixture")
    # REFERENCE is registered (resolvable) but NOT in the canonical status set
    assert policy.registry_status_for(_datasets(store), "dataset:ds_ref") == "REFERENCE"
    assert policy.canonical_authority(
        _datasets(store), "dataset:ds_ref").canonical is False
    assert store.is_canonical_source("dataset:ds_ref") is False
    # a canonical status grants authority
    store.register_dataset(
        dataset_id="ds_frozen2", name="frozen2", path="scratch/frozen2.csv",
        version="1", status="FROZEN", scope="demo", rows=2,
        columns=["a"], definition="canonical", source="fixture")
    assert store.is_canonical_source("dataset:ds_frozen2") is True


def test_register_dataset_rejects_bad_status():
    store = _store()
    raised = False
    try:
        store.register_dataset(
            dataset_id="ds_bad", name="bad", path="x.csv", version="1",
            status="WHATEVER", scope="demo", rows=1, columns=["a"],
            definition="bad", source="fixture")
    except MemoryError:
        raised = True
    assert raised, "register_dataset must reject an unrecognized status"


if __name__ == "__main__":
    test_dataset_id_resolution_is_canonical()
    test_exact_path_resolution_is_canonical()
    test_unique_basename_resolution_is_canonical()
    test_unregistered_source_never_canonical()
    test_ambiguous_basename_not_canonical()
    test_unregistered_source_never_auto_accepted()
    test_register_dataset_validates_status()
    test_register_dataset_rejects_bad_status()
    print("registry authority OK")
