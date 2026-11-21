"""Annual sources: due logic, parsers, rollups. No network."""
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from kad import annual, annual_build as ab, build, store
from kad.adapters import cdl, nass_annual, rap
from kad.config import load_region


def region(tmp_path, monkeypatch):
    r = load_region("tx")
    monkeypatch.setattr(type(r), "data_dir", property(lambda self: tmp_path / "tx"))
    return r


def test_due_when_never_fetched_or_older_than_refresh(tmp_path, monkeypatch):
    r = region(tmp_path, monkeypatch)
    assert annual.due(r, "census")
    store.log_fetch(r, "census")
    assert not annual.due(r, "census")
    later = datetime.now(timezone.utc) + timedelta(days=91)
    assert annual.due(r, "census", now=later)          # refresh_days 90: a missed cron just means a later catch-up


def test_failed_or_partial_source_is_not_marked_done(tmp_path, monkeypatch):
    r = region(tmp_path, monkeypatch)
    calls = []
    fake = {
        "census": lambda region, deadline: (pd.DataFrame(), True, []),
        "nass_county": lambda region, deadline: (_ for _ in ()).throw(RuntimeError("down")),
        "cdl": lambda region, deadline: (pd.DataFrame(), False, ["stopped at the time budget"]),
        "rap": lambda region, deadline: calls.append("rap") or (pd.DataFrame(), True, []),
    }
    monkeypatch.setattr(annual, "_adapters", lambda: fake)

    def try_(key, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception:
            return None
    done = annual.run_due(r, try_=try_)
    assert done == ["census", "rap"]
    log = store.read_fetch_log(r)
    assert "census" in log and "rap" in log and "nass_county" not in log and "cdl" not in log
    assert annual.due(r, "nass_county") and annual.due(r, "cdl")     # retried next run


def test_nass_county_drops_other_counties_and_withheld():
    rows = [{"state_fips_code": "48", "county_code": "491", "year": "2025", "Value": "106,000", "domain_desc": "TOTAL"},
            {"state_fips_code": "48", "county_code": "998", "year": "2025", "Value": "500,000", "domain_desc": "TOTAL"},
            {"state_fips_code": "48", "county_code": "331", "year": "2025", "Value": "(D)", "domain_desc": "TOTAL"}]
    out = nass_annual.parse_rows(rows, "corn:planted_acres", "nass_county")
    assert [(r["geo"], r["value"]) for r in out] == [("48491", 106000.0)]
    assert out[0]["date"] == pd.Timestamp(2025, 1, 1)


def test_rap_drops_minus_99():
    cover = [["year", "AFG", "PFG", "SHR", "TRE", "LTR", "BGR"], [2025, 5.0, 32.8, 23.0, 21.5, 7.8, -99]]
    prod = [["date", "year", "doy", "AFG", "PFG", "HER"], ["2026-10-31", 2026, 304, 10, 20, 30.0],
            ["2026-11-16", 2026, -99, -99, -99, -99], ["1986-01-16", 1986, 16, -99, -99, -99]]
    c = rap.parse_cover("48171", cover)
    assert {r["var"] for r in c} == {"cover:afg", "cover:pfg", "cover:shr", "cover:tre", "cover:ltr"}
    p = rap.parse_production("48171", prod)
    assert [(r["date"], r["value"]) for r in p] == [(pd.Timestamp("2026-10-31"), 30.0)]


def test_cdl_acres_are_shares_of_county_land_area():
    names = {1: "corn", 111: "open_water", 176: "grassland_pasture"}
    counts = [5.0, 300.0] + [0.0] * 109 + [100.0] + [0.0] * 64 + [700.0]     # code 0 background, 111 water
    rows = cdl.acres_from_counts("48491", 2025, counts, names, 10_000.0)
    got = {r["var"]: r["value"] for r in rows}
    assert got == {"cdl:corn": 3000.0, "cdl:grassland_pasture": 7000.0, "cdl:open_water": 1000.0}
    assert all(r["date"] == pd.Timestamp(2025, 1, 1) and r["source"] == "cdl" for r in rows)


def test_cdl_rings_are_esri_oriented():
    ccw = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]                      # GeoJSON outer ring (counterclockwise)
    hole_cw = [[0.2, 0.2], [0.2, 0.8], [0.8, 0.8], [0.8, 0.2], [0.2, 0.2]]
    outer, hole = cdl.esri_rings({"type": "Polygon", "coordinates": [ccw, hole_cw]})
    assert cdl._signed_area(outer) < 0 and cdl._signed_area(hole) > 0
    assert len(cdl.esri_rings({"type": "MultiPolygon", "coordinates": [[ccw], [ccw]]})) == 2

