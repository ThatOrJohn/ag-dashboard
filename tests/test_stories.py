import pandas as pd

from kad import stories
from kad.build import _drought_frame
from kad.config import load_region

TX = load_region("tx")


def _usdm(rows):
    """rows: (geo, date, d0..d4) → long store rows."""
    out = []
    for geo, date, *levels in rows:
        for lvl, v in zip(stories.DROUGHT, levels):
            out.append({"geo": geo, "var": f"drought:{lvl}", "date": pd.Timestamp(date), "value": v, "source": "usdm"})
    return pd.DataFrame(out)


def test_county_category_is_worst_class_covering_half():
    assert stories.county_category({"d0": 100, "d1": 80, "d2": 50, "d3": 49.9, "d4": 0}) == "2"
    assert stories.county_category({"d0": 40, "d1": 0, "d2": 0, "d3": 0, "d4": 0}) == "-"


def test_drought_weeks_one_char_per_county_in_roster_order():
    first, second = TX.counties[0].fips, TX.counties[1].fips
    w = _drought_frame(_usdm([
        ("48", "2026-11-10", 60, 40, 20, 5, 1),
        (first, "2026-11-10", 100, 100, 100, 100, 60),
        (second, "2026-11-10", 0, 0, 0, 0, 0),
        (first, "2026-11-17", 100, 0, 0, 0, 0),
    ]))
    out = stories.drought_weeks(w, TX)
    assert out["counties"][:2] == [first, second]
    assert [wk["date"] for wk in out["weeks"]] == ["2026-11-10", "2026-11-17"]
    assert out["weeks"][0]["map"][:2] == "4-"
    assert out["weeks"][1]["map"][:2] == "0?"        # missing county that week
    assert len(out["weeks"][0]["map"]) == len(TX.counties)
    assert out["weeks"][0]["state"]["d1"] == 40.0
    assert "state" not in out["weeks"][1]


def test_cotton_seasons_keep_fall_reports_only():
    nass = pd.DataFrame([
        {"geo": "48", "var": "cotton:harvested", "date": pd.Timestamp(d), "value": v, "source": "nass"}
        for d, v in [("2025-09-07", 10), ("2025-11-23", 70), ("2025-12-31", 27), ("2026-01-04", 90), ("2026-09-06", 12)]
    ])
    out = stories.cotton_seasons(nass, TX)
    assert [(s["year"], [r["pct"] for r in s["reports"]]) for s in out["seasons"]] == [(2025, [10, 70]), (2026, [12])]


def test_stale_sources_leave_their_story_out():
    out = stories.site_data(TX, pd.DataFrame(), pd.DataFrame(), drought_ok=False, nass_ok=False)
    assert set(out) == {"drought", "cotton", "reservoirs", "wells", "river", "cattle", "census", "rain"}
    assert all(v is None for v in out.values())


def _obs(geo, var, values):
    return pd.DataFrame([{"geo": geo, "var": var, "date": pd.Timestamp(d), "value": v, "source": "x"} for d, v in values])


def test_reservoirs_start_in_1950_as_monthly_means():
    res = _obs("statewide", "percent_full", [("1949-12-31", 10), ("1950-01-01", 70), ("1950-01-31", 72), ("1950-02-15", 80)])
    out = stories.reservoir_months(res)
    assert out["months"] == [{"month": "1950-01", "pct": 71.0}, {"month": "1950-02", "pct": 80.0}]
    assert out["through"] == "1950-02-15"


def test_wells_use_the_winter_median():
    gw = _obs("w1", "depth_ft", [("2020-01-05", 100), ("2020-02-05", 102), ("2020-03-05", 110), ("2020-07-01", 150),
                                 ("2021-08-01", 160)])
    out = stories.well_winters(gw, [{"id": "w1", "name": "Test well"}])
    assert out[0]["winters"] == [{"year": 2020, "depth_ft": 102.0}]       # summer pumping and summer-only years left out


def test_river_drops_a_partial_first_month_and_flags_provisional_flow():
    days = pd.date_range("1990-12-26", "1991-02-28")
    flow = pd.concat([_obs("g", "discharge_cfs", [(d, 100) for d in days]),
                      _obs("g", "unapproved", [(d, 1 if d >= pd.Timestamp("1991-02-01") else 0) for d in days])])
    out = stories.river_months(flow, [{"id": "g", "name": "Gauge"}])[0]
    assert [m["month"] for m in out["months"]] == ["1991-01", "1991-02"]
    assert out["provisional_from"] == "1991-02-01"


def test_rain_classes():
    assert [stories.rain_class(x) for x in (0, 0.009, 0.01, 0.3, 0.75, 1.5, 4.3)] == ["0", "0", "1", "2", "3", "4", "5"]
