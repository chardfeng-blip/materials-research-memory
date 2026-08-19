# PLUGIN_ARCHITECTURE

## What this is

`materials-research-memory` is a long-term **materials-science research
memory + self-evolution system** for DeepSeek Harness. "Self-evolution" here
is NOT weight modification — it is the continuous evolution of:

    Memory + Reflection + Verified Lessons + Reusable Skills + Scientific Decision Rules

## Why it is a wrapper/service + session hooks (not a native plugin)

The DSH capability audit (`DSH_PLUGIN_CAPABILITY_AUDIT.md`, verified against
the real source tree) established:

- DSH plugins are **Cordis (TypeScript) plugins**; there is **no Python plugin
  runtime**.
- DSH skills are markdown files loaded via `dsh-skill-filesystem`.
- DSH has **no general session-hook API** for arbitrary services.
- DSH has **no built-in cross-session scientific memory store** (sessions are
  isolated JSONL logs + per-session projections).

Therefore the plugin is implemented as a **Python service with a unified CLI**
(`bin/materials-memory.py`) plus **two DSH integration layers** that consume
the same interface: (1) a DSH skill (`skills/materials_research_memory.md`)
that drives the session protocol, and (2) an optional Cordis host-plugin
bridge (`dsh/dsh-session-bridge.ts`).

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ DSH agent / skill (session_start -> brief, task -> retrieve) │
│ DSH bridge (optional Cordis host plugin, shells to the CLI)  │
└──────────────────────────┬───────────────────────────────────┘
                           │ unified CLI: materials-memory <verb>
┌──────────────────────────▼───────────────────────────────────┐
│ bin/materials-memory.py   (argparse, all verbs)              │
│ core/                                                        │
│   memory_manager.py   facade: file layout + orchestration    │
│   transition_policy.py  ONE transition policy (P0-3/P0-5/P0-6)│
│   models.py           shared TypedDict record shapes         │
│   storage.py          atomic writes + file lock (P1-11)      │
│   retrieval.py        BM25/full-text (CJK-aware), FTS5 opt.  │
│   reflection.py       task-end proposal + gated auto-commit  │
│   lesson_manager.py   CANDIDATE->VERIFIED->PROMOTED          │
│   skill_promoter.py   proposal + approval path               │
│   provenance.py       source/date/status/confidence          │
│   scientific_gate.py  ten-check claim gate                   │
│   project_snapshot.py snapshots + bounded rollback + compress│
│   ontology.py         materials ontology (extensible)        │
└──────────────────────────┬───────────────────────────────────┘
                           │ durable files (the long-term state)
