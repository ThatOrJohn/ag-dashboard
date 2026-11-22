"""One-report-ahead Texas cotton harvest forecasts and their issue-time history."""
from __future__ import annotations

import math
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import store
from .config import Region

HISTORY = "cotton_harvest"
BASELINE = "seasonal-median-v1"
CANDIDATE = "recent-pace-ridge-v1"
MODEL = CANDIDATE
WEEK = pd.Timedelta(days=7)


def observations(region: Region) -> pd.Series:
    rows = store.read_obs(region, "nass")
    rows = rows[(rows["geo"] == region.state_fips) & (rows["var"] == "cotton:harvested")
                & rows["value"].between(0, 100)]
    return rows.set_index("date")["value"].sort_index()


def _season(series: pd.Series) -> pd.Series:
    # Fall reports form a consistent series. Some year-end and January reports use a different survey.
    if series.empty:
        return series
    return series[series.index.month.isin([8, 9, 10, 11])]


def _training(series: pd.Series) -> pd.DataFrame:
    season = _season(series)
    rows = []
    for week, current in season.items():
        actual = season.get(week + WEEK)
        if current < 100 and actual is not None:
            rows.append({"year": week.year, "week": week.isocalendar().week, "current": current,
                         "pace": _pace(season, week), "gain": actual - current})
    return pd.DataFrame(rows, columns=["year", "week", "current", "pace", "gain"])


def _pace(series: pd.Series, week: pd.Timestamp) -> float | None:
    previous = series.get(week - WEEK)
    return None if previous is None else float(series[week] - previous)


def _predictions(training: pd.DataFrame, week: pd.Timestamp, current: float, pace: float | None) -> dict:
    prior = training[training["year"] < week.year]
    calendar_week = week.isocalendar().week
    nearby = prior[(prior["week"] - calendar_week).abs() <= 1]
    if nearby["year"].nunique() < 2:
        return {}

    baseline_gain = nearby["gain"].median()
    candidate_gain = baseline_gain
    fit = prior.dropna(subset=["pace"])
    if pace is not None and len(fit) >= 12:
        columns = ["week", "current", "pace"]
        center = fit[columns].mean().to_numpy()
        scale = fit[columns].std(ddof=0).replace(0, 1).to_numpy()
        design = (fit[columns].to_numpy() - center) / scale
        mean_gain = fit["gain"].mean()
        weights = np.linalg.solve(design.T @ design + 10 * np.eye(3),
                                  design.T @ (fit["gain"].to_numpy() - mean_gain))
        candidate_gain = mean_gain + ((np.array([calendar_week, current, pace]) - center) / scale) @ weights

    return {BASELINE: round(float(np.clip(current + baseline_gain, current, 100)), 1),
            CANDIDATE: round(float(np.clip(current + candidate_gain, current, 100)), 1)}


def _replay(series: pd.Series) -> list[dict]:
    """Use preceding seasons to train and the prior report to predict the exact next week."""
    season = _season(series)
    training = _training(season)
    rows = []
    for week, current in season.items():
        actual = season.get(week + WEEK)
        if actual is None or current >= 100:
            continue
        predictions = _predictions(training, week, current, _pace(season, week))
        if predictions:
            rows.append({"season": week.year, "actual": float(actual), "predictions": predictions})
    return rows


def _score(rows: list[dict], model: str) -> dict:
    errors = [row["predictions"][model] - row["actual"] for row in rows]
    return {"count": len(errors), "mae": round(float(np.mean(np.abs(errors))), 2),
            "bias": round(float(np.mean(errors)), 2)}


def backtest(series: pd.Series) -> dict:
    rows = _replay(series)
    years = sorted({row["season"] for row in rows})
    return {
        "models": {model: _score(rows, model) for model in (BASELINE, CANDIDATE)} if rows else {},
        "seasons": {year: {model: _score([row for row in rows if row["season"] == year], model)
                           for model in (BASELINE, CANDIDATE)} for year in years},
    }


