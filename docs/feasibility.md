# Feasibility — what the sources actually return

Probed 2026-11-20 with `scripts/probe_sources.py` plus follow-up queries. Focus: the Blacklands NASS district
and its neighboring counties (Williamson, Milam, Bell, Falls, McLennan, ...).

## Bottom line
- **The weekly "this week" view is buildable at the state level, plus county drought.** NASS crop progress,
  crop condition and pasture condition are weekly and current, but **state-level only**. The Drought Monitor
  is weekly, current and **county-level**. Weather is daily at any point.
- **NASS no longer publishes district-level estimates** (crop districts end in 2019). The district view has to
  be computed from counties, and that isn't exact (see below).
- **NASS county estimates are patchy.** For 2025 corn, only 47 Texas counties are published by name, and every
  other county is lumped into one statewide "OTHER COUNTIES" bucket with no district attached. In the Blacklands,
  Williamson has corn acres for 5 of the last 5 years, but sorghum and wheat for only 2. A district total built
  from NASS counties is a **lower bound**, not a total.
- **The Cropland Data Layer fills that gap.** It covers every county, every year, every land-cover class, at
  30 m. For Williamson 2025 it reports 102,246 acres of corn; NASS says 106,000 planted. That's close enough to
  use as the backbone for county and district crop mix, labeled as satellite-classified.
- **Verdict on county pages:** a county card is justified (drought this week vs last year, CDL crop mix and how
  it shifted, NASS acres/yield where published, Census of Ag). A standalone county page isn't, yet.

## Source by source

| Source | Reachable | Level | Fresh to | Notes |
|---|---|---|---|---|
| NASS crop progress (corn, cotton, sorghum, wheat) | yes | state only | week ending 2026-11-15 | % planted / emerged / harvested etc. No district or county. |
| NASS crop condition | yes | state only | 2026-10-25 (corn), 2026-10-18 (sorghum), 2026-07-05 (wheat) | Seasonal; stops after harvest. Fine, but the card must say "season over". |
| NASS pasture condition | yes | state only | 2026-10-25 | Good Cattle & Hay card. |
| NASS county planted acres / yield | yes | county (named ones only) | 2025 | No `(D)` values; unpublished counties are simply missing, or in "OTHER COUNTIES". |
| NASS county cattle inventory | yes | county | 2026 | 142 of 396 Blacklands values suppressed (36%). Usable with clear gaps. |
| NASS hay by county | **no** | — | 1986 | County hay series ended decades ago. Hay is state-level only. |
| NASS district (agricultural district) | **no** | — | 2019 | Discontinued. Compute from counties + CDL. |
| Census of Agriculture | yes | county | 2022 (next 2027) | Farm counts, acres, cattle (Williamson 2022: 44,765 head). 2 of 387 values suppressed. |
| Cropland Data Layer (CropScape) | **was** yes | county / 30 m pixel | 2025 | **2026-11-20: GetCDLStat 503s and CropScape redirects to a sign-in; replaced by CroplandCROS's public statistics service (0016).** `GetCDLStat` returns a URL to a cached stats file per county-year. That file is a JS object literal with unquoted keys, not strict JSON, so it needs a lenient parser. |
| US Drought Monitor | yes | county | map date 2026-11-17 | Clean JSON. Values are cumulative (D1 = "D1 or worse"). Milam: 100% D2, 10.7% D3 this week. |
| Open-Meteo archive | yes | point | ~5-day lag | Rain and temperature history; CC BY 4.0 attribution. Free tier is non-commercial; 30 years × 117 counties ≈ 90k calls of quota (see 0013). **Dropped 2026-11-20 (0014).** |
| NWS API (api.weather.gov) | yes | grid (2.5 km) | forecast, updated hourly | Added 2026-11-20. No key; send a User-Agent. `/points/{lat},{lon}` → `forecastGridData`; max/min temperature (°C) and 6-hour QPF (mm) as ISO 8601 intervals, ~7 days. 117 home counties ≈ 13 s. Public domain. |
| NOAA nClimGrid-Daily county averages | yes | county | ~6-day lag (prelim) | Added 2026-11-20. Monthly CSVs per variable, all US counties, 1951 on; °C and mm; -999.99 pads; NCEI state codes (Texas 41), not FIPS. Public domain. Normals source (0013). |
| NWS/NCEP Stage IV daily precipitation | yes | grid (4 km HRAP) | about 1 day | Added 2026-11-20. Daily netCDF-4 (HDF5) per day at `water.noaa.gov/resources/downloads/precip/stageIV/YYYY/MM/DD/nws_precip_1day_YYYYMMDD_conus.nc`, 3.7 MB, inches, 24 h ending 12Z. Polar stereographic (sphere 6,371,200 m, 60° N, 105° W), x/y given. Lines up with nClimGrid's same date; runs 9–34% wetter by month. Public domain. Fill for NOAA's lag (0017). |
| AMS Market News (MyMarketNews) | yes (key) | market | auctions 2026-11-16 | Key works (basic auth, key as user, blank password). 1,052 reports. Auctions are clean rows (class, weight break, avg price/cwt, head). Hay and grain bids are *sectioned* reports: fetch `/reports/{slug}/Report Details`. |
| TFS burn bans | yes | county | daily | KMZ at `https://tfsfrp.tamu.edu/WILDFIRES/Burn_Ban.kmz` (424 KB). 254 placemarks, one per county, named by the 3-digit county FIPS code padded with spaces ("001       "). Two styles, `#PolyStyle00` and `#PolyStyle02`, carry ban / no ban; **which is which is not yet confirmed**, so check against the TFS web map on the first build. TFS asks for credit (their logo) on graphics. |
| Rangeland Analysis Platform | yes | polygon mean | cover 1986–2025; 16-day production into 2026 | Public POST API (`https://us-central1-rap-data-365417.cloudfunctions.net/{coverV3,production16dayV3}`); body is a GeoJSON Feature with `properties: {mask: true, year: null}`. A small box near Fredericksburg: cover 3.5 s, 40 years; 16-day production 8.9 s, 943 rows. Tables have a header row. **Future 16-day intervals come back as `-99`**: treat as missing and use the latest real value. County polygons will be slower than the test box; cache annual cover, refresh production every 16 days. Credit "Rangeland Analysis Platform, USDA ARS". |

