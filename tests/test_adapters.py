"""Parser tests for the gotchas in docs/feasibility.md. No network."""
import io
import zipfile
from datetime import date

import pandas as pd
import pytest
from requests import Timeout

from kad.adapters import ams, burnbans, nass, nclimgrid, usdm
from kad.config import load_region


class FakeResp:
    def __init__(self, status, text="", data=None):
        self.status_code, self.text, self._data = status, text, data

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, resp):
        self.resp = resp

    def get(self, *a, **kw):
        return self.resp


def test_nass_400_invalid_query_is_empty_not_an_outage(monkeypatch):
    monkeypatch.setenv("NASS_QUICK_STATS_API_KEY", "k")
    http = FakeHttp(FakeResp(400, '{"error":["bad request - invalid query"]}'))
    assert nass.query({"commodity_desc": "CORN"}, http=http) == []


def test_nass_other_errors_raise_and_redact_key(monkeypatch):
    monkeypatch.setenv("NASS_QUICK_STATS_API_KEY", "secretkey")
    http = FakeHttp(FakeResp(500, "boom secretkey"))
    with pytest.raises(nass.NassError) as e:
        nass.query({}, http=http)
    assert "secretkey" not in str(e.value)


@pytest.mark.parametrize("raw,want", [("106,000", 106000.0), (" 42 ", 42.0), ("(D)", None), ("(Z)", None),
                                      ("", None), (None, None), ("n/a", None)])
def test_nass_parse_value(raw, want):
    assert nass.parse_value(raw) == want


def test_nass_stat_key():
    assert nass._stat_key("CORN - PROGRESS, MEASURED IN PCT PLANTED") == "planted"
    assert nass._stat_key("COTTON - PROGRESS, MEASURED IN PCT BOLLS OPENING") == "bolls_opening"
    assert nass._stat_key("PASTURELAND - CONDITION, MEASURED IN PCT VERY POOR") == "very_poor"
    assert nass._stat_key("CORN - ACRES PLANTED") is None


@pytest.mark.parametrize("saved,years_back,want", [
    (None, None, 2021),
    ("2026-11-15", None, 2025),
    ("2023-11-19", None, 2023),
    ("2019-11-17", None, 2021),
    ("2026-11-15", 5, 2021),
])
def test_nass_weekly_reuses_saved_comparison_years(monkeypatch, saved, years_back, want):
    obs = pd.DataFrame() if saved is None else pd.DataFrame({"date": [pd.Timestamp(saved)]})
    monkeypatch.setattr(nass.store, "read_obs", lambda region, source: obs)
    queries = []

    def query(params, **kwargs):
        queries.append(params["year__GE"])
        return []

    monkeypatch.setattr(nass, "query", query)
    nass.weekly(load_region("tx"), years_back=years_back, today=date(2026, 11, 21))
    assert queries and set(queries) == {want}


def test_nclimgrid_skips_finalized_old_rain_and_retries_preliminary(monkeypatch):
    region = load_region("tx")
    monkeypatch.setattr(nclimgrid.store, "read_snapshot", lambda region, name: ["2026-01"])
    calls = []
    csv = "cty,41001,TX: Anderson County,2026,2,PRCP," + ",".join(["1"] * 31)

    class Http:
        def get(self, url, **kwargs):
            calls.append(url)
            if "-202602-cty-scaled" in url and "prcp-" in url:
                return FakeResp(404)
            response = FakeResp(200, csv)
            response.raise_for_status = lambda: None
            return response

    monkeypatch.setattr(nclimgrid, "session", Http)
    obs, finalized = nclimgrid.recent(region, today=pd.Timestamp("2026-06-21"))
    assert not any("-202601-" in url for url in calls)
    assert any("prcp-202602-cty-prelim" in url for url in calls)
    assert any("prcp-202604-cty-scaled" in url for url in calls)
    assert "2026-02" not in finalized and finalized == ["2026-01", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert set(obs.loc[obs["var"] == "rain_mm", "date"].dt.month) == {2, 3, 4, 5, 6}


def test_usdm_parse_keeps_cumulative_levels():
    rows = [{"mapDate": "2026-11-17T00:00:00", "fips": "48331", "none": 0.0, "d0": 100.0, "d1": 100.0,
             "d2": 100.0, "d3": 10.72, "d4": 0.0}]
    df = usdm.parse(rows).set_index("var")["value"]
    assert df["drought:d3"] == 10.72 and df["drought:d1"] == 100.0


def _kmz(placemarks):
    kml = "<kml><Document>" + "".join(
        f"<Placemark><name>{n}</name><styleUrl>{s}</styleUrl></Placemark>" for n, s in placemarks) + "</Document></kml>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", kml)
    return buf.getvalue()


