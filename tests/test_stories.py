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
    assert stories.site_data(TX, pd.DataFrame(), pd.DataFrame(), drought_ok=False, nass_ok=False) == {"drought": None, "cotton": None}
