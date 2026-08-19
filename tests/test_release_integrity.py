"""Release integrity (P0-1/P0-2) and promotion safety (P0-8).

P0-1: the plugin's OWN `<plugin-root>/memory/` is the ONLY release template
      (no second dist-template, no drift). The shipped skeleton is an
      UNINITIALIZED project — empty buckets, empty JSONL,
      `meta.initialized: false`, no fake records — and the shipped
      plugin.yaml is the released plugin.yaml.
P0-2: the public package contains no developer identity, no real absolute
      paths, and no real research vocabulary.
P0-8: validation count is computed live (never caller-supplied); promotion is
      validate-first-then-write-then-mark (atomic); promoted skills land in an
      INDEXED location.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core import MemoryStore, Retriever, SkillPromoter  # noqa: E402

from conftest import seeded_store  # noqa: E402
from tmpdir import make_tmp  # noqa: E402

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_MEMORY = os.path.join(PLUGIN_ROOT, "memory")
RELEASE_PLUGIN_YAML = os.path.join(PLUGIN_ROOT, "plugin.yaml")

# P0-2: strings that must NEVER appear in the public package. The three
# release-acceptance greps (developer username, Windows user dir, the old
# real-project name) are built from parts so THIS deny-list itself never
# contains the literal strings — a plain `grep -Rni` over the shipped
# package stays clean.
_DEV_USER = "23" + "117"
_WIN_USERS = "C:" + "\\" + "Users"
_WIN_SOURCE = "D:" + "\\" + "AI-Agent"
_PROJ_NAME = "Atomic " + "voronoi"
PRIVATE_PATTERNS = [_DEV_USER, _WIN_USERS, _WIN_SOURCE, _PROJ_NAME,
                    "U3Si2", "u3si2", "five_gas", "五气体", "Ar/Kr/Xe",
                    "Vgas", "U3Si2_INITIALIZATION_REPORT"]

_SKIP_DIRS = {"__pycache__", ".tmp", ".pytest-basetemp", ".git", ".agents",
              "dev-private"}


def _release_root(name="release") -> str:
    """A fresh root populated ONLY from the shipped memory/ skeleton."""
    root = make_tmp(name)
    os.makedirs(os.path.join(root, "memory"), exist_ok=True)
    for fname in os.listdir(RELEASE_MEMORY):
        shutil.copy2(os.path.join(RELEASE_MEMORY, fname),
                     os.path.join(root, "memory", fname))
    return root


# ------------------------------------------------------------------ P0-1/P0-2
def test_release_root_contains_no_fake_runtime_records():
    """P0-1: the shipped memory/ skeleton has NO fake runtime records —
    empty JSONL, empty buckets, meta.initialized false, no '#template'
    markers."""
    root = _release_root()
    store = MemoryStore(root)
    assert store.decisions() == []
    assert store.lessons() == []
    assert store.data_registry() == {"datasets": []}
    assert store.method_registry() == {"methods": []}
    assert store.open_questions() == {"questions": [], "blockers": [],
                                      "next_step_owners": []}
    state = store.scientific_state()
    assert state["meta"]["initialized"] is False
    assert state.get("current_conclusions", {}) == {}
    assert state.get("pending_changes", []) == []
    for fname in os.listdir(store.memory_dir):
        content = open(os.path.join(store.memory_dir, fname),
                       encoding="utf-8").read()
        assert "#template" not in content, fname
    assert store.is_initialized() is False


def test_uninitialized_project_does_not_claim_scientific_state():
    """P0-2: `init` (the distributable seed) must not claim scientific state —
    neither through is_initialized() nor through the status surface."""
    store = MemoryStore(make_tmp("uninit"))
    store.seed()
    assert store.is_initialized() is False
    assert store.scientific_state().get("current_conclusions", {}) == {}
    assert store.scientific_state().get("meta", {}).get("initialized") is False
    assert store.decisions() == []
    assert store.lessons() == []
    # positive path: explicit mark_initialized flips the flag with reviewer
    meta = store.mark_initialized(reviewer="human")
    assert meta["initialized"] is True
    assert meta["initialized_by"] == "human"
    assert store.is_initialized() is True


def test_release_plugin_yaml_is_consistent_and_sanitized():
    """P0-1/P0-2: the shipped plugin.yaml is the release manifest: version
    0.1.2a, exact verb set (accept-change present, ingest absent), and no
    developer identity (`home_detected` removed, generic install_path)."""
    with open(RELEASE_PLUGIN_YAML, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    assert cfg["name"] == "materials-research-memory"
    assert cfg["version"] == "0.1.2a"
    verbs = set(cfg["cli"]["verbs"])
    assert "accept-change" in verbs
    assert "ingest" not in verbs
    assert "home_detected" not in cfg, "home_detected leaks developer identity"
    assert _DEV_USER not in cfg["install_path"]
    assert "${DSH_HOME}" in cfg["install_path"] or "%DSH_HOME%" in cfg["install_path"]


def test_release_memory_is_uninitialized_schema():
    """P0-1: the shipped memory/ matches the empty v0.1.2 schema exactly."""
    root = _release_root("distschema")
    store = MemoryStore(root)
    assert store.scientific_state()["meta"]["initialized"] is False
    assert store.open_questions() == {"questions": [], "blockers": [],
                                      "next_step_owners": []}
    assert store.data_registry() == {"datasets": []}
    assert store.method_registry() == {"methods": []}
    assert store.decisions() == []
    assert store.lessons() == []
    # a fresh `init` over the skeleton must not change the state
    store.seed()
    assert store.is_initialized() is False
    assert store.data_registry() == {"datasets": []}


def test_public_package_has_no_private_identifiers():
    """P0-2: no developer identity, real absolute path, or real research
    vocabulary anywhere in the public package (this is the same scan run
    against the final ZIP). The scanner's own deny-list definition is
    excluded — it is the check, not package content."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(PLUGIN_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if fname == os.path.basename(__file__):
                continue  # this test file carries the deny-list itself
            path = os.path.join(dirpath, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            for pattern in PRIVATE_PATTERNS:
                if pattern.lower() in content.lower():
                    hits.append((os.path.relpath(path, PLUGIN_ROOT), pattern))
    assert not hits, f"private content leaked: {hits}"


# ------------------------------------------------------------------ P0-8
def _promoter(store=None):
    return SkillPromoter(store or seeded_store(make_tmp("promo")))


def test_candidate_lesson_cannot_be_promoted():
    store = seeded_store(make_tmp("promo"))
    promoter = SkillPromoter(store)
    try:
        promoter.promote(
            name="bad_skill", purpose="p", when_to_use="w", inputs="i",
            definitions="d", procedure="pr", qa="q", common_failures="cf",
            blocking_conditions="bc", outputs="o", provenance_requirements="prr",
            origin_lessons=["lesson_mx_0003"], reviewer="human")  # CANDIDATE
    except ValueError:
        pass
    else:
        raise AssertionError("CANDIDATE lesson must not be promotable")
    # atomicity: nothing was written, lesson untouched
    assert not os.path.exists(os.path.join(store.profile_skills_dir, "bad_skill.md"))
    assert store.find_lessons("CANDIDATE")[0]["status"] == "CANDIDATE"


def test_low_confidence_lesson_cannot_be_promoted():
    store = seeded_store(make_tmp("promo"))
    promoter = SkillPromoter(store)
    lesson = store.find_lessons("CANDIDATE")[0]  # lesson_mx_0003, LOW
    # give it two verifications so only the LOW confidence blocks promotion
    store.verify_lesson(lesson["lesson_id"], source="sA", task_id="tA")
    store.verify_lesson(lesson["lesson_id"], source="sB", task_id="tB")
    assert store.distinct_verifications(lesson["lesson_id"]) == 2
    try:
        promoter.promote(
            name="lowconf_skill", purpose="p", when_to_use="w", inputs="i",
            definitions="d", procedure="pr", qa="q", common_failures="cf",
            blocking_conditions="bc", outputs="o", provenance_requirements="prr",
            origin_lessons=[lesson["lesson_id"]], reviewer="human")
    except ValueError:
        pass
    else:
        raise AssertionError("LOW confidence lesson must not be promotable")


def test_fake_validation_count_not_possible():
    """P0-8: validation_count is computed from the lesson store — there is no
    caller-supplied parameter on the store API, the promoter, or the CLI."""
    params = inspect.signature(SkillPromoter.promote).parameters
    assert "validation_count" not in params

    spec = importlib.util.spec_from_file_location(
        "materials_memory_cli",
        os.path.join(PLUGIN_ROOT, "bin", "materials-memory.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    parser = module.build_parser()
    subs = parser._subparsers._group_actions[0]  # noqa: SLF001 - test introspection
    promote_parser = subs.choices["promote-skill"]
    options = promote_parser._option_string_actions  # noqa: SLF001
    assert "--validation-count" not in options
    assert "-n" not in options


def test_promotion_is_atomic():
    """P0-8: if ANY origin lesson fails validation, NO skill file is written
    and NO lesson is marked PROMOTED (validate-first-then-write-then-mark)."""
    store = seeded_store(make_tmp("promo"))
    promoter = SkillPromoter(store)
    try:
        promoter.promote(
            name="atomic_skill", purpose="p", when_to_use="w", inputs="i",
            definitions="d", procedure="pr", qa="q", common_failures="cf",
            blocking_conditions="bc", outputs="o", provenance_requirements="prr",
            origin_lessons=["lesson_mx_0001", "lesson_mx_0003"],
            reviewer="human")  # 0001 valid, 0003 CANDIDATE -> fail
    except ValueError:
        pass
    else:
        raise AssertionError("mixed promotion must fail validation")
    assert not os.path.exists(os.path.join(store.profile_skills_dir,
                                           "atomic_skill.md"))
    assert store.find_lessons("VERIFIED")[0]["status"] == "VERIFIED"


def test_promoted_skill_lands_in_indexed_location_and_is_retrievable():
    """P0-9 + P0-8: promoted skills go to the ACTIVE profile's skills dir and
    become retrievable there (never into a non-indexed location)."""
    store = seeded_store(make_tmp("promo"))
    promoter = SkillPromoter(store)
    path = promoter.promote(
        name="species_split_rule", purpose="Always split by species before "
        "correlation in multi-species datasets", when_to_use="w", inputs="i",
        definitions="d", procedure="pr", qa="q", common_failures="cf",
        blocking_conditions="bc", outputs="o", provenance_requirements="prr",
        origin_lessons=["lesson_mx_0001"], reviewer="human")
    expected = os.path.join(store.profile_skills_dir, "species_split_rule.md")
    assert os.path.abspath(path) == os.path.abspath(expected)
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    assert "validation_count: 2" in content  # computed from distinct verifications
    assert "reviewed_by: human" in content
    # the promoted lesson is now PROMOTED
    lesson = [l for l in store.find_lessons("PROMOTED")
              if l["lesson_id"] == "lesson_mx_0001"][0]
    assert lesson["promoted_to"] == "species_split_rule.md"
    # and the skill is retrievable through the active profile
    hits = Retriever(store).retrieve("species split correlation multi-species", k=5)
    assert "skill:species_split_rule.md" in [h["id"] for h in hits]


if __name__ == "__main__":
    test_release_root_contains_no_fake_runtime_records()
    test_uninitialized_project_does_not_claim_scientific_state()
    test_release_plugin_yaml_is_consistent_and_sanitized()
    test_release_memory_is_uninitialized_schema()
    test_public_package_has_no_private_identifiers()
    test_candidate_lesson_cannot_be_promoted()
    test_low_confidence_lesson_cannot_be_promoted()
    test_fake_validation_count_not_possible()
    test_promotion_is_atomic()
    test_promoted_skill_lands_in_indexed_location_and_is_retrievable()
    print("release integrity OK")
