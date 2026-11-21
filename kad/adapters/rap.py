"""Rangeland Analysis Platform (RAP), USDA ARS / University of Montana: per-county means over rangeland.

POST a GeoJSON Feature (county outline from regions/tx-counties.geojson, `mask: true` = rangeland only):
  coverV3            annual % cover, 1986 → last year: AFG annual forbs & grasses, PFG perennial forbs &
                     grasses, SHR shrubs, TRE trees, LTR litter, BGR bare ground
  production16dayV3  herbaceous production per 16-day period, lb/acre: AFG, PFG, HER (= AFG + PFG)
-99 marks missing (future periods, early gaps) and is dropped. Credit: "Rangeland Analysis Platform, USDA ARS".

Home-district counties only. Incremental: each county is refetched when its last fetch is older than
`refresh_days` (production updates every 16 days); a run stops at its deadline and the next continues.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pandas as pd

from .. import store
from ..config import REGIONS, Region
from ..http import session
from ..report import plain_error

BASE = "https://us-central1-rap-data-365417.cloudfunctions.net"
SOURCE = "rap"
COVER = ("AFG", "PFG", "SHR", "TRE", "LTR", "BGR")
WORKERS = 4


def shapes(region: Region) -> dict[str, dict]:
    fc = json.loads((REGIONS / f"{region.id}-counties.geojson").read_text())
    return {f["id"]: f["geometry"] for f in fc["features"]}


def _post(http, endpoint: str, geom: dict) -> list[list]:
    r = http.post(f"{BASE}/{endpoint}", json={"type": "Feature", "properties": {"mask": True, "year": None},
                                              "geometry": geom}, timeout=300)
    r.raise_for_status()
    props = r.json()["properties"]
    return next(v for v in props.values() if isinstance(v, list))


def parse_cover(fips: str, table: list[list]) -> list[dict]:
    head = table[0]
    out = []
    for row in table[1:]:
        rec = dict(zip(head, row))
        for k in COVER:
            v = rec.get(k)
            if v is not None and v != -99:
                out.append({"geo": fips, "var": f"cover:{k.lower()}", "date": pd.Timestamp(int(rec["year"]), 1, 1),
                            "value": round(float(v), 2), "source": SOURCE})
    return out


def parse_production(fips: str, table: list[list]) -> list[dict]:
    head = table[0]
    out = []
    for row in table[1:]:
        rec = dict(zip(head, row))
        v = rec.get("HER")
        if v is None or v == -99 or rec.get("doy") == -99:
            continue
        out.append({"geo": fips, "var": "prod:her_lb_ac", "date": pd.Timestamp(rec["date"]),
                    "value": round(float(v), 1), "source": SOURCE})
    return out


def fetch(region: Region, *, deadline: float | None = None):
    """Returns (rows, complete, problems). Per-county fetch times live in the `rap_fetched` snapshot."""
    days = region.source("rap").get("refresh_days", 16)
    fetched: dict = store.read_snapshot(region, "rap_fetched") or {}
    now = datetime.now(timezone.utc)
    geoms = shapes(region)
    todo = [c.fips for d in region.home_districts for c in region.counties_in(d["slug"])
            if c.fips not in fetched or now - datetime.fromisoformat(fetched[c.fips]) > timedelta(days=days)]
    http = session()
    rows: list[dict] = []
    problems: list[str] = []
    done: set[str] = set()

    def one(fips: str):
        return parse_cover(fips, _post(http, "coverV3", geoms[fips])) + \
            parse_production(fips, _post(http, "production16dayV3", geoms[fips]))

    with ThreadPoolExecutor(WORKERS) as pool:
        for i in range(0, len(todo), WORKERS):
            if deadline and time.monotonic() >= deadline:
                break
            batch = todo[i:i + WORKERS]
            for fips, fut in [(f, pool.submit(one, f)) for f in batch]:
                try:
                    rows += fut.result()
                    fetched[fips] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    done.add(fips)
                except Exception as e:  # one county failing doesn't lose the others
                    problems.append(f"{fips}: {plain_error(e)}")
            if len(problems) >= 3 and not done:
                raise RuntimeError(f"RAP looks down: {problems[0]}")
    store.write_snapshot(region, "rap_fetched", fetched)
    complete = len(done) == len(todo)
    if problems:
        problems = [f"{len(problems)} of {len(todo)} counties failed, e.g. {problems[0]}"]
    return pd.DataFrame(rows), complete, problems
