---
name: vasp_data_audit
description: >
  VASP 数据审计：区分结构/计算/电子资产，验证能量与几何出处，防止用
  STRUCTURE_ID 冒充 CALCULATION_ID。Audit VASP output provenance and never
  conflate geometry identity with calculation identity.
version: 1
origin_lessons: lesson_same_geometry_neq_calc
validation_count: 2
last_reviewed: 2026-01-01
---

# vasp_data_audit

## Purpose

Audit a VASP-based dataset so every row's provenance is verifiable: the same
geometry (coordinates) does NOT imply the same calculation (electronic
settings), and neither implies the same electronic asset (CONTCAR/OUTCAR
snapshot). Prevent silent conflation of STRUCTURE_ID, CALCULATION_ID, and
ELECTRONIC_ASSET_ID.

## When to use

- Before merging any VASP-derived tables (energies, volumes, descriptors).
- When a dataset mixes outputs from different INCAR/POTCAR/KPOINT generations.
- When asked "are these energies comparable?" across two files.

## Inputs

- Source VASP files: INCAR, POTCAR, KPOINT, CONTCAR/POSCAR, OUTCAR/OSZICAR.
- Derived tables: energy rows, volume rows, descriptor rows.
- Any manifest/registry that assigns STRUCTURE_ID / CALCULATION_ID /
  ELECTRONIC_ASSET_ID.

## Definitions

- STRUCTURE_ID: identity of the relaxed geometry (coordinates/species).
- CALCULATION_ID: identity of the electronic calculation settings
  (ENCUT, POTCAR, KPOINT mesh, smearing, DFT+U ...) for that geometry.
- ELECTRONIC_ASSET_ID: identity of the actual output snapshot
  (which CONTCAR/OUTCAR file produced the value).
- same geometry != same calculation: two files may share coordinates yet
  differ in ENCUT/POTCAR; their energies are not directly comparable.

## Procedure

1. For every value row, resolve its STRUCTURE_ID, CALCULATION_ID, and
   ELECTRONIC_ASSET_ID independently.
2. Verify the INCAR/POTCAR/KPOINT set actually used for that row's
   ELECTRONIC_ASSET_ID (match file path, not name).
3. Flag rows whose geometry matches but whose electronic settings differ.
4. Flag any row whose provenance cannot be resolved to a real file.
5. Record flags in the memory's DATA_REGISTRY with status, not filename
   guesses.

## QA

- Re-run on a 10-row sample: every row must resolve to a real asset path.
- No row may be justified by "same structure as X" alone.

## Common failures

- Conflating STRUCTURE_ID with CALCULATION_ID (a prior project lesson:
  "same geometry != same calculation").
- Trusting a filename (e.g. `final`) instead of registry status.
- Merging legacy generations into a canonical dataset.

## Blocking conditions

- No manifest/registry → do not merge; build provenance first.
- Mixed POTCAR/POTCAR versions with no per-row tag → block.

## Outputs

- An audit report: row → STRUCTURE_ID, CALCULATION_ID,
  ELECTRONIC_ASSET_ID, verdict (comparable / flag).
- Updated DATA_REGISTRY entries with status + supersedes.

## Provenance requirements

Every flagged row must carry: source file path, date, status, confidence.
Legacy-source rows must be quarantined, never auto-committed.
