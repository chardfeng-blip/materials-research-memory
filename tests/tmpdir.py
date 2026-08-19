"""Sandbox-safe temp dirs: created under the plugin's tests/.tmp (writable
workspace area) with plain os.makedirs — NOT tempfile.mkdtemp, whose dirs get
restrictive ACLs under the DSH sandbox. Pytest's built-in tmp_path fixture is
also unusable here (symlink farm denied), so tests use make_tmp() everywhere."""

from __future__ import annotations

import atexit
import itertools
import os
import shutil

_TMP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp")
_counter = itertools.count()


def _cleanup() -> None:
    try:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    except Exception:  # noqa: BLE001 - cleanup is best-effort
        pass


atexit.register(_cleanup)


def make_tmp(name: str) -> str:
    os.makedirs(_TMP_ROOT, exist_ok=True)
    d = os.path.join(_TMP_ROOT, f"{name}_{next(_counter)}")
    os.makedirs(d, exist_ok=True)
    return d
