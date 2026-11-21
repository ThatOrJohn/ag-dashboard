"""U.S. Drought Monitor county statistics (percent of area). One call returns every county in the state.

Values are cumulative: d1 means "D1 or worse". We keep them that way (var drought:d0 .. drought:d4) and
store `drought:none` too, so the shares can be un-stacked when a chart needs bands.
The official statewide row is stored under the state FIPS: where the Drought Monitor publishes a figure
itself, the site uses theirs. District figures are our area-weighted aggregation of counties.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..config import Region
from ..http import session

BASE = "https://usdmdataservices.unl.edu/api"
COUNTY = f"{BASE}/CountyStatistics/GetDroughtSeverityStatisticsByAreaPercent"
STATE = f"{BASE}/StateStatistics/GetDroughtSeverityStatisticsByAreaPercent"   # aoi = state FIPS, not "TX"
SOURCE = "usdm"
LEVELS = ("none", "d0", "d1", "d2", "d3", "d4")


def fetch(region: Region, *, weeks: int = 6, start: date | None = None, today: date | None = None) -> pd.DataFrame:
    end = today or date.today()
    start = start or end - timedelta(weeks=weeks)
    http = session()
    params = {"startdate": f"{start.month}/{start.day}/{start.year}",
              "enddate": f"{end.month}/{end.day}/{end.year}", "statisticsType": 1}
    out = []
    for url, aoi, geo in ((COUNTY, region.extras.get("state_alpha", "TX"), None), (STATE, region.state_fips, region.state_fips)):
        r = http.get(url, params={"aoi": aoi, **params}, headers={"Accept": "application/json"}, timeout=180)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            raise ValueError(f"Drought Monitor returned no rows for aoi={aoi}")
        out.append(parse(rows, geo))
    return pd.concat(out, ignore_index=True)


def parse(rows: list[dict], geo: str | None = None) -> pd.DataFrame:
    out = []
    for x in rows:
        d = pd.Timestamp(x["mapDate"]).normalize()
        for lvl in LEVELS:
            if x.get(lvl) is not None:
                out.append({"geo": geo or x["fips"], "var": f"drought:{lvl}", "date": d, "value": float(x[lvl]),
                            "source": SOURCE})
    return pd.DataFrame(out)
