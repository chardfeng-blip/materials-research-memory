---
name: species_accommodation_analysis_demo
description: demo profile skill about three-species accommodation analysis
---

# species_accommodation_analysis

## Purpose
Analyze three-species accommodation with matched design and CV.

## When to use
When comparing species across defects (three-species accommodation).

## Inputs
Matched defect x species tables.

## Definitions
strict matched vs all available; CV = cross-validation (leave-one-species-out).

## Procedure
1. State the dataset identity.
2. Run per-species analysis.
3. Run the claim gate.

## QA
Every claim quotes the dataset id.

## Common failures
Pooling; CV misread; discrete mode overclaim.

## Blocking conditions
Dataset identity unstated.

## Outputs
Dataset-qualified conclusion.

## Provenance requirements
source, date, status, confidence.
