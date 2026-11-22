"""Store → JSON for the site.

  web/public/data/<region>/latest.json             sources + freshness, Texas digest, every county's card
  web/public/data/<region>/districts/<slug>.json   every district: counties, drought history, markets
  web/public/data/<region>/stories.json            history the animated stories replay (stories.py)

Rules (CLAUDE.md):
- A source past its max age is `stale`, and its sections carry no numbers (the site hides them).
- Seasonal NASS series outside their season say "out of season" with the last report date, never last
  season's numbers.
- District figures are our own aggregation of counties (area-weighted), labeled as such by the site.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from . import annual_build as ab
from . import harvest, headline, normals, store, stories, water
from .adapters.ams import SHEEP_GOAT_SERIES
from .config import SITE_OUT, Region

NASS_NOTICE = "This product uses the NASS API but is not endorsed or certified by NASS."
CONDITION = ("excellent", "good", "fair", "poor", "very_poor")
DROUGHT = ("d0", "d1", "d2", "d3", "d4")
# Statewide weekly crops, in the order district pages show them. A district lists its own in tx.yaml (`crops`).
CROPS = ("wheat", "cotton", "corn", "sorghum")
CATTLE_SERIES = ("steers:500", "steers:700", "heifers:500", "cows:slaughter")


def _iso(d) -> str | None:
    return None if d is None or pd.isna(d) else pd.Timestamp(d).date().isoformat()


def _r(x, n=1):
    return None if x is None or pd.isna(x) else round(float(x), n)


def _near(df: pd.DataFrame, when: pd.Timestamp, days: int = 3) -> pd.DataFrame:
    """Rows whose date is within `days` of `when` (weekly series don't land on the same weekday each year)."""
    return df[(df["date"] - when).abs() <= pd.Timedelta(days=days)]


class Freshness:
    """Per-source as-of and staleness, measured from the newest figure's own date."""

    def __init__(self, region: Region, asof: pd.Timestamp):
        self.region, self.asof, self.log = region, asof, store.read_fetch_log(region)
        self.sources: dict[str, dict] = {}

    def mark(self, key: str, newest) -> bool:
        cfg = self.region.source(key)
        newest = None if newest is None or pd.isna(newest) else pd.Timestamp(newest).normalize()
        stale = newest is None or (self.asof - newest).days > cfg.get("max_age_days", 7)
        # A source's quiet months (NASS's winter break): old data is expected, so it isn't an outage.
        between = stale and newest is not None and self.asof.month in cfg.get("quiet_months", [])
        self.sources[key] = {"name": cfg.get("name", key), "url": cfg.get("url"), "license": cfg.get("license"),
                             "as_of": _iso(newest), "fetched_at": self.log.get(key),
                             "stale": stale and not between, "between_reports": between}
        return not stale


# --- NASS state weekly -------------------------------------------------------------------------------

def _season_items(region: Region, crop: str, stat: str) -> dict | None:
    return next((i for i in region.source("nass").get("weekly", []) if i["id"] == crop and i["stat"] == stat), None)


def _status(region: Region, asof: pd.Timestamp, latest, item: dict | None) -> str:
    """fresh | out_of_season | stale. Out of season beats stale: a quiet winter is not an outage."""
    cfg = region.source("nass")
    if latest is not None and (asof - latest).days <= cfg.get("max_age_days", 10):
        return "fresh"
    if (item and asof.month not in item.get("in_season", range(1, 13))) or asof.month in cfg.get("quiet_months", []):
        return "out_of_season"
    return "stale"


def progress_card(region: Region, df: pd.DataFrame, crop: str, asof: pd.Timestamp) -> dict:
    rows = df[df["var"].str.startswith(f"{crop}:") & ~df["var"].str.split(":").str[1].isin(CONDITION)]
    rows = rows.assign(stage=rows["var"].str.split(":").str[1])
    latest = rows["date"].max() if not rows.empty else None
    status = _status(region, asof, latest, _season_items(region, crop, "PROGRESS"))
    out = {"status": status, "last_report": _iso(latest), "level": "state"}
    if status != "fresh":
        return out
    now = rows[rows["date"] == latest]
    stages = []
    for _, r in now.iterrows():
        hist = rows[rows["stage"] == r["stage"]]
        last_week = hist[hist["date"] == latest - pd.Timedelta(days=7)]["value"]
        last_year = _near(hist, latest - pd.DateOffset(years=1))["value"]
        prior = [_near(hist, latest - pd.DateOffset(years=k))["value"] for k in range(1, 6)]
        prior = [p.iloc[0] for p in prior if not p.empty]
        stages.append({"stage": r["stage"], "pct": _r(r["value"], 0),
                       "last_week": _r(last_week.iloc[0], 0) if not last_week.empty else None,
                       "last_year": _r(last_year.iloc[0], 0) if not last_year.empty else None,
                       "avg_5yr": _r(sum(prior) / len(prior), 0) if len(prior) == 5 else None})
    out.update({"week_ending": _iso(latest), "stages": stages})
    return out


def condition_card(region: Region, df: pd.DataFrame, crop: str, asof: pd.Timestamp) -> dict:
    rows = df[df["var"].str.startswith(f"{crop}:") & df["var"].str.split(":").str[1].isin(CONDITION)]
    rows = rows.assign(cls=rows["var"].str.split(":").str[1])
    latest = rows["date"].max() if not rows.empty else None
    status = _status(region, asof, latest, _season_items(region, crop, "CONDITION"))
    out = {"status": status, "last_report": _iso(latest), "level": "state"}
    if status != "fresh":
        return out

    def ge(when):
        w = rows[rows["date"] == when] if when == latest else _near(rows, when)
        w = w[w["date"] == w["date"].min()] if not w.empty else w
        v = w[w["cls"].isin(["good", "excellent"])]["value"]
        return _r(v.sum(), 0) if len(v) == 2 else None

    now = rows[rows["date"] == latest].set_index("cls")["value"]
    out.update({"week_ending": _iso(latest), "classes": {c: _r(now.get(c), 0) for c in CONDITION},
                "good_excellent": ge(latest), "last_week": ge(latest - pd.Timedelta(days=7)),
                "last_year": ge(latest - pd.DateOffset(years=1))})
    return out


# --- Drought -----------------------------------------------------------------------------------------

def _drought_frame(usdm: pd.DataFrame) -> pd.DataFrame:
    """Wide: one row per (geo, date), columns none, d0..d4 (cumulative percent of area)."""
    if usdm.empty:
        return pd.DataFrame()
    w = usdm.assign(lvl=usdm["var"].str.split(":").str[1]).pivot_table(
        index=["geo", "date"], columns="lvl", values="value", aggfunc="last").reset_index()
    return w


def _weighted(w: pd.DataFrame, area: dict[str, float]) -> dict:
    w = w[w["geo"].isin(area)]
    if w.empty:
        return {}
    a = w["geo"].map(area)
    return {lvl: _r((w[lvl] * a).sum() / a.sum()) for lvl in DROUGHT if lvl in w}


def drought_summary(w: pd.DataFrame, area: dict[str, float], when: pd.Timestamp, *, official: bool = False) -> dict | None:
    def at(t):
        rows = _near(w, t, 3)
        if rows.empty:
            return None
        return _weighted(rows[rows["date"] == rows["date"].max()], area) or None
    now = at(when)
    if not now:
        return None
    return {"map_date": _iso(when), "basis": "official" if official else "county_area_weighted", "now": now,
            "week_ago": at(when - pd.Timedelta(days=7)), "year_ago": at(when - pd.Timedelta(days=364))}


def drought_history(w: pd.DataFrame, area: dict[str, float], weeks: int = 104) -> list[dict]:
    dates = sorted(w["date"].unique())[-weeks:]
    return [{"date": _iso(d), **_weighted(w[w["date"] == d], area)} for d in dates]


# --- Weather -----------------------------------------------------------------------------------------

def rain_by_county(nc: pd.DataFrame) -> dict[str, dict]:
    """County → rain over the 7 and 30 days through NOAA's newest day (nClimGrid county averages)."""
    rain = nc[nc["var"] == "rain_mm"] if not nc.empty else nc
    out: dict[str, dict] = {}
    if rain.empty:
        return out
    last = rain["date"].max()
    for geo, g in rain.groupby("geo"):
        s = g.set_index("date")["value"]
        out[geo] = {"through": _iso(last),
                    "last_7d_in": _r(s[s.index > last - pd.Timedelta(days=7)].sum() / 25.4, 2),
                    "last_30d_in": _r(s[s.index > last - pd.Timedelta(days=30)].sum() / 25.4, 2)}
    return out


def rain_estimate(est: pd.DataFrame, after: pd.Timestamp | None) -> dict[str, dict]:
    """County → Stage IV rain for the days after NOAA's newest county-average day (decision 0017).

    An estimate, shown apart from NOAA's figures and never in a vs-normal comparison. A county gets one only
    when it has every day from the day after `after` through the newest estimate.
    """
    if after is None or est.empty:
        return {}
    r = est[(est["var"] == "rain_mm") & (est["date"] > after)]
    if r.empty:
        return {}
    last = r["date"].max()
    want = pd.date_range(after + pd.Timedelta(days=1), last)
    out = {}
    for geo, g in r.groupby("geo"):
        if g["date"].nunique() == len(want):
            out[geo] = {"from": _iso(want[0]), "through": _iso(last), "in": _r(g["value"].sum() / 25.4, 2)}
    return out


def _district_estimate(cards: dict[str, dict], area: dict[str, float]) -> dict | None:
    got = [(cards[f]["rain_estimate"], a) for f, a in area.items() if f in cards and "rain_estimate" in cards[f]]
    if not got or len(got) < len(area) / 2:
        return None
    wsum = sum(a for _, a in got)
    return {"from": got[0][0]["from"], "through": got[0][0]["through"],
            "in": _r(sum(v["in"] * a for v, a in got) / wsum, 2), "counties": len(got)}


def forecast_rain_by_county(fc: pd.DataFrame | None, asof: pd.Timestamp) -> dict[str, float]:
    """County → NWS forecast rain over the next 7 days (today included), in inches."""
    if fc is None or fc.empty:
        return {}
    f = fc[(fc["var"] == "rain_mm") & (fc["date"] >= asof) & (fc["date"] < asof + pd.Timedelta(days=7))]
    return {geo: _r(g["value"].sum() / 25.4, 2) for geo, g in f.groupby("geo")}


def rain_vs_normal(nc: pd.DataFrame, nm: "normals.Normals | None", days: int = 30) -> dict[str, dict]:
    """County → rain over the `days` days through NOAA's newest day vs the 1991–2020 normal for those dates.

    Both sides are nClimGrid county averages, so the comparison is like for like (decision 0013). A county
    with a missing day in the window gets no percentage rather than a low one.
    """
    out: dict[str, dict] = {}
    rain = nc[nc["var"] == "rain_mm"] if not nc.empty else nc
    if nm is None or rain.empty:
        return out
    last = rain["date"].max()
    window = pd.date_range(end=last, periods=days)
    for geo, g in rain[rain["date"].isin(window)].groupby("geo"):
        a = nm.on(geo, window)
        if g["date"].nunique() < days or a is None or pd.isna(a[:, 2]).any():
            continue
        actual, normal = g["value"].sum() / 25.4, a[:, 2].sum() / 25.4
        out[geo] = {"through": _iso(last), "days": days, "in": _r(actual, 2), "normal_in": _r(normal, 2),
                    "pct": _pct_normal(actual, normal)}
    return out


def _district_vs_normal(cards: dict[str, dict], area: dict[str, float]) -> dict | None:
    got = [(cards[f]["rain_vs_normal"], a) for f, a in area.items() if f in cards and "rain_vs_normal" in cards[f]]
    if not got:
        return None
    wsum = sum(a for _, a in got)
    actual = sum(v["in"] * a for v, a in got) / wsum
    normal = sum(v["normal_in"] * a for v, a in got) / wsum
    return {"through": got[0][0]["through"], "days": got[0][0]["days"], "in": _r(actual, 2),
            "normal_in": _r(normal, 2), "pct": _pct_normal(actual, normal), "counties": len(got)}


def _pct_normal(actual: float | None, normal: float | None) -> int | None:
    """Percent of normal; none when the normal is too small for a percentage to mean anything."""
    if actual is None or normal is None or normal < 0.1:
        return None
    return int(round(100 * actual / normal))


def _daily_area_mean(df: pd.DataFrame, area: dict[str, float]) -> pd.DataFrame:
    """Area-weighted mean per (date, var) over the district's counties that have a value that day."""
    d = df[df["geo"].isin(area.keys())].copy()
    if d.empty:
        return pd.DataFrame(columns=["date", "var", "value"])
    d["w"] = d["geo"].map(area)
    d["wv"] = d["value"] * d["w"]
    g = d.groupby(["date", "var"], as_index=False)[["wv", "w"]].sum()
    g["value"] = g["wv"] / g["w"]
    return g[["date", "var", "value"]]


def weather_strip(nc: pd.DataFrame, fc: pd.DataFrame | None, area: dict[str, float], asof: pd.Timestamp,
                  days: int = 35, nm: "normals.Normals | None" = None, est: pd.DataFrame | None = None) -> dict | None:
    """A district's daily high, low and rain, in runs of days (decisions 0014, 0017):

      observed   the last `days` days NOAA has published (nClimGrid county averages, about a week behind)
      estimated  days since then with a Stage IV rain estimate (`est`): rain only, no high or low
      pending    days with neither yet: dates only, no numbers
      forecast   NWS, from today for 7 days

    Values are our area-weighted average over the district's counties, in °F and inches. With normals, every
    day (pending and forecast too) carries the 1991–2020 normal high and low for its date.
    """
    if nc.empty:
        return None
    last = nc["date"].max()
    obs = nc[nc["date"] > last - pd.Timedelta(days=days)]
    parts = [_daily_area_mean(obs, area).assign(kind="observed")]
    if fc is not None and not fc.empty:
        parts.append(_daily_area_mean(fc[(fc["date"] > last) & (fc["date"] >= asof)], area).assign(kind="forecast"))
    m = pd.concat(parts)
    if m.empty:
        return None
    wide = m.pivot_table(index=["date", "kind"], columns="var", values="value").reset_index()
    pending = pd.date_range(last + pd.Timedelta(days=1), asof - pd.Timedelta(days=1))
    if len(pending):
        gap = pd.DataFrame({"date": pending, "kind": "pending"})
        if est is not None and not est.empty:
            e = _daily_area_mean(est[est["date"].isin(pending) & (est["var"] == "rain_mm")], area)
            # Only days where most of the district has an estimate; otherwise the average is of a corner.
            n = est[est["date"].isin(pending) & est["geo"].isin(area.keys())].groupby("date")["geo"].nunique()
            e = e[e["date"].map(n).fillna(0) >= len(area) / 2]
            gap = gap.merge(e[["date", "value"]].rename(columns={"value": "rain_mm"}), on="date", how="left")
            gap.loc[gap["rain_mm"].notna(), "kind"] = "estimated"
        wide = pd.concat([wide, gap])
    wide = wide.sort_values("date").reset_index(drop=True)
    # Normal high and low per day: the same area weighting, over counties that have normals.
    nhi = nlo = None
    if nm is not None:
        got = [(nm.on(f, wide["date"]), a) for f, a in area.items()]
        got = [(x, a) for x, a in got if x is not None]
        if got:
            wsum = sum(a for _, a in got)
            nhi = sum(x[:, 0] * a for x, a in got) / wsum
            nlo = sum(x[:, 1] * a for x, a in got) / wsum
    f = lambda c: None if c is None or pd.isna(c) else round(c * 9 / 5 + 32)
    out = []
    for k, r in wide.iterrows():
        rain = r.get("rain_mm")
        day = {"date": _iso(r["date"]), "kind": r["kind"], "hi_f": f(r.get("tmax_c")), "lo_f": f(r.get("tmin_c")),
               "rain_in": None if rain is None or pd.isna(rain) else _r(rain / 25.4, 2)}
        if nhi is not None:
            day["normal_hi_f"], day["normal_lo_f"] = f(nhi[k]), f(nlo[k])
        out.append(day)
    return {"through": _iso(last), "basis": "county_average_area_weighted", "days": out}


def season_rain(nc: pd.DataFrame, nm: "normals.Normals | None", monthly: pd.DataFrame | None,
                area: dict[str, float]) -> dict | None:
    """A district's rain since Jan. 1 through NOAA's newest day, against 1991–2020 (decision 0015).

    `actual` is the running total, one value per day from Jan. 1. `normal` is the running total of the daily
    normals and `low` / `high` are the 10th and 90th percentiles of the 30 years' running totals, each for the
    whole year. Years are built from their monthly totals (all the backfill keeps), spread across each month
    in the shape of the normal, and averaged over the district's counties by area like everything else. Needs
    every day since Jan. 1: a gap gives no chart rather than a total that looks low.
    """
    rain = nc[nc["var"] == "rain_mm"] if not nc.empty else nc
    if nm is None or monthly is None or rain.empty:
        return None
    through = rain["date"].max()
    year = through.year
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    got = {f: nm.on(f, dates) for f in area}
    got = {f: x[:, 2] for f, x in got.items() if x is not None and not np.isnan(x[:, 2]).any()}
    if not got:
        return None
    w = np.array([area[f] for f in got])
    daily_normal = np.array(list(got.values())).T @ w / w.sum()                       # mm per day
    # This year, observed.
    obs = _daily_area_mean(rain[(rain["date"] >= dates[0]) & (rain["date"] <= through)], area)
    obs = obs.set_index("date")["value"].reindex(pd.date_range(dates[0], through))
    if obs.isna().any():
        return None
    actual = obs.cumsum().to_numpy()
    # 1991–2020, from monthly totals.
    mr = monthly[monthly["geo"].isin(got.keys())].copy()
    mr["w"] = mr["geo"].map(area)
    mr["wv"] = mr["rain_mm"] * mr["w"]
    g = mr.groupby(["year", "month"])[["wv", "w"]].sum()
    tot = (g["wv"] / g["w"]).unstack("month")
    tot = tot[tot.notna().all(axis=1)]                                                   # years with all 12 months
    if len(tot) < 20:
        return None
    month_of = dates.month.to_numpy() - 1
    frac = np.zeros(len(dates))                     # share of each month's normal rain that has fallen by each day
    for m in range(12):
        idx = np.where(month_of == m)[0]
        c = np.cumsum(daily_normal[idx])
        frac[idx] = c / c[-1] if c[-1] > 0 else (np.arange(len(idx)) + 1) / len(idx)
    M = tot.to_numpy()                                                                   # years × 12
    before = np.concatenate([np.zeros((len(M), 1)), np.cumsum(M, axis=1)[:, :-1]], axis=1)
    years = before[:, month_of] + M[:, month_of] * frac                                  # years × days
    normal = np.cumsum(daily_normal)
    ti = len(actual) - 1
    inch = lambda a: [round(float(v) / 25.4, 2) for v in a]
    return {"year": year, "through": _iso(through), "start": _iso(dates[0]),
            "actual": inch(actual), "normal": inch(normal),
            "low": inch(np.percentile(years, 10, axis=0)), "high": inch(np.percentile(years, 90, axis=0)),
            "to_date_in": _r(actual[-1] / 25.4, 2), "normal_to_date_in": _r(normal[ti] / 25.4, 2),
            "pct": _pct_normal(actual[-1] / 25.4, normal[ti] / 25.4), "normal_year_in": _r(normal[-1] / 25.4, 1),
            "drier_years": int((years[:, ti] < actual[-1]).sum()), "years": int(len(years)),
            "range_years": [int(tot.index.min()), int(tot.index.max())]}


def _area_mean(cards: dict[str, dict], key: str, area: dict[str, float]) -> float | None:
    pairs = [(cards[f][key], a) for f, a in area.items() if f in cards and cards[f].get(key) is not None]
    return _r(sum(v * a for v, a in pairs) / sum(a for _, a in pairs), 2) if pairs else None


# --- Markets -----------------------------------------------------------------------------------------

def market_cards(region: Region, ams: pd.DataFrame, notes: dict, fresh: Freshness) -> list[dict]:
    out = []
    max_age = region.source("ams").get("max_age_days", 14)
    for rep in region.source("ams").get("reports", []):
        geo = f"ams:{rep['slug']}"
        rows = ams[ams["geo"] == geo]
        latest = rows["date"].max() if not rows.empty else None
        card = {"slug": rep["slug"], "name": rep["name"], "scope": rep.get("scope", "market"),
                "kind": rep.get("kind", "cattle"),
                "district": rep.get("district"), "url": f"https://mymarketnews.ams.usda.gov/viewReport/{rep['slug']}",
                "report_date": _iso(latest),
                "stale": latest is None or (fresh.asof - latest).days > max_age}
        if not card["stale"]:
            now = rows[rows["date"] == latest].set_index("var")["value"]
            prev_dates = sorted(rows[rows["date"] < latest]["date"].unique())
            prev = rows[rows["date"] == prev_dates[-1]].set_index("var")["value"] if prev_dates else pd.Series(dtype=float)
            year = _near(rows, latest - pd.Timedelta(days=364), 4)
            year = year[year["date"] == year["date"].min()].set_index("var")["value"] if not year.empty else pd.Series(dtype=float)
            series = []
            for var in SHEEP_GOAT_SERIES if card["kind"] == "sheep_goats" else CATTLE_SERIES:
                if var in now:
                    series.append({"id": var, "price_cwt": _r(now[var], 2),
                                   "head": _r(now.get(f"{var}:head"), 0),
                                   "prev": _r(prev.get(var), 2), "year_ago": _r(year.get(var), 2)})
            note = notes.get(str(rep["slug"])) or {}
            card.update({"series": series, "receipts": _r(now.get("receipts"), 0),
                         "narrative": note.get("narrative") if note.get("report_date") == _iso(latest) else None})
        out.append(card)
    return out


# --- Screwworm ---------------------------------------------------------------------------------------

def screwworm_card(region: Region, fresh: Freshness) -> dict | None:
    cfg = region.source("screwworm")
    if not cfg:
        return None
    snap = store.read_snapshot(region, "screwworm")
    checked = (pd.Timestamp(snap["fetched_at"]).tz_convert(region.timezone).tz_localize(None).normalize()
               if snap is not None else None)
    if checked is not None and checked > fresh.asof:
        checked = None
    age = (fresh.asof - checked).days if checked is not None else None
    hidden = age is None or age >= cfg["hide_after_days"]
    delayed = not hidden and age >= cfg["warn_after_days"]
    fresh.sources["screwworm"] = {
        "name": cfg["name"], "url": cfg["url"], "license": cfg.get("license"), "as_of": _iso(checked),
        "fetched_at": snap["fetched_at"] if checked is not None else None, "stale": hidden, "delayed": delayed,
    }
    if hidden:
        return None

    names = {county.fips: county.name for county in region.counties}
    detections = snap["detections"]
    recent = {}
    for row in sorted(detections, key=lambda r: r["date"], reverse=True):
        fips = row["fips"]
        county = recent.setdefault(fips, {"county": names[fips], "date": row["date"], "animals": 0, "fly_traps": 0})
        if row["date"] == county["date"]:
            county["fly_traps" if row["fly_trap"] else "animals"] += 1
    fly_traps = sum(row["fly_trap"] for row in detections)

    return {
        "active_animals": sum(row["active"] and not row["fly_trap"] for row in detections),
        "animals": len(detections) - fly_traps,
        "fly_traps": fly_traps,
        "recent": list(recent.values())[:5],
        "stale_at": (checked + pd.Timedelta(days=cfg["warn_after_days"])).tz_localize(region.timezone).isoformat(),
        "hide_at": (checked + pd.Timedelta(days=cfg["hide_after_days"])).tz_localize(region.timezone).isoformat(),
        "movement_map_url": cfg["movement_map_url"], "dispersal_url": cfg["dispersal_url"],
    }


# --- Boll weevil -------------------------------------------------------------------------------------

def boll_weevil_card(region: Region, fresh: Freshness) -> dict | None:
    key = "boll_weevil"
    cfg = region.source(key)
    if not cfg:
        return None
    snapshot = store.read_snapshot(region, key)
    if snapshot and snapshot["week"] > fresh.asof.date().isoformat():
        snapshot = None
    current = fresh.mark(key, snapshot["week"] if snapshot else None)
    if snapshot:
        fresh.sources[key]["fetched_at"] = snapshot["fetched_at"]
    return {"report_url": snapshot["url"] if snapshot else cfg["url"], "zone_url": cfg["zone_url"],
            "zones": snapshot["zones"] if current else []}


# --- Build -------------------------------------------------------------------------------------------
def build(region: Region, asof: date | None = None, failures: list[str] | None = None) -> dict:
    asof_ts = pd.Timestamp(asof) if asof else pd.Timestamp.now(tz=region.timezone).tz_localize(None).normalize()
    fresh = Freshness(region, asof_ts)

    def upto(df):
        return df[df["date"] <= asof_ts] if not df.empty else df

    usdm, nass = upto(store.read_obs(region, "usdm")), upto(store.read_obs(region, "nass"))
    ams = upto(store.read_obs(region, "ams"))
    fc_path = region.data_dir / "forecast.parquet"
    fc = pd.read_parquet(fc_path) if fc_path.exists() else None      # NWS; its dates are today onward
    bans = store.read_snapshot(region, "burn_bans")
    notes = store.read_snapshot(region, "ams_notes") or {}

    area = {c.fips: c.land_sqmi for c in region.counties}
    names = {c.fips: c.name for c in region.counties}

    # Drought
    w_all = _drought_frame(usdm)
    w = w_all[w_all["geo"] != region.state_fips] if not w_all.empty else w_all
    map_date = w["date"].max() if not w.empty else None
    drought_ok = fresh.mark("usdm", map_date)

    # NASS
    nass_ok = fresh.mark("nass", nass["date"].max() if not nass.empty else None)
    crops = {}
    for crop in CROPS:
        crops[crop] = {"progress": progress_card(region, nass, crop, asof_ts),
                       "condition": condition_card(region, nass, crop, asof_ts)}
    cotton = crops["cotton"]["progress"]
    outlook = harvest.site_data(region, asof_ts, input_week=cotton.get("week_ending"))
    if outlook is not None:
        cotton["harvest_outlook"] = outlook
    pasture = condition_card(region, nass, "pasture", asof_ts)

    # Burn bans: the KMZ's Last-Modified is the figure's date.
    ban_date = None
    if bans:
        ban_date = pd.Timestamp(bans.get("last_modified") or bans["fetched_at"]).tz_convert(region.timezone).tz_localize(None)
    bans_ok = fresh.mark("burn_bans", ban_date)

    # Weather
    nm = normals.Normals.load(region)
    monthly = normals.monthly_rain(region)
    fresh.mark("normals", pd.Timestamp(f"{normals.LAST}-12-31") if nm is not None else None)
    nc = upto(store.read_obs(region, "nclimgrid"))
    rain_ok = fresh.mark("nclimgrid", nc["date"].max() if not nc.empty else None)
    fc_ok = fresh.mark("nws", fc["date"].min() if fc is not None and not fc.empty else None)
    fc = fc if fc_ok else None
    vs_normal = rain_vs_normal(nc, nm) if rain_ok else {}
    # Stage IV estimates for the days since NOAA's newest county-average day, up to yesterday (decision 0017).
    st4 = upto(store.read_obs(region, "stage4"))
    st4 = st4[st4["date"] < asof_ts] if not st4.empty else st4
    est_ok = fresh.mark("stage4", st4["date"].max() if not st4.empty else None)
    nc_last = nc["date"].max() if rain_ok else None
    est = st4[st4["date"] > nc_last] if est_ok and nc_last is not None else st4.iloc[0:0]
    estimate = rain_estimate(est, nc_last)
    rain = rain_by_county(nc) if rain_ok else {}
    ahead = forecast_rain_by_county(fc, asof_ts)

    state_water, district_water = water.cards(region, fresh)

    # Markets
    fresh.mark("ams", ams["date"].max() if not ams.empty else None)
    markets = market_cards(region, ams, notes, fresh)

    # County cards
    counties = {}
    now_rows = w[w["date"] == map_date].set_index("geo") if drought_ok else None
    year_rows = None
    if drought_ok:
        y = _near(w, map_date - pd.Timedelta(days=364), 3)
        year_rows = y[y["date"] == y["date"].max()].set_index("geo") if not y.empty else None
    for c in region.counties:
        card: dict = {"name": c.name, "district": c.district}
        if drought_ok and c.fips in now_rows.index:
            card["drought"] = {lvl: _r(now_rows.at[c.fips, lvl]) for lvl in DROUGHT}
            if year_rows is not None and c.fips in year_rows.index:
                card["drought_year_ago"] = {lvl: _r(year_rows.at[c.fips, lvl]) for lvl in DROUGHT}
        if bans_ok:
            card["burn_ban"] = bool(bans["counties"].get(c.fips, False))
        if rain_ok and c.fips in rain:
            card.update(rain[c.fips])
        if c.fips in ahead:
            card["next_7d_in"] = ahead[c.fips]
        if c.fips in vs_normal:
            card["rain_vs_normal"] = vs_normal[c.fips]
        if c.fips in estimate:
            card["rain_estimate"] = estimate[c.fips]
        counties[c.fips] = card

    # Districts
    districts = []
    for d in region.districts:
        d_area = {c.fips: c.land_sqmi for c in region.counties_in(d["slug"])}
        entry = {"slug": d["slug"], "name": d["name"], "home": bool(d.get("home")), "counties": len(d_area),
                 "crops": d.get("crops", list(CROPS))}
        if drought_ok:
            entry["drought"] = drought_summary(w, d_area, map_date)
        if bans_ok:
            entry["burn_bans"] = sum(counties[f].get("burn_ban", False) for f in d_area)
        if rain_ok:
            entry["rain_through"] = next(iter(rain.values()))["through"] if rain else None
            entry["rain_7d_in"] = _area_mean(counties, "last_7d_in", d_area)
            entry["rain_30d_in"] = _area_mean(counties, "last_30d_in", d_area)
        if fc_ok:
            entry["rain_next_7d_in"] = _area_mean(counties, "next_7d_in", d_area)
        if vs_normal:
            entry["rain_vs_normal"] = _district_vs_normal(counties, d_area)
        if estimate:
            entry["rain_estimate"] = _district_estimate(counties, d_area)
        local = next((m for m in markets if m["kind"] == "cattle" and m["district"] == d["slug"]), None)
        entry["headline"] = headline.district(entry, d.get("phrase") or f"the {d['name']} district", local)
        districts.append(entry)

    texas = {
        # The Drought Monitor's own statewide figure (weight 1 on the state row), not our aggregation.
        "drought": drought_summary(w_all, {region.state_fips: 1.0}, map_date, official=True) if drought_ok else None,
        "burn_bans": {"count": sum(v.get("burn_ban", False) for v in counties.values()), "of": len(counties)}
        if bans_ok else None,
        "crops": crops, "pasture": pasture, "screwworm": screwworm_card(region, fresh),
        "boll_weevil": boll_weevil_card(region, fresh), "water": state_water,
    }
    statewide = next((m for m in markets if m["scope"] == "statewide"), None)
    texas["headline"] = headline.texas(texas, statewide)
    texas["headline_all"] = headline.texas(texas, statewide, all_crops=True)   # persona pages filter this
    latest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asof": _iso(asof_ts),
        "region": {"id": region.id, "name": region.name},
        "nass_notice": NASS_NOTICE,
        "sources": fresh.sources,
        "failures": sorted(set(failures or [])),
        "personas": region.personas,
        "texas": texas,
        "districts": districts,
        "markets": markets,
        "counties": counties,
    }
    # Annual sources (when due; docs/decisions/0011). A stale annual source hides its figures like any other.
    census = store.read_obs(region, "census")
    county_est = store.read_obs(region, "nass_county")
    rap = store.read_obs(region, "rap")
    cdl = store.read_obs(region, "cdl")
    census_ok = fresh.mark("census", census["date"].max() if not census.empty else None)
    county_ok = fresh.mark("nass_county", county_est["date"].max() if not county_est.empty else None)
    rap_cover = rap["var"].str.startswith("cover:")
    rap_prod = rap["var"] == "prod:her_lb_ac"
    rap_cutoff = asof_ts - pd.Timedelta(days=region.source("rap").get("max_age_days", 7))
    # Cover and forage arrive independently. Keep the history for each series that is still current.
    rap_current = rap_cover & rap.loc[rap_cover, "date"].ge(rap_cutoff).any()
    rap_current |= rap_prod & rap.loc[rap_prod, "date"].ge(rap_cutoff).any()
    rap_use = rap.loc[rap_current]
    fresh.mark("rap", rap["date"].max())
    cdl_ok = fresh.mark("cdl", cdl["date"].max() if not cdl.empty else None)
    census_idx = ab._index(census) if census_ok else {}
    county_idx = ab._index(county_est) if county_ok else {}
    cdl_idx = ab._index(cdl) if cdl_ok else {}
    latest["sources"] = fresh.sources

    out = SITE_OUT / region.id
    (out / "districts").mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(latest, separators=(",", ":")))
    story_data = stories.site_data(
        region, w_all, nass, drought_ok=drought_ok, nass_ok=nass_ok, fresh=fresh,
        frames={"ams": ams, "census": census, "nclimgrid": nc,
                **{k: upto(store.read_obs(region, k)) for k in ("twdb_reservoirs", "twdb_groundwater", "usgs_streamflow")}})
    (out / "stories.json").write_text(json.dumps(story_data, separators=(",", ":")))

    for d in region.districts:
        d_area = {c.fips: c.land_sqmi for c in region.counties_in(d["slug"])}
        annual_cards = {}
        for f in d_area:
            a = {"census": ab.census_card(census_idx, f), "estimates": ab.nass_county_card(county_idx, f),
                 "rangeland": ab.rap_card(rap_use, f, asof_ts), "crop_mix": ab.cdl_card(cdl_idx, f)}
            annual_cards[f] = {k: v for k, v in a.items() if v}
        doc = {
            "slug": d["slug"], "name": d["name"], "asof": latest["asof"],
            "summary": next(x for x in districts if x["slug"] == d["slug"]),
            "annual": ab.district_rollup(list(d_area), d_area, census_idx, county_idx, rap_use, asof_ts, cdl_idx),
            "drought_history": drought_history(w, d_area) if drought_ok else [],
            "weather": weather_strip(nc, fc, d_area, asof_ts, nm=nm, est=est) if rain_ok else None,
            "season_rain": season_rain(nc, nm, monthly, d_area) if rain_ok else None,
            "water": district_water.get(d["slug"], []),
            "counties": sorted(({"fips": f, **counties[f], "annual": annual_cards[f]} for f in d_area),
                               key=lambda x: x["name"]),
            "markets": [m for m in markets if m["scope"] == "statewide" or m.get("district") == d["slug"]],
        }
        (out / "districts" / f"{d['slug']}.json").write_text(json.dumps(doc, separators=(",", ":")))
    return latest
