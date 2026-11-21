"""Build rules: stale hides, out of season says so, no last-season numbers."""
import pandas as pd
import pytest

from kad.build import (
    Freshness, condition_card, forecast_rain_by_county, market_cards, progress_card, rain_by_county,
    rain_estimate, weather_strip,
)
from kad.config import load_region

TX = load_region("tx")


def test_sheep_goat_market_displays_only_current_sale_prices():
    obs = pd.DataFrame([
        {"geo": "ams:2014", "date": pd.Timestamp(day), "var": var, "value": value}
        for day, var, value in (
            ("2026-11-10", "goat_kids:50", 380), ("2026-11-10", "hair_lambs:50", 390),
            ("2026-11-17", "reported", 1), ("2026-11-17", "goat_kids:50", 400),
        )
    ])
    market = market_cards(TX, obs, {}, Freshness(TX, pd.Timestamp("2026-11-21")))[-1]
    assert market["kind"] == "sheep_goats" and market["district"] == "edwards-plateau"
    assert market["series"] == [{"id": "goat_kids:50", "price_cwt": 400, "head": None, "prev": 380, "year_ago": None}]
    stale = market_cards(TX, obs, {}, Freshness(TX, pd.Timestamp("2026-12-02")))[-1]
    assert stale["stale"] and "series" not in stale


def _cond(date, good, exc, crop="corn"):
    rows = [(f"{crop}:good", good), (f"{crop}:excellent", exc), (f"{crop}:fair", 30), (f"{crop}:poor", 10),
            (f"{crop}:very_poor", 100 - good - exc - 40)]
    return [{"geo": "48", "var": v, "date": pd.Timestamp(date), "value": x, "source": "nass"} for v, x in rows]


def test_condition_out_of_season_has_no_numbers():
    df = pd.DataFrame(_cond("2026-08-30", 40, 10))
    card = condition_card(TX, df, "corn", pd.Timestamp("2026-11-20"))
    assert card["status"] == "out_of_season"
    assert card["last_report"] == "2026-08-30"
    assert "classes" not in card and "good_excellent" not in card


def test_condition_in_season_but_old_is_stale():
    df = pd.DataFrame(_cond("2026-06-01", 40, 10))
    card = condition_card(TX, df, "corn", pd.Timestamp("2026-07-01"))
    assert card["status"] == "stale" and "classes" not in card


def test_condition_fresh_compares_week_and_year():
    df = pd.DataFrame(_cond("2026-07-05", 40, 10) + _cond("2026-06-28", 35, 10) + _cond("2025-07-06", 30, 5))
    card = condition_card(TX, df, "corn", pd.Timestamp("2026-07-08"))
    assert card["status"] == "fresh"
    assert (card["good_excellent"], card["last_week"], card["last_year"]) == (50, 45, 35)


def test_progress_five_year_average_needs_all_five_years():
    rows = [{"geo": "48", "var": "wheat:planted", "date": pd.Timestamp(f"{y}-11-{d}"), "value": v, "source": "nass"}
            for y, d, v in [(2026, 15, 84), (2025, 16, 86), (2024, 17, 80), (2023, 12, 90), (2022, 13, 88),
                            (2021, 14, 91), (2026, 8, 82)]]
    card = progress_card(TX, pd.DataFrame(rows), "wheat", pd.Timestamp("2026-11-20"))
    st = card["stages"][0]
    assert (st["pct"], st["last_week"], st["last_year"], st["avg_5yr"]) == (84, 82, 86, 87)
    rows = [r for r in rows if r["date"].year != 2021]
    card = progress_card(TX, pd.DataFrame(rows), "wheat", pd.Timestamp("2026-11-20"))
    assert card["stages"][0]["avg_5yr"] is None


def test_region_counties_complete():
    assert len(TX.counties) == 254
    assert [d["slug"] for d in TX.home_districts] == ["blacklands", "south-central", "edwards-plateau",
                                                      "east-texas-north", "east-texas-south"]
    assert [len(TX.counties_in(d["slug"])) for d in TX.home_districts] == [25, 21, 28, 24, 19]
    assert len(TX.districts) == 15 and all(TX.counties_in(d["slug"]) for d in TX.districts)


def test_district_crops_must_be_weekly_series(tmp_path, monkeypatch):
    import yaml
    from kad import config
    raw = yaml.safe_load((config.REGIONS / "tx.yaml").read_text())
    raw["districts"][0]["crops"] = ["rice"]
    (tmp_path / "tx.yaml").write_text(yaml.safe_dump(raw))
    (tmp_path / "tx-counties.csv").write_text((config.REGIONS / "tx-counties.csv").read_text())
    monkeypatch.setattr(config, "REGIONS", tmp_path)
    with pytest.raises(ValueError, match="crops"):
        config.load_region("tx")


def test_winter_break_is_out_of_season_not_stale():
    df = pd.DataFrame(_cond("2026-11-29", 30, 10, crop="wheat"))
    card = condition_card(TX, df, "wheat", pd.Timestamp("2027-01-12"))
    assert card["status"] == "out_of_season" and "classes" not in card


def test_freshness_quiet_months_pass_health():
    from kad.build import Freshness
    f = Freshness(TX, pd.Timestamp("2027-01-12"))
    f.mark("nass", pd.Timestamp("2026-11-29"))
    assert f.sources["nass"]["stale"] is False and f.sources["nass"]["between_reports"] is True
    f = Freshness(TX, pd.Timestamp("2027-03-12"))
    f.mark("nass", pd.Timestamp("2026-11-29"))
    assert f.sources["nass"]["stale"] is True



