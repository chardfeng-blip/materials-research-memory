# MEMORY_SCHEMA (v0.1.2)

Durable memory lives under `memory/`. Every scientific result record must
carry `source`, `date`, `status`, `confidence` (enforced by
`core/provenance.py`).

v0.1.2 hardening summary:

- **Unified claim model** (`core/models.py`): claims, pending changes,
  decisions, verifications, and lessons share one TypedDict shape; there is no
  duplicated structure and no `accepted_results` bucket anymore (folded into
  `current_conclusions` on read via `_migrate_v011_claims`).
- **One transition policy** (`core/transition_policy.py`): auto-accept
  requires registry-resolved canonical source + HIGH confidence + no conflict
  for claims AND decisions; an UNREVIEWED conflicting claim/decision can never
  change an ACCEPTED one.
- **Explicit supersede paths**: `accept_change(change_id, reviewer)` /
  `accept_decision(decision_id, reviewer)` (CLI `accept-change` /
  `accept-decision`). `change_id`/`claim_id`/`decision_id` are STABLE
  identities, never array indices.
- **Registry authority** (P0-5): canonical WRITE authority comes ONLY from
  `DATA_REGISTRY` resolution (`dataset:<id>` exact → normalized exact path →
  unique basename). Filename heuristics are display/migration hints only.
- **Explicit initialization** (P0-1): `meta.initialized` decides
  `MemoryStore.is_initialized()`; a fresh project reports
  `project initialized: NO` and ships no fake records.

## Lifecycle statuses

    OBSERVATION -> CANDIDATE -> VERIFIED -> PROMOTED
                                   |-> ACCEPTED / REJECTED / SUPERSEDED / FROZEN

Only VERIFIED information enters long-term scientific state; only
repeat-verified, cross-task reusable VERIFIED lessons may be PROMOTED.
New claims and decisions default to CANDIDATE; acceptance requires the
transition policy (canonical + HIGH + no conflict) or explicit reviewer
approval.

## PROJECT_MEMORY.md

Long-term stable background ONLY (never full logs): project title, material,
scientific question, species, methods, current stage, major milestones, main
findings, data authority.

## SCIENTIFIC_STATE.yaml (canonical scientific truth)

```
meta:                    {initialized: bool, initialized_at?, initialized_by?}
project, system, current_stage
canonical_datasets:      {id: {value, definition, source, date, status, confidence}}
frozen_definitions:      descriptors / transition channels / rules
current_conclusions:     {topic: ClaimRecord}      # the ONLY accepted-claims bucket
rejected_results:        {topic: ClaimRecord(status: REJECTED)}
superseded_results:      [ClaimRecord(status: SUPERSEDED, superseded_by)]
blockers, next_steps
pending_changes:         [PendingChange]           # gated updates awaiting review
```

ClaimRecord (core/models.py):

```
claim_id, topic, value, source, date, status, confidence,
[reviewed_by], [reviewed_at], [contradictions[]], [superseded_by]
```

PendingChange (core/models.py):

```
change_id (stable), topic, value, source, date, status: CANDIDATE,
confidence, requires_review: true, conflicts[]
```

**v0.1.2 claim safety (P0-3):** an UNREVIEWED conflicting claim may NEVER
change an ACCEPTED claim:

- conflict on an existing topic (value changed) and/or an unregistered source
  → the new claim becomes a CANDIDATE PendingChange with
  `requires_review: true`; the old ACCEPTED claim is untouched.
- superseding happens ONLY via
  `MemoryStore.accept_change(change_id, reviewer=...)` (CLI
  `materials-memory accept-change <change_id> --reviewer human`): new →
  ACCEPTED (with `reviewed_by`/`reviewed_at` and contradiction provenance),
  conflicting old ACCEPTED → SUPERSEDED with `superseded_by`, history kept.

Legacy v0.1.1 files (primitive `topic: value` claims and the
`accepted_results` bucket) are migrated on READ (`_migrate_v011_claims`);
writes always persist the normalized ClaimRecord schema.

## DECISION_LEDGER.jsonl (append-only)

```
decision_id, timestamp, topic, decision, alternatives[], reason,
evidence, source, confidence, status, [superseded_by], [reviewed_by],
[reviewed_at], [contradictions], [requires_review], [imported]
```

**P0-6:** `add_decision()` DEFAULTS to CANDIDATE. `status="ACCEPTED"` is
honored only when the transition policy allows it (registry-canonical source
+ HIGH confidence + no conflict); otherwise the entry is forced to CANDIDATE
with `requires_review: true`. A conflicting decision can never change an
ACCEPTED one. There is NO generic `trusted=True`; already-confirmed history
enters through `import_accepted_decision(..., reviewer="migration")` which
records `reviewed_by`/`imported`.

## LESSON_MEMORY.jsonl (append-only)

```
lesson_id, trigger, failure, root_cause, fix, generalizable_rule,
scope, confidence, times_verified, status, source, date, [verifications]
```

VerificationRecord (P0-7):

```
verification_id, source, task_id, date, confirmation
```

`times_verified` is NEVER caller-supplied: it is recomputed as
`len(unique (source, task_id) verifications)`; an exact duplicate
verification does not increment. Promotion requires `>= 2` distinct
verifications, HIGH confidence, and a generalizable rule (enforced by
`core/skill_promoter._validate_origin_lessons` BEFORE any write; the
`validation_count` in a promoted skill file is computed live from this
count).

## OPEN_QUESTIONS.yaml

`questions[]`, `blockers[]`, `next_step_owners[]`.

## DATA_REGISTRY.json (registry-authoritative, P0-5)

```
datasets[]: dataset_id, name, path, version, status, scope, rows,
            columns[], definition, source, created_at,
            supersedes, superseded_by
```

Resolution order for a source string (strict, no loose substring matching):

1. `dataset:<dataset_id>` — explicit id match.
2. normalized exact path equality (`results/.../master.csv` == `results\...\master.csv`).
3. basename equality ONLY when that basename is unique in the registry.

Canonical statuses: `CANONICAL`, `FROZEN`, `FINAL`, `ACCEPTED`. Anything
unresolvable or ambiguous → `unregistered` → never canonical. Filename
heuristics (`final`/`frozen`/...) are a READ-ONLY legacy hint
(`legacy_canonical_hint`) for display/migration warnings and NEVER grant
write authority.

## METHOD_REGISTRY.yaml (versioned methods)

```
methods[]: method, version, settings{}, notes, source, registered_at
```

Method consistency is a claim-gate check; a method change creates a new
version and splits the dataset.

## Provenance rules

- `source` = exact path / `dataset:<id>` / calculation id.
- `date` = ISO date.
- `status` in the lifecycle set.
- `confidence` in {LOW, MEDIUM, HIGH}.
- LEGACY-sourced records are quarantined, never committed to canonical state.
