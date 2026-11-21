"""Parser tests for the gotchas in docs/feasibility.md. No network."""
import io
import zipfile

import pandas as pd
import pytest

from kad.adapters import ams, burnbans, nass, usdm


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
