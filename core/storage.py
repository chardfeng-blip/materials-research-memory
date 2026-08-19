"""Durable atomic storage primitives (P1-11).

Every canonical-state / registry / ledger write goes through these helpers:
  temp file in the same directory -> flush -> fsync -> os.replace.
os.replace is atomic on the same volume (Windows and POSIX), so an abnormal
exit can never leave a half-written canonical file. A tiny lockfile-based
file_lock context manager serializes writers without a database.

No business logic lives here.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time

import yaml


def _atomic_write_bytes(path: str, data: bytes) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dsh-mem-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """Atomically replace `path` with UTF-8 `text`."""
    _atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: str, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def atomic_write_yaml(path: str, data) -> None:
    atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def atomic_rewrite_jsonl(path: str, rows: list[dict]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    _atomic_write_bytes(path, payload.encode("utf-8"))


def append_jsonl(path: str, row: dict) -> None:
    """Append one JSONL record with flush+fsync (append-only logs)."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


@contextlib.contextmanager
def file_lock(path: str, timeout_ms: int = 5000):
    """Minimal cross-platform advisory lock (lockfile created with O_EXCL,
    stale-lock reclaimed after `timeout_ms`). Serializes writers of one
    durable file; no database, no threads/fork bookkeeping."""
    lock_path = path + ".lock"
    deadline = time.monotonic() + timeout_ms / 1000.0
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                with contextlib.suppress(OSError):
                    os.remove(lock_path)  # stale-lock reclaim
                    continue
                raise TimeoutError(f"could not acquire lock {lock_path}") from None
            time.sleep(0.01)
    try:
        yield
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(OSError):
            os.remove(lock_path)
