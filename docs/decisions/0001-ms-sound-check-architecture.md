# 0001: Same shape as ms-sound-check: scheduled pipeline, Parquet store, static site

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
A free, low-upkeep site from public data that updates weekly at most (burn bans daily). The owner already
runs ms-sound-check (MIT) on this pattern, and upkeep, not build, is the real cost (seed.md).

## Decision
Python package `kad/` (one adapter per source, every call wrapped in `_try`), region config in
`regions/tx.yaml` plus `regions/tx-counties.csv`, one long Parquet table per source
(`geo, var, date, value, source`) on a single-commit `data` branch, JSON into `web/public/data/tx/`, and an
Astro + React static site. GitHub Actions runs it twice a day.

## Why
Same mental model and the same failure handling as a project that already works. A per-source table (not
ms-sound-check's per-year daily table) fits sources that are weekly, county-keyed and mixed-cadence.

## Consequences
No server, no per-user state. Swapping one source is a one-file change. Anything needing real-time data or
accounts would need a new decision.
