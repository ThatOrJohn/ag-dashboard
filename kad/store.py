"""Storage: one long Parquet table per source, so any tool (DuckDB, pandas, notebooks) can read it.

  data/<region>/obs/<source>.parquet       geo, var, date, value, source
  data/<region>/snapshots/<name>.json      text and structured pulls (AMS narratives, burn-ban snapshot)
  data/<region>/fetch_log.json             last successful fetch per source (for the site's as-of lines)

`geo` is a county FIPS ("48491"), the state FIPS ("48"), a market id ("ams:1955"), or a district slug for
figures we aggregate ourselves. `date` is the figure's own date (week ending, map date, observation day).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .config import Region

OBS_COLS = ["geo", "var", "date", "value", "source"]


def _obs_path(region: Region, source: str):
    return region.data_dir / "obs" / f"{source}.parquet"


def read_obs(region: Region, source: str) -> pd.DataFrame:
    p = _obs_path(region, source)
    if not p.exists():
        return pd.DataFrame(columns=OBS_COLS)
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    return df


def upsert_obs(region: Region, source: str, new: pd.DataFrame) -> int:
    """Insert or replace rows by (geo, var, date). Newer wins: sources revise."""
    if new is None or new.empty:
        return 0
    new = new[OBS_COLS].copy()
    new["date"] = pd.to_datetime(new["date"]).dt.normalize()
    new = new.dropna(subset=["value"])
    old = read_obs(region, source)
    df = pd.concat([old, new], ignore_index=True) if not old.empty else new
    df = df.drop_duplicates(["geo", "var", "date"], keep="last").sort_values(["geo", "var", "date"])
    p = _obs_path(region, source)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return len(new)


def write_snapshot(region: Region, name: str, obj) -> None:
    p = region.data_dir / "snapshots" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, default=str))


def read_snapshot(region: Region, name: str):
    p = region.data_dir / "snapshots" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def log_fetch(region: Region, source: str) -> None:
    p = region.data_dir / "fetch_log.json"
    log = json.loads(p.read_text()) if p.exists() else {}
    log[source] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(log, indent=1, sort_keys=True))


def read_fetch_log(region: Region) -> dict:
    p = region.data_dir / "fetch_log.json"
    return json.loads(p.read_text()) if p.exists() else {}
