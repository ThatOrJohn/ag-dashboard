# ag-dashboard

Free, plain-language agriculture dashboard built from public data, starting with Texas. A personal
project: public repo, MIT-licensed, served by GitHub Pages at **thatorjohn.github.io/ag-dashboard/**.

## Read first
0. `QUICKSTART.md`: how it fits together.
1. `docs/seed.md`: what this is, decisions so far, personas, hosting, attribution rules.
2. `docs/feasibility.md`: what each source actually returns (probed 2026-11-20), gotchas, district rosters.
3. `docs/ROADMAP.md`: what's next.

**Template:** this repo follows the owner's own `ms-sound-check` project (MIT):
<https://github.com/ThatOrJohn/ms-sound-check>. Clone it beside this repo and read its `CLAUDE.md`,
`QUICKSTART.md` and `docs/decisions/` before scaffolding. Reuse its structure and patterns (scheduled
Python pipeline → JSON → static Astro + React site, personas as config, adapters per source, `_try`
wrapper, stale data hides, parquet store on a `data` branch). Don't copy its Mississippi-specific models.

## Commands
```bash
source .venv/bin/activate              # Python 3.11+, requirements-dev.txt
python -m kad run                      # ingest + build JSON into web/public/data/tx/
python -m kad build [--asof DATE]      # rebuild JSON from the local store only
python -m kad check                    # health check CI runs
python -m pytest -q
cd web && npm run dev                  # http://localhost:4321/ag-dashboard/
cd web && npm run build                # astro check + build (0 errors)
cd web && npx playwright test          # Playwright + axe, both themes; gates deploys (PORT=… if 4321 is taken)
```
See `QUICKSTART.md` for the whole system and `docs/decisions/` before changing what a record covers.

## Setup
- Python 3.11+, Node (pin in `web/.nvmrc` once scaffolded).
- Secrets live in `.env.local` (gitignored). Keys needed: see `.env.example`
  (`NASS_QUICK_STATS_API_KEY`, `AMS_MMN_API_KEY` for USDA MyMarketNews). Both are free; get the values from
  the owner, never commit them, and in CI pass them as GitHub Actions secrets.
- `scripts/probe_sources.py` re-runs the feasibility probe (`python3 scripts/probe_sources.py [names...]`);
  output goes to `data/probe/` (gitignored).

## Scope
- **Texas first.** All 15 NASS agricultural statistics districts get the full district view (decision 0018).
  Five are featured, with header links and first place (decision 0010): Blacklands first, then South Central,
  Edwards Plateau, East Texas North, East Texas South. District names follow Quick Stats. The featured list
  lives in `regions/tx.yaml` (`home:`). Key everything by county FIPS
  and keep state-specific settings in `regions/<state>.yaml`, so another state is config plus adapters, not a rewrite.
- **Zoom:** US (intro) → Texas → district (main working view) → county as a map stop with a card, not a
  standalone page.
- **Two views:** operator view (farm/ranch, plain language, "this week") is the default; a data view
  (tables, units, as-of dates, methods, source links, CSV/Parquet downloads) is a nice-to-have.

## Rules
- **NASS notice, verbatim, prominently, on every page with NASS data (footer) and on the About the data page:**
  "This product uses the NASS API but is not endorsed or certified by NASS." Never word anything to imply
  NASS (or any agency) endorses this site.
- Every figure shows its source and as-of date. Credit every publisher, plus their required notice
  (TFS logo on burn-ban graphics; "Rangeland Analysis Platform, USDA ARS"). Use only sources whose terms allow
  any use with no permission to ask for: no "non-commercial only" licenses, since the code is MIT and anyone
  may reuse it (decision 0014).
- Not an official source; where I differ from USDA, NOAA or the state, they are right. Keep that
  disclaimer and plain, non-alarmist language.
- District figures are **my own** aggregation (NASS stopped district estimates after 2019). Label them as
  such, say when they are a lower bound (published counties only), and label Cropland Data Layer figures
  as satellite-classified.
- NASS returns HTTP 400 "bad request - invalid query" for zero rows: treat as empty, not as an outage.
- One bad source hides only its own section; stale data (past its max age) hides rather than shows old
  numbers. Seasonal series (crop condition) show an "out of season" state, not last season's numbers.
- **Look:** colors only via `web/src/styles/tokens.css` and its tuned pairs (neutral palette, one blue
  accent; orange/green/amber/danger are data colors). Fonts: Inter Tight, Fraunces, JetBrains Mono. AA
  contrast in both themes; 44 px touch targets; respect reduced motion; never color alone. American English.
- **Voice:** site copy is first person singular ("I", "my own totals"), plain and non-alarmist.
- **Hosting:** static build, GitHub Pages, deployed by `.github/workflows/update.yml` (decision 0002).
  `site`/`base` in `web/astro.config.mjs` (`SITE_URL`/`SITE_BASE` override) drive canonical URLs and share
  images; the tests read the same variables.
- Never commit secrets, sample data or pipeline output.
- When you finish a feature: update `docs/ROADMAP.md`, `CHANGELOG.md` (user-visible changes), and add a
  decision record in `docs/decisions/` for anything a future reader would ask "why?" about.
- Follow the architecture maintenance rule in [AGENTS.md](AGENTS.md) when changing how the dashboard works.
