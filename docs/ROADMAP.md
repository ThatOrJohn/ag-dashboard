# Roadmap

## Done
- Idea, decisions and personas: `docs/seed.md` (2026-11-20).
- Feasibility probe of every candidate source: `docs/feasibility.md`, `scripts/probe_sources.py`.
- Pipeline, the weekly sources, Texas / district / county views, tests, CI workflow.
- Annual sources: NASS county estimates, Census of Agriculture, Cropland Data Layer via CroplandCROS
  ([0016](decisions/0016-cdl-via-croplandcros.md)), Rangeland Analysis Platform.
- County labels, headlines, dark drought scale, phone layout, persona pages, share images, district
  weather strip ([0012](decisions/0012-district-weather-strip.md)), 1991–2020 normals and rain vs normal
  from NOAA nClimGrid-Daily ([0013](decisions/0013-normals-from-noaa-nclimgrid.md)), NOAA observed + NWS
  forecast instead of Open-Meteo ([0014](decisions/0014-drop-open-meteo.md)), rain since Jan. 1
  ([0015](decisions/0015-rain-since-jan-1.md)), Stage IV rain estimates for the days NOAA hasn't published
  ([0017](decisions/0017-stage4-rain-estimates.md)).
- Full district view for every Texas district; the five featured ones keep the header links
  ([0018](decisions/0018-every-district-full-view.md)).
- County satellite summaries show CDL crop mix and RAP rangeland cover with historical comparisons
  where available ([0019](decisions/0019-county-satellite-summaries.md)).
- Weekly San Angelo sheep and goat auction prices for Edwards Plateau on Cattle & Hay
  ([0020](decisions/0020-san-angelo-sheep-goats.md)).
- Texas New World screwworm detections with a stale-data warning and automatic expiry
  ([0021](decisions/0021-screwworm-detections.md)).
- Cotton boll weevil monitoring and crop-specific AgriLife pest resources
  ([0022](decisions/0022-crop-pest-monitoring.md)).
- Texas cotton harvest outlook with an estimate for the next USDA report and a public accuracy history
  ([0023](decisions/0023-texas-cotton-harvest-outlook.md)).
- Stories: animated replays of two years of county drought maps, daily county rain this year, the cotton
  harvest race, reservoirs since 1950, Ogallala wells, the Brazos at Richmond, a year of calf prices,
  Census farms by county, and five weeks of district rain ([0024](decisions/0024-animated-stories.md)).
- Public repo on GitHub Pages ([0002](decisions/0002-hosting-github-pages.md)), neutral look.

## Next
- Data view (tables, methods, CSV / Parquet downloads).

## Later / maybe
- More stories: crop yields by county (NASS county estimates since 2015), satellite crop mix change (CDL
  2022–2025), the Brazos basin reservoirs.
- National context on the US map (drought, where Texas ranks per commodity).
- Weekly digest (RSS / social) like ms-sound-check.
- More districts' auctions if AMS adds Blacklands or East Texas markets. Hay prices (Texas Direct Hay 2707).

## Exit plan
If pipelines rot and value is near zero: leave the site up with a notice saying what stopped and when.