def _wx(geo, date, tmax_c, tmin_c, rain_mm, source="nclimgrid"):
    return [{"geo": geo, "var": v, "date": pd.Timestamp(date), "value": x, "source": source}
            for v, x in (("tmax_c", tmax_c), ("tmin_c", tmin_c), ("rain_mm", rain_mm))]


def test_weather_strip_observed_then_pending_then_forecast():
    nc = pd.DataFrame(_wx("A", "2026-11-13", 20, 0, 25.4) + _wx("B", "2026-11-13", 24, 10, 0)
                      + _wx("A", "2026-11-14", 20, 0, 0) + _wx("B", "2026-11-14", 20, 0, 0)
                      + _wx("Z", "2026-11-14", 40, 30, 99))           # not in the district
    fc = pd.DataFrame(_wx("A", "2026-11-14", 5, 5, 5, "nws")           # overlaps observed: dropped
                      + _wx("A", "2026-11-20", 10, -10, 50.8, "nws") + _wx("B", "2026-11-20", 10, -10, 0, "nws"))
    s = weather_strip(nc, fc, {"A": 3.0, "B": 1.0}, pd.Timestamp("2026-11-20"))
    assert s["through"] == "2026-11-14"
    d = s["days"]
    assert [x["date"] for x in d] == ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17",
                                      "2026-11-18", "2026-11-19", "2026-11-20"]
    assert [x["kind"] for x in d] == ["observed"] * 2 + ["pending"] * 5 + ["forecast"]
    assert d[0] == {"date": "2026-11-13", "kind": "observed", "hi_f": 70, "lo_f": 36, "rain_in": 0.75}
    assert d[3] == {"date": "2026-11-16", "kind": "pending", "hi_f": None, "lo_f": None, "rain_in": None}
    assert d[7]["lo_f"] == 14 and d[7]["rain_in"] == 1.5


def test_weather_strip_keeps_only_recent_days_and_works_without_a_forecast():
    nc = pd.DataFrame([r for i in range(50) for r in _wx("A", pd.Timestamp("2026-10-01") + pd.Timedelta(days=i), 20, 10, 0)])
    s = weather_strip(nc, None, {"A": 1.0}, pd.Timestamp("2026-11-20"), days=35)
    kinds = [x["kind"] for x in s["days"]]
    assert kinds.count("observed") == 35 and "forecast" not in kinds and s["days"][-1]["date"] == "2026-11-19"


def test_weather_strip_none_without_data():
    assert weather_strip(pd.DataFrame(columns=["geo", "var", "date", "value"]), None, {"A": 1.0}, pd.Timestamp("2026-11-20")) is None


def test_rain_totals_run_through_noaas_newest_day_and_forecast_is_the_next_7():
    nc = pd.DataFrame([r for i in range(40) for r in _wx("A", pd.Timestamp("2026-10-06") + pd.Timedelta(days=i), 20, 10, 2.54)])
    r = rain_by_county(nc)["A"]
    assert r == {"through": "2026-11-14", "last_7d_in": 0.7, "last_30d_in": 3.0}
    fc = pd.DataFrame([r for i in range(9) for r in _wx("A", pd.Timestamp("2026-11-19") + pd.Timedelta(days=i), 20, 10, 25.4, "nws")])
    assert forecast_rain_by_county(fc, pd.Timestamp("2026-11-20")) == {"A": 7.0}


def _rain(geo, day, mm):
    return {"geo": geo, "var": "rain_mm", "date": pd.Timestamp(day), "value": mm, "source": "stage4"}


def test_weather_strip_fills_pending_rain_with_estimates_where_most_of_the_district_has_one():
    nc = pd.DataFrame(_wx("A", "2026-11-14", 20, 0, 0) + _wx("B", "2026-11-14", 20, 0, 0))
    est = pd.DataFrame([_rain("A", "2026-11-15", 25.4), _rain("B", "2026-11-15", 0),
                        _rain("A", "2026-11-16", 0), _rain("B", "2026-11-16", 0),
                        _rain("Z", "2026-11-17", 50)])                 # not in the district: 11-17 stays pending
    s = weather_strip(nc, None, {"A": 3.0, "B": 1.0}, pd.Timestamp("2026-11-18"), est=est)
    d = {x["date"]: x for x in s["days"]}
    assert d["2026-11-15"] == {"date": "2026-11-15", "kind": "estimated", "hi_f": None, "lo_f": None, "rain_in": 0.75}
    assert d["2026-11-16"]["kind"] == "estimated" and d["2026-11-16"]["rain_in"] == 0
    assert d["2026-11-17"]["kind"] == "pending" and d["2026-11-17"]["rain_in"] is None
    assert s["through"] == "2026-11-14"


def test_rain_estimate_needs_every_day_since_noaas_newest():
    est = pd.DataFrame([_rain("A", "2026-11-15", 12.7), _rain("A", "2026-11-16", 12.7),
                        _rain("B", "2026-11-16", 5),                    # missing 11-15: no figure
                        _rain("A", "2026-11-14", 99)])                  # NOAA has this day: ignored
    out = rain_estimate(est, pd.Timestamp("2026-11-14"))
    assert out == {"A": {"from": "2026-11-15", "through": "2026-11-16", "in": 1.0}}
    assert rain_estimate(est, None) == {}
