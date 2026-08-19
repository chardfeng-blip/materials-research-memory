# SKILL_SCHEMA

Skills are markdown files in `skills/`, authored in a **dual format**: the
plugin's own schema (below) and DSH skill frontmatter
(`name`, `description`) so they can be registered as DSH skills.

## Required sections (every skill file)

| Section | Meaning |
|---|---|
| Purpose | What the skill does and why |
| When to use | Trigger conditions |
| Inputs | Required data/files |
| Definitions | Frozen vocabulary (never redefine mid-analysis) |
| Procedure | Step-by-step |
| QA | Verification checks |
| Common failures | Known failure modes |
| Blocking conditions | When to refuse |
| Outputs | What it produces |
| Provenance requirements | source/date/status/confidence discipline |

## Frontmatter (DSH + promotion metadata)

```yaml
---
name: <kebab-case skill name>
description: <one-line purpose>
version: <int>
origin_lessons: <lesson_id, ...>
validation_count: <int>
last_reviewed: <ISO date>
---
```

- `origin_lessons`: lesson_ids the skill was built from (traceability).
- `validation_count`: number of independent verifications behind it.
- `last_reviewed` / `version`: reviewed lifecycle — a skill is never
  "final"; it is versioned and re-reviewed.

## Promotion rules (enforced by core/skill_promoter.py)

A VERIFIED lesson becomes a skill candidate only when:

- `times_verified >= 2`
- `confidence == HIGH`
- `generalizable_rule` is non-empty (cross-task reusable)

`materials-memory propose-skills` writes `outputs/SKILL_PROMOTION_PROPOSAL.md`
listing candidates. The real `skills/<name>.md` is written ONLY via
`materials-memory promote-skill ...` after human/reviewer approval.
A promoted lesson is marked `PROMOTED` with `promoted_to` = skill filename.

## Anti-reinforcement guarantees

- A CANDIDATE lesson NEVER affects a hard scientific rule (it cannot enter
  SCIENTIFIC_STATE or gate logic).
- Every skill records `origin_lessons`, `validation_count`, `last_reviewed`,
  `version` so bad lessons cannot silently harden into rules.
- The `scientific_claim_gate` skill runs before any conclusion is output and
  lowers claim strength when checks fail.

## Shipped baseline skills (generic engine skills, `skills/core/`)

The public release ships only GENERIC engine skills in `skills/core/`
(vasp_data_audit, vasp_method_audit, scientific_claim_gate, and the
memory-protocol skill materials_research_memory). Project-specific skills
live under `profiles/<id>/skills/` and are indexed only for the ACTIVE
profile (P0-9); a public release ships no project-profile skills.
