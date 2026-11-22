from contextlib import nullcontext
from types import SimpleNamespace

import pandas as pd
import pytest

from kad import build, config, store, water
from kad.adapters import water as adapter


def test_well_uses_daily_high_and_keeps_publisher_day():
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        text="datetime,water_level(ft below land surface)\n"
             "2026-11-19 23:00:00,432.2\n2026-11-19 01:00:00,431.8\n"
             "2026-11-20 00:00:00,432.6\n2026-11-20 13:00:00,\n",
    )
    daily = adapter.groundwater(SimpleNamespace(get=lambda *a, **kw: response), {"url": "https://example.org/well"})
    assert daily["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-11-19", "2026-11-20"]
    assert daily["value"].tolist() == [431.8, 432.6]


def test_usgs_pages_keep_discharge_and_approval():
    site = {"id": "USGS-08114000"}

    def feature(day, value, status):
        return {"properties": {"monitoring_location_id": site["id"], "unit_of_measure": "ft^3/s",
                               "time": day, "value": value, "approval_status": status}}

    pages = iter([
        {"features": [feature("2026-11-18", "0", "Approved")], "links": [{"rel": "next", "href": "https://example.org/next"}]},
        {"features": [feature("2026-11-19", "170", "Provisional"), feature("2026-11-20", None, "Provisional")]},
    ])

    def get(url, **kwargs):
        page = next(pages)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: page)

    daily = adapter.streamflow(SimpleNamespace(get=get), site, "2026-11-18", "2026-11-20")
    assert daily.pivot(index="date", columns="var", values="value").to_dict() == {
        "discharge_cfs": {"2026-11-18": 0, "2026-11-19": 170},
        "unapproved": {"2026-11-18": 0, "2026-11-19": 1},
    }


def test_seasonal_flow_requires_consecutive_days_and_ranks_ties_at_the_midpoint():
    rows = []
    for year in range(1991, 2021):
        flow = 100 if year <= 2000 else 200 if year <= 2010 else 300
        for day in pd.date_range(end=f"{year}-11-19", periods=7):
            rows.append((day, "discharge_cfs", flow))
    for day in pd.date_range(end="2026-11-19", periods=7):
        rows += [(day, "discharge_cfs", 200), (day, "unapproved", int(day.day == 15))]
    rows.append((pd.Timestamp("2026-11-21"), "discharge_cfs", 500))  # The intervening day is missing.
    day, card = water._stream_card(pd.DataFrame(rows, columns=["date", "var", "value"]))
    assert day == pd.Timestamp("2026-11-19")
    assert card["value"] == 200 and card["percentile"] == 50 and card["baseline_count"] == 30
    assert card["provisional"] is True


def test_refresh_saves_healthy_sites_when_one_download_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(adapter.http, "session", lambda: nullcontext(None))
    region = config.load_region("tx")

    def fetch(client, site):
        if site["id"] == "brazos":
            raise ValueError("missing percent_full")
        return pd.DataFrame({"date": ["2020-11-21"], "value": [72], "var": ["percent_full"]})

    monkeypatch.setattr(adapter, "reservoirs", fetch)
    with pytest.raises(ValueError, match="brazos: missing percent_full"):
        adapter.refresh(region, "twdb_reservoirs")
    assert store.read_obs(region, "twdb_reservoirs")["geo"].tolist() == ["statewide"]
    assert "twdb_reservoirs" not in store.read_fetch_log(region)


def test_water_cards_use_site_freshness_and_publish_with_existing_build(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(build, "SITE_OUT", tmp_path / "site")
    region = config.load_region("tx")
    wells = [("0260303", "2026-11-20", 434), ("0260303", "2026-11-21", 500), ("0260303", "2025-11-22", 430),
             ("0260303", "2021-10-01", 420), ("1151403", "2026-11-13", 220)]
    reservoir = [("statewide", "2026-11-21", 72), ("statewide", "2025-11-21", 73)]
    for source, var, rows in (("twdb_groundwater", "depth_ft", wells),
                              ("twdb_reservoirs", "percent_full", reservoir)):
        store.upsert_obs(region, source, pd.DataFrame(rows, columns=["geo", "date", "value"]).assign(var=var, source=source))

    asof = pd.Timestamp("2026-11-21")
    latest = build.build(region, asof=asof.date())
    assert latest["texas"]["water"][0]["year_ago"] == {"value": 73, "date": "2025-11-21"}
    assert not latest["sources"]["twdb_groundwater"]["stale"]
    district = pd.read_json(tmp_path / "site/tx/districts/northern-high-plains.json", typ="series")
    [well] = district["water"]
    assert well["id"] == "0260303" and well["date"] == "2026-11-20" and well["value"] == 434
    assert well["year_ago"] == {"value": 430, "date": "2025-11-22"}
    assert well["five_years_ago"] is None
