"""Annual figures for county cards and district pages (Census of Ag, NASS county estimates, RAP, CDL).

Rules (CLAUDE.md): NASS county totals for a district are a LOWER BOUND (published counties only) and say
how many counties they cover; CDL figures are satellite-classified; RAP is "Rangeland Analysis Platform,
USDA ARS". Missing means "not published", never zero.
"""
from __future__ import annotations

import pandas as pd

CROPS = {"corn": "yield_bu_ac", "sorghum": "yield_bu_ac", "cotton": "yield_lb_ac", "wheat": "yield_bu_ac"}
CENSUS_KEYS = ("farms", "land_in_farms_acres", "avg_farm_acres", "median_farm_acres", "cropland_acres",
               "pasture_acres", "sales_usd", "land_value_usd_ac", "producers", "cattle", "goats", "sheep")
COVER = ("pfg", "afg", "shr", "tre", "ltr", "bgr")
BASELINE_YEARS = (1986, 1995)     # RAP's first decade: "then" for woody-cover change
CDL_NOT_LAND = {"background", "open_water", "water"}


def _r(x, n=0):
    return None if x is None or pd.isna(x) else (round(float(x), n) if n else int(round(float(x))))


def _index(df: pd.DataFrame) -> dict:
    """{geo: {var: {year: value}}} for annual tables."""
    out: dict = {}
    if df.empty:
        return out
    for (geo, var), g in df.groupby(["geo", "var"]):
        out.setdefault(geo, {})[var] = dict(zip(g["date"].dt.year, g["value"]))
    return out


def census_card(idx: dict, fips: str) -> dict | None:
    c = idx.get(fips)
    if not c:
        return None
    year = max((max(v) for v in c.values()), default=None)
    out = {"year": int(year)}
    for k in CENSUS_KEYS:
        v = c.get(k, {}).get(year)
        if v is not None:
            out[k] = _r(v)
    prev = c.get("farms", {}).get(year - 5)
    if prev is not None:
        out["farms_prev"] = _r(prev)
        out["prev_year"] = int(year - 5)
    return out


def nass_county_card(idx: dict, fips: str) -> dict:
    c = idx.get(fips, {})
    out = {}
    for crop, ykey in CROPS.items():
        acres = c.get(f"{crop}:planted_acres", {})
        if acres:
            y = max(acres)
            out[crop] = {"year": int(y), "planted_acres": _r(acres[y]),
                         "yield": _r(c.get(f"{crop}:{ykey}", {}).get(y), 1), "yield_unit": ykey.split("_", 1)[1].replace("_", "/")}
    cattle = c.get("cattle:all", {})
    if cattle:
        y = max(cattle)
        out["cattle"] = {"year": int(y), "head": _r(cattle[y]), "beef_cows": _r(c.get("cattle:beef_cows", {}).get(y))}
    return out


def rap_card(rap: pd.DataFrame, fips: str, asof: pd.Timestamp) -> dict | None:
    g = rap[rap["geo"] == fips]
    if g.empty:
        return None
    out: dict = {}
    cov = g[g["var"].str.startswith("cover:")]
    if not cov.empty:
        cov = cov.assign(k=cov["var"].str.split(":").str[1], y=cov["date"].dt.year)
        last = int(cov["y"].max())
        now = cov[cov["y"] == last].set_index("k")["value"]
        base = cov[cov["y"].between(*BASELINE_YEARS)].groupby("k")["value"].mean()
        out["cover"] = {"year": last, "now": {k: _r(now.get(k), 1) for k in COVER},
                        "baseline": {k: _r(base.get(k), 1) for k in COVER}, "baseline_years": list(BASELINE_YEARS)}
    prod = g[g["var"] == "prod:her_lb_ac"]
    if not prod.empty:
        latest = prod["date"].max()
        y = latest.year
        ytd = prod[prod["date"].dt.year == y]["value"].sum()
        # Same calendar date in earlier years (not day-of-year, which shifts a day in leap years).
        past = [prod[(prod["date"].dt.year == yy) & (prod["date"] <= latest - pd.DateOffset(years=y - yy))]["value"].sum()
                for yy in range(y - 10, y)]
        past = [p for p in past if p > 0]
        normal = sum(past) / len(past) if len(past) >= 8 else None
        out["production"] = {"through": latest.date().isoformat(), "ytd_lb_ac": _r(ytd),
                             "normal_lb_ac": _r(normal), "pct_of_normal": _r(100 * ytd / normal) if normal else None}
    return out or None


def cdl_card(idx: dict, fips: str, top: int = 6) -> dict | None:
    """Leading crop classes in either comparison year, with shares of all county land."""
    by_year: dict[int, dict[str, float]] = {}
    for var, values in idx.get(fips, {}).items():
        cls = var.split(":", 1)[1]
        if cls not in CDL_NOT_LAND:
            for year, acres in values.items():
                by_year.setdefault(year, {})[cls] = acres

    land_by_year = {year: sum(acres.values()) for year, acres in by_year.items()}
    years = [year for year, land in land_by_year.items() if land > 0]
    if not years:
        return None
    year, first = max(years), min(years)
    now = by_year[year]
    then = by_year[first] if first != year else {}
    crops = (now.keys() | then.keys()) - NOT_CROP - DEVELOPED - {"aquaculture"}
    ranked = sorted(
        (k for k in crops if not k.startswith("class_") and max(now.get(k, 0), then.get(k, 0)) > 0),
        key=lambda k: (-max(now.get(k, 0), then.get(k, 0)), k),
    )[:top]
    if not ranked:
        return None
    rows = []
    for k in ranked:
        acres = now.get(k, 0)
        row = {"id": k, "acres": _r(acres), "pct": _r(100 * acres / land_by_year[year], 1)}
        if first != year:
            row["acres_then"] = _r(then.get(k, 0))
        rows.append(row)
    return {"year": int(year), "since": int(first) if first != year else None, "classes": rows}


