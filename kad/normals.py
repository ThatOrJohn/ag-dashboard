"""1991–2020 daily normals per county: running sums while backfilling, then a smoothed table (decision 0013).

  data/<region>/normals/accum.npz        running sums by county × variable × calendar day, months done,
                                         and each month's rain total (for season-to-date bands later)
  data/<region>/normals/daily.parquet    geo, var (hi_c, lo_c, rain_mm), doy (0–365, leap calendar), value
  data/<region>/normals/monthly_rain.parquet   geo, year, month, rain_mm (complete months only)

A day's normal is the 30-year mean for that calendar day, smoothed over a ±15-day window (weighted by how
many years each day has, so Feb. 29's seven or eight years don't make it noisy). Rain's daily normal is the
mean daily total including dry days, so a window's normal is the sum of its days' normals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import store
from .config import Region

VARS = ("hi_c", "lo_c", "rain_mm")
FIRST, LAST = 1991, 2020
HALF_WINDOW = 15
_MDAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_START = np.cumsum((0,) + _MDAYS[:-1])        # leap-calendar day index of each month's 1st


def doy(month: int, day: int) -> int:
    """Calendar-day index on a leap-year calendar: Jan. 1 = 0, Feb. 29 = 59, Dec. 31 = 365."""
    return int(_START[month - 1]) + day - 1


def _days_in(year: int, month: int) -> int:
    return pd.Timestamp(year, month, 1).days_in_month


def _dir(region: Region):
    return region.data_dir / "normals"


class Accumulator:
    def __init__(self, geos: list[str]):
        self.geos = geos
        self.idx = {g: i for i, g in enumerate(geos)}
        self.sum = np.zeros((len(geos), 3, 366))
        self.n = np.zeros((len(geos), 3, 366), dtype=np.int32)
        self.monthly = np.full((len(geos), LAST - FIRST + 1, 12), np.nan)
        self.months: set[str] = set()

    @classmethod
    def load(cls, region: Region) -> "Accumulator":
        geos = [c.fips for c in region.counties]
        acc = cls(geos)
        p = _dir(region) / "accum.npz"
        if p.exists():
            z = np.load(p)
            if list(z["geos"]) == geos:                 # county list changed: start over
                acc.sum, acc.n, acc.monthly = z["sum"], z["n"], z["monthly"]
                acc.months = set(z["months"].tolist())
        return acc

    def add_month(self, year: int, month: int, by_var: list[dict[str, list[float | None]]]) -> None:
        """by_var: [tmax, tmin, prcp], each county FIPS → 31 daily values. Idempotent per month."""
        key = f"{year}-{month:02d}"
        if key in self.months:
            return
        nd = _days_in(year, month)
        start = doy(month, 1)
        for v, table in enumerate(by_var):
            for geo, vals in table.items():
                i = self.idx.get(geo)
                if i is None:
                    continue
                days = vals[:nd]
                for d, x in enumerate(days):
                    if x is not None:
                        self.sum[i, v, start + d] += x
                        self.n[i, v, start + d] += 1
                if v == 2 and all(x is not None for x in days):
                    self.monthly[i, year - FIRST, month - 1] = sum(days)
        self.months.add(key)

    def save(self, region: Region) -> None:
        with store.atomic_write(_dir(region) / "accum.npz") as pending:
            np.savez_compressed(pending, geos=np.array(self.geos), sum=self.sum, n=self.n,
                                monthly=self.monthly, months=np.array(sorted(self.months)))

    def smoothed(self) -> np.ndarray:
        """county × var × day: windowed sum / windowed count, wrapping around the year."""
        k = np.ones(2 * HALF_WINDOW + 1)
        pad = lambda a: np.concatenate([a[..., -HALF_WINDOW:], a, a[..., :HALF_WINDOW]], axis=-1)
        conv = lambda a: np.apply_along_axis(lambda r: np.convolve(r, k, mode="valid"), -1, pad(a))
        s, n = conv(self.sum), conv(self.n.astype(float))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(n > 0, s / n, np.nan)


def write(region: Region, acc: Accumulator) -> None:
    sm = acc.smoothed()
    g, v, d = np.meshgrid(np.arange(len(acc.geos)), np.arange(3), np.arange(366), indexing="ij")
    df = pd.DataFrame({"geo": np.array(acc.geos)[g.ravel()], "var": np.array(VARS)[v.ravel()],
                       "doy": d.ravel().astype(np.int16), "value": sm.ravel().astype(np.float32)})
    gi, yi, mi = np.meshgrid(np.arange(len(acc.geos)), np.arange(LAST - FIRST + 1), np.arange(12), indexing="ij")
    mr = pd.DataFrame({"geo": np.array(acc.geos)[gi.ravel()], "year": (yi.ravel() + FIRST).astype(np.int16),
                       "month": (mi.ravel() + 1).astype(np.int8), "rain_mm": acc.monthly.ravel().astype(np.float32)})
    with store.atomic_write(_dir(region) / "monthly_rain.parquet") as pending:
        mr.dropna().to_parquet(pending, index=False)
    with store.atomic_write(_dir(region) / "daily.parquet") as pending:
        df.dropna().to_parquet(pending, index=False)


def monthly_rain(region: Region) -> pd.DataFrame | None:
    """geo, year, month, rain_mm for 1991–2020 (complete months only), or None before the backfill finishes."""
    p = _dir(region) / "monthly_rain.parquet"
    return pd.read_parquet(p) if p.exists() else None


class Normals:
    """Lookup for the build: county × calendar day → normal high (°C), low (°C) and rain (mm)."""

    def __init__(self, df: pd.DataFrame):
        self.arr: dict[str, np.ndarray] = {}
        for geo, g in df.groupby("geo"):
            a = np.full((366, 3), np.nan)
            a[g["doy"].to_numpy(), g["var"].map({k: i for i, k in enumerate(VARS)}).to_numpy()] = g["value"].to_numpy()
            self.arr[geo] = a

    @classmethod
    def load(cls, region: Region) -> "Normals | None":
        p = _dir(region) / "daily.parquet"
        return cls(pd.read_parquet(p)) if p.exists() else None

    def on(self, geo: str, dates) -> np.ndarray | None:
        """len(dates) × [hi_c, lo_c, rain_mm], or None for a county without normals."""
        a = self.arr.get(geo)
        if a is None:
            return None
        ts = pd.DatetimeIndex(dates)
        return a[[doy(m, d) for m, d in zip(ts.month, ts.day)]]

    def annual_rain_inches(self) -> dict[str, float]:
        """Sum the daily rainfall normals on a typical 365-day calendar."""
        return {geo: float(a[:, 2].sum() - a[doy(2, 29), 2]) / 25.4
                for geo, a in self.arr.items() if np.isfinite(a[:, 2]).all()}
