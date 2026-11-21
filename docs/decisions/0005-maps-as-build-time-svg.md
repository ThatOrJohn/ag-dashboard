# 0005: Maps are static SVG drawn at build time, not a tiled web map

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
The zoom is US → Texas → district → county. ms-sound-check uses MapLibre with tiles for a small coastal area.

## Decision
Draw county maps at build time with d3-geo from `us-atlas` (Census 1:10m boundaries). Each county is a link
(on Texas, to its card on the district page; on a district, to `#c-<fips>`). A county's color is the most
severe drought category covering at least half of it. D3 and D4 are also hatched, every county has a text
title, and the cards and tables carry the same facts.

## Why
Choropleths of 254 counties don't need tiles or pan and zoom. Static SVG ships no map JavaScript, works
without JS, is indexable, and passes axe in both themes.

## Consequences
No basemap, roads or towns. When the satellite layers (CDL crop mix, RAP) arrive, they may need a raster or
tiled map, which would need a new decision.

## Addendum (2026-11-20): county names on district maps
District maps label every county. Labels are placed at build time, largest county first, shrinking to 72%
and then dropped if they would still overlap (separately for desktop and phone sizes). A dropped name is
still in the county's tooltip and card. Labels are ink with a 3px paper halo, so they meet AA on any fill;
axe can't see the halo, so its contrast rule skips `.county-name` only.
