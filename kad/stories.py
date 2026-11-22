"""Store → web/public/data/<region>/stories.json: the history the animated stories replay (docs/decisions/0024).

  drought   every county's Drought Monitor category for each of the last 104 weekly maps, plus the official
            statewide percentages. One character per county per week keeps two years of maps small.
  cotton    statewide percent of cotton harvested for each fall report (Aug.–Nov., the same reports the
            harvest outlook uses), grouped by season.

A stale source leaves its story out (null), like any other section.
"""
from __future__ import annotations

import pandas as pd

from .config import Region

DROUGHT = ("d0", "d1", "d2", "d3", "d4")
WEEKS = 104


def _iso(d) -> str:
    return pd.Timestamp(d).date().isoformat()


def county_category(row) -> str:
    """The worst category covering at least half the county, as the dashboard's maps use: '-' for none."""
    c = "-"
    for i, lvl in enumerate(DROUGHT):
        v = row.get(lvl)
        if v is not None and not pd.isna(v) and v >= 50:
            c = str(i)
    return c


def drought_weeks(w: pd.DataFrame, region: Region, weeks: int = WEEKS) -> dict | None:
    """`w` is the wide drought frame (geo, date, d0..d4), statewide row included."""
    if w.empty:
        return None
    fips = [c.fips for c in region.counties]
    state = w[w["geo"] == region.state_fips].set_index("date")
    cw = w[w["geo"] != region.state_fips]
    dates = sorted(cw["date"].unique())[-weeks:]
    out = []
    for d in dates:
        rows = cw[cw["date"] == d].set_index("geo")
        cats = "".join(county_category(rows.loc[f]) if f in rows.index else "?" for f in fips)
        entry = {"date": _iso(d), "map": cats}
        if d in state.index:
            entry["state"] = {lvl: round(float(state.at[d, lvl]), 1) for lvl in DROUGHT if lvl in state.columns}
        out.append(entry)
    return {"counties": fips, "weeks": out}


def cotton_seasons(nass: pd.DataFrame, region: Region) -> dict | None:
    rows = nass[(nass["geo"] == region.state_fips) & (nass["var"] == "cotton:harvested")
                & nass["value"].between(0, 100) & nass["date"].dt.month.isin([8, 9, 10, 11])]
    if rows.empty:
        return None
    seasons = []
    for year, g in rows.sort_values("date").groupby(rows["date"].dt.year):
        seasons.append({"year": int(year),
                        "reports": [{"date": _iso(d), "pct": round(float(v))} for d, v in zip(g["date"], g["value"])]})
    return {"seasons": seasons}


def site_data(region: Region, w: pd.DataFrame, nass: pd.DataFrame, *, drought_ok: bool, nass_ok: bool) -> dict:
    return {"drought": drought_weeks(w, region) if drought_ok else None,
            "cotton": cotton_seasons(nass, region) if nass_ok and not nass.empty else None}
