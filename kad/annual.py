"""Annual sources, run when due rather than on a schedule of their own (docs/decisions/0011).

Every regular run calls `run_due`. A source is due when it has no successful fetch within its
`refresh_days` (regions/tx.yaml). Missed cron runs don't matter: whichever run comes next catches up.

Adapters may be incremental (CDL, RAP: hundreds of county-years). They get a deadline; when they stop
early they return complete=False, nothing is recorded as a success, and the next run continues from what is
already in the store. A failure also records nothing, so it is retried next run.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from . import store
from .config import Region

log = logging.getLogger("kad")


def _adapters():
    from .adapters import cdl, nass_annual, nclimgrid, rap
    # key: (fetch fn returning (rows, complete), store source name)
    return {
        "census": nass_annual.census,
        "nass_county": nass_annual.county,
        "cdl": cdl.fetch,
        "rap": rap.fetch,
        "normals": nclimgrid.fetch,                   # one-time normals backfill; last, so it gets leftover budget
    }


def due(region: Region, key: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    last = store.read_fetch_log(region).get(key)
    days = region.source(key).get("refresh_days", 30)
    return last is None or now - datetime.fromisoformat(last) > timedelta(days=days)


def run_due(region: Region, *, budget_s: float = 480, force: bool = False, only: list[str] | None = None,
            try_=None) -> list[str]:
    """Run every due annual source within a shared time budget. Returns the keys that completed.
    Each source's outcome goes to the run report (kad/report.py)."""
    from .report import REPORT
    deadline = time.monotonic() + budget_s
    done = []
    for key, fn in _adapters().items():
        if only and key not in only:
            continue
        if not force and not due(region, key):
            REPORT.record(key, "not_due", f"last fetched {store.read_fetch_log(region).get(key, '')[:10]}")
            continue
        if time.monotonic() >= deadline:
            REPORT.record(key, "deferred", "due, but this run's time budget is spent; the next run continues")
            continue
        res = (try_ or (lambda label, f, *a, **kw: f(*a, **kw)))(key, fn, region, deadline=deadline)
        if res is None:
            continue                                  # failed: reported by try_, retried next run
        rows, complete, problems = res
        n = store.upsert_obs(region, key, rows) if rows is not None and not rows.empty else 0
        log.info("annual %s: %d rows%s", key, n, "" if complete else " (partial; continues next run)")
        if complete:
            store.log_fetch(region, key)
            done.append(key)
            REPORT.record(key, "ok", f"{n:,} rows" if rows is not None else "complete")
        else:
            REPORT.record(key, "partial", "; ".join(problems) or f"{n:,} rows this run; stopped at the time budget, continues next run")
    return done
