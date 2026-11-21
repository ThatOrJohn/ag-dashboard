# 0015: Rain since Jan. 1, against the 1991–2020 normal and typical range

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
A week or 30 days of rain says little about drought; the running total for the year does. The normals
backfill ([0013](0013-normals-from-noaa-nclimgrid.md)) kept daily normals and every county's monthly totals
for 1991–2020, but not 30 years of daily values.

## Decision
- Each home district page gets "Rain since Jan. 1". It shows this year's running total through NOAA's newest
  day, the normal running total, and the typical range (10th to 90th percentile of the 30 years' running
  totals). The normal and the range run to Dec. 31. One y axis, in inches. A legend and labels at the ends of
  the lines name everything, there's a hover readout, and a month-by-month table.
- **Calendar year.** In early January it shows last year until NOAA's newest day crosses Jan. 1, because
  the chart's year is the year of that day.
- **Range from monthly totals:** each year's running total is its monthly totals spread across each month in
  the shape of the daily normal. The percentiles are taken across the years of the district average, not
  averaged from county percentiles.
- **Rank in plain words:** "By this date, 6 of the 30 years had less rain and 24 had more". When only a few
  years are on one side, it says so ("Only 2 of the 30 years…").
- The recent NOAA pull now covers rain back to Jan. 1 (of last year too, while NOAA's newest day is in it).
  Highs and lows still cover 3 months. The files are fetched in parallel, about 3 seconds per run.

## Why
- Monthly totals give the right year-to-year spread at month ends, which is what drives the range. Inside
  a month, the normal's shape is a fair guide, and it avoids storing 8 million daily rows.
- The middle 80% shows where most years fall without letting one record year stretch the band.

## Consequences
- The chart hides if any day since Jan. 1 is missing (a short total would look like a drought), if the
  normals backfill isn't done, or if NOAA's data is stale.
- A water year (Oct. 1 start) or a growing-season view would only need a different start date.
