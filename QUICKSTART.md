# Quickstart

For a walkthrough of the pipeline, site, and deployment, see the [architecture guide](docs/ARCHITECTURE.md).

```
 Public sources                     GitHub Actions (13:17, 23:17 UTC + push)       The site
 Drought Monitor ──┐
 NASS Quick Stats  ┤                python -m kad run                            GitHub Pages,
 AMS Market News   ┤  ──────────►     ingest (adapters) → store (data branch)    served at
 TFS burn bans     ┤                  build  → web/public/data/tx/*.json   ───►  thatorjohn.github.io/
 NOAA nClimGrid    ┤                  check  (health)                            ag-dashboard/
 NWS Stage IV      ┤
 NWS forecast      ┘
```

## Run it locally
Install Poppler (`brew install poppler` on macOS or `sudo apt-get install poppler-utils` on Ubuntu) to
refresh the Texas boll weevil report. Builds from saved data do not require Poppler.

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
(cd web && npm ci)
# keys in .env.local (see .env.example); kad reads it automatically
python -m kad backfill        # first time: 2 years of drought, 60 weeks of auctions
python -m kad run             # pull this week, annual sources if due, build JSON, print the run report
python -m kad annual --force --only rap   # refetch one annual source now
python -m pytest -q
(cd web && npm run dev)       # http://localhost:4321/ag-dashboard/
(cd web && npm run build && npx playwright test)
```
`python -m kad build --asof YYYY-MM-DD` shows the site as of another date (e.g. a January date to see the
NASS winter break). Local data is in `data/tx/` and `web/public/data/` (both gitignored).

## What GitHub Actions fetches

Scheduled runs, pushes to `main`, and manual `run` dispatches start with the `data` branch snapshot.
They refresh six weeks of drought and auction data, refresh recent weather and burn bans, and check annual
sources on their individual schedules. Once NASS crop progress has a baseline, it refreshes the current and
previous years and catches up after longer gaps. Older year-to-date NOAA rain is reused after finalization.

Use **Run workflow → backfill** for two years of drought history, 60 weeks of auction reports, the full NASS
comparison baseline, and a longer annual refresh pass. The workflow saves the data snapshot before building
the site and running browser tests so later runs can resume partial history. Pull requests build from the
saved snapshot with no live ingestion.

## Where things live
| Path | What |
|---|---|
| `web/src/styles/tokens.css` | Color tokens, light and dark, with AA-tuned pairs. |
| `web/src/lib/site.ts` | Site name, author, repo link, the mark. |
| `regions/tx.yaml` | Districts (all get a page; featured = `home`, and order; `crops`), personas, sources, max ages, seasons, AMS reports. |
| `regions/tx-counties.csv` | 254 counties → district, centroid, land area. `scripts/make_county_table.py`. |
| `kad/adapters/` | One file per source. |
| `kad/build.py` | Freshness, seasons, district totals, JSON for the site. |
| `web/src/` | Pages (`index`, `district/[slug]`, `about`), components, `lib/types.ts` mirrors build.py. |
| `docs/decisions/` | Why things are the way they are. |

## When something breaks
| Symptom | Likely cause |
|---|---|
| Red **health** job | Its summary says which: update job failed, deploy failed, or core data (Drought Monitor / NASS weekly) is stale. |
| Anything else odd | The update job's summary has **Data sources this run**: every source's status, newest figure and the error in plain words. Annual sources that failed retry on the next run by themselves. |
| Burn-ban section gone, log says "unknown styles" | TFS changed the KMZ. See [0003](docs/decisions/0003-burn-ban-style-ids.md). |
| NASS "not set" / AMS "not set" in the log | Repo secrets missing. |
| Red **deploy** job | Settings → Pages source isn't "GitHub Actions", or the `github-pages` environment blocks `main`. |
| Scheduled runs stopped | GitHub disables schedules after 60 days without activity; the deploy job re-enables the workflow each run, so this means deploys stopped too. Actions → Enable workflow. |
