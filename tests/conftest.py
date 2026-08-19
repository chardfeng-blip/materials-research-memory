"""Shared test helpers (v0.1.2a — fully hermetic).

All test data lives in tests/fixtures/materials_demo/ (a SYNTHETIC
Material-X / species A/B/C demo — no real research data).
`seeded_store` / `materials_demo_store` copy the fixture into a fresh temp
root, so pytest never depends on the release package's runtime memory.
"""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MemoryStore  # noqa: E402

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "materials_demo")


def copy_fixture(root: str) -> None:
    """Copy the hermetic demo fixture into `root` (root must exist)."""
    shutil.copytree(FIXTURE_DIR, root, dirs_exist_ok=True)


def seeded_store(root: str, active_profile: str = "materialx") -> MemoryStore:
    """A store seeded from the hermetic Material-X demo fixture (default
    active profile = materialx so its project skills are indexed)."""
    copy_fixture(root)
    return MemoryStore(root, active_profile=active_profile)


def materials_demo_store(root: str, active_profile: str = "materialx") -> MemoryStore:
    return seeded_store(root, active_profile=active_profile)
