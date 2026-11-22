# 0024: Animated stories replay stored history

- **Status:** Accepted
- **Date:** 2026-11-22

## Context
The first story drafts animated values that already appear on district pages. One of them showed seven weeks
of drought for three districts as bars beside a static map. The map never changed, so the animation added
little. The store has much richer history the site never publishes: 104 weekly county Drought Monitor maps
and six seasons of weekly statewide cotton harvest reports.

## Decision
The pipeline writes `stories.json` with the history the stories replay: a one-character drought category per
county per week, the official statewide percentages, and cotton harvest reports grouped by season. Stories
built from this file refresh on every build. They find their chapters in the data instead of relying on
hand-written captions. A story whose data no longer refreshes (rain) keeps its figures and captions in code,
labeled with the period it covers.

## Why
- A county flipbook is the familiar way to show drought moving, and it needs per-county history. The 104 weeks
  are about 40 KB of JSON, around 55 KB gzipped for the whole page.
- Data-derived chapters (least and most drought, fastest spread, turning points) keep captions accurate as
  new maps arrive without anyone rewriting them.
- Stale sources hide their story as they hide any section, and its stable URL points to the live dashboard.
- County categories use the same rule as the dashboard's maps (the worst class covering half the county), so
  the story and the map agree.

## Consequences
- New stories take a builder, a visual component and, if the history isn't published, a `stories.json`
  entry. Long series such as reservoirs (1933 on) should be downsampled before they go into the file.
- Captions are generated, so their wording is tested through the story builders, not reviewed by hand.
