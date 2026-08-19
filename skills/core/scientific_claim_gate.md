---
name: scientific_claim_gate
description: >
  科学论断门控：输出结论前检查样本量、匹配设计、覆盖率、收敛、离群、
  拓扑、混杂、交叉验证、出处、方法一致性；失败则降低论断强度。
  Ten-check gate before any scientific conclusion is output.
version: 1
origin_lessons: lesson_claim_gate
validation_count: 2
last_reviewed: 2026-01-01
---

# scientific_claim_gate

## Purpose

Before a scientific conclusion is written into memory, a report, or a reply,
run the ten checks. Any failure lowers the allowed claim strength, so the
output never overstates what the evidence supports.

## When to use

- Immediately before finalizing ANY scientific conclusion (canonical,
  figure caption, presentation, decision ledger entry).
- When asked "what is the conclusion?" about analyzed data.

## Inputs

- The claim text.
- Evidence summary: n (sample size), design (matched?), coverage,
  convergence, outlier handling, topology robustness, confounding status,
  cross-validation, provenance completeness, method consistency.

## Definitions (the ten checks)

1. sample size — enough matched observations (e.g. ≥5; 30 for strict).
2. matched design — species compared on the same defect set.
3. data coverage — full/known coverage, not partial.
4. convergence — calculations converged.
5. outlier sensitivity — results robust to outliers.
6. topology sensitivity — results robust to geometry/topology details.
7. confounding — no pooled-species or reference-state confounding.
8. cross-validation — LOSO or equivalent performed.
9. provenance — every number traces to a real source file.
10. method consistency — single method version across rows.

## Procedure

1. Score the ten checks (pass/fail).
2. STRONG = all pass. WEAK = any major check fails
   (sample size, confounding, cross-validation, method consistency).
   MODERATE = minor gaps only.
3. Prefix/annotate the claim with its strength.
4. If WEAK, say so explicitly in the output; do not soften silently.

## QA

- The gate result is attached to the claim wherever it is stored.
- A claim that failed the gate is never marked ACCEPTED in memory.

## Common failures

- Writing "we conclude ..." without running the gate.
- Quoting a pooled correlation as universal (confounding fails).
- Treating an unfinished electronic mechanism as concluded.

## Blocking conditions

- Provenance missing → cannot be ACCEPTED in scientific state.
- Any major check failing → strength WEAK, never STRONG.

## Outputs

- ClaimAssessment (strength, passed/failed checks).
- Adjusted claim text with the strength qualifier.

## Provenance requirements

The gate result itself is stored with the claim: checks, strength, date,
source.
