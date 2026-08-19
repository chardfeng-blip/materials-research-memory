"""Retrieval checks: session-question recalls (§32) and the long-context
new-session recall (§33), all fully hermetic (fixture-only, P0-2), plus the
P0-9 profile-isolation invariants:

  * retrieval indexes ONLY core skills + the ACTIVE project profile's skills;
  * the active profile is decided by project configuration
    (`.active_profile` / `MemoryStore(active_profile=...)`), never by query
    keywords;
  * a fresh generic project cannot retrieve another project's conclusions.

The fixture is a SYNTHETIC Material-X / species A/B/C demo — no real research
data is exercised by retrieval tests.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryStore, Retriever  # noqa: E402

from conftest import copy_fixture, seeded_store  # noqa: E402
from tmpdir import make_tmp  # noqa: E402


def _recalled_text(retriever, query, k=3) -> str:
    hits = retriever.retrieve_text(query, k=k)
    return " ".join(h["text"] for h in hits).lower()


def _recalled_kinds(retriever, query, k=5):
    return [h["kind"] for h in retriever.retrieve(query, k=k)]


def test_three_session_questions_recall():
    store = seeded_store(make_tmp("recall"))
    retriever = Retriever(store)

    # A: three-species classification verdict must be recalled (canonical verdict).
    text_a = _recalled_text(retriever, "现在三物种分类的最终结论是什么？")
    assert ("连续" in text_a or "continuous" in text_a), text_a

    # B: Vcav is a per-defect computed descriptor, not intrinsic vdW radius.
    text_b = _recalled_text(retriever, "Vcav 是不是 intrinsic radius？")
    assert "vcav" in text_b and ("intrinsic" in text_b or "vdw" in text_b), text_b

    # C: electronic mechanism — recall its real status (not fabricated).
    text_c = _recalled_text(retriever, "机制现在可以直接做吗？")
    assert ("机制" in text_c or "mechanism" in text_c), text_c
    assert ("尚未确立" in text_c or "not established" in text_c), text_c


def test_long_context_new_session_recall_hermetic():
    """§33 against the hermetic fixture (P0-2): a genuinely new session, given
    only "继续三物种容纳的下一步。", must recall the three-species
    accommodation canonical state."""
    store = seeded_store(make_tmp("recall33"))
    retriever = Retriever(store)
    hits = retriever.retrieve_text("继续三物种容纳的下一步", k=5)
    kinds = [h["kind"] for h in hits]
    texts = " ".join(h["text"] for h in hits).lower()
    assert kinds, "no memory recalled"
    assert "scientific_state" in kinds or "project_memory" in kinds, (kinds, texts)
    assert ("continuous" in texts or "连续" in texts), texts


def _write_skill(store, name: str, text: str) -> None:
    target = store.profile_skills_dir or store.core_skills_dir
    path = os.path.join(target, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_many_skills_do_not_drown_canonical_state():
    """P0-3: with many highly relevant skills, a relevant canonical document
    (scientific_state / project_memory) must still get a Top-K slot, and no
    single kind may monopolize the results."""
    store = seeded_store(make_tmp("drown"))
    for i in range(12):
        _write_skill(store, f"skill_{i:02d}.md",
                     f"# skill {i}\nspecies scale dependent accommodation analysis "
                     "species scale dependent accommodation procedure species "
                     "scale dependent accommodation\n" * 40)
    retriever = Retriever(store)
    hits = retriever.retrieve("species scale dependent accommodation", k=5)
    kinds = [h["kind"] for h in hits]
    assert "scientific_state" in kinds or "project_memory" in kinds, kinds
    assert kinds.count("skill") <= 2, kinds


def test_unrelated_canonical_not_forced():
    """P0-3: when the query only matches skills (canonical documents have zero
    token overlap), no unrelated canonical memory is force-injected."""
    store = MemoryStore(make_tmp("unrel"))
    store.ensure_layout()
    store.write_project_memory(
        "# zebra population dynamics\n\nsavanna grassland rainfall predator "
        "migration herd behavior\n")
    store.update_scientific_state(
        {"grassland_rainfall": "seasonal bimodal"},
        source="scratch/field_census.txt", confidence="LOW")
    for i in range(3):
        _write_skill(store, f"qd_{i}.md",
                     f"# quantum dot synthesis\nquantum dot ligand exchange "
                     f"synthesis procedure case {i}\n")
    retriever = Retriever(store)
    hits = retriever.retrieve("quantum dot synthesis", k=3)
    kinds = [h["kind"] for h in hits]
    assert kinds, "no hits"
    assert "project_memory" not in kinds, kinds
    assert "scientific_state" not in kinds, kinds
    assert all(h["kind"] == "skill" for h in hits), kinds


# ------------------------------------------------------------------ P0-9 isolation
def test_fresh_project_cannot_retrieve_materialx_facts():
    """P0-9: a fresh generic project (no materialx profile active) never
    retrieves the Material-X demo project's conclusions — even when the
    materialx profile directory exists on disk."""
    root = make_tmp("freshiso")
    store = MemoryStore(root)  # no active profile -> profile_skills_dir None
    store.seed()
    store.write_project_memory(
        "# fresh project\n\nnew generic research project, no prior knowledge\n")
    # materialx profile directory exists on disk but is NOT active
    os.makedirs(os.path.join(root, "profiles", "materialx", "skills"), exist_ok=True)
    with open(os.path.join(root, "profiles", "materialx", "skills",
                           "species_accommodation_analysis.md"), "w",
              encoding="utf-8") as fh:
        fh.write("# species accommodation\nthree species accommodation Material-X A B C\n")

    retriever = Retriever(store)
    for query in ("三物种容纳", "three species accommodation Material-X", "A B C"):
        texts = _recalled_text(retriever, query, k=5)
        assert "material-x" not in texts, (query, texts)
        assert "三物种容纳" not in texts or "fresh project" in texts, (query, texts)
    assert retriever.retrieve("three species accommodation", k=5) == []


def test_active_profile_can_retrieve_project_skills():
    """P0-9: with profile materialx active, its skills ARE indexed and
    retrievable."""
    store = seeded_store(make_tmp("actiso"))  # active_profile="materialx"
    retriever = Retriever(store)
    hits = retriever.retrieve(
        "species accommodation analysis CV matched design", k=5)
    kinds = [h["kind"] for h in hits]
    ids = [h["id"] for h in hits]
    assert "skill" in kinds, (kinds, ids)
    assert "skill:species_accommodation_analysis.md" in ids, ids


def test_inactive_profile_not_indexed():
    """P0-9: the same materialx profile is NOT indexed when another profile
    (or none) is active — the project config decides, never the query text."""
    root = make_tmp("inactiso")
    copy_fixture(root)
    store = MemoryStore(root, active_profile="other")  # materialx inactive
    retriever = Retriever(store)
    hits = retriever.retrieve(
        "cavity Vcav Dmin Rg DR1 tessellate", k=5)
    ids = [h["id"] for h in hits]
    assert "skill:cavity_analysis.md" not in ids, ids
    assert "skill:species_accommodation_analysis.md" not in ids, ids
    # core skills remain indexed for every project
    hits2 = retriever.retrieve("scientific claim gate ten checks", k=5)
    assert "skill:claim_gate_demo.md" in [h["id"] for h in hits2]


def test_active_profile_is_config_not_query_keywords():
    """P0-9: activating the profile requires configuration; a query full of
    materialx keywords does NOT activate it."""
    root = make_tmp("kwiso")
    copy_fixture(root)
    store = MemoryStore(root)  # no .active_profile -> inactive
    retriever = Retriever(store)
    hits = retriever.retrieve("Material-X three species accommodation", k=5)
    ids = [h["id"] for h in hits]
    assert "skill:species_accommodation_analysis.md" not in ids, ids


if __name__ == "__main__":
    test_three_session_questions_recall()
    test_long_context_new_session_recall_hermetic()
    test_many_skills_do_not_drown_canonical_state()
    test_unrelated_canonical_not_forced()
    test_fresh_project_cannot_retrieve_materialx_facts()
    test_active_profile_can_retrieve_project_skills()
    test_inactive_profile_not_indexed()
    test_active_profile_is_config_not_query_keywords()
    print("retrieval OK")
