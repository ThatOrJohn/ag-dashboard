from datetime import date

import pandas as pd
import pytest

from kad import config, store
from kad.adapters import boll_weevil
from kad.build import Freshness, boll_weevil_card


TX = config.load_region("tx")
WEEK = date(2026, 11, 9)
HOMEPAGE = TX.source("boll_weevil")["url"]
PDF = "/wp-content/uploads/2026/04/Weekly-Report-11-09-2026.pdf"


def section(zone, traps, captures, ytd, acres):
    return f"""{zone}
11/9/2026   COTTON ACREAGE:               Acreage Planted           1,000.00
    TRAPPING INFORMATION (Report Week):  Total Traps Inspected      {traps}
                                         Total Weevils Captured     {captures}
    TRAPPING INFORMATION (YTD):          YTD Weevils Captured       {ytd}
    TREATMENT INFORMATION (Report Week): Number of Acres Treated    {acres}
"""


REPORT = ("Weekly Report\nFor Week Beginning 11/09/2026\n\f"
          + section("Lower Rio Grande Valley (LRGV)", "2,000", "1", "54.00", "1,234.56")
          + "\f" + section("East Texas Maintenance Area (ETMA)", "500.00", "0", "0", "0")
          + section("West Texas Maintenance Area (WTMA)", "0", "0", "0", "0"))


def test_report_link_is_discovered_from_homepage():
    html = f'<a href="https://example.org{PDF}">Other</a><a href="{PDF}">Download Now</a>'
    assert boll_weevil.report_url(HOMEPAGE, html) == HOMEPAGE.rstrip("/") + PDF
    with pytest.raises(ValueError, match="expected one"):
        boll_weevil.report_url(HOMEPAGE, html + '<a href="/Weekly-Report-11-16-2026.pdf">Second</a>')


def test_zone_values_expire_from_report_week(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    snapshot = boll_weevil.parse(REPORT, WEEK)
    assert snapshot["zones"][0] == {"name": "Lower Rio Grande Valley", "traps": 2000, "captures": 1,
                                    "captures_ytd": 54, "acres_treated": 1234.56}
    assert snapshot["zones"][2]["traps"] == 0
    snapshot.update(url=HOMEPAGE.rstrip("/") + PDF, fetched_at="2026-11-24T15:00:00+00:00")
    store.write_snapshot(TX, "boll_weevil", snapshot)

    for day, stale in [("2026-11-23", False), ("2026-11-24", True)]:
        fresh = Freshness(TX, pd.Timestamp(day))
        card = boll_weevil_card(TX, fresh)
        assert card["zones"] == ([] if stale else snapshot["zones"])
        assert card["report_url"] == snapshot["url"]
        assert fresh.sources["boll_weevil"]["as_of"] == "2026-11-09"
        assert fresh.sources["boll_weevil"]["stale"] == stale


@pytest.mark.parametrize("invalid", [
    REPORT.replace("West Texas Maintenance Area (WTMA)", "Other area"),
    REPORT.replace("11/9/2026", "11/2/2026", 1),
    REPORT.replace("54.00", "0"),
])
def test_incomplete_or_inconsistent_report_is_rejected(invalid):
    with pytest.raises(ValueError):
        boll_weevil.parse(invalid, WEEK)
