# SELF_EVOLUTION_DESIGN

Self-evolution is defined operationally — NOT as weight modification:

    Memory + Reflection + Verified Lessons + Reusable Skills + Scientific Decision Rules

## The evolution loop

```
task → [task_start retrieval] → work → [task_end reflection]
                                          │
                MEMORY_UPDATE_PROPOSAL (nine questions)
                                          │ gated auto-commit
                observations / candidate lessons   accepted conclusions
                (auto)                              (canonical source + HIGH
                                                     + no conflict, else review)
                                          │
                verify_lesson ×≥2 (distinct source,task_id), HIGH, generalizable
                                          │ (human/agent approval)
                SKILL_PROMOTION_PROPOSAL → profiles/<active>/skills/<name>.md
                                          │   (or skills/core/<name>.md)
                milestone → snapshot/YYYY-MM-DD_<milestone>/
                review → accept-change <change_id> | accept-decision <id>
```

## What evolves

| Artifact | Grows via |
|---|---|
| Memory coverage | brief + retrieve reuse; richer PROJECT_MEMORY / SCIENTIFIC_STATE |
| Decisions | DECISION_LEDGER (alternatives + reason + evidence) |
| Lessons | LESSON_MEMORY (CANDIDATE -> VERIFIED on confirmation) |
| Skills | promotion of repeat-verified lessons (approval-gated) |
| Scientific decision rules | frozen definitions + claim gate discipline |

## SELF_EVOLUTION_SCORE (spec §27)

Not "how smart the model is" — it measures the memory system's health:

- memory coverage
- lesson reuse
- failure recurrence rate
- skill reuse rate
- scientific claim correction rate
- provenance completeness

## Metrics (spec §28, `materials-memory metrics`)

- MEMORY_RECALL_RATE — share of lessons VERIFIED/PROMOTED
- CANONICAL_SOURCE_ACCURACY — share of decisions sourced from canonical/frozen
- REPEATED_FAILURE_RATE — share of lessons with times_verified >= 2
- LESSON_REUSE_RATE — share of lessons with >= 1 confirmation
- SKILL_REUSE_RATE — skill count vs target
- PROVENANCE_COMPLETENESS — decisions carrying source/date/status/confidence
- CONTRADICTION_DETECTION_RATE — superseded/flagged decisions

## Anti-reinforcement safeguards (spec §29)

- CANDIDATE lessons can never influence hard scientific rules.
- Every skill records `origin_lessons`, `validation_count` (computed live
  from DISTINCT verification identities — never caller-supplied),
  `last_reviewed`, `version`.
- Accepted conclusions are gated by ONE transition policy (canonical source
  resolved from DATA_REGISTRY + HIGH confidence + no conflict).
- v0.1.2 (P0-3/P0-6): claims AND decisions share the same policy. An
  unreviewed conflicting claim/decision can never change an ACCEPTED one —
  it becomes CANDIDATE + requires_review; superseding requires the explicit
  `accept-change <change_id> --reviewer` / `accept-decision <id> --reviewer`
  approval paths (records `reviewed_by`/`reviewed_at` and full contradiction
  provenance). `add_decision()` defaults to CANDIDATE.
- v0.1.2 (P0-5): canonical write authority comes ONLY from DATA_REGISTRY
  resolution (`dataset:<id>` → exact path → unique basename); filename
  heuristics are display/migration hints only.
- v0.1.2 (P0-7): `times_verified` is recomputed as
  `len(unique (source, task_id))`; a duplicate verification never counts.
- v0.1.2 (P0-8): promotion is atomic — validate ALL origin lessons first,
  then write the skill, then mark lessons PROMOTED; a failed validation
  leaves no skill file and no marked lesson.
- v0.1.2 (P0-9): generic engine skills (`skills/core/`) are isolated from
  project knowledge (`profiles/<id>/skills/`); retrieval indexes only core +
  the ACTIVE profile, decided by configuration, never by query keywords.
- Contradictions supersede rather than overwrite; full history retained.
- Snapshot/rollback provides rollback points (restore allowed only from
  `snapshots/`, durable-memory allowlist only, `pre_rollback_*` auto-created);
  compression archives (never deletes) while keeping all ids traceable.

## Compatibility with soul.md (spec §30)

If a DSH `soul.md` exists, this plugin does NOT put project knowledge into it:
soul.md keeps agent identity / reasoning principles / scientific discipline /
behavior rules; project facts go to memory/, skills to skills/, decisions to
the ledger.