def test_rap_card_percent_of_normal_and_baseline():
    recs = []
    for y in range(2016, 2027):
        for d, v in (("-04-01", 100.0), ("-06-01", 200.0), ("-10-01", 100.0)):
            recs.append({"geo": "1", "var": "prod:her_lb_ac", "date": pd.Timestamp(f"{y}{d}"),
                         "value": v if y < 2026 else v / 2, "source": "rap"})
    for y in range(1986, 1996):
        recs.append({"geo": "1", "var": "cover:tre", "date": pd.Timestamp(y, 1, 1), "value": 10.0, "source": "rap"})
    recs.append({"geo": "1", "var": "cover:tre", "date": pd.Timestamp(2025, 1, 1), "value": 20.0, "source": "rap"})
    card = ab.rap_card(pd.DataFrame(recs), "1", pd.Timestamp("2026-11-20"))
    assert card["production"]["pct_of_normal"] == 50
    assert card["cover"]["now"]["tre"] == 20.0 and card["cover"]["baseline"]["tre"] == 10.0


def test_district_crop_total_is_lower_bound_with_count():
    idx = {"a": {"corn:planted_acres": {2025: 100.0, 2024: 90.0}}, "b": {"corn:planted_acres": {2024: 50.0}}, "c": {}}
    out = ab.district_rollup(["a", "b", "c"], {"a": 1, "b": 1, "c": 1}, {}, idx, pd.DataFrame(columns=store.OBS_COLS),
                             pd.Timestamp("2026-11-20"))
    assert out["crops_published"]["corn"] == {"year": 2025, "planted_acres": 100, "published_counties": 1}


def test_district_crop_mix_sums_counties_combines_developed_and_compares_years():
    idx = {
        "A": {"cdl:corn": {2021: 100.0, 2025: 150.0}, "cdl:grassland_pasture": {2021: 800.0, 2025: 700.0},
              "cdl:developed_low_intensity": {2021: 50.0, 2025: 80.0}, "cdl:developed_open_space": {2021: 50.0, 2025: 70.0},
              "cdl:open_water": {2021: 30.0, 2025: 30.0}},
        "B": {"cdl:corn": {2021: 0.0, 2025: 0.0}, "cdl:grassland_pasture": {2021: 1000.0, 2025: 1000.0}},
    }
    m = ab.district_crop_mix(["A", "B"], idx)
    assert m["year"] == 2025 and m["since"] == 2021 and m["land_acres"] == 2000
    rows = {r["id"]: r for r in m["classes"]}
    assert "open_water" not in rows
    # Non-crop cover is not compared across years (NASS reworks that base layer); crops are.
    assert rows["grassland_pasture"] == {"id": "grassland_pasture", "acres": 1700, "pct": 85.0, "crop": False}
    assert rows["developed"]["acres"] == 150 and "change_acres" not in rows["developed"]
    assert rows["corn"]["acres_then"] == 100 and rows["corn"]["change_acres"] == 50 and rows["corn"]["crop"]
    assert [r["id"] for r in m["classes"]][0] == "grassland_pasture"


