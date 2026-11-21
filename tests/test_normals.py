"""Normals: nClimGrid parsing, running sums, smoothing, and their use in the build."""
import numpy as np
import pandas as pd

from kad import normals
from kad.adapters.nclimgrid import parse
from kad.build import _district_vs_normal, rain_vs_normal, season_rain, weather_strip


def _line(code, name, y, m, var, vals):
    vals = list(vals) + [-999.99] * (31 - len(vals))
    return ",".join(["cty", code, name, str(y), f"{m:02d}", var] + [f"{v:9.2f}" for v in vals])


def test_parse_keeps_state_maps_ncei_code_to_fips_and_drops_padding():
    text = "\n".join([
        _line("01001", "AL: Autauga", 1992, 2, "TMAX", [10] * 29),
        _line("41453", "TX: Travis County", 1992, 2, "TMAX", [21.99] * 29),
        _line("41001", "TX: Odd, Name County", 1992, 2, "TMAX", [5] * 28 + [-999.99]),   # comma in name
    ])
    t = parse(text, "41", "48")
    assert set(t) == {"48453", "48001"}
    assert t["48453"][:29] == [21.99] * 29 and t["48453"][29:] == [None, None]
    assert t["48001"][28] is None and t["48001"][0] == 5.0


def test_doy_is_a_leap_calendar():
    assert normals.doy(1, 1) == 0 and normals.doy(2, 29) == 59 and normals.doy(3, 1) == 60 and normals.doy(12, 31) == 365


def _acc_with(value_by_month):
    acc = normals.Accumulator(["48001"])
    for (y, m), (hi, lo, rain) in value_by_month.items():
        nd = pd.Timestamp(y, m, 1).days_in_month
        acc.add_month(y, m, [{"48001": [hi] * nd}, {"48001": [lo] * nd}, {"48001": [rain] * nd}])
    return acc


def test_accumulator_sums_by_calendar_day_monthly_rain_and_is_idempotent():
    acc = _acc_with({(1991, 1): (20, 5, 1.0), (1992, 1): (10, 1, 3.0)})
    acc.add_month(1991, 1, [{"48001": [99] * 31}] * 3)          # same month again: ignored
    jan5 = normals.doy(1, 5)
    assert acc.sum[0, 0, jan5] == 30 and acc.n[0, 0, jan5] == 2
    assert acc.monthly[0, 0, 0] == 31.0 and acc.monthly[0, 1, 0] == 93.0
    assert acc.months == {"1991-01", "1992-01"}


def test_smoothing_is_a_weighted_window_that_wraps_the_year():
    acc = normals.Accumulator(["48001"])
    acc.sum[0, 0, :] = 10.0
    acc.n[0, 0, :] = 1
    acc.sum[0, 0, 0] = 10.0 + 31 * 5                         # one spike on Jan. 1
    sm = acc.smoothed()
    assert np.isclose(sm[0, 0, 0], 15.0)                     # spread over the 31-day window
    assert np.isclose(sm[0, 0, 365], 15.0)                   # Dec. 31's window reaches Jan. 1
    assert np.isclose(sm[0, 0, 100], 10.0)
    assert np.isnan(sm[0, 1, 0])                             # no data: no normal


def test_write_and_load_round_trip(tmp_path, monkeypatch):
    acc = _acc_with({(1991, m): (20, 5, 2.0) for m in range(1, 13)})
    monkeypatch.setattr(normals, "_dir", lambda region: tmp_path)
    normals.write(None, acc)
    nm = normals.Normals.load(None)
    a = nm.on("48001", pd.to_datetime(["2026-07-04", "2024-02-29"]))
    assert np.allclose(a[0], [20, 5, 2.0]) and np.allclose(a[1], [20, 5, 2.0])
    assert nm.on("48999", pd.to_datetime(["2026-07-04"])) is None
    mr = pd.read_parquet(tmp_path / "monthly_rain.parquet")
    assert len(mr) == 12 and mr["rain_mm"].iloc[0] == 62.0


class _FlatNormals:
    """Every day: high 20 °C, low 10 °C, rain 2.54 mm (0.1 in)."""
    def on(self, geo, dates):
        return np.tile([20.0, 10.0, 2.54], (len(dates), 1)) if geo == "A" else None


def _wx(geo, date, tmax_c, tmin_c, rain_mm):
    return [{"geo": geo, "var": v, "date": pd.Timestamp(date), "value": x, "source": "nclimgrid"}
            for v, x in (("tmax_c", tmax_c), ("tmin_c", tmin_c), ("rain_mm", rain_mm))]


