"""USDA NASS Quick Stats API.

Gotchas (docs/feasibility.md):
- Zero rows comes back as HTTP 400 "bad request - invalid query". That is empty, not an outage.
- Values are strings with thousands separators and codes like "(D)" (withheld) or "(Z)" (less than half the unit).
- Progress, condition and pasture condition are state-level only. District estimates ended in 2019.
"""
from __future__ import annotations

import os
import re
from datetime import date

import pandas as pd

from .. import store
from ..config import Region
from ..http import session

API = "https://quickstats.nass.usda.gov/api/api_GET/"
SUPPRESSED = {"(D)", "(Z)", "(NA)", "(X)", "(S)", "(H)", "(L)"}
SOURCE = "nass"


class NassError(RuntimeError):
    pass


def query(params: dict, *, http=None) -> list[dict]:
    key = os.environ.get("NASS_QUICK_STATS_API_KEY")
    if not key:
        raise NassError("NASS_QUICK_STATS_API_KEY is not set")
    r = (http or session()).get(API, params={"key": key, "format": "JSON", **params}, timeout=120)
    if r.status_code == 400 and "invalid query" in r.text.lower():
        return []   # NASS's way of saying "no rows"
    if r.status_code != 200:
        raise NassError(f"HTTP {r.status_code}: {r.text[:200].replace(key, '<key>')}")
    return r.json().get("data", [])


def parse_value(v: str | None) -> float | None:
    """'106,000' → 106000.0; '(D)' and blanks → None."""
    if v is None:
        return None
    v = v.strip()
    if not v or v in SUPPRESSED:
        return None
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return None


_UNIT = re.compile(r"MEASURED IN PCT (.+)$")


def _stat_key(short_desc: str) -> str | None:
    """'CORN - PROGRESS, MEASURED IN PCT PLANTED' → 'planted'; 'CORN - CONDITION, MEASURED IN PCT GOOD' → 'good'."""
    m = _UNIT.search(short_desc)
    return re.sub(r"[^a-z0-9]+", "_", m.group(1).lower()).strip("_") if m else None


def weekly(region: Region, *, years_back: int | None = None, today: date | None = None) -> pd.DataFrame:
    """Seed five comparison years, then refresh the current and previous years and catch up after gaps."""
    today = today or date.today()
    first_year = today.year - (5 if years_back is None else years_back)
    if years_back is None:
        saved = store.read_obs(region, SOURCE)
        if not saved.empty:
            first_year = max(first_year, min(today.year - 1, saved["date"].max().year))
    cfg = region.source("nass")
    http = session()
    out = []
    for item in cfg.get("weekly", []):
        rows = query({"source_desc": "SURVEY", "state_alpha": region.extras.get("state_alpha", "TX"),
                      "agg_level_desc": "STATE", "commodity_desc": item["commodity"],
                      "statisticcat_desc": item["stat"], "freq_desc": "WEEKLY",
                      "year__GE": first_year}, http=http)
        for r in rows:
            if item.get("class") and r.get("class_desc") != item["class"]:
                continue
            key = _stat_key(r.get("short_desc", ""))
            val = parse_value(r.get("Value"))
            if key is None or val is None or not r.get("week_ending"):
                continue
            out.append({"geo": region.state_fips, "var": f"{item['id']}:{key}",
                        "date": pd.Timestamp(r["week_ending"]), "value": val, "source": SOURCE})
    return pd.DataFrame(out)
