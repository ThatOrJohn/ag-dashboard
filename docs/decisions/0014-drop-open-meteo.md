# 0014: Drop Open-Meteo; weather comes from NOAA (observed) and the NWS (forecast)

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
Open-Meteo's free API is for non-commercial use, and its terms list "promotional activities" as commercial.
This site is free, but its code is MIT-licensed and anyone may reuse it for any purpose. So it uses only
sources whose terms allow any use with no permission to ask for.

## Decision
- **Observed:** NOAA nClimGrid-Daily county averages (high, low, rain), the same data as the normals
  ([0013](0013-normals-from-noaa-nclimgrid.md)). Every ingest pulls the last three months; NOAA's newest day
  is about a week back.
- **Forecast:** National Weather Service API, 7 days of high, low and rain at each featured-district county's center
  (`kad/adapters/nws.py`). Grid lookups are cached in the `nws_points` snapshot.
- **The lag is shown, not hidden.** The weather strip has three runs of days: observed, *pending* (NOAA hasn't
  published them: a textured, labeled gap with no bars, still showing the normal band), and forecast. Rain
  totals say the day they run through ("Rain, 7 days to Nov. 14"). The district headline credits NOAA for past
  rain and the NWS for the forecast in separate sentences.

## Why
- Both sources are public domain and need no key or quota.
- Observed weather and normals now come from the same product, so "vs normal" compares like with like for
  temperature too.
- A gap that says "not yet reported" is more honest than a chart that silently ends a week ago or
  blends in modeled values from another source.

## Consequences
- "Last 7 days" is now the week through NOAA's newest day, not through yesterday. A storm in the last week
  shows up a week later.
- `max_age_days`: nclimgrid 14 (allows the usual lag plus a slow update), nws 2. Either going stale hides
  only its own parts.
- Filling the pending days with a public-domain, near-real-time county rain estimate is on the roadmap.
