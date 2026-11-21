# 0016: Cropland Data Layer from CroplandCROS, as shares of county land

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
The CDL adapter was written against CropScape's `GetCDLStat` ([0011](0011-annual-sources-when-due.md)). On
2026-11-20 that endpoint returned 503 on every CI run, and CropScape's site redirected to a CropSmart sign-in
page. NASS and ARS now publish the CDL through CroplandCROS (croplandcros.scinet.usda.gov). Its statistics tool
calls a public ArcGIS geoprocessing service, `Calculate_Statistics_with_HI` (dataset `CDLS_WM`, years through
2025), that takes an outline and returns pixel counts per class, with no account.

## Decision
- One statistics job per county-year, with the county outline from `regions/tx-counties.geojson`, four jobs at
  a time, about 6–13 s each. Class names come from the CDL image service's own raster attribute table, so
  slugs match NASS's names ("Grassland/Pasture" → `grassland_pasture`).
- **Acres by share.** The mosaic is Web Mercator, so a pixel's ground area depends on latitude and the
  dataset's cell size. Each class's acres = its share of the county's land pixels (all but background and
  water) × the county's Census land area.
- **2021 to last year** for home-district counties (585 county-years, a one-time backfill, then 117 a year).
- District pages show "What covers the land": our sum of county acres for the newest year that every county
  has, against the earliest. The four developed classes are combined. Only crops show a change in acres;
  grass, forest, shrub, wetland, barren and developed say "not compared".

## Why
- Williamson County corn, 2025: 101,891 acres this way, against 102,246 from CropScape in the feasibility
  probe (0.4% apart).
- Non-crop cover comes from a base layer NASS reworks between years. Blacklands "gained" 1.3 million acres
  of grassland and lost 0.5 million of deciduous forest from 2023 to 2025, which is a change in method, not
  in the land. Crops are what the CDL is built to track year over year.
- Shares don't depend on the projection or the cell size, and the Census land area is the same one used
  everywhere else on the site.

## Consequences
- This is the service behind a public USDA app, not a documented API, so it may change without notice. The
  adapter fails like any source: CDL hides, and the run report says why.
- Classification noise: the site says small year-to-year changes can be noise and labels figures as
  satellite-classified.
- More years, or the rest of Texas, only need `first_year` or the county list changed (about 13 s each).
