"""Annual sources, run when due rather than on a schedule of their own (docs/decisions/0011).

Every regular run calls `run_due`. A source is due when it has no successful fetch within its
`refresh_days` (regions/tx.yaml). Missed cron runs don't matter: whichever run comes next catches up.

Adapters may be incremental (CDL, RAP: hundreds of county-years). They get a deadline; when they stop
early they return complete=False, nothing is recorded as a success, and the next run continues from what is
already in the store. A failure also records nothing, so it is retried next run.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from . import store
from .config import Region, load_region
from .report import REPORT, plain_error

log = logging.getLogger("kad")
STOP_GRACE_S = 10


def _adapters():
    from .adapters import cdl, nass_annual, nclimgrid, rap
    return {
        "census": nass_annual.census,
        "nass_county": nass_annual.county,
        "cdl": cdl.fetch,
        "rap": rap.fetch,
        "normals": nclimgrid.fetch,
    }


def pending(region: Region, key: str) -> bool:
    """Per-county sources with counties not yet covered, e.g. after more districts get the full view. These
    run now and continue each run until covered, rather than waiting out refresh_days."""
    fips = {c.fips for c in region.counties}
    if key == "rap":
        return bool(fips - set(store.read_snapshot(region, "rap_fetched") or {}))
    if key == "cdl":
        have = store.read_obs(region, "cdl")
        if have.empty:
            return True
        # Every year some county already has (an unreleased newest year is in no county, so it isn't owed).
        got = set(zip(have["geo"], have["date"].dt.year))
        return any((f, y) not in got for y in {y for _, y in got} for f in fips)
    return False


def due(region: Region, key: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    last = store.read_fetch_log(region).get(key)
    days = region.source(key).get("refresh_days", 30)
    return last is None or now - datetime.fromisoformat(last) > timedelta(days=days) or pending(region, key)


def _refresh(region: Region, key: str, fn, deadline: float) -> tuple[bool, str]:
    count = 0

    def checkpoint(rows):
        nonlocal count
        count += store.upsert_obs(region, key, rows)

    kwargs = {"checkpoint": checkpoint} if key in {"cdl", "rap"} else {}
    rows, complete, problems = fn(region, deadline=deadline, **kwargs)
    checkpoint(rows)
    log.info("annual %s: %d rows%s", key, count, "" if complete else " (partial; continues next run)")
    if complete:
        store.log_fetch(region, key)
        return True, f"{count:,} rows" if rows is not None else "complete"
    return False, "; ".join(problems) or f"{count:,} rows this run; stopped at the time budget, continues next run"


def _isolated_refresh(region: Region, key: str, deadline: float) -> tuple[bool, str]:
    # Stopping the process also stops its worker threads and any HTTP retries still in flight.
    try:
        result = subprocess.run(
            [sys.executable, "-m", "kad.annual", region.id, key, str(deadline)],
            stdout=subprocess.PIPE, text=True, check=True,
            env={**os.environ, "KAD_DATA_DIR": str(region.data_dir.parent.resolve())},
            timeout=max(0, deadline - time.monotonic()) + STOP_GRACE_S,
        )
    except subprocess.TimeoutExpired:
        return False, "exceeded its time limit; the next run continues from saved checkpoints"
    outcome = json.loads(result.stdout)
    if "error" in outcome:
        raise RuntimeError(outcome["error"])
    return outcome["complete"], outcome["note"]


def run_due(region: Region, *, budget_s: float = 480, force: bool = False, only: list[str] | None = None,
            try_=None, isolate: bool = False) -> list[str]:
    """Reserve a share for every due source and pass unused time to later sources."""
    pending_sources = []
    for key, fn in _adapters().items():
        if only and key not in only:
            continue
        if not force and not due(region, key):
            REPORT.record(key, "not_due", f"last fetched {store.read_fetch_log(region).get(key, '')[:10]}")
            continue
        pending_sources.append((key, fn))
    done = []
    remaining = budget_s
    for position, (key, fn) in enumerate(pending_sources):
        if remaining <= 0:
            REPORT.record(key, "deferred", "due, but this run's time budget is spent; the next run continues")
            continue
        share = remaining / (len(pending_sources) - position)
        started = time.monotonic()
        deadline = started + share
        execute = _isolated_refresh if isolate else _refresh
        args = (region, key, deadline) if isolate else (region, key, fn, deadline)
        res = try_(key, execute, *args) if try_ else execute(*args)
        remaining -= min(share, time.monotonic() - started)
        if res is None:
            continue
        complete, note = res
        REPORT.record(key, "ok" if complete else "partial", note)
        if complete:
            done.append(key)
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    region_id, source, deadline_arg = sys.argv[1:]
    try:
        complete, note = _refresh(load_region(region_id), source, _adapters()[source], float(deadline_arg))
        print(json.dumps({"complete": complete, "note": note}))
    except Exception as exc:
        print(json.dumps({"error": plain_error(exc)}))
