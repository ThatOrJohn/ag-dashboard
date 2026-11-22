"""Store → web/public/data/<region>/stories.json: the history the animated stories replay (docs/decisions/0024).

  drought     every county's Drought Monitor category for each of the last 104 weekly maps, plus the official
              statewide percentages. One character per county per week keeps two years of maps small.
  cotton      statewide percent of cotton harvested for each fall report (Aug.–Nov., the same reports the
              harvest outlook uses), grouped by season.
  reservoirs  statewide storage, monthly mean percent full, from 1950 (earlier years mostly reflect reservoirs
              still being built and filled).
  wells       each configured well's winter depth to water (Jan.–March median), one value per year.
  river       each configured stream gauge's monthly mean flow.
  cattle      the statewide weekly auction's feeder steer prices and head counts.
  census      farms and land in farms by county for each Census of Agriculture year in the store.

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


RESERVOIRS_FROM = 1950


def reservoir_months(res: pd.DataFrame, site: str = "statewide") -> dict | None:
    s = res[(res["geo"] == site) & (res["var"] == "percent_full")].set_index("date")["value"].sort_index()
    s = s[s.index.year >= RESERVOIRS_FROM]
    if s.empty:
        return None
    m = s.resample("MS").mean().dropna()
    return {"through": _iso(s.index.max()),
            "months": [{"month": d.strftime("%Y-%m"), "pct": round(float(v), 1)} for d, v in m.items()]}


def well_winters(gw: pd.DataFrame, sites: list[dict]) -> list[dict]:
    out = []
    for site in sites:
        s = gw[(gw["geo"] == site["id"]) & (gw["var"] == "depth_ft")].set_index("date")["value"].sort_index()
        winter = s[s.index.month <= 3]
        if winter.empty:
            continue
        years = winter.groupby(winter.index.year).median()
        out.append({"id": site["id"], "name": site.get("name", site["id"]), "aquifer": site.get("aquifer"),
                    "district": site.get("district"), "url": site.get("url"),
                    "winters": [{"year": int(y), "depth_ft": round(float(v), 1)} for y, v in years.items()]})
    return out


def river_months(flow: pd.DataFrame, sites: list[dict]) -> list[dict]:
    out = []
    for site in sites:
        rows = flow[flow["geo"] == site["id"]]
        q = rows[rows["var"] == "discharge_cfs"].set_index("date")["value"].sort_index()
        if q.empty:
            continue
        flag = rows[rows["var"] == "unapproved"].set_index("date")["value"]
        provisional = flag[flag > 0].index.min() if not flag.empty and (flag > 0).any() else None
        m = q.resample("MS").mean().dropna()
        if len(m) and q[q.index < m.index[0] + pd.offsets.MonthBegin(1)].size < 20:
            m = m.iloc[1:]            # a first month with only a few days of record isn't a monthly average
        out.append({"id": site["id"], "name": site.get("name", site["id"]), "url": site.get("url"),
                    "through": _iso(q.index.max()), "provisional_from": _iso(provisional) if provisional is not None else None,
                    "months": [{"month": d.strftime("%Y-%m"), "cfs": round(float(v))} for d, v in m.items()]})
    return out


def cattle_weeks(ams: pd.DataFrame, report: str) -> dict | None:
    rows = ams[ams["geo"] == f"ams:{report}"]
    if rows.empty:
        return None
    p = rows.pivot_table(index="date", columns="var", values="value").sort_index()
    cols = {"steers:500": "s500", "steers:700": "s700", "steers:500:head": "h500", "steers:700:head": "h700"}
    weeks = []
    for d, r in p.iterrows():
        if pd.isna(r.get("steers:500")) and pd.isna(r.get("steers:700")):
            continue
        weeks.append({"date": _iso(d), **{k: (None if pd.isna(r.get(c)) else round(float(r[c]), 2)) for c, k in cols.items()}})
    return {"report": report, "weeks": weeks} if weeks else None


def census_counties(census: pd.DataFrame, region: Region) -> dict | None:
    rows = census[census["var"].isin(["farms", "land_in_farms_acres"])]
    if rows.empty:
        return None
    years = sorted(rows["date"].dt.year.unique())[-2:]
    if len(years) < 2:
        return None
    p = rows.assign(y=rows["date"].dt.year).pivot_table(index="geo", columns=["var", "y"], values="value")
    counties = {}
    for c in region.counties:
        if c.fips not in p.index:
            continue
        r = p.loc[c.fips]
        vals = [r.get(("farms", y)) for y in years] + [r.get(("land_in_farms_acres", y)) for y in years]
        counties[c.fips] = [None if v is None or pd.isna(v) else int(v) for v in vals]
    return {"years": [int(y) for y in years], "counties": counties}



def site_data(region: Region, w: pd.DataFrame, nass: pd.DataFrame, *, drought_ok: bool, nass_ok: bool,
              fresh=None, frames: dict | None = None) -> dict:
    """`frames` holds the other store frames (already cut at the as-of date); `fresh` says which are current."""
    f = frames or {}
    ok = (lambda key: fresh is not None and key in fresh.sources and not fresh.sources[key]["stale"])
    empty = pd.DataFrame(columns=["geo", "var", "date", "value"])
    get = (lambda key: f.get(key) if f.get(key) is not None else empty)
    statewide_ams = next((r["slug"] for r in region.source("ams").get("reports", []) if r.get("scope") == "statewide"), "1955")
    return {
        "drought": drought_weeks(w, region) if drought_ok else None,
        "cotton": cotton_seasons(nass, region) if nass_ok and not nass.empty else None,
        "reservoirs": reservoir_months(get("twdb_reservoirs")) if ok("twdb_reservoirs") else None,
        "wells": well_winters(get("twdb_groundwater"), region.source("twdb_groundwater").get("sites", []))
        if ok("twdb_groundwater") else None,
        "river": river_months(get("usgs_streamflow"), region.source("usgs_streamflow").get("sites", []))
        if ok("usgs_streamflow") else None,
        "cattle": cattle_weeks(get("ams"), str(statewide_ams)) if ok("ams") else None,
        "census": census_counties(get("census"), region) if ok("census") else None,
    }
