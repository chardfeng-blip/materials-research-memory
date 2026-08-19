# TEST_REPORT — v0.1.2a (public-release hotfix)

This report records ONLY the results of the final public-release ZIP
clean-room run: the ZIP was unzipped into a completely fresh directory (no
parent-tree dependency), then `python -m pytest tests -q` and the CLI verbs
were executed there. No development-directory result is reported.

## Final ZIP clean-room results (actual run)

```
$ python -m pytest tests -q
63 passed in 2.14s

$ python bin/materials-memory.py --root . init        -> exit 0
$ python bin/materials-memory.py --root . status      -> project initialized: NO
$ python bin/materials-memory.py --root . brief       -> wrote outputs/PROJECT_BRIEF.md (108 tokens)
$ python bin/materials-memory.py --root . retrieve "generic materials research" -k 5 -> exit 0
$ python bin/materials-memory.py --root . metrics     -> exit 0
```

Status from the fresh unzip: `project initialized: NO`, `active profile:
(none)`, 0 decisions / 0 lessons / 0 datasets / 0 methods / 0 open questions,
4 core skills — the shipped `memory/` skeleton is an UNINITIALIZED generic
project (P0-1).

## Rollback transactional consistency (P0-3)

`test_failed_rollback_restores_entire_pre_state` (fault-injection): a store
whose live PROJECT_MEMORY / SCIENTIFIC_STATE / ledger / registry differ from
the snapshot is rolled back with `storage.atomic_write_text` monkeypatched to
raise OSError on the SECOND durable file. Result:

- rollback raises (MemoryError);
- the ENTIRE durable memory — including PROJECT_MEMORY.md which had already
  been replaced before the fault — is restored to the pre-rollback content;
- a `pre_rollback_<timestamp>` snapshot was created first.

```
test_snapshot.py::test_failed_rollback_restores_entire_pre_state PASSED
```

## Release integrity (P0-1)

The plugin's own `<plugin-root>/memory/` + `plugin.yaml` are the ONLY release
template (the separate `dist-template/` was removed). From the fresh unzip:

- `test_release_root_contains_no_fake_runtime_records` — PASS (empty JSONL,
  empty buckets, `meta.initialized: false`, no `#template` markers);
- `test_release_memory_is_uninitialized_schema` — PASS;
- `test_release_plugin_yaml_is_consistent_and_sanitized` — PASS (version
  0.1.2a, exact verb set with `accept-change`, no `home_detected`, generic
  `${DSH_HOME}` install path);
- `test_public_package_has_no_private_identifiers` — PASS (scans the whole
  public tree for the deny-list).

## Privacy scan (P0-2) — run in the unzipped directory after the verbs

The three release greps — (1) the developer username, (2) the Windows user
directory prefix, (3) the old real-project directory name — each returned
**0 hits**; the scan is clean. (pytest bytecode caches — `.pyc`, which embed
the local unzip path and are never shipped — were removed before the scan;
the shipped package contains no bytecode.) The hermetic fixture is the
SYNTHETIC `tests/fixtures/materials_demo/` (Material-X, species A/B/C,
fictional conclusions); no real research data ships anywhere. Real dev state
was moved to `dev-private/` (excluded from the ZIP).

## Test matrix (all run inside the fresh unzip)

| Area | Tests | Result |
|---|---|---|
| contradiction & claim/decision safety (P0-3/P0-4/P0-6) | 15 | PASS |
| claim gate (10 checks) | 4 | PASS |
| lesson lifecycle + verification dedupe (P0-7) | 5 | PASS |
| registry authority (P0-5) | 8 | PASS |
| release integrity (P0-1/P0-2) + promotion safety (P0-8) | 10 | PASS |
| retrieval (§32 + hermetic §33 + P0-9 isolation) | 8 | PASS |
| snapshot / rollback bounds + fault-injection (P1-12/P0-3) | 6 | PASS |
| CLI consistency (verbs, init idempotent, status, accept-change, UTF-8) | 6 | PASS |
| **Total** | **63** | **PASS** |
