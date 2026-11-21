# Ag Dashboard — Project Seed

## What this is
A free, public, plain-language read on agriculture built on public data, starting with Texas. Modeled on
ms-sound-check: a scheduled Python pipeline writes JSON, and a static Astro + React site renders it. A
personal project, published on GitHub Pages; not a revenue product.

## Decisions so far (Nov 2026)
- **Texas only, for a long time.** Keep data keyed by FIPS so another state isn't a rewrite, but build no
  multi-state framework. National sources are pulled only for national context (the intro map).
- **Featured districts:** five NASS districts are featured: Blacklands (first), South Central, Edwards
  Plateau, East Texas North and East Texas South (decision 0010). They started as the only districts with the
  full view; every district got it on 2026-11-21 (decision 0018). Rosters in feasibility.md.
- **No programmatic per-county pages** unless a county view carries real value (see below).
- **Exit plan is acceptable:** if pipelines rot and the value is near zero, leave the site up with a notice
  saying what stopped and when.

- **Two views of the same data.** Default is the **operator view** (farm/ranch: plain language, "this
  week," what it means). A **data view** serves analysts and data-science readers: the tables behind each
  card, units, as-of dates, methodology notes, links to the source query, and CSV/Parquet downloads of the
  derived tables. Nice-to-have, not a launch blocker; cheap because the pipeline already writes the data.
- **Look:** a neutral palette of its own (`web/src/styles/tokens.css`: OKLCH, light + dark), Inter Tight /
  Fraunces / JetBrains Mono, `--measure`/`--inset` layout. House rules: AA contrast floor using the tuned
  pairs only, 44 px touch targets, reduced motion, never color alone.

## Hosting
GitHub Pages, deployed by the scheduled workflow (decision 0002). The site builds under the repo's path
(`/ag-dashboard/`); `SITE_URL` / `SITE_BASE` override it for a custom domain.

## Attribution (required)
- NASS API terms: display prominently, on every page that shows NASS-derived data (site footer plus the
  About the data page): **"This product uses the NASS API but is not endorsed or certified by NASS."**
  The NASS name may identify the source of figures; never phrase anything to imply NASS endorses this site.
- Same pattern for every source: name, link, as-of date, and the publisher's own required notice where
  one exists (TFS logo on burn-ban graphics; "Rangeland Analysis Platform, USDA ARS"). Federal data is public domain, but credit it anyway.
- Site-wide disclaimer in the ms-sound-check spirit: not an official source; where I differ from USDA,
  NOAA or the state, they are right.

## Core insight
Most of the data is public already (NASS Quick Stats, CropScape, the Drought Monitor, AMS Market News).
What's missing is the same thing ms-sound-check supplies: a layout organized around the person reading it
and a plain-language "so what" for this week, for this part of Texas.

## Satellite layers
Satellite-derived layers (crop mix from the Cropland Data Layer, rangeland cover and forage from RAP,
land-cover change) at 30 m show each county from above, which the weekly feeds can't.

## Personas (Blackland-first)
Personas are config, as in ms-sound-check (decision 0010 there).
- **Corn & Sorghum**: crop progress and condition, planted/harvested acres, prices, heat and rain at
  pollination/heading.
- **Cotton**: planting and boll progress, condition, prices, Blackland cotton root rot season context.
- **Wheat & Small Grains**: planting, grazing vs grain, condition.
- **Cattle & Hay**: auction prices (Texas weekly summary, Giddings, San Angelo), inventory, hay prices,
  pasture condition, rangeland forage from RAP. Sheep and goats belong here too for the Edwards Plateau.
- **Land, Water & Weather** (shared by all): drought, soil moisture, rain vs normal, burn bans,
  land-use change.

## The zoom: US → Texas → ag district → county
Texas's agricultural statistics districts (the Blacklands are one) are the natural middle stop. NASS
stopped publishing district estimates after 2019, so district figures are my own aggregation of counties
plus the Cropland Data Layer (see feasibility.md).
- **US map (intro):** national context only (drought, where Texas sits in each commodity).
- **Texas:** statewide this-week digest, district choropleths.
- **District (Blacklands first):** the main working view; most weekly and annual data lands here cleanly.
- **County:** a zoom stop on the map, with a card, not a page of its own. It earns a page only if it can
  show something county-native, such as:
  - crop mix and how it shifted over the years (Cropland Data Layer, annual, 30 m)
  - drought category coverage this week vs a year ago
  - NASS county estimates where they aren't suppressed (many are)
  If a county view would be mostly "see district," it stays a card.

## Candidate sources (as first listed; see feasibility.md for what each actually returns)
| Source | What | Cadence | Level |
|---|---|---|---|
| USDA NASS Quick Stats API | acres, yield, production, inventory, prices, crop progress/condition | weekly–annual | state/district/county |
| USDA NASS Cropland Data Layer (CropScape) | crop type map, 30 m | annual | pixel |
| US Drought Monitor | drought categories, county stats | weekly | county |
| USDA AMS Market News (MARS API) | Texas livestock auctions, hay, grain bids | weekly | market |
| Census of Agriculture (2022; next 2027) | farm counts, sizes, land use | 5-yearly | county |
| NOAA / NWS | rain, temp, normals | daily | point/grid |
| Texas A&M Forest Service | burn bans, fire danger | daily | county |
| Rangeland Analysis Platform / Sentinel-2 / MODIS | vegetation cover and condition | annual–weekly | 10–250 m |
| AgriLife / TX crop and weather reports | district narrative | weekly | district |

## Red-team notes
- Static annual stats don't bring people back. The weekly feeds (crop progress, drought, auctions, burn
  bans) carry the "this week" view; annual data is context.
- Quick Stats county data has heavy suppression; county-level ambitions may shrink once you look.
- A wrong number hurts more than no page. Every figure shows source and
  as-of date; stale data hides rather than showing old numbers (ms-sound-check rule).
- Raw rehosting of NASS is already done (Quick Stats itself). The value is layout and interpretation.
- Upkeep, not build, is the real cost. One bad source hides only its own section (ms-sound-check 0046).

## Open questions
- ~~Deploy target for this repo~~: GitHub Pages, public repo (decision 0002).
- Weekly cadence enough, or daily for weather/burn bans?
- Is a weekly digest (RSS/social), like ms-sound-check's, worth it here?

## Next
Feasibility is done (`docs/feasibility.md`). Work continues from `docs/ROADMAP.md`.
