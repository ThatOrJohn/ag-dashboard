# 0012: District weather strip, two panels on one date axis

- **Status:** Accepted; sources changed by [0014](0014-drop-open-meteo.md) (NOAA observed, NWS forecast, pending days)
- **Date:** 2026-11-20

## Context
The Open-Meteo adapter already fetched daily high, low and rain for every county (35 past days plus a 7-day
forecast), but the site showed only three rain totals. The temperatures were fetched and never used.

## Decision
Each home district page gets a "Temperature and rain" chart. One bar per day runs from that day's low to its
high, and a rain panel below shares the same dates. Forecast days are shaded, labeled "Forecast" and hatched.
The values are our area-weighted average of county-center values, in °F and inches, written to
`districts/<slug>.json` as `weather` (`kad/build.py` `weather_strip`).

## Why
- Temperature and rain have different units, so they get two panels with their own y axes on one shared date
  axis, never one chart with two y scales.
- Forecast days are told apart by a labeled band and hatching, not by color alone. Only forecast days after
  the last observed day are used, so an old forecast never overlaps observations.
- It is static SVG drawn at build time, like the maps ([0005](0005-maps-as-build-time-svg.md)). A small
  script adds a hover/tap readout. Without it, each day keeps a native tooltip, and a "Daily numbers"
  table carries every value.
- Labels are kept sparse: the warmest high, the coldest low and the wettest day. A 32°F line appears only
  when lows get to 40°F or below.
- The rain axis runs to at least 0.5 in, so a trace in a dry spell doesn't look like a downpour.

## Consequences
The section hides with the rest of Open-Meteo when that source is stale. A normal high/low band behind the
bars needs the normals backfill (roadmap: rain vs normal). Persona pages and the Texas page don't show the
strip yet.