┌──────────────────────────▼───────────────────────────────────┐
│ memory/  PROJECT_MEMORY, SCIENTIFIC_STATE, DECISION_LEDGER,  │
│          LESSON_MEMORY, OPEN_QUESTIONS, DATA_REGISTRY,       │
│          METHOD_REGISTRY                                     │
│ skills/core/        generic engine skills (all projects)     │
│ profiles/<id>/skills/  project-profile skills (P0-9)         │
│ cases/ reflections/ snapshots/ outputs/                      │
└──────────────────────────────────────────────────────────────┘
```

## Key design decisions

1. **File-based memory, registry-authoritative.** Dataset freshness is decided
   by `DATA_REGISTRY.status`, never by filename. JSONL for append-only
   ledgers; YAML for canonical state; MD for prose memory; JSON for the
   dataset registry.
2. **Four-stage lifecycle.** `OBSERVATION -> CANDIDATE -> VERIFIED ->
   PROMOTED`. Only VERIFIED enters long-term scientific state; only
   repeat-verified (distinct verifications >= 2), HIGH-confidence,
   generalizable lessons may be promoted — and promotion still requires
   approval.
3. **One transition policy, two artifacts (P0-3/P0-4/P0-6).** Claims AND
   decisions go through the SAME `core/transition_policy.py` — auto-accept
   requires registry-resolved canonical source + HIGH confidence + no
   conflict; anything else is CANDIDATE with `requires_review`. An
   UNREVIEWED conflicting claim/decision can NEVER change an ACCEPTED one
   (it records a CONTRADICTION and keeps the old ACCEPTED untouched).
   Superseding happens ONLY through the explicit reviewer paths
   `accept-change <change_id> --reviewer` (claims, P0-3) and
   `accept-decision <id> --reviewer` (decisions), which write
   `reviewed_by`/`reviewed_at` and full contradiction provenance. There is no
   `trusted=True`; migrated history enters via
   `import_accepted_decision(..., reviewer="migration")`.
4. **Gated auto-commit.** task logs / observations / candidate lessons are
   auto-written; accepted scientific conclusions auto-commit ONLY when the
   unified policy allows it — otherwise `requires_review = true`.
   `add_decision()` DEFAULTS to CANDIDATE (P0-6).
5. **Canonical authority is registry-resolution ONLY (P0-5).** A source is
   canonical iff it resolves against DATA_REGISTRY — `dataset:<id>` exact, or
   normalized exact path, or a unique basename. `legacy_canonical_hint`
   (filename `final`/`frozen`) is a READ-ONLY display/migration warning and
   NEVER a write authorization; there is no loose substring matching.
6. **No expensive embedding dependency.** Retrieval is BM25-style
   full-text (CJK-aware) with an optional SQLite FTS5 index; semantic
   retrieval can be layered on later. v0.1.1+ generic kind diversification
   caps any single kind in Top-K and reserves a slot for a genuinely-matched
   canonical document.
7. **Profile isolation (P0-9).** Retrieval indexes ONLY `skills/core/` (generic
   engine skills) plus the ACTIVE project profile's skills
   (`profiles/<id>/skills/`). The active profile is decided by project
   configuration (`.active_profile` marker / `--profile`), never by query
   keywords. Promoted skills land in the active profile's skills dir (core
   fallback), so a fresh generic project can never retrieve another project's
   conclusions.
8. **Dual-format skills.** `skills/core/*.md` and `profiles/*/skills/*.md`
   carry both the plugin's skill schema (Purpose / When to use / Inputs /
   Definitions / Procedure / QA / Common failures / Blocking conditions /
   Outputs / Provenance requirements) and DSH skill frontmatter (name +
   description), so they can be registered as DSH skills without an app
   rebuild.
9. **Atomic durable writes (P1-11).** Every durable write goes through
   `core/storage.py` (`atomic_write_text/json/yaml`, `atomic_rewrite_jsonl`,
   `file_lock`); no manager keeps its own temp-file logic.
10. **Bounded snapshot/rollback (P1-12).** Rollback accepts ONLY snapshot
    directories inside `store.snapshots_dir`, restores ONLY the
    durable-memory allowlist, and always takes a `pre_rollback_<timestamp>`
    snapshot first so a failed restore never leaves half-state.
11. **Explicit initialization (P0-1).** `meta.initialized` decides
    `is_initialized()`; the release artifact ships an UNINITIALIZED project
    (empty buckets, empty JSONL, no fake records) and `status` reports
    `project initialized: NO` until real content is accepted.

## Data flow

- **Session start** → `materials-memory brief` → `outputs/PROJECT_BRIEF.md`
  (<= 8000 tokens; current project, stage, canonical definitions, latest
  conclusions, blockers, next steps). Only the brief enters context.
- **Task start** → `materials-memory retrieve "<query>"` → top-k memories
  (project memory, scientific state, decisions, lessons, skills, registries).
- **Task end** → `materials-memory reflect ...` → `MEMORY_UPDATE_PROPOSAL.md`
  answering the nine reflection questions, with gated auto-commit.
- **Review** → `materials-memory accept-change <change_id> --reviewer human`
  / `accept-decision <id> --reviewer human` — the only supersede paths.
- **Promotion** → `materials-memory propose-skills` → proposal; after human
  approval `promote-skill` writes the real skill file (validation_count
  computed live from distinct verifications).
- **Milestone** → `materials-memory snapshot --milestone <name>` →
  `snapshots/YYYY-MM-DD_<milestone>/` (rollback point).
