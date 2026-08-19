---
name: cavity_analysis_demo
description: demo profile skill about cavity analysis
---

# cavity_analysis

## Purpose
Compute cavity descriptors (Vcav, Dmin, Rg, DR1).

## When to use
When computing cavity volumes.

## Inputs
Relaxed structures.

## Definitions
Frozen descriptor definitions.

## Procedure
Tessellate; extract; tag method version.

## QA
Two runs agree.

## Common failures
Definition drift; treating transition channels as state variables.

## Blocking conditions
Frozen definitions missing.

## Outputs
Descriptor table.

## Provenance requirements
source structure path + method version.
