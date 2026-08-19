# materials-research-memory

DSH 材料科研长期记忆、经验学习与 Skill 进化插件。
Long-term materials-science research memory, experience learning, and skill
evolution for DeepSeek Harness (DSH).

**Self-evolution is NOT weight modification.** It is the continuous evolution
of:

    Memory + Reflection + Verified Lessons + Reusable Skills + Scientific Decision Rules

## Safety principle (non-negotiable)

The model may never modify long-term scientific truth without review. Every
piece of information moves through:

    OBSERVATION -> CANDIDATE -> VERIFIED -> PROMOTED

- Only **VERIFIED** information enters long-term scientific state.
- Only **repeat-verified, cross-task reusable VERIFIED lessons**
  (distinct verifications >= 2, HIGH confidence, generalizable) may be
  **PROMOTED to skills** — and promotion still requires human/reviewer
  approval (`validation_count` is computed live, never caller-supplied).
- All scientific-state transitions (claims AND decisions) go through ONE
  transition policy (`core/transition_policy.py`): auto-accept requires a
  registry-resolved canonical source + HIGH confidence + no conflict;
  everything else is **CANDIDATE** with `requires_review`.
- An **UNREVIEWED conflicting claim/decision can NEVER change an ACCEPTED
  one**. Superseding happens ONLY via explicit reviewer approval
  (`accept-change <change_id> --reviewer` / `accept-decision <id>
  --reviewer`), which records `reviewed_by`/`reviewed_at` and full
  contradiction history. Never overwrite.

## Layout

```
materials-research-memory/
├── plugin.yaml                 # plugin metadata (name, safety, CLI verbs)
├── README.md
├── bin/materials-memory.py     # unified CLI (the "service" interface)
├── core/                       # python core (stdlib + PyYAML)
│   ├── memory_manager.py       # facade: file layout + orchestration
│   ├── transition_policy.py    # ONE transition policy (P0-3/P0-5/P0-6)
│   ├── models.py               # shared ClaimRecord/PendingChange/... shapes
│   ├── storage.py              # atomic writes + file lock (P1-11)
│   ├── retrieval.py            # BM25/full-text retrieval (no embedding API needed)
│   ├── reflection.py           # task-end reflection + gated auto-commit
│   ├── lesson_manager.py       # CANDIDATE -> VERIFIED -> PROMOTED
│   ├── skill_promoter.py       # SKILL_PROMOTION_PROPOSAL + approval path
│   ├── provenance.py           # source/date/status/confidence enforcement
│   ├── scientific_gate.py      # ten-check claim gate
│   ├── project_snapshot.py     # milestone snapshots + bounded rollback
│   └── ontology.py             # materials ontology (extensible)
├── memory/                     # durable memory (the long-term state)
│   ├── PROJECT_MEMORY.md       # stable project background (never full logs)
│   ├── SCIENTIFIC_STATE.yaml   # current canonical scientific truth (+ meta.initialized)
│   ├── DECISION_LEDGER.jsonl   # decisions with alternatives/reason/evidence
│   ├── LESSON_MEMORY.jsonl     # lesson lifecycle
│   ├── OPEN_QUESTIONS.yaml
│   ├── DATA_REGISTRY.json      # dataset registry (resolution = write authority)
│   └── METHOD_REGISTRY.yaml    # versioned method definitions
├── cases/                      # successes/ failures/ task cases
├── skills/core/                # generic engine skills (indexed for all projects)
├── profiles/<id>/skills/       # project-profile skills (indexed only when active)
├── reflections/                # task/ milestone/ reflection proposals
├── snapshots/                  # YYYY-MM-DD_<milestone>/ rollback points
├── outputs/                    # generated briefs, task context, proposals
├── dsh/                        # DSH integration (skill protocol + optional bridge)
├── docs/                       # architecture, schemas, audit, installation, reports
└── tests/                      # pytest/standalone test suite (hermetic fixtures)
```

