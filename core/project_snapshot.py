"""Milestone snapshots and rollback.

snapshots/YYYY-MM-DD_<milestone>/ holds the durable memory set. Rollback
(P1-12) is strictly bounded:
  * the source must be a directory INSIDE store.snapshots_dir;
  * only the durable-memory allowlist is restored;
  * a `pre_rollback_<timestamp>` snapshot of the current memory is taken
    before restoring, and a failed restore is rolled back file-by-file so no
    half-state is left behind.
"""

from __future__ import annotations

import datetime
import glob
import os

from .memory_manager import MemoryStore


class SnapshotManager:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, milestone: str) -> str:
        return self.store.snapshot(milestone)

    def list(self) -> list[str]:
        return sorted(glob.glob(os.path.join(self.store.snapshots_dir, "*")))

    def rollback(self, snapshot_dir: str) -> str:
        if not os.path.isdir(snapshot_dir):
            raise FileNotFoundError(snapshot_dir)
        return self.store.rollback(snapshot_dir)

    def compress(self, keep_months: int = 6) -> int:
        """Archive old snapshots to snapshots/_archive (never delete history)."""
        archive = os.path.join(self.store.snapshots_dir, "_archive")
        os.makedirs(archive, exist_ok=True)
        cutoff = datetime.date.today() - datetime.timedelta(days=30 * keep_months)
        moved = 0
        for folder in self.list():
            name = os.path.basename(folder)
            if name.startswith("_"):
                continue
            try:
                day = datetime.date.fromisoformat(name[:10])
            except ValueError:
                continue
            if day < cutoff:
                dest = os.path.join(archive, name)
                if not os.path.exists(dest):
                    os.rename(folder, dest)
                    moved += 1
        return moved