DEVELOPED = {"developed_open_space", "developed_low_intensity", "developed_med_intensity", "developed_high_intensity"}
# Non-crop cover comes from a base layer NASS reworks between years, so its year-to-year differences are mostly
# method, not land (Blacklands "gained" 1.3 million acres of grassland 2023 to 2025). Only crops get a change.
NOT_CROP = {"developed", "grassland_pasture", "deciduous_forest", "evergreen_forest", "mixed_forest", "shrubland",
            "woody_wetlands", "herbaceous_wetlands", "barren", "wetlands", "forest", "clouds_no_data", "nonag_undefined"}


def district_crop_mix(fipss: list[str], cdl_idx: dict, top: int = 8) -> dict | None:
    """District land cover from the Cropland Data Layer: the newest year every county has, against the earliest
    such year. Our sum of county acres; developed classes are combined. Shares are of land (no water)."""
    years = [{y for v in cdl_idx.get(f, {}).values() for y in v} for f in fipss]
    if not years or not all(years):
        return None
    common = set.intersection(*years)
    if not common:
        return None
    y1, y0 = max(common), min(common)

    def totals(y):
        t: dict[str, float] = {}
        for f in fipss:
            for k, v in cdl_idx[f].items():
                if y in v:
                    cls = k.split(":", 1)[1]
                    cls = "developed" if cls in DEVELOPED else cls
                    t[cls] = t.get(cls, 0.0) + v[y]
        return t

    now, then = totals(y1), totals(y0)
    land = sum(v for k, v in now.items() if k not in CDL_NOT_LAND)
    land0 = sum(v for k, v in then.items() if k not in CDL_NOT_LAND)
    ranked = sorted((k for k in now if k not in CDL_NOT_LAND | {"barren"}), key=lambda k: -now[k])[:top]
    rows = []
    for k in ranked:
        row = {"id": k, "acres": _r(now[k]), "pct": _r(100 * now[k] / land, 1), "crop": k not in NOT_CROP}
        if y0 != y1 and row["crop"]:
            was = then.get(k, 0.0)
            row.update({"acres_then": _r(was), "change_acres": _r(now[k] - was),
                        "change_pts": _r(100 * now[k] / land - 100 * was / land0, 1)})
        rows.append(row)
    return {"year": int(y1), "since": int(y0) if y0 != y1 else None, "land_acres": _r(land), "classes": rows,
            "counties": len(fipss)}


def district_rollup(fipss: list[str], area: dict[str, float], census_idx: dict, county_idx: dict,
                    rap: pd.DataFrame, asof: pd.Timestamp, cdl_idx: dict | None = None) -> dict:
    out: dict = {"counties": len(fipss)}
    mix = district_crop_mix(fipss, cdl_idx or {})
    if mix:
        out["crop_mix"] = mix
    # Census: sums over counties (withheld values are missing, so these are slightly low where withheld).
    cards = [census_card(census_idx, f) for f in fipss]
    cards = [c for c in cards if c]
    if cards:
        year = max(c["year"] for c in cards)
        same = [c for c in cards if c["year"] == year]
        tot = {k: sum(c.get(k, 0) or 0 for c in same) for k in ("farms", "land_in_farms_acres", "sales_usd", "cattle")}
        prev = [c for c in same if c.get("farms_prev") is not None]
        out["census"] = {"year": year, **tot, "counties": len(same),
                         "farms_prev": sum(c["farms_prev"] for c in prev) if len(prev) == len(same) else None,
                         "prev_year": year - 5}
    # NASS county: published counties only, newest year with any county; a LOWER BOUND.
    crops = {}
    for crop in CROPS:
        vals = {f: county_idx.get(f, {}).get(f"{crop}:planted_acres", {}) for f in fipss}
        years = [y for v in vals.values() for y in v]
        if not years:
            continue
        y = max(years)
        pub = {f: v[y] for f, v in vals.items() if y in v}
        crops[crop] = {"year": int(y), "planted_acres": _r(sum(pub.values())), "published_counties": len(pub)}
    out["crops_published"] = crops
    # RAP: forage production % of normal, land-area weighted over counties that have it.
    pcts = [(rap_card(rap, f, asof) or {}).get("production", {}) for f in fipss]
    pairs = [(p["pct_of_normal"], area[f]) for f, p in zip(fipss, pcts) if p.get("pct_of_normal") is not None]
    if pairs:
        through = max(p["through"] for p in pcts if p.get("through"))
        out["forage_pct_of_normal"] = {"pct": _r(sum(v * a for v, a in pairs) / sum(a for _, a in pairs)),
                                       "through": through, "counties": len(pairs)}
    return out