def test_district_crop_mix_needs_every_county():
    idx = {"A": {"cdl:corn": {2025: 1.0}}}
    assert ab.district_crop_mix(["A", "B"], idx) is None


def test_county_crop_mix_compares_leading_crops_in_either_year():
    idx = {"A": {
        "cdl:grassland_pasture": {2021: 700, 2025: 800},
        "cdl:open_water": {2021: 50, 2025: 50},
        "cdl:developed_high_intensity": {2021: 120, 2025: 90},
        "cdl:cotton": {2021: 150},
        "cdl:corn": {2021: 30, 2025: 100},
        "cdl:sorghum": {2025: 10},
    }}
    assert ab.cdl_card(idx, "A") == {"year": 2025, "since": 2021, "classes": [
        {"id": "cotton", "acres": 0, "pct": 0, "acres_then": 150},
        {"id": "corn", "acres": 100, "pct": 10, "acres_then": 30},
        {"id": "sorghum", "acres": 10, "pct": 1, "acres_then": 0},
    ]}
    assert ab.cdl_card(idx, "B") is None
    assert ab.cdl_card({"B": {"cdl:corn": {2024: 100}}}, "B") == {
        "year": 2024, "since": None, "classes": [{"id": "corn", "acres": 100, "pct": 100}],
    }


def test_build_shows_current_rap_cover_with_stale_forage(tmp_path, monkeypatch):
    r = region(tmp_path, monkeypatch)
    monkeypatch.setattr(build, "SITE_OUT", tmp_path / "site")
    fips = "48491"
    store.upsert_obs(r, "rap", pd.DataFrame([
        {"geo": fips, "var": "cover:ltr", "date": pd.Timestamp("1990-01-01"), "value": 5.5, "source": "rap"},
        {"geo": fips, "var": "cover:ltr", "date": pd.Timestamp("2025-01-01"), "value": 7.8, "source": "rap"},
        {"geo": fips, "var": "prod:her_lb_ac", "date": pd.Timestamp("2023-11-16"), "value": 30, "source": "rap"},
    ]))
    latest = build.build(r, asof=date(2026, 11, 21))
    assert not latest["sources"]["rap"]["stale"]
    assert latest["sources"]["rap"]["as_of"] == "2025-01-01"
    path = tmp_path / "site" / "tx" / "districts" / "blacklands.json"
    county = next(c for c in json.loads(path.read_text())["counties"] if c["fips"] == fips)
    rap = county["annual"]["rangeland"]
    assert rap["cover"]["now"]["ltr"] == 7.8
    assert rap["cover"]["baseline"]["ltr"] == 5.5
    assert "production" not in rap


def test_new_counties_make_per_county_sources_due_before_refresh_days(tmp_path, monkeypatch):
    # After more districts get the full view, CDL and RAP catch up now instead of waiting out refresh_days.
    r = region(tmp_path, monkeypatch)
    for key in ("cdl", "rap"):
        store.log_fetch(r, key)
    fips = [c.fips for c in r.counties]
    store.write_snapshot(r, "rap_fetched", {f: "2026-11-01T00:00:00+00:00" for f in fips[:-1]})
    rows = [{"geo": f, "var": "corn", "date": pd.Timestamp(y, 1, 1), "value": 1.0, "source": "cdl"}
            for f in fips for y in (2024, 2025) if not (f == fips[-1] and y == 2024)]
    store.upsert_obs(r, "cdl", pd.DataFrame(rows))
    assert annual.due(r, "cdl") and annual.due(r, "rap")
    store.write_snapshot(r, "rap_fetched", {f: "2026-11-01T00:00:00+00:00" for f in fips})
    store.upsert_obs(r, "cdl", pd.DataFrame([{**rows[0], "geo": fips[-1], "date": pd.Timestamp(2024, 1, 1)}]))
    assert not annual.due(r, "cdl") and not annual.due(r, "rap")   # a year no county has (unreleased) isn't owed
