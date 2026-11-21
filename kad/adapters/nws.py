"""National Weather Service API: 7-day forecast high, low and rain at each home-district county's center.

  GET https://api.weather.gov/points/{lat},{lon}      → properties.forecastGridData (cached: it doesn't change)
  GET https://api.weather.gov/gridpoints/{wfo}/{x},{y} → maxTemperature, minTemperature (°C) and
                                                         quantitativePrecipitation (mm), as ISO 8601 intervals
                                                         ("2026-11-21T13:00:00+00:00/PT13H")
No key; NWS asks for a User-Agent that identifies the application (kad/http.py). Public domain.

Days are local (region timezone). A high belongs to the day its daytime period starts; a low to the night
that starts that evening, the way NWS pairs "Thursday" with "Thursday night". Rain sums the 6-hour amounts by
the local day each interval starts. Home districts only: the forecast feeds their strips and headlines.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .. import store
from ..config import Region
from ..http import session

API = "https://api.weather.gov"
SOURCE = "nws"
VARS = {"maxTemperature": "tmax_c", "minTemperature": "tmin_c", "quantitativePrecipitation": "rain_mm"}
WORKERS = 4


def _http():
    h = session()
    h.headers["Accept"] = "application/geo+json"
    return h


def grid_urls(region: Region, http, counties) -> dict[str, str]:
    """County FIPS → forecastGridData URL, from the snapshot or looked up once and saved."""
    cache = store.read_snapshot(region, "nws_points") or {}
    missing = [c for c in counties if c.fips not in cache]

    def look(c):
        r = http.get(f"{API}/points/{c.lat:.4f},{c.lon:.4f}", timeout=60)
        r.raise_for_status()
        return c.fips, r.json()["properties"]["forecastGridData"]

    if missing:
        with ThreadPoolExecutor(WORKERS) as pool:
            for fips, url in pool.map(look, missing):
                cache[fips] = url
        store.write_snapshot(region, "nws_points", cache)
    return {c.fips: cache[c.fips] for c in counties}


def parse(geo: str, props: dict, tz: str) -> list[dict]:
    rows = []
    for key, var in VARS.items():
        for v in props.get(key, {}).get("values", []):
            if v.get("value") is None:
                continue
            start = pd.Timestamp(v["validTime"].split("/")[0]).tz_convert(tz)
            rows.append({"geo": geo, "var": var, "date": start.tz_localize(None).normalize(),
                         "value": float(v["value"]), "source": SOURCE})
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    # Rain: 6-hour amounts summed per day. Highs and lows: one per day already; keep the first if doubled.
    rain = df[df["var"] == "rain_mm"].groupby(["geo", "var", "date", "source"], as_index=False)["value"].sum()
    temps = df[df["var"] != "rain_mm"].drop_duplicates(["geo", "var", "date"])
    return pd.concat([temps, rain]).to_dict("records")


def fetch(region: Region, *, counties=None) -> pd.DataFrame:
    counties = counties if counties is not None else [c for d in region.home_districts for c in region.counties_in(d["slug"])]
    http = _http()
    urls = grid_urls(region, http, counties)
    today = pd.Timestamp.now(tz=region.timezone).tz_localize(None).normalize()
    failed: list[str] = []

    def one(item):
        fips, url = item
        try:
            r = http.get(url, timeout=60)
            r.raise_for_status()
            return parse(fips, r.json()["properties"], region.timezone)
        except Exception:
            failed.append(fips)
            return []

    with ThreadPoolExecutor(WORKERS) as pool:
        rows = [row for part in pool.map(one, urls.items()) for row in part]
    if len(failed) > len(counties) / 2:
        raise RuntimeError(f"NWS forecast failed for {len(failed)} of {len(counties)} counties")
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[(df["date"] >= today) & (df["date"] < today + pd.Timedelta(days=7))].reset_index(drop=True)
