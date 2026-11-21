# 0007: NASS's winter break is "between reports", not stale

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
Texas weekly Crop Progress pauses from about Nov. 30 until January (first report Jan. 3 to Jan. 23 across
2021–2026). With a 10-day max age, every December the crop sections would hide as broken and the health job
would fail daily.

## Decision
`quiet_months: [12, 1]` on the NASS source. In those months an old report makes the cards "out of season"
(last report date, no numbers) and the source reads "between reports"; the health check passes.

## Why
CLAUDE.md: seasonal series show an out-of-season state, and a quiet off-season must not look like an outage.

## Consequences
A real NASS outage in December or January won't fail the health check. That's acceptable: there's nothing
to show then anyway. A failed fetch still appears in the run log as a failed source.
