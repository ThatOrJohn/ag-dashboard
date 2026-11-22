# ag-dashboard

A free, plain-language read on agriculture from public data, starting with Texas: drought, crop progress,
cattle prices, burn bans and rain, statewide and by NASS district.

**Live site:** <https://thatorjohn.github.io/ag-dashboard/>

A scheduled Python pipeline (`kad/`) pulls public sources twice a day and writes JSON; a static Astro site
(`web/`) renders it and GitHub Pages serves it. See the [Quickstart](QUICKSTART.md) to run it locally,
the [architecture guide](docs/ARCHITECTURE.md) to follow the data from source to page, and the
[decision records](docs/decisions/) for the reasoning behind design choices. The
[development workflow](AGENTS.md) covers keeping the architecture guide current.

## Data
Every figure on the site names its source and as-of date. Sources: USDA NASS (Quick Stats, Cropland Data
Layer), the U.S. Drought Monitor, USDA AMS Market News, Texas A&M Forest Service, the Rangeland Analysis
Platform (USDA ARS), NOAA NCEI nClimGrid-Daily and the National Weather Service. Only sources whose terms
allow any use, with no permission to ask for, are used ([0014](docs/decisions/0014-drop-open-meteo.md)).

This is not an official source. Where it differs from USDA, NOAA or the State of Texas, they are right.

This product uses the NASS API but is not endorsed or certified by NASS.

## Running it
You need free API keys for NASS Quick Stats and USDA MyMarketNews in `.env.local` (see `.env.example`).
In CI they are the repo secrets `NASS_QUICK_STATS_API_KEY` and `AMS_MMN_API_KEY`.

## License
Code: MIT ([LICENSE](LICENSE)). The data belongs to its publishers; see the About page for each source's
terms and required notices.

A personal project by John Walley. The layout and pipeline pattern follow
[ms-sound-check](https://github.com/ThatOrJohn/ms-sound-check).
