# 0011: Annual sources run when due from every regular run; every run reports per source

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
Census of Agriculture, NASS county estimates, the Cropland Data Layer and the Rangeland Analysis Platform
change yearly (RAP production every 16 days). GitHub Actions often skips or delays cron runs, so a separate
monthly schedule could silently miss a refresh. CDL and RAP cover hundreds of county-years, more than one
run should spend. The owner wants a failed run to show at a glance which sources failed.

## Decision
- Every regular run (twice daily, on push) calls `kad annual` logic: a source is **due** when it has no
  successful fetch within `refresh_days` (regions/tx.yaml: Census 90, NASS county 30, CDL 30, RAP 16).
  Not due = skipped in milliseconds. Whichever run comes next catches up after missed crons.
- The runner divides `--budget` (8 minutes by default) among due sources and passes unused time to later
  sources. The CLI stops a source process 10 seconds after its deadline if a request is still running.
  CDL, RAP, and normals save progress while fetching. Only a complete refresh updates the source's
  success timestamp, so a later run continues from the checkpoint after a failure or timeout.
- Three consecutive failures with nothing fetched means the service is down: stop and report, instead of
  spending the budget on retries.
- Each run ends with a per-source report (kad/report.py): a table in the run summary (ok, failed, stale,
  partial, not due, deferred, no data yet, between reports), `::error` / `::warning` annotations on the
  run page, and network errors translated into plain words ("service unavailable (HTTP 503…)").
  The health job adds one-line verdicts for the update job, deploy, and core data freshness.

## Why
Due-based catch-up is robust to missed schedules without a scheduler. Budgets keep runs short. A table
plus annotations answers "what broke?" without opening logs.

## Consequences
- The first CI run after this lands fetches all annual sources; RAP (~6 minutes for 117 counties) may
  finish on the following run.
- Quick Stats must be asked for `domain_desc=TOTAL`: unfiltered, one Census series is 15 MB.
- (Superseded by [0016](0016-cdl-via-croplandcros.md): CDL now comes from CroplandCROS.) CDL was written while CropScape returned 503 all day (2026-11-20). Its parser follows the feasibility
  notes and a unit test of that format, **not yet a live response**. When CropScape is back, the report
  will show CDL as ok, partial or failed; if it fails on parsing, fix `lenient_json` / `parse_stats`.
- Annual failures are warnings or errors in the report but don't fail the health job; only stale core
  weekly data, a failed update job or a failed deploy do.
