---
name: vasp_method_audit
description: >
  VASP 方法审计：核对 ENCUT/KPOINT/POTCAR/DFT+U 并保证方法一致性，
  versioned method registry. Audit DFT method settings and enforce method
  consistency across calculations.
version: 1
origin_lessons: lesson_method_consistency
validation_count: 2
last_reviewed: 2026-01-01
---

# vasp_method_audit

## Purpose

Verify that every calculation in a dataset used an identical, versioned
method (ENCUT, KPOINT scheme, POTCAR, smearing, DFT+U when used) so energies
and descriptors are comparable. Any method change creates a NEW method
version and splits the dataset; it never silently reuses old rows.

## When to use

- Before interpreting any energy/formation-energy comparison.
- When merging vasp_input packages (e.g. "ultra efficient" vs "real
  potcar") into one analysis.
- When a convergence check is requested.

## Inputs

- INCAR, POTCAR, KPOINT files per calculation.
- METHOD_REGISTRY.yaml entries (versioned).
- Energy/descriptor tables to be compared.

## Definitions

- ENCUT: plane-wave cutoff.
- KPOINT: k-mesh scheme (gamma-centered / Monkhorst-Pack, density).
- POTCAR: projector augmented wave potential set (which PAW, which version).
- DFT+U: Hubbard U per species (host-dependent: e.g. U on U-5f if used).
- Method consistency: all rows share the same resolved method version.

## Procedure

1. Resolve the method version for every row from METHOD_REGISTRY.
2. Compare ENCUT/KPOINT/POTCAR across rows; split on any difference.
3. Check convergence (energy vs ENCUT / k-mesh) if claimed.
4. Record each method version in METHOD_REGISTRY.yaml with its settings.
5. Never mix two method versions in one trend line.

## QA

- Two random rows share one method version → OK; else fail.
- Convergence claim must cite the sweep that established it.

## Common failures

- Mixing "ultra efficient" (low ENCUT) and "real potcar" runs in one table.
- Comparing formation energies across different POTCAR generations.
- Not recording U values in DFT+U settings.

## Blocking conditions

- Unknown ENCUT/KPOINT for any row → block comparison.
- Two method versions in one trend → block or split.

## Outputs

- Method-consistent dataset split report.
- METHOD_REGISTRY.yaml updated with new versions.

## Provenance requirements

Each method entry: method, version, settings (ENCUT/KPOINT/POTCAR/DFT+U),
notes, source, registered_at.
