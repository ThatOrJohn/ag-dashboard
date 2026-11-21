"""NWS/NCEP Stage IV multi-sensor precipitation: provisional daily rain per county for the days NOAA's
county averages (nClimGrid, about a week behind) haven't reached yet. Decision 0017.

  GET https://water.noaa.gov/resources/downloads/precip/stageIV/YYYY/MM/DD/nws_precip_1day_YYYYMMDD_conus.nc
  → netCDF-4 (HDF5): `observation` (inches) on the 4 km HRAP grid (polar stereographic, sphere radius
    6,371,200 m, true at 60° N, centered on 105° W) with `x`/`y` cell centers in meters. 1121 × 881 cells.

A file dated D holds the 24 hours ending 12Z on D, radar adjusted to rain gauges by the River Forecast
Centers. Against nClimGrid, file D lines up with nClimGrid's day D (Sept.–Nov. 2026: district-day
correlation 0.96; one day either side, 0.26). Each day's file is up within about a day.

A county's value is the mean of the cells whose centers fall inside it (25 to 1,100 cells per Texas county).
Stage IV ran 9% to 34% wetter than nClimGrid by month over the same period, so the site calls these
estimates and never mixes them into the vs-normal figures. Public domain (NOAA/NWS).
"""
from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..config import REGIONS, Region
from ..http import session

BASE = "https://water.noaa.gov/resources/downloads/precip/stageIV"
SOURCE = "stage4"
DAYS = 10                       # files to look at, ending today; covers nClimGrid's lag with room to spare
WORKERS = 4
R, LON0, LAT_TS = 6371200.0, -105.0, 60.0


def url(day: date) -> str:
    return f"{BASE}/{day:%Y/%m/%d}/nws_precip_1day_{day:%Y%m%d}_conus.nc"


def project(lon, lat):
    """Lon/lat (degrees) → HRAP polar stereographic x, y (meters)."""
    lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    rho = R * (1 + np.sin(np.radians(LAT_TS))) * np.cos(lat) / (1 + np.sin(lat))
    return rho * np.sin(lon - np.radians(LON0)), -rho * np.cos(lon - np.radians(LON0))


def _inside(px: np.ndarray, py: np.ndarray, rx: np.ndarray, ry: np.ndarray) -> np.ndarray:
    """Even-odd point-in-ring test, vectorized over points."""
    c = np.zeros(px.shape, bool)
    for a, b, a2, b2 in zip(rx, ry, np.roll(rx, -1), np.roll(ry, -1)):
        if b == b2:
            continue
        m = (b > py) != (b2 > py)
        c ^= m & (px < (a2 - a) * (py - b) / (b2 - b) + a)
    return c


def county_cells(geoms: dict[str, dict], x: np.ndarray, y: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """County FIPS → (row, col) indices of the grid cells whose centers fall inside the county."""
    out = {}
    for fips, g in geoms.items():
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        rows_all, cols_all = [], []
        for poly in polys:
            keep = None
            for k, ring in enumerate(poly):
                ring = np.asarray(ring, float)
                rx, ry = project(ring[:, 0], ring[:, 1])
                if k == 0:
                    ci = np.nonzero((x >= rx.min()) & (x <= rx.max()))[0]
                    ri = np.nonzero((y >= ry.min()) & (y <= ry.max()))[0]
                    RR, CC = np.meshgrid(ri, ci, indexing="ij")
                    RR, CC = RR.ravel(), CC.ravel()
                    keep = _inside(x[CC], y[RR], rx, ry)
                else:                                   # a hole
                    keep &= ~_inside(x[CC], y[RR], rx, ry)
            rows_all.append(RR[keep])
            cols_all.append(CC[keep])
        out[fips] = (np.concatenate(rows_all), np.concatenate(cols_all))
    return out


def read_grid(content: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import h5py
    with h5py.File(io.BytesIO(content), "r") as f:
        obs = f["observation"][:].astype(float)
        x, y = f["x"][:], f["y"][:]
        fill = f["observation"].attrs.get("_FillValue")
    bad = obs < -1e30
    if fill is not None:
        bad |= obs == float(np.asarray(fill).ravel()[0])
    obs[bad | (obs < 0)] = np.nan
    return x, y, obs


def county_means(day: date, obs: np.ndarray, cells: dict) -> list[dict]:
    rows = []
    for fips, (ri, ci) in cells.items():
        if len(ri) == 0:
            continue
        v = obs[ri, ci]
        if np.isnan(v).mean() > 0.5:                   # mostly missing: leave the day out for this county
            continue
        rows.append({"geo": fips, "var": "rain_mm", "date": pd.Timestamp(day),
                     "value": round(float(np.nanmean(v)) * 25.4, 2), "source": SOURCE})
    return rows


def recent(region: Region, *, today: date | None = None) -> pd.DataFrame:
    """The last DAYS days' files, every county in the region. A day not posted yet (404) is skipped."""
    today = today or date.today()
    http = session()
    geoms = {f["id"]: f["geometry"] for f in json.loads((REGIONS / f"{region.id}-counties.geojson").read_text())["features"]}

    def get(day):
        r = http.get(url(day), timeout=120)
        if r.status_code == 404:
            return day, None
        r.raise_for_status()
        return day, r.content

    days = [today - timedelta(days=k) for k in range(DAYS)]
    with ThreadPoolExecutor(WORKERS) as pool:
        files = [(d, c) for d, c in pool.map(get, days) if c is not None]
    if not files:
        raise RuntimeError(f"no Stage IV files for the last {DAYS} days")
    rows, cells = [], None
    for day, content in sorted(files):
        x, y, obs = read_grid(content)
        if cells is None:
            cells = county_cells(geoms, x, y)
        rows += county_means(day, obs, cells)
    return pd.DataFrame(rows)