def _nc(geo, start, n, mm):
    return [{"geo": geo, "var": "rain_mm", "date": pd.Timestamp(start) + pd.Timedelta(days=i), "value": mm,
             "source": "nclimgrid"} for i in range(n)]


def test_rain_vs_normal_over_noaas_latest_30_days():
    nc = pd.DataFrame(_nc("A", "2026-10-10", 36, 1.27) + _nc("B", "2026-10-16", 30, 5.0)
                      + _nc("C", "2026-10-20", 26, 1.0))                     # C misses days: no percentage
    out = rain_vs_normal(nc, _FlatNormals())
    assert out["A"] == {"through": "2026-11-14", "days": 30, "in": 1.5, "normal_in": 3.0, "pct": 50}
    assert "B" not in out                                                   # no normals for B
    assert "C" not in out
    assert rain_vs_normal(nc, None) == {}


def test_district_vs_normal_is_area_weighted_over_counties_that_have_it():
    cards = {"A": {"rain_vs_normal": {"through": "2026-11-14", "days": 30, "in": 1.0, "normal_in": 2.0, "pct": 50}},
             "B": {"rain_vs_normal": {"through": "2026-11-14", "days": 30, "in": 4.0, "normal_in": 2.0, "pct": 200}},
             "C": {}}
    d = _district_vs_normal(cards, {"A": 3.0, "B": 1.0, "C": 5.0})
    assert d["in"] == 1.75 and d["normal_in"] == 2.0 and d["pct"] == 88 and d["counties"] == 2


def test_weather_strip_carries_normal_high_and_low():
    nc = pd.DataFrame(_wx("A", "2026-11-14", 25, 12, 0))
    s = weather_strip(nc, None, {"A": 1.0}, pd.Timestamp("2026-11-17"), nm=_FlatNormals())
    assert s["days"][0]["normal_hi_f"] == 68 and s["days"][0]["normal_lo_f"] == 50
    assert s["days"][-1]["kind"] == "pending" and s["days"][-1]["normal_hi_f"] == 68   # pending days keep normals
    s = weather_strip(nc, None, {"A": 1.0}, pd.Timestamp("2026-11-17"))
    assert "normal_hi_f" not in s["days"][0]


def _monthly(geo, per_year):
    """Years 1991–2020; per_year(y) → that year's rain per month, mm."""
    return pd.DataFrame([{"geo": geo, "year": y, "month": m, "rain_mm": per_year(y)}
                         for y in range(1991, 2021) for m in range(1, 13)])


def test_season_rain_running_total_normal_range_and_rank():
    # Observed: 2.54 mm (0.1 in) every day Jan. 1 – Mar. 31, 2026 → 9.0 in through Mar. 31.
    nc = pd.DataFrame(_nc("A", "2026-01-01", 90, 2.54))
    # Normal: 0.1 in a day. Years: month totals from 1 to 30 × 2.54 mm per day-equivalent (year k ranks k).
    monthly = _monthly("A", lambda y: (y - 1990) * 2.54 * 30 / 10)
    s = season_rain(nc, _FlatNormals(), monthly, {"A": 1.0})
    assert s["through"] == "2026-03-31" and s["start"] == "2026-01-01" and len(s["actual"]) == 90
    assert len(s["normal"]) == 365 and s["actual"][0] == 0.1 and s["to_date_in"] == 9.0
    assert s["normal_to_date_in"] == 9.0 and s["pct"] == 100 and s["normal_year_in"] == 36.5
    assert s["low"][89] < s["normal"][89] < s["high"][89]
    assert s["years"] == 30 and s["range_years"] == [1991, 2020]
    # Years k=1..30 have 0.3k in per month → by Mar. 31, 0.9k in; 9.0 in beats k = 1..9 (k = 10 ties).
    assert s["drier_years"] == 9


def test_season_rain_needs_every_day_and_the_backfill():
    gap = pd.DataFrame(_nc("A", "2026-01-01", 40, 2.54) + _nc("A", "2026-02-15", 10, 2.54))
    monthly = _monthly("A", lambda y: 50.0)
    assert season_rain(gap, _FlatNormals(), monthly, {"A": 1.0}) is None
    full = pd.DataFrame(_nc("A", "2026-01-01", 50, 2.54))
    assert season_rain(full, _FlatNormals(), None, {"A": 1.0}) is None
    assert season_rain(full, None, monthly, {"A": 1.0}) is None
