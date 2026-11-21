from contextlib import nullcontext
from datetime import datetime, timezone

import pandas as pd
import pytest

from kad import config, store
from kad.adapters import screwworm
from kad.build import Freshness, screwworm_card

TX = config.load_region("tx")
FETCHED = datetime(2026, 11, 21, 22, tzinfo=timezone.utc)
CSV = """Animal ID,State,County,Confirmed Date,Case Type,Species,Status
1,Texas,Duval,11/20/2026,Domestic,Cattle,Active
2,Texas,Duval,11/20/2026,Fly Trap,Fly,Active
3,Texas,Duval,11/19/2026,Domestic,Dog,Inactive
4,Texas,Presidio,11/19/2026,Wildlife & Feral,Elk,Inactive
5,New Mexico,Lea,11/20/2026,Domestic,Dog,Active
"""


def test_screwworm_snapshot_counts_and_freshness(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    store.write_snapshot(TX, "screwworm", screwworm.parse(TX, CSV, FETCHED))

    def build_on(day):
        fresh = Freshness(TX, pd.Timestamp(day))
        return screwworm_card(TX, fresh), fresh.sources["screwworm"]

    card, source = build_on("2026-11-23")
    assert source["as_of"] == "2026-11-21"
    assert not source["delayed"] and not source["stale"]
    assert (card["active_animals"], card["animals"], card["fly_traps"]) == (1, 3, 1)
    assert card["recent"] == [
        {"county": "Duval", "date": "2026-11-20", "animals": 1, "fly_traps": 1},
        {"county": "Presidio", "date": "2026-11-19", "animals": 1, "fly_traps": 0},
    ]
    assert card["stale_at"] == "2026-11-24T00:00:00-06:00"
    assert card["hide_at"] == "2026-12-05T00:00:00-06:00"

    for day in ("2026-11-24", "2026-12-04"):
        delayed_card, source = build_on(day)
        assert delayed_card == card and source["delayed"] and not source["stale"]

    hidden_card, source = build_on("2026-12-05")
    assert hidden_card is None and not source["delayed"] and source["stale"]
    assert source["as_of"] == "2026-11-21"
    assert build_on("2026-11-20")[0] is None


def test_screwworm_failed_refresh_keeps_last_good_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    saved = screwworm.parse(TX, CSV, FETCHED)
    store.write_snapshot(TX, "screwworm", saved)

    class Session:
        def get(self, url, timeout):
            assert url == TX.source("screwworm")["csv_url"]
            return self

        def raise_for_status(self):
            pass

        content = b"<html>unexpected server response</html>"

    monkeypatch.setattr(screwworm.http, "session", lambda: nullcontext(Session()))
    with pytest.raises(ValueError, match="missing required columns"):
        screwworm.refresh(TX)
    assert store.read_snapshot(TX, "screwworm") == saved


def test_screwworm_valid_national_export_can_have_no_texas_detections(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    lines = CSV.splitlines()
    snap = screwworm.parse(TX, "\n".join([lines[0], lines[-1]]), FETCHED)
    store.write_snapshot(TX, "screwworm", snap)
    card = screwworm_card(TX, Freshness(TX, pd.Timestamp("2026-11-21")))
    assert card["recent"] == []
    assert (card["active_animals"], card["animals"], card["fly_traps"]) == (0, 0, 0)
