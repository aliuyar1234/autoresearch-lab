# DESIGN.md

## Design intent

Autoresearch Lab should feel like a **serious instrument**, not a toy demo and not a bloated platform.

The core design move is simple:

> Keep the trainer small. Make the surrounding research loop real.

## Five pillars

### 1. Legibility
Everything important must be understandable from the repo.
Docs, schemas, contracts, and code all matter.

### 2. Throughput
The lab exists to increase useful overnight iteration on one workstation.

### 3. Comparability
Campaigns, budgets, and metrics must be versioned and explicit.

### 4. Robustness
A late eval crash should not waste a whole night.
Artifacts should survive process restarts.
The repo should not rely on log scraping.

### 5. Taste
The upgrade must not erase the upstream repo's personality.
Compactness is a feature.

## Product shape

The lab is:
- CLI-first
- SQLite-backed
- artifact-rich
- report-oriented
- campaign-aware
- dense-model-first

## Notable product choices

- structured search is first-class
- code search is supported, but not the only path
- reports beat dashboards
- worktrees beat dirty branches
- schemas beat grep
- campaign manifests beat hidden assumptions
- cleanup is part of the product, not afterthought tech debt
