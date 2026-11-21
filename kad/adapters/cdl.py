"""USDA NASS Cropland Data Layer via CroplandCROS: satellite-classified acres by land-cover class, per county-year.

CropScape's GetCDLStat (the original plan) now answers 503 and its site redirects to a sign-in, so this uses
the public geoprocessing service behind NASS/ARS CroplandCROS (https://croplandcros.scinet.usda.gov/),
decision 0016:

  POST .../Calculate_Statistics_with_HI/GPServer/Calculate%20Statistics/submitJob
       AOI = the county outline (Esri JSON, WGS 84), Dataset_Name = CDLS_WM, Year = YYYY
  → a job; when it succeeds, results/Statistics is {"histograms": [{"counts": [...]}]}: pixels per class code.
  Class names come from the CDL image service's raster attribute table (CDL_WM/ImageServer/rasterAttributeTable).

Pixel counts become acres by share, not pixel size (the mosaic is Web Mercator, so a pixel's ground area depends
on latitude): each class's share of the county's land pixels (everything but background and water) times the
county's Census land area. Water classes get acres on the same scale.

Home-district counties, `first_year` to last year. Incremental: only county-years missing from the store are
fetched, four jobs at a time; a run stops at its deadline and the next continues. Public domain (USDA NASS).
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from .. import store
from ..config import Region
from ..http import session
from ..report import plain_error
from .rap import shapes

GP = "https://pdi.scinet.usda.gov/geoprocessing/rest/services/Calculate_Statistics_with_HI/GPServer/Calculate%20Statistics"
RAT = "https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer/rasterAttributeTable"
SOURCE = "cdl"
DATASET = "CDLS_WM"
WATER = {0, 83, 111}            # background, water, open water: not land
WORKERS = 4
JOB_TIMEOUT = 180               # seconds to wait for one statistics job


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def class_names(http) -> dict[int, str]:
    """CDL class code → slug of its NASS class name ("Grassland/Pasture" → grassland_pasture)."""
    r = http.get(RAT, params={"f": "json"}, timeout=60)
    r.raise_for_status()
    out = {}
    for f in r.json().get("features", []):
        a = f["attributes"]
        if a.get("Class_Names"):
            out[int(a["Value"])] = slug(a["Class_Names"])
    if len(out) < 50:
        raise ValueError(f"CDL class table looks wrong ({len(out)} classes)")
    return out


def _signed_area(ring: list) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def esri_rings(geom: dict) -> list:
    """GeoJSON Polygon/MultiPolygon → Esri rings (outer clockwise, holes counterclockwise)."""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    rings = []
    for poly in polys:
        for k, ring in enumerate(poly):
            clockwise = _signed_area(ring) < 0
            rings.append(ring if clockwise == (k == 0) else ring[::-1])
    return rings


def acres_from_counts(fips: str, year: int, counts: list[float], names: dict[int, str], land_acres: float) -> list[dict]:
    land = sum(c for code, c in enumerate(counts) if code not in WATER)
    if land <= 0:
        raise ValueError(f"CDL statistics for {fips} {year} had no land pixels")
    rows = []
    for code, c in enumerate(counts):
        if c and code != 0:
            rows.append({"geo": fips, "var": f"cdl:{names.get(code, f'class_{code}')}", "date": pd.Timestamp(year, 1, 1),
                         "value": round(c / land * land_acres, 1), "source": SOURCE})
    return rows


def county_year(http, fips: str, year: int, geom: dict, names: dict[int, str], land_acres: float) -> list[dict]:
    aoi = {"geometryType": "esriGeometryPolygon", "spatialReference": {"wkid": 4326},
           "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID"}],
           "features": [{"geometry": {"rings": esri_rings(geom), "spatialReference": {"wkid": 4326}},
                         "attributes": {"OBJECTID": 1}}]}
    r = http.post(f"{GP}/submitJob", data={"f": "json", "AOI": json.dumps(aoi), "Dataset_Name": DATASET,
                                           "Year": str(year), "Cache_Key": ""}, timeout=120)
    r.raise_for_status()
    job = r.json().get("jobId")
    if not job:
        raise ValueError(f"CroplandCROS gave no job for {fips} {year}: {r.text[:120]}")
    t0 = time.monotonic()
    while True:
        s = http.get(f"{GP}/jobs/{job}", params={"f": "json"}, timeout=60).json()
        status = s.get("jobStatus")
        if status == "esriJobSucceeded":
            break
        if status in ("esriJobFailed", "esriJobCancelled", "esriJobTimedOut"):
            msg = next((m.get("description", "") for m in reversed(s.get("messages", [])) if m.get("type") == "esriJobMessageTypeError"), "")
            raise RuntimeError(f"CroplandCROS job {status[7:].lower()} for {fips} {year}: {msg[:120]}")
        if time.monotonic() - t0 > JOB_TIMEOUT:
            raise TimeoutError(f"CroplandCROS job still running after {JOB_TIMEOUT} s for {fips} {year}")
        time.sleep(2)
    out = http.get(f"{GP}/jobs/{job}/results/Statistics", params={"f": "json"}, timeout=60).json()
    hist = (out.get("value") or {}).get("histograms") or []
    if not hist or not any(hist[0].get("counts", [])):
        raise ValueError(f"CroplandCROS returned no pixels for {fips} {year}")
    return acres_from_counts(fips, year, hist[0]["counts"], names, land_acres)


def fetch(region: Region, *, deadline: float | None = None):
    """Returns (rows, complete, problems)."""
    first = region.source("cdl").get("first_year", 2021)
    last = date.today().year - 1            # a year's CDL comes out early the next year; it may not exist yet
    have = store.read_obs(region, SOURCE)
    have_keys = set(zip(have["geo"], have["date"].dt.year)) if not have.empty else set()
    counties = [c for d in region.home_districts for c in region.counties_in(d["slug"])]
    todo = [(c, y) for y in range(last, first - 1, -1) for c in counties if (c.fips, y) not in have_keys]
    if not todo:
        return pd.DataFrame(), True, []
    http = session()
    names = class_names(http)
    geoms = shapes(region)
    rows: list[dict] = []
    failed: list[tuple[int, str]] = []

    def one(item):
        c, y = item
        try:
            return y, county_year(http, c.fips, y, geoms[c.fips], names, c.land_sqmi * 640), None
        except Exception as e:
            return y, [], f"{c.fips} {y}: {plain_error(e)}"

    stopped = False
    with ThreadPoolExecutor(WORKERS) as pool:
        for i in range(0, len(todo), WORKERS):
            if deadline is not None and time.monotonic() >= deadline:
                stopped = True
                break
            for y, part, err in pool.map(one, todo[i:i + WORKERS]):
                rows += part
                if err:
                    failed.append((y, err))
            if len(failed) >= 3 * WORKERS and not rows:
                raise RuntimeError(f"CroplandCROS looks down: {failed[0][1]}")
    # The newest year failing everywhere just means it isn't released yet.
    newest_missing = bool(failed) and all(y == last for y, _ in failed) and not any(r["date"].year == last for r in rows)
    real = [e for y, e in failed if not (newest_missing and y == last)]
    complete = not stopped and not real
    problems = [f"{len(real)} of {len(todo)} county-years failed, e.g. {real[0]}"] if real else []
    if stopped:
        done = len({(r["geo"], r["date"]) for r in rows})
        problems.append(f"{done} county-years this run, {len(todo) - done} to go; continues next run")
    return pd.DataFrame(rows), complete, problems
