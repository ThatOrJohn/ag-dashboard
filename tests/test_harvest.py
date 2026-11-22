from datetime import datetime, timezone

import pandas as pd

from kad import build, harvest, store
from kad.config import load_region


def _save(region, pairs):
    rows = [{"geo": region.state_fips, "var": "cotton:harvested", "date": pd.Timestamp(week),
             "value": value, "source": "nass"} for week, value in pairs]
    store.upsert_obs(region, "nass", pd.DataFrame(rows))


def _seed(region):
    for year in range(2021, 2026):
        weeks = pd.date_range(f"{year}-09-01", periods=12, freq="W-SUN")
        _save(region, zip(weeks, range(10, 82, 6)))


def _refresh(region, date):
    harvest.refresh(region, now=datetime.fromisoformat(date).replace(tzinfo=timezone.utc, hour=19))


def test_forecast_issue_score_and_build_asof(tmp_path, monkeypatch):
    monkeypatch.setattr("kad.config.DATA", tmp_path / "store")
    monkeypatch.setattr(build, "SITE_OUT", tmp_path / "site")
    region = load_region("tx")
    _seed(region)
    _save(region, [("2026-10-04", 30), ("2026-10-11", 35)])
    _refresh(region, "2026-10-12")
    first = store.read_snapshot(region, harvest.HISTORY)["2026-10-18"]
    assert first["range"][0] >= 35
    assert first["range"][0] <= first["estimate"] <= first["range"][1] <= 100
    assert set(first["predictions"]) == {harvest.BASELINE, harvest.CANDIDATE}

    _save(region, [("2026-10-11", 36)])
    _refresh(region, "2026-10-13")
    assert store.read_snapshot(region, harvest.HISTORY) == {"2026-10-18": first}

    _save(region, [("2026-10-18", 42)])
    _refresh(region, "2026-10-19")
    _save(region, [("2026-10-18", 43)])
    _refresh(region, "2026-10-20")
    result = build.build(region, asof=pd.Timestamp("2026-10-20").date())
    outlook = result["texas"]["crops"]["cotton"]["progress"]["harvest_outlook"]
    assert outlook["active"]["target_week"] == "2026-10-25"
    assert outlook["history"][0]["actual"] == 42
    assert outlook["accuracy"]["count"] == 1
    assert outlook["accuracy"]["mae"] == round(abs(first["estimate"] - 42), 1)

    before = harvest.site_data(region, pd.Timestamp("2026-10-13"), input_week="2026-10-11")
    assert before["active"]["input_pct"] == 35
    assert before["accuracy"] is None
    assert before["history"] == []
    assert "actual" not in before["active"]

    # A missing week stays unscored and expires instead of being matched to a later report.
    _save(region, [("2026-11-01", 55)])
    _refresh(region, "2026-11-09")
    expired = harvest.site_data(region, pd.Timestamp("2026-11-09"), input_week="2026-11-01")
    assert expired["active"] is None
    assert expired["history"][0]["target_week"] == "2026-10-25"
    assert expired["history"][0]["actual"] is None
    assert expired["accuracy"]["count"] == 1


def test_backtest_uses_earlier_seasons_and_exact_week_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr("kad.config.DATA", tmp_path)
    region = load_region("tx")
    _refresh(region, "2026-10-12")
    assert store.read_snapshot(region, harvest.HISTORY) is None
    _seed(region)
    earlier = harvest.backtest(harvest.observations(region))["seasons"]
    assert set(earlier) == {2023, 2024, 2025}
    _save(region, [("2026-10-04", 32), ("2026-10-18", 50), ("2026-10-25", 62)])
    later = harvest.backtest(harvest.observations(region))["seasons"]
    assert {year: later[year] for year in earlier} == earlier
    assert later[2026][harvest.BASELINE]["count"] == 1
