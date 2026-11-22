# 0026: Stories cover an area: the US, a state or a district

- **Status:** Proposed
- **Date:** 2026-11-22

## Context
The site was planned to cover the whole US and drill down to any state (seed.md), and the pipeline is already
region-aware: `kad/stories.py` takes a `Region`, writes `data/<region>/stories.json`, and the web build reads
`REGION` (`lib/data.ts`). The stories themselves are not. Their builders write "Texas" into about 50
captions and titles, `/stories/<slug>/` has no area in the path, `lib/geo.ts` filters to the Texas FIPS
prefix, and one flat registry (`lib/stories/index.ts`) mixes two kinds of story:

- stories whose source covers every state the same way (Drought Monitor, NASS progress and harvest, Census of
  Agriculture, CDL, RAP, NASS county yields, nClimGrid);
- stories whose source exists only for one state, or was chosen for one state (TWDB reservoirs and wells, the
  configured USGS gauges, the AMS auction report picked for Texas).

The stories shipped today (0024, 0025), so their URLs have few outside links yet. Changing them later would be
much more costly.

## Decision
Every story is built for an **area**: `{ level: "us" | "state" | "district", id, name, phrase }`, using
`name` and `phrase` as the district config already does (`regions/tx.yaml`).

- **Template stories** are written once and built for every area their source covers. Their copy names
  the area only through `name`/`phrase`, never a literal state name.
- **Local stories** are registered per region in `regions/<state>.yaml` (`stories:`), with their adapters
  and settings (gauges, wells, auction report) beside them. Another state's local stories are config plus
  adapters, not edits to the template stories.
- **URLs carry the area:** `/stories/<state>/<slug>/` for a state, `/stories/<state>/<district>/<slug>/` for a
  district, `/stories/us/<slug>/` for the nation. The Stories index stays at `/stories/`. Share images follow
  the same path (`og/story-<state>-<slug>.png`, and so on).
- Today's `/stories/<slug>/` URLs become small static pages that redirect to `/stories/tx/<slug>/`
  (`<meta http-equiv="refresh">` plus a canonical link and a plain link). GitHub Pages has no server
  redirects.
- `lib/geo.ts` takes the state FIPS (or none, for the US) from the area instead of a Texas constant.

## Why
- Most of the stories worth telling (drought, harvest, Census farms, crop mix) come from national sources.
  Writing them once for any area is the same idea as keying everything by county FIPS.
- The district `phrase` already solved how to name a place in the middle of a sentence ("Drought eased in the
  Blacklands"). Reusing it keeps captions grammatical at every level.
- An area in the URL keeps every story's address stable as states are added. Without it, a second state's
  drought story would have to take a new name or push Texas off the old one.
- Splitting templates from local stories keeps state-specific sources from blocking a new state. Oklahoma
  can launch with every template story before anyone finds its reservoir data.

## Consequences
- Story builders take an area and the region's data, not `latest` and `data` for a fixed region. The
  registry lists template stories once and expands them across areas at build time.
- A test fails if a state name appears as a literal in `web/src/lib/stories/`. A small second-region fixture
  (a few Oklahoma counties) must build every template story, so Texas assumptions surface in CI.
- The Stories index needs a way to choose an area once there is more than one state. Until then it lists
  Texas stories as it does now.
- Stories for all 15 districts would multiply the index. District-level stories are linked from their
  district page first (see 0027), not all listed on `/stories/`.
- US-level stories need a national data set (`data/us/`) that the pipeline doesn't produce yet. Showing all
  ~3,100 counties for 104 weeks would be about 330 KB of drought characters, so US stories draw states by
  default.
- Revisit if the site stays Texas-only for good. The area parameter would then be overhead, but cheap
  overhead.
