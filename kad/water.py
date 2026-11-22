"""Build site-specific Texas water indicators from saved observations."""
from __future__ import annotations

import pandas as pd

from . import store
from .adapters.water import SOURCES

BASELINE = (1991, 2020)
MIN_BASELINE_YEARS = 20


def _comparison(values: pd.Series, target: pd.Timestamp, tolerance: int) -> dict | None:
    nearest = values.index.get_indexer([target], method="nearest", tolerance=pd.Timedelta(days=tolerance))[0]
    if nearest < 0:
        return None
    return {"date": values.index[nearest].date().isoformat(), "value": round(float(values.iloc[nearest]), 2)}


def _stream_card(rows: pd.DataFrame) -> tuple[pd.Timestamp, dict] | None:
    daily = rows.pivot(index="date", columns="var", values="value").asfreq("D")
    means = daily["discharge_cfs"].rolling(7, min_periods=7).mean().dropna()
    if means.empty:
        return None
    day = means.index[-1]
    flow = means.iloc[-1]
    # Compare equivalent trailing windows ending on the same month and day in each baseline year.
    match_day = day.replace(day=28) if (day.month, day.day) == (2, 29) else day
    baseline = means[(means.index.year >= BASELINE[0]) & (means.index.year <= BASELINE[1])
                     & (means.index < day) & (means.index.month == match_day.month)
                     & (means.index.day == match_day.day)]
    percentile = None
    if len(baseline) >= MIN_BASELINE_YEARS:
        percentile = round(100 * (baseline.lt(flow).sum() + 0.5 * baseline.eq(flow).sum()) / len(baseline))
    approvals = daily["unapproved"].loc[day - pd.Timedelta(days=6):day]
    return day, {"value": round(float(flow), 1), "percentile": percentile,
                 "baseline_years": list(BASELINE), "baseline_count": len(baseline),
                 "provisional": bool(approvals.fillna(1).any())}


def cards(region, fresh) -> tuple[list[dict], dict[str, list[dict]]]:
    statewide, districts = [], {}
    for source in SOURCES:
        cfg = region.source(source)
        if not cfg:
            continue
        observations = store.read_obs(region, source)
        dates = []
        for site in cfg["sites"]:
            rows = observations[observations["geo"] == site["id"]]
            # The reservoir export publishes a current-day estimate. Wells and streams use completed days.
            cutoff = fresh.asof if source == "twdb_reservoirs" else fresh.asof - pd.Timedelta(days=1)
            rows = rows[rows["date"] <= cutoff]
            if rows.empty:
                continue
            if source == "usgs_streamflow":
                result = _stream_card(rows)
                if result is None:
                    continue
                day, card = result
                kind = "streamflow"
            else:
                values = rows.set_index("date")["value"].sort_index()
                day = values.index[-1]
                is_well = source == "twdb_groundwater"
                kind = "groundwater" if is_well else "reservoir"
                card = {
                    "value": round(float(values.iloc[-1]), 2),
                    "year_ago": _comparison(values, day - pd.DateOffset(years=1), 14 if is_well else 0),
                }
                if is_well:
                    card["five_years_ago"] = _comparison(values, day - pd.DateOffset(years=5), 14)
            dates.append(day)
            if (fresh.asof - day).days > cfg["max_age_days"]:
                continue
            card.update(site, kind=kind, source=source, date=day.date().isoformat())
            if site.get("district"):
                districts.setdefault(site["district"], []).append(card)
            else:
                statewide.append(card)
        fresh.mark(source, max(dates, default=None))
    return statewide, districts