## Quick start

```bash
python bin/materials-memory.py --root <plugin-root> init
python bin/materials-memory.py --root <plugin-root> brief        # session start
python bin/materials-memory.py --root <plugin-root> retrieve "三物种分类结论" -k 5
python bin/materials-memory.py --root <plugin-root> reflect --task-id t1 --summary "..."
python bin/materials-memory.py --root <plugin-root> accept-change <change_id> --reviewer human
python bin/materials-memory.py --root <plugin-root> accept-decision <decision_id> --reviewer human
python bin/materials-memory.py --root <plugin-root> propose-skills
python bin/materials-memory.py --root <plugin-root> status       # shows "project initialized: YES/NO"
```

## DSH integration

See `dsh/README.md` and `docs/DSH_PLUGIN_CAPABILITY_AUDIT.md`. The plugin is a wrapper/service with session hooks: the DSH skill
(`skills/core/materials_research_memory.md`) drives the protocol; an optional
Cordis bridge (`dsh/dsh-session-bridge.ts`) automates it.

## Tests

```bash
python -m pytest tests/ -p no:cacheprovider --basetemp <writable-tmp>   # pytest
python tests/test_lesson_lifecycle.py   # standalone runners (sandbox-safe)
python tests/test_contradiction.py
python tests/test_registry_authority.py
python tests/test_release_integrity.py
python tests/test_snapshot.py
python tests/test_retrieval.py
python tests/test_gate.py
python tests/test_cli_consistency.py
```

All tests are hermetic — fixtures only (see `tests/fixtures/materials_demo/`,
a synthetic Material-X demo, and the shipped `memory/` skeleton); they never
read the developer's real memory.

## Changelog

### v0.1.2a (public-release hotfix)

- **P0-1** release integrity tests now target the ACTUAL release artifact:
  the plugin's own `memory/` + `plugin.yaml` are the ONLY release template
  (the separate `dist-template/` was removed — no more drift, no more
  `../dist-template` dependency in tests). `python -m pytest tests -q` from a
  freshly unzipped ZIP is fully green.
- **P0-2** public release sanitization: `home_detected` removed from
  plugin.yaml; `install_path` is the generic `${DSH_HOME}/plugins/...`;
  developer paths in docs replaced with `<DSH_HOME>` / `<DSH_SOURCE>` /
  `<PROJECT_ROOT>`; the real initialization report and all real research
  memory/skills/artifacts moved to `dev-private/` (excluded from the ZIP);
  the hermetic test fixture is now the SYNTHETIC `tests/fixtures/materials_demo/`
  (Material-X, species A/B/C, fictional conclusions) — no real research
  content anywhere in the public package.
- **P0-3** rollback is now transactionally consistent: all restore payloads
  are read before any write; on ANY mid-restore failure the ENTIRE durable
  memory is restored from the `pre_rollback_*` snapshot (files already
  replaced earlier are restored too); a failed pre-restore raises a
  catastrophic error instead of leaving half-state. New fault-injection test
  `test_failed_rollback_restores_entire_pre_state`.
- **P1-4** documentation now states only what is actually verified: the
  clean-room numbers in TEST_REPORT.md come from the final ZIP run, and
  "failed restore is never half-applied" is backed by the fault-injection
  test.

### v0.1.2 (safety + architecture hardening)

- **P0-1** release artifact vs docs inconsistency fixed: the distributable
  ships a GENERIC, UNINITIALIZED project (empty buckets,
  empty JSONL, `meta.initialized: false`, no `#template` fake records);
  `MemoryStore.is_initialized()` is decided by the explicit schema and
  `status` reports `project initialized: NO` until real content is accepted.
- **P0-2** tests are fully hermetic: all test data lives in
  `tests/fixtures/materials_demo/`; `REAL_ROOT` removed; new
  `test_release_root_contains_no_fake_runtime_records` and
  `test_uninitialized_project_does_not_claim_scientific_state`;
  TEST_REPORT.md written from actual runs.
