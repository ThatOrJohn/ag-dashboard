# 0018: Every Texas district gets the full district view; five stay featured

- **Status:** Accepted
- **Date:** 2026-11-21

## Context
[0010](0010-featured-districts.md) gave five districts the full view and left the other ten as rows in a
table. All district figures are built from county data the pipeline already fetches for all 254 counties
(Drought Monitor, nClimGrid, Stage IV, burn bans, NASS county estimates, Census), so the gap was three
per-county sources limited to featured counties (CDL, RAP, NWS forecast) and the pages themselves.

## Decision
- All 15 NASS districts get a district page, county cards, a headline and a share image. `home:` in
  `regions/tx.yaml` now means *featured*: header links and first place on the Texas page and persona tables.
- CDL, RAP and the NWS forecast cover every county.
- The header keeps the five featured links; a "More districts" menu holds the other ten (all 15 below
  1100 px). The Texas map links every county to its card, and the "Every other district" table links each name.
- Statewide crop cards per district come from `crops:` in the config (default all four). Edwards Plateau and
  East Texas North keep wheat only, as before; Cross Timbers is set to wheat and Trans-Pecos to cotton and wheat.
- A per-county annual source with counties it hasn't covered yet is due now (`annual.pending`), not after
  `refresh_days`. Otherwise widening the county list would wait up to 30 days for CDL.

## Why
The work was configuration and loops, not new sources, and "why not my district" was the obvious question
0010 could only answer with "in time".

## Consequences
- One-time catch-up after deploy: about 137 counties × 5 years of CDL (about 685 jobs, roughly 13 s each, four
  at a time), so several regular runs at the 480 s annual budget, or one **backfill** dispatch to go faster.
  Each district's land-cover card stays hidden until all its counties have a year; forecasts appear on the
  first run (one-time points lookups, then about 254 forecast calls per run).
- Ten more pages in the Playwright + axe suite (both themes, desktop and phone).
- The `crops:` choices for the new districts are judgment calls; change them in config.
