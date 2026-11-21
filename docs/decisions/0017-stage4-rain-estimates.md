# 0017: Fill NOAA's lag with Stage IV rain estimates

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
NOAA's nClimGrid-Daily county averages (0013, 0014) run about six days behind, so every rain figure ended
a week ago and the weather strip showed a "Pending" gap. Open-Meteo is gone (0014), so the fill had to be
public domain. The pipeline has no GRIB or raster libraries.

## Decision
Use the National Weather Service's Stage IV multi-sensor precipitation (radar adjusted to rain gauges by the
River Forecast Centers), from the daily netCDF files at
`water.noaa.gov/resources/downloads/precip/stageIV/YYYY/MM/DD/nws_precip_1day_YYYYMMDD_conus.nc`, read with
`h5py`. Each run takes the last 10 days' files and averages the 4 km HRAP cells whose centers fall in each
county (`kad/adapters/stage4.py`, source `stage4`).

The site uses them only for the days after NOAA's newest county-average day and before today, and always as
an estimate:
- weather strip: those days' rain as outlined bars; their highs and lows stay "Pending";
- district rain section, county cards and the district headline: "Since then, Nov. 15 to Nov. 19: about
  1.08 in (estimate)", below NOAA's figures;
- never in 7- or 30-day totals, "vs normal" or "Rain since Jan. 1", which stay NOAA against NOAA.

## Why
- File D (24 hours ending 12Z on D) lines up with nClimGrid's day D: Sept. 1 to Nov. 16, 2026, Texas
  county-days correlate 0.86 on the same date and 0.26 one day either way; district-day averages, 0.96.
- Files are posted within about a day, so the gap shrinks from about six days to none or one.
- It runs wetter than nClimGrid, and not by a steady amount: 25% in September, 9% in October, 34% in early
  November. A fixed correction would be false precision, so the site labels it and keeps it out of normals.
  For a county's 7 days, the difference is +0.03 in at the median and +0.5 in at the 90th percentile.
- Public domain (NOAA/NWS); no key.

## Consequences
- 10 files of about 3.7 MB each per run; the county cell lists are recomputed each run (under a second).
- A day goes from estimate to NOAA's number when nClimGrid catches up, with no change on our side.
- Stale after 4 days (`max_age_days`), when the estimate lines and bars hide.
- If the files move (they moved once, from water.weather.gov), the adapter fails like any source.
- Revisit if NOAA starts publishing county averages sooner, or if the bias turns out to be steady enough
  to correct.
