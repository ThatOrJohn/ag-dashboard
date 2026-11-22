"""NOAA nClimGrid-Daily county averages → 1991–2020 daily normals of high, low and rain (docs/decisions/0013).

NCEI publishes one CSV per variable per month with every US county's daily area average:
  https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/<YYYY>/<var>-<YYYYMM>-cty-scaled.csv
  row: cty,<NCEI state code><county>,<"TX: Travis County">,<year>,<month>,<VAR>,<31 daily values>
Values are °C (tmax, tmin) and mm (prcp); -999.99 pads days past the month's end. NCEI state codes are not
FIPS (Texas is 41, FIPS 48); the county part is the FIPS county code. Public domain (NOAA).

A one-time backfill of 360 months × 3 variables (~1 GB, kept to the region's rows). It runs as an annual
source (docs/decisions/0011) and is incremental: each finished month is added to running sums by calendar day
(data/<region>/normals/accum.npz), so a run that hits its deadline continues next run, and the store never
holds the 8 million raw daily rows. When all months are in, `kad/normals.py` writes the normals table.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from .. import normals, store
from ..config import Region
from ..http import session
from ..report import plain_error

log = logging.getLogger("kad")

BASE = "https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages"
VARS = ("tmax", "tmin", "prcp")          # order matches normals.VARS
FIRST, LAST = 1991, 2020
RECENT_VARS = {"tmax": "tmax_c", "tmin": "tmin_c", "prcp": "rain_mm"}   # same names the build uses


def url(var: str, year: int, month: int) -> str:
    return f"{BASE}/{year}/{var}-{year}{month:02d}-cty-scaled.csv"


def parse(text: str, ncei_state: str, state_fips: str) -> dict[str, list[float | None]]:
    """County FIPS → 31 daily values (None for padding or missing). Only the given state's rows."""
    out = {}
    prefix = f"cty,{ncei_state}"
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        parts = line.split(",")
        head, vals = parts[:-31], parts[-31:]           # the county name could hold a comma; values can't
        code = head[1].strip()
        if len(code) != 5:
            continue
        out[state_fips + code[2:]] = [None if float(v) <= -999 else float(v) for v in vals]
    return out


def _month(http, year: int, month: int, ncei_state: str, state_fips: str) -> list[dict]:
    res = []
    for var in VARS:
        r = http.get(url(var, year, month), timeout=120)
        r.raise_for_status()
        res.append(parse(r.text, ncei_state, state_fips))
    return res


def _state_code(region: Region) -> str:
    code = str(region.source("nclimgrid").get("ncei_state_code", ""))
    if not code:
        raise ValueError("regions file has no sources.nclimgrid.ncei_state_code")
    return code


def recent(region: Region, *, months: int = 3, today: pd.Timestamp | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Daily county averages: high, low and rain for this month and the `months - 1` before it, plus rain back
    to Jan. 1 for the season-to-date chart (of last year too, while NOAA's newest day is still in it).

    The site's observed weather (decision 0014). The newest month is preliminary (`-prelim.csv`) until NCEI
    finalizes it (`-scaled.csv`). Once a finalized rain month ages out of the recent window, reuse its saved
    rows. Return the finalized months alongside the observations so the caller can save them in that order.
    """
    ncei_state = _state_code(region)
    today = (today or pd.Timestamp.now()).normalize()
    now = today.to_period("M")
    jan = pd.Period(f"{(today - pd.Timedelta(days=14)).year}-01", "M")
    finalized = set(store.read_snapshot(region, "nclimgrid_final_rain") or [])
    tasks = [(var, now - k) for k in range(months) for var in RECENT_VARS]
    tasks += [("prcp", p) for p in pd.period_range(jan, now - months, freq="M") if str(p) not in finalized]
    http = session()

    def one(task):
        var, p = task
        for kind in ("scaled", "prelim"):
            r = http.get(url(var, p.year, p.month).replace("-scaled.csv", f"-{kind}.csv"), timeout=120)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            return task, kind, r.text
        return task, None, None                          # not out yet (first days of a month)

    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (var, p), kind, text in pool.map(one, tasks):
            if text is None:
                continue
            before = len(rows)
            for geo, vals in parse(text, ncei_state, region.state_fips).items():
                for d, v in enumerate(vals[:p.days_in_month], 1):
                    if v is not None:
                        rows.append({"geo": geo, "var": RECENT_VARS[var], "date": pd.Timestamp(p.year, p.month, d),
                                     "value": v, "source": "nclimgrid"})
            if var == "prcp" and kind == "scaled" and len(rows) > before:
                finalized.add(str(p))
    if not rows:
        raise RuntimeError("no nClimGrid county files found for the last months")
    return pd.DataFrame(rows), sorted(month for month in finalized if month >= str(jan))


def fetch(region: Region, *, deadline: float | None = None):
    """Returns (None, complete, problems). Progress lives in the normals accumulator, not the obs store."""
    ncei_state = _state_code(region)
    acc = normals.Accumulator.load(region)
    todo = [(y, m) for y in range(FIRST, LAST + 1) for m in range(1, 13) if f"{y}-{m:02d}" not in acc.months]
    http = session()
    problems: list[str] = []
    fails = 0
    added = 0
    saved = 0
    # A few months at a time in parallel: NCEI serves static files; keep it polite.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i in range(0, len(todo), 4):
            if deadline is not None and time.monotonic() >= deadline:
                break
            chunk = todo[i:i + 4]
            futs = {ym: pool.submit(_month, http, *ym, ncei_state, region.state_fips) for ym in chunk}
            for (y, m), f in futs.items():
                try:
                    acc.add_month(y, m, f.result())
                    added += 1
                    fails = 0
                except Exception as e:
                    fails += 1
                    problems.append(f"{y}-{m:02d}: {plain_error(e)}")
            if fails >= 3 and added == 0:
                problems.append("three months failed in a row with nothing fetched; stopping until next run")
                break
            if added - saved >= 12:
                acc.save(region)
                saved = added
    acc.save(region)
    complete = len(acc.months) == (LAST - FIRST + 1) * 12
    log.info("nclimgrid: %d months this run, %d of %d in", added, len(acc.months), (LAST - FIRST + 1) * 12)
    if complete:
        normals.write(region, acc)
    return None, complete, problems[:5]