## Featured districts and markets
The featured area spans four NASS districts (five after decision 0010). Rosters as NASS returns them (each also has an
"OTHER (COMBINED) COUNTIES" bucket in older years):
- **Blacklands** (home, 25): Bell, Bosque, Collin, Cooke, Coryell, Dallas, Delta, Denton, Ellis, Falls, Fannin,
  Grayson, Hamilton, Hill, Hunt, Johnson, Kaufman, Lamar, Limestone, McLennan, Milam, Navarro, Rockwall,
  Tarrant, Williamson.
- **South Central** (21): Austin, Bastrop, Bee, Bexar, Burleson, Caldwell, Colorado, Comal, DeWitt, Fayette,
  Goliad, Gonzales, Guadalupe, Hays, Karnes, Lavaca, Lee, Medina, Travis, Washington, Wilson.
- **Edwards Plateau** (28): Bandera, Blanco, Burnet, Coke, Concho, Crockett, Edwards, Gillespie, Irion, Kendall,
  Kerr, Kimble, Kinney, Lampasas, Llano, Mason, McCulloch, Menard, Reagan, Real, San Saba, Schleicher, Sterling,
  Sutton, Tom Green, Upton, Uvalde, Val Verde.
- **East Texas North** (24): Anderson, Bowie, Camp, Cass, Cherokee, Franklin, Gregg, Harrison, Henderson,
  Hopkins, Houston, Marion, Morris, Nacogdoches, Panola, Rains, Red River, Rusk, Shelby, Smith, Titus,
  Upshur, Van Zandt, Wood.

(These are counties that appear in NASS cattle data; a county with no published data at all could be
missing. Cross-check against a full FIPS-to-district table before relying on it.)

The four districts are different kinds of country, which suits the personas: Blacklands and South Central
are row crops plus cattle; Edwards Plateau is range, cattle, sheep and goats (RAP matters most there);
East Texas North is pasture, hay, cattle and timber.

Relevant AMS reports (Texas, active): Texas Weekly Cattle Auction Summary (1955), Giddings Livestock
Auction (3724, Lee County, South Central), Producers Livestock San Angelo cattle (2015), sheep and goats
(2014) and feeder calves (2013) for the Edwards Plateau side, Texas Direct Hay Report (2707, regions are
Panhandle and South only), Texas Daily Grain Bids (2711). No AMS-covered auction sits inside the
Blacklands or East Texas North; the statewide summary covers them.

## Gotchas found
- NASS answers "no rows" with **HTTP 400 "bad request - invalid query"**, not an empty list. The adapter must
  treat that as empty-not-broken, or a quiet off-season will look like an outage.
- NASS values are strings with thousands separators ("106,000") and footnote codes; parse defensively.
- The NASS county roster for the Blacklands, as returned: Bell, Bosque, Collin, Cooke, Coryell, Dallas, Delta,
  Denton, Ellis, Falls, Fannin, Grayson, Hamilton, Hill, Hunt, Johnson, Kaufman, Lamar, Limestone, McLennan,
  Milam, Navarro, Rockwall, Tarrant, Williamson. Not Travis. The area of interest may
  cross into the East Texas districts; decide which districts the site features.
- Crop condition series stop at harvest; the site needs "out of season" states rather than stale numbers.

## What this changes in the seed
- District stays the main view, but it is **our** aggregation: CDL for crop mix every year, NASS county
  figures where published (shown as "published counties" with the gap stated), state weekly reports for
  progress and condition.
- The weekly operator view leans on: Drought Monitor (county), state progress/condition, pasture condition,
  rain vs normal, and (with a key) auction prices.
- Hay drops to state level plus CDL hay acreage.

## Next
- Build a FIPS → NASS district lookup for all 254 counties (once, committed as config).
- Then scaffold from ms-sound-check.