def _range(series: pd.Series, model: str, estimate: float, current: float) -> list[int] | None:
    errors = [abs(row["predictions"][model] - row["actual"]) for row in _replay(series)]
    if len(errors) < 20:
        return None
    width = float(np.quantile(errors, 0.8, method="higher"))
    return [max(math.floor(current), math.floor(estimate - width)), min(100, math.ceil(estimate + width))]


def _save_history(region: Region, history: dict) -> None:
    folder = region.data_dir / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=folder) as temp:
        path = Path(temp) / f"{HISTORY}.json"
        path.write_text(json.dumps(history, indent=2) + "\n")
        path.replace(folder / path.name)


def refresh(region: Region, *, now: datetime | None = None) -> None:
    if region.id != "tx":
        return
    now = now or datetime.now(timezone.utc)
    today = pd.Timestamp(now.astimezone(ZoneInfo(region.timezone)).date())
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    values = observations(region)
    if values.empty:
        return
    values = values.loc[:today]
    original = store.read_snapshot(region, HISTORY) or {}
    history = {}
    for target, saved in original.items():
        row = saved.copy()
        actual = values.get(pd.Timestamp(target))
        if actual is not None and "actual" not in row:
            row.update(actual=float(actual), scored_at=stamp)
        history[target] = row

    # A new forecast needs a recent fall report and a target week that has yet to end.
    if not values.empty:
        week = values.index[-1]
        target = week + WEEK
        target_key = target.date().isoformat()
        current = float(values[week])
        if week < today < target and target.month in (8, 9, 10, 11) and current < 100 and target_key not in history:
            predictions = _predictions(_training(values), week, current, _pace(values, week))
            if predictions:
                estimate = predictions[MODEL]
                history[target_key] = {
                    "issued_at": stamp, "input_week": week.date().isoformat(), "input_pct": current,
                    "target_week": target_key, "model": MODEL, "estimate": estimate, "predictions": predictions,
                    "range": _range(values[values.index.year < week.year], MODEL, estimate, current),
                }

    if history != original:
        _save_history(region, history)


def site_data(region: Region, asof: pd.Timestamp, *, input_week: str | None) -> dict | None:
    if region.id != "tx":
        return None
    history = store.read_snapshot(region, HISTORY) or {}
    end = (asof + pd.Timedelta(days=1)).tz_localize(region.timezone)
    issued = [row for _, row in sorted(history.items(), reverse=True) if pd.Timestamp(row["issued_at"]) < end]
    if not issued:
        return None

    scored = [row for row in issued if "actual" in row and pd.Timestamp(row["scored_at"]) < end]
    ranged = [row for row in scored if row["range"] is not None]
    errors = [row["estimate"] - row["actual"] for row in scored]
    accuracy = {
        "count": len(scored), "mae": round(float(np.mean(np.abs(errors))), 1),
        "bias": round(float(np.mean(errors)), 1),
        "baseline_mae": round(float(np.mean([abs(row["predictions"][BASELINE] - row["actual"])
                                             for row in scored])), 1),
        "range_count": len(ranged),
        "in_range": sum(row["range"][0] <= row["actual"] <= row["range"][1] for row in ranged),
    } if scored else None

    latest = issued[0]
    active = (latest["input_week"] == input_week and latest not in scored
              and asof <= pd.Timestamp(latest["target_week"]) + pd.Timedelta(days=1))
    results = []
    for row in issued:
        if active and row is latest:
            continue
        result = {key: row[key] for key in ("target_week", "issued_at", "estimate", "range")}
        result["actual"] = row["actual"] if row in scored else None
        results.append(result)
    return {
        "active": {key: latest[key] for key in ("target_week", "issued_at", "input_week", "input_pct", "estimate", "range")}
        if active else None,
        "accuracy": accuracy,
        "history": results,
    }
