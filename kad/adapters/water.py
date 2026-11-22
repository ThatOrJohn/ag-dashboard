"""TWDB reservoir and recorder-well downloads and USGS daily discharge."""
from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

import numpy as np
import pandas as pd
import requests

from .. import http, store
from ..config import Region
from ..report import plain_error

USGS_DAILY = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items"
STREAM_HISTORY_START = date(1990, 12, 26)  # First complete seven-day mean ends on Jan. 1, 1991.
SOURCES = ("twdb_reservoirs", "twdb_groundwater", "usgs_streamflow")
TIMEOUT = (5, 20)


def _csv(client, url: str, columns: list[str]) -> pd.DataFrame:
    response = client.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text.lstrip("\ufeff")), comment="#", usecols=columns)


def reservoirs(client, site: dict) -> pd.DataFrame:
    frame = _csv(client, site["url"] + ".csv", ["date", "percent_full"])
    frame["value"] = pd.to_numeric(frame["percent_full"], errors="coerce")
    return frame.loc[frame["value"].between(0, 100), ["date", "value"]].assign(var="percent_full")


def groundwater(client, site: dict) -> pd.DataFrame:
    depth = "water_level(ft below land surface)"
    frame = _csv(client, site["url"] + ".csv", ["datetime", depth])
    frame["date"] = pd.to_datetime(frame["datetime"], errors="coerce", format="mixed").dt.normalize()
    frame["value"] = pd.to_numeric(frame[depth], errors="coerce")
    # TWDB's daily high water level corresponds to the shallowest recorded depth that day.
    daily = frame.loc[np.isfinite(frame["value"])].groupby("date", as_index=False)["value"].min()
    return daily.assign(var="depth_ft")


def streamflow(client, site: dict, start: date, end: date) -> pd.DataFrame:
    url = USGS_DAILY
    params = {
        "monitoring_location_id": site["id"], "parameter_code": "00060", "statistic_id": "00003",
        "datetime": f"{start}/{end}", "limit": 10000, "f": "json",
    }
    rows = []
    while url:
        response = client.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        page = response.json()
        features = page["features"]
        for feature in features:
            item = feature["properties"]
            if item["monitoring_location_id"] != site["id"] or item["unit_of_measure"] != "ft^3/s":
                raise ValueError("unexpected USGS site or discharge unit")
            rows.append({
                "date": item["time"], "discharge_cfs": item["value"],
                "unapproved": int(item.get("approval_status") != "Approved"),
            })
        url = next((link["href"] for link in page.get("links", []) if link["rel"] == "next"), None) if features else None
        params = None
    frame = pd.DataFrame(rows, columns=["date", "discharge_cfs", "unapproved"])
    if frame["date"].duplicated().any():
        raise ValueError("USGS returned multiple daily means for the same date")
    frame["discharge_cfs"] = pd.to_numeric(frame["discharge_cfs"], errors="coerce")
    frame = frame[np.isfinite(frame["discharge_cfs"]) & frame["discharge_cfs"].ge(0)]
    return frame.melt(id_vars="date", var_name="var")


def refresh(region: Region, source: str, *, force: bool = False) -> None:
    """Save available sites even if another site under the same publisher fails."""
    today = pd.Timestamp.now(tz=region.timezone).date()
    saved = store.read_obs(region, source) if source == "usgs_streamflow" else None
    frames, errors = [], []
    with http.session() as client:
        for site in region.source(source)["sites"]:
            try:
                if source == "twdb_reservoirs":
                    frame = reservoirs(client, site)
                elif source == "twdb_groundwater":
                    frame = groundwater(client, site)
                else:
                    dates = saved.loc[saved["geo"] == site["id"], "date"]
                    start = STREAM_HISTORY_START
                    if not force and not dates.empty:
                        start = min(today, dates.max().date()) - timedelta(days=400)
                        start = max(start, STREAM_HISTORY_START)
                    frame = streamflow(client, site, start, today)
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
                frame = frame.loc[frame["date"].notna() & frame["date"].le(pd.Timestamp(today))]
                if frame.empty:
                    raise ValueError("no usable observations")
                frames.append(frame.assign(geo=site["id"], source=source))
            except (requests.RequestException, ValueError, KeyError) as exc:
                errors.append(f"{site['id']}: {plain_error(exc)}")
    if frames:
        store.upsert_obs(region, source, pd.concat(frames, ignore_index=True))
    if errors:
        raise ValueError(" | ".join(errors))
    if frames:
        store.log_fetch(region, source)
