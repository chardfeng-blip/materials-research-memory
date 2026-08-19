"""CLI surface consistency (v0.1.2).

P0-1: `init` must run, be idempotent, and leave a PARSABLE empty state
      (the v0.1.0 bug wrote an empty DATA_REGISTRY.json).
P0-1: a freshly initialized project must report `project initialized: NO`
      (no fake runtime records).
P0-2: the declared verb set (plugin.yaml cli.verbs) must EXACTLY match the
      argparse verbs; `ingest` must not be declared anywhere.
P0-3: `accept-change <change_id> --reviewer` is reachable through the CLI.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core import MemoryStore  # noqa: E402

from conftest import copy_fixture  # noqa: E402
from tmpdir import make_tmp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_cli():
    """Load bin/materials-memory.py by file path (the CLI name contains a
    hyphen, so it is not a plain importable module name)."""
    spec = importlib.util.spec_from_file_location(
        "materials_memory_cli", os.path.join(ROOT, "bin", "materials-memory.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


cli = _load_cli()


def _plugin_verbs() -> set[str]:
    with open(os.path.join(ROOT, "plugin.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return set(cfg["cli"]["verbs"])


def _argparse_verbs() -> set[str]:
    parser = cli.build_parser()
    subs = parser._subparsers._group_actions[0]  # noqa: SLF001 - test-only introspection
    return set(subs.choices)


def test_declared_verbs_match_argparse():
    declared = _plugin_verbs()
    actual = _argparse_verbs()
    assert declared == actual, f"verb drift: {sorted(declared ^ actual)}"
    assert "ingest" not in declared and "ingest" not in actual


def test_cli_init_works_and_is_idempotent():
    root = make_tmp("init")
    assert cli.main(["--root", root, "init"]) == 0
    store = MemoryStore(root)
    assert os.path.isdir(store.memory_dir)
    for path in (store.project_memory_path, store.scientific_state_path,
                 store.decision_ledger_path, store.lesson_memory_path,
                 store.open_questions_path, store.data_registry_path,
                 store.method_registry_path):
        assert os.path.exists(path)
    # init must leave every memory file in a PARSABLE state
    assert store.data_registry() == {"datasets": []}
    assert store.open_questions() == {"questions": [], "blockers": [],
                                      "next_step_owners": []}
    assert store.method_registry() == {"methods": []}
    # seed one decision; a second `init` must not clobber existing memory
    store.add_decision(topic="t", decision="d", reason="r", source="s")
    assert cli.main(["--root", root, "init"]) == 0
    rows = store.decisions()
    assert len(rows) == 1 and rows[0]["decision"] == "d"
    assert store.data_registry() == {"datasets": []}


def test_status_reports_not_initialized_on_fresh_project():
    """P0-1: a fresh `init` (the distributable template) must NOT claim
    scientific state."""
    root = make_tmp("statusfresh")
    assert cli.main(["--root", root, "init"]) == 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(["--root", root, "status"]) == 0
    text = buf.getvalue()
    assert "project initialized: NO" in text, text
    assert "project initialized: YES" not in text


def test_status_reports_initialized_on_fixture():
    root = make_tmp("statusinit")
    copy_fixture(root)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(["--root", root, "--profile", "materialx", "status"]) == 0
    text = buf.getvalue()
    assert "project initialized: YES" in text, text
    assert "active profile: materialx" in text, text


def test_cli_accept_change_supersedes_after_review():
    """P0-3 end-to-end: a conflicting unreviewed fact lands as CANDIDATE; the
    CLI `accept-change` (stable change_id) is the explicit supersede path."""
    root = make_tmp("acceptchange")
    copy_fixture(root)
    store = MemoryStore(root, active_profile="materialx")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main([
            "--root", root, "reflect", "--task-id", "t_cfg",
            "--summary", "conflicting demo claim",
            "--facts",
            '{"topic": "species_ranked_accommodation", '
            '"value": "THREE_DISCRETE_MODES", "source": "scratch note"}',
            "--confidence", "HIGH"])
    assert rc == 0, buf.getvalue()
    state = store.scientific_state()
    assert state["current_conclusions"]["species_ranked_accommodation"]["status"] == "ACCEPTED"
    pending = state["pending_changes"]
    assert len(pending) == 1 and pending[0]["status"] == "CANDIDATE"
    change_id = pending[0]["change_id"]
    assert change_id
    with contextlib.redirect_stdout(io.StringIO()):
        assert cli.main(["--root", root, "accept-change", change_id,
                         "--reviewer", "human"]) == 0
    after = store.scientific_state()
    claim = after["current_conclusions"]["species_ranked_accommodation"]
    assert claim["value"] == "THREE_DISCRETE_MODES"
    assert claim["reviewed_by"] == "human"
    assert after["superseded_results"][0]["status"] == "SUPERSEDED"
    assert after["superseded_results"][0]["superseded_by"] == claim["claim_id"]


def test_retrieve_output_encodes_utf8():
    """Regression: retrieve echoes recalled text that may contain 'Å' / CJK;
    on a GBK Windows console this previously raised UnicodeEncodeError."""
    root = make_tmp("enc")
    store = MemoryStore(root)
    store.ensure_layout()
    store.write_project_memory("# p\ncavity radius 2.16 Å, 连续尺寸依赖演化\n")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["--root", root, "retrieve", "radius", "-k", "3"])
    assert rc == 0
    assert "Å" in buf.getvalue()


if __name__ == "__main__":
    test_declared_verbs_match_argparse()
    test_cli_init_works_and_is_idempotent()
    test_status_reports_not_initialized_on_fresh_project()
    test_status_reports_initialized_on_fixture()
    test_cli_accept_change_supersedes_after_review()
    test_retrieve_output_encodes_utf8()
    print("cli consistency OK")
