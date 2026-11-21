"""NASS annual county figures: survey estimates (acres, yield, cattle) and the Census of Agriculture.

Survey county estimates are patchy (docs/feasibility.md): unpublished counties are simply missing, or
lumped into "OTHER COUNTIES" (county code 998), which we drop. A district total built from these is a lower
bound, and the site says so. Census of Agriculture covers every county (few values withheld), every 5 years.

Each figure is stored with date = Jan 1 of its year; `var` names are below.
"""
from __future__ import annotations

import time

import pandas as pd

from ..config import Region
from ..http import session
from .nass import parse_value, query

COUNTY_SERIES = {
    "corn:planted_acres": "CORN - ACRES PLANTED",
    "corn:yield_bu_ac": "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
    "sorghum:planted_acres": "SORGHUM - ACRES PLANTED",
    "sorghum:yield_bu_ac": "SORGHUM, GRAIN - YIELD, MEASURED IN BU / ACRE",
    "cotton:planted_acres": "COTTON, UPLAND - ACRES PLANTED",
    "cotton:yield_lb_ac": "COTTON, UPLAND - YIELD, MEASURED IN LB / ACRE",
    "wheat:planted_acres": "WHEAT, WINTER - ACRES PLANTED",
    "wheat:yield_bu_ac": "WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE",
    "cattle:all": "CATTLE, INCL CALVES - INVENTORY",
    "cattle:beef_cows": "CATTLE, COWS, BEEF - INVENTORY",
}

CENSUS_SERIES = {
    "farms": "FARM OPERATIONS - NUMBER OF OPERATIONS",
    "land_in_farms_acres": "FARM OPERATIONS - ACRES OPERATED",
    "avg_farm_acres": "FARM OPERATIONS - AREA OPERATED, MEASURED IN ACRES / OPERATION",
    "median_farm_acres": "FARM OPERATIONS - AREA OPERATED, MEASURED IN ACRES / OPERATION, MEDIAN",
    "cropland_acres": "AG LAND, CROPLAND - ACRES",
    "pasture_acres": "AG LAND, PASTURELAND - ACRES",
    "sales_usd": "COMMODITY TOTALS - SALES, MEASURED IN $",
    "land_value_usd_ac": "AG LAND, INCL BUILDINGS - ASSET VALUE, MEASURED IN $ / ACRE",
    "producers": "PRODUCERS, (ALL) - NUMBER OF PRODUCERS",
    "cattle": "CATTLE, INCL CALVES - INVENTORY",
    "goats": "GOATS - INVENTORY",
    "sheep": "SHEEP, INCL LAMBS - INVENTORY",
}


def parse_rows(rows: list[dict], var: str, source: str) -> list[dict]:
    out = []
    for r in rows:
        code = r.get("county_code", "")
        if not code or code == "998" or not r.get("state_fips_code"):     # 998 = "OTHER (COMBINED) COUNTIES"
            continue
        if r.get("domain_desc", "TOTAL") != "TOTAL":
            continue
        v = parse_value(r.get("Value"))
        if v is None:
            continue
        out.append({"geo": r["state_fips_code"] + code, "var": var,
                    "date": pd.Timestamp(int(r["year"]), 1, 1), "value": v, "source": source})
    return out


def _pull(region: Region, series: dict, base: dict, source: str, deadline: float | None):
    http = session()
    out = []
    for var, short in series.items():
        if deadline and time.monotonic() >= deadline:
            return pd.DataFrame(out), False, []
        # domain_desc=TOTAL up front: without it Quick Stats also sends every breakdown (farm size classes,
        # organization types...), e.g. 15 MB / 14,831 rows instead of ~500 for one Census series.
        rows = query({**base, "state_alpha": region.extras.get("state_alpha", "TX"), "agg_level_desc": "COUNTY",
                      "short_desc": short, "domain_desc": "TOTAL"}, http=http)
        out += parse_rows(rows, var, source)
    return pd.DataFrame(out), True, []


def county(region: Region, *, deadline: float | None = None, since: int = 2015):
    """NASS survey county estimates, `since` onward. Returns (rows, complete, problems)."""
    return _pull(region, COUNTY_SERIES, {"source_desc": "SURVEY", "year__GE": since}, "nass_county", deadline)


def census(region: Region, *, deadline: float | None = None, since: int = 2017):
    """Census of Agriculture county figures (2017, 2022; 2027 when published). Returns (rows, complete, problems)."""
    return _pull(region, CENSUS_SERIES, {"source_desc": "CENSUS", "year__GE": since}, "census", deadline)