- **P0-3** scientific-state conflict safety identical to decisions: an
  unreviewed conflicting claim never changes an ACCEPTED claim; new
  `accept-change <change_id> --reviewer` supersede path; stable `change_id`;
  fields `change_id/reviewed_by/reviewed_at/superseded_by/contradictions[]`.
- **P0-4** unified ClaimRecord model (claim_id/topic/value/source/date/status/
  confidence/reviewed_by/reviewed_at); legacy v0.1.1 files migrate on read;
  no duplicated structures.
- **P0-5** canonical write authority ONLY from DATA_REGISTRY resolution
  (`dataset:<id>` → exact path → unique basename); unregistered sources can
  never auto-accept; filename heuristics are display/migration hints only.
- **P0-6** `add_decision()` defaults to CANDIDATE; acceptance only via
  policy; `import_accepted_decision(..., reviewer="migration")` replaces any
  `trusted=True`; `core/transition_policy.py` is the single source of truth.
- **P0-7** lesson verification is independent: `verifications[]` records with
  `verification_id/source/task_id/date/confirmation`;
  `times_verified = len(unique (source, task_id))`; duplicates don't count.
- **P0-8** `--validation-count` removed everywhere; validation count computed
  live from the lesson store; promotion is atomic (validate first → write
  skill → update lesson states).
- **P0-9** generic engine isolated from project knowledge: `skills/core/` +
  `profiles/<id>/skills/` + `MemoryStore(active_profile=...)`; retrieval
  indexes only core + active profile; profile decided by config, never by
  query keywords.
- **P1-10** DSH bridge `expandHome()` for `~/` / `~` / `~\`; normalized root
  shared by runCli and the warning.
- **P1-11** `core/storage.py`: atomic write helpers + file lock; no per-manager
  temp logic anywhere.
- **P1-12** rollback accepts only snapshots inside `store.snapshots_dir`,
  restores only the durable-memory allowlist, and auto-creates
  `pre_rollback_<timestamp>` before restoring.

### v0.1.1 (stability fix)

- **P0-1** `init` is bound and idempotent (was printing help / exit 2) and
  now seeds valid empty-state skeleton files (fixes a corrupt
  `DATA_REGISTRY.json` on fresh init).
- **P0-2** removed the `ingest` declaration drift: plugin.yaml cli.verbs,
  the CLI docstring, and argparse now agree exactly (verified by
  `tests/test_cli_consistency.py`); `ingest` is planned for a future release.
- **P0-3** generic retrieval diversification: any single kind is capped in
  Top-K, and a genuinely-matched canonical document (scientific_state /
  project_memory) is always kept a slot, so skills cannot drown canonical
  memory (no project-specific keywords; `sources` / `include_skills=False`
  unchanged).
- **P0-4** decision safety: an unreviewed conflicting decision can NEVER
  auto-supersede an ACCEPTED decision — it becomes CANDIDATE +
  requires_review; only the explicit `accept-decision <id> --reviewer`
  path supersedes (with full provenance). task-end reflection now routes
  gated decisions to `requires_review`.
- **P1-5** canonical-source judgment: DATA_REGISTRY status is the authority
  and overrides the filename heuristic (NON_CANONICAL / LEGACY / SUPERSEDED /
  TEMP / REJECTED / REFERENCE / WORK_IN_PROGRESS deny; CANONICAL / FROZEN /
  FINAL / ACCEPTED grant); the heuristic remains a backward-compatible
  fallback for unregistered paths.
- **P1-6** CLI emits UTF-8 (fixes UnicodeEncodeError on GBK Windows consoles
  when recalling text with `Å`/CJK); docs, plugin.yaml version → 0.1.1, and
  this changelog updated; full pytest + CLI smoke green.

## License

This project is released under the MIT License.

You are free to use, modify, distribute, and build upon the project under the
terms of the [MIT License](LICENSE).
