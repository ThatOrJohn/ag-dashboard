# 0013: Weather normals and "rain vs normal" come from NOAA nClimGrid-Daily

- **Status:** Accepted; the Open-Meteo parts are superseded by [0014](0014-drop-open-meteo.md)
- **Date:** 2026-11-20

## Context
"Vs normal" needs 1991–2020 daily normals for every county. The roadmap assumed a backfill from the Open-Meteo
archive. That would take about 90,000 calls' worth of quota for the 117 home-district counties, more than 9
days of the free daily limit, and Open-Meteo's free tier is for non-commercial use. NOAA NCEI's nClimGrid-Daily
publishes daily high, low and rain already averaged over every US county (one CSV per variable per month,
1951 to about a week ago). It is public domain and has no rate limit.

## Decision
- **Normals:** a one-time backfill (`kad/adapters/nclimgrid.py`, annual source `normals`) pulls 1991–2020
  (360 months × 3 variables, ~1 GB, Texas rows only). Each finished month goes into running sums by calendar
  day (`data/<region>/normals/accum.npz`), so a run that hits its time budget continues next run. Once all
  months are in, `kad/normals.py` writes `normals/daily.parquet`: each calendar day's 30-year mean, smoothed
  over ±15 days. It also writes `normals/monthly_rain.parquet`, which a later season-to-date chart can use.
- **Rain vs normal** uses NOAA on both sides. Every ingest pulls nClimGrid's recent months (`nclimgrid`, rain
  only) and compares the 30 days through its newest day with the normal for those dates. That runs about a
  week behind, so the figure carries its own date ("30 days through Nov. 14").
- **Temperature normals** shade a band behind the weather strip's Open-Meteo bars, labeled as a rough guide.

## Why
- On 2026-10-16 to 10-31, Open-Meteo's county-center highs averaged 1.4 °F below nClimGrid's county
  averages, and lows 1.0 °F above. That is close enough for a visual band.
- Rain was not close. Over 87 days (2026-08-20 to 11-14, 117 counties), Open-Meteo's totals came to 1.13×
  nClimGrid's overall, but county by county they correlated only 0.47. Some months and districts differed by
  25–60% (September 1.63×, East Texas South 1.46×). A percentage built on one source's rain and the other's
  normal would be off by that much, so both sides come from NOAA.
- The normals agree with NOAA's station normals: Travis County comes out at 62/38 °F in January,
  96/73 °F in July and 35.4 in a year; El Paso at 9.5 in.

## Consequences
- No API key, no quota, and no license question for the normals. The data branch holds about 3 MB of sums and
  normals, not 8 million daily rows.
- The site shows two rain clocks. The 7- and 30-day totals come from Open-Meteo, through yesterday. "Vs normal"
  comes from NOAA, about a week behind. Each is labeled with its date.
- If Open-Meteo is replaced (its free tier is for non-commercial use), nClimGrid can carry observed rain too,
  at the cost of that week's lag.
- The 2001–2030 normals (expected around 2031) need a re-run with new years (`FIRST`, `LAST`).
