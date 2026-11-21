# 0004: Use the agency's figure where it publishes one; districts are our area-weighted totals

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
NASS stopped district estimates after 2019. The Drought Monitor publishes county and state statistics, but
not NASS districts.

## Decision
Texas-wide drought is the Drought Monitor's own state figure. District drought and rain are our
land-area-weighted average of county figures (Census Gazetteer land area), labeled "our total" wherever they
appear. Crop progress and condition are statewide only and say so on every card.

## Why
"Where we differ, they are right" (CLAUDE.md), so we shouldn't publish our own version of a number they
publish. Our weighting reproduces the official state figure closely (2026-11-17: D1+ 42.7% ours vs
43.07% official; the gap is land vs total area), which is good enough for districts.

## Consequences
Small gaps between the Texas number and a sum of districts are expected. If NASS ever resumes district
estimates, use theirs.