def test_burn_bans_parse_padded_names_and_styles():
    pms = [(f"{i:03d}       ", "#PolyStyle02" if i == 1 else "#PolyStyle00") for i in range(1, 508, 2)]
    snap = burnbans.parse(_kmz(pms), "48", "#PolyStyle02", "#PolyStyle00")
    assert len(snap["counties"]) == 254
    assert snap["counties"]["48001"] is True and snap["counties"]["48003"] is False


def test_burn_bans_zero_bans_is_fine():
    pms = [(f"{i:03d}", "#PolyStyle00") for i in range(1, 508, 2)]
    snap = burnbans.parse(_kmz(pms), "48", "#PolyStyle02", "#PolyStyle00")
    assert not any(snap["counties"].values())


def test_burn_bans_unknown_style_fails_loudly():
    pms = [(f"{i:03d}", "#PolyStyle07") for i in range(1, 508, 2)]
    with pytest.raises(ValueError, match="unknown styles"):
        burnbans.parse(_kmz(pms), "48", "#PolyStyle02", "#PolyStyle00")


def test_ams_buckets_by_weight_and_head_weights_prices():
    base = {"report_date": "11/16/2026", "commodity": "Feeder Cattle", "class": "Steers",
            "frame": "Medium and Large", "muscle_grade": "1", "price_unit": "Per Cwt", "receipts": 4617}
    rows = [{**base, "avg_weight": 520, "avg_price": 400.0, "head_count": 10},
            {**base, "avg_weight": 580, "avg_price": 420.0, "head_count": 30},
            {**base, "avg_weight": 580, "avg_price": 999.0, "head_count": 5, "muscle_grade": "2"},   # other grade
            {**base, "commodity": "Slaughter Cattle", "class": "Cows", "frame": "N/A", "muscle_grade": "N/A",
             "avg_weight": 1200, "avg_price": 120.0, "head_count": 50}]
    df = ams.parse(1955, rows).set_index("var")["value"]
    assert df["steers:500"] == 415.0          # (400*10 + 420*30) / 40
    assert df["steers:500:head"] == 40
    assert df["cows:slaughter"] == 120.0
    assert df["receipts"] == 4617
    assert (ams.parse(1955, rows)["geo"] == "ams:1955").all()


def test_ams_sheep_and_goats_use_comparable_weight_and_price_units():
    base = {"report_date": "11/17/2026", "commodity": "Slaughter Sheep/Lambs", "class": "Hair Breeds",
            "price_unit": "Per Cwt", "avg_weight": "55", "avg_price": "400", "head_count": "10"}
    kid = {**base, "commodity": "Slaughter Goats", "class": "Kids", "avg_price": 450}
    rows = [
        base, {**base, "avg_weight": 69, "avg_price": 420, "head_count": 30}, kid,
        {**base, "avg_weight": 70}, {**base, "avg_weight": 49}, {**base, "price_unit": "Per Head"},
        {**base, "class": "Ewes"}, {**base, "head_count": 0}, {**base, "price_unit": None},
        {**kid, "commodity": "Feeder Goats"}, {**kid, "report_date": "11/24/2026", "avg_weight": 75},
    ]
    obs = ams.parse_sheep_goats(2014, rows)
    assert obs[obs["date"] == pd.Timestamp("2026-11-17")].set_index("var")["value"].to_dict() == {
        "reported": 1, "hair_lambs:50": 415, "hair_lambs:50:head": 40, "goat_kids:50": 450, "goat_kids:50:head": 10,
    }
    assert obs[obs["date"] == pd.Timestamp("2026-11-24")]["var"].tolist() == ["reported"]


def test_ams_can_fetch_sectioned_sheep_goat_report_without_affecting_cattle(monkeypatch):
    region = load_region("tx")
    header = {"report_date": "11/17/2026", "report_narrative": "Auction summary."}
    lot = {"commodity": "Slaughter Goats", "class": "Kids", "price_unit": "Per Cwt",
           "avg_weight": 60, "avg_price": 420, "head_count": 10}
    fail = False

    def get(slug, _start, _end, *, section=""):
        if slug == 2014:
            if not section:
                return [header]
            assert section == "Details"
            if fail:
                raise Timeout("Read timed out")
            return [{"report_date": header["report_date"], **lot}]
        return [{**header, **lot, "commodity": "Feeder Cattle", "class": "Steers",
                 "avg_weight": 540, "frame": "Medium and Large", "muscle_grade": "1"}]

    monkeypatch.setattr(ams, "_get", get)
    obs, notes = ams.fetch(region, today=date(2026, 11, 21))
    assert "goat_kids:50" in set(obs["var"])
    assert notes["2014"]["narrative"] == "Auction summary."
    fail = True
    obs, notes = ams.fetch(region, today=date(2026, 11, 21))
    assert set(obs["geo"]) == {"ams:1955", "ams:3724", "ams:2015"}
    assert "2014" not in notes
