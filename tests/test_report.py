import requests
from urllib3.exceptions import MaxRetryError, ResponseError

from kad.report import RunReport, plain_error


def test_plain_errors():
    e = requests.exceptions.RetryError(MaxRetryError(None, "/x", ResponseError("too many 503 error responses")))
    assert plain_error(e) == "service unavailable (HTTP 503, still failing after retries)"
    assert plain_error(requests.exceptions.ReadTimeout("Read timed out. (read timeout=120)")) == "timed out waiting for the service"
    assert plain_error(RuntimeError("NASS_QUICK_STATS_API_KEY is not set")) == "NASS_QUICK_STATS_API_KEY is not set"
    assert plain_error(requests.HTTPError("404 Client Error: Not Found for url")) == "HTTP 404 (client error)"


def test_report_rows_merge_fetch_and_freshness(capsys, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    r = RunReport()
    r.record("usdm", "ok")
    r.record("nass", "ok")
    r.record("cdl", "failed", "service unavailable (HTTP 503, still failing after retries)")
    r.record("cdl", "ok")                       # a later ok can't hide the failure
    r.record("rap", "partial", "stopped at the time budget")
    sources = {"usdm": {"name": "U.S. Drought Monitor", "as_of": "2026-11-17", "stale": False},
               "nass": {"name": "USDA NASS Quick Stats", "as_of": "2026-09-01", "stale": True},
               "cdl": {"name": "Cropland Data Layer", "as_of": "", "stale": True},
               "rap": {"name": "RAP", "as_of": "2026-11-01", "stale": False}}
    rows = {x["key"]: x for x in r.rows(sources)}
    assert [rows[k]["status"] for k in ("usdm", "nass", "cdl", "rap")] == ["ok", "stale", "failed", "partial"]
    r.write(sources)
    out = capsys.readouterr().out
    assert "**3 source(s) need a look:**" in out
    assert "::error title=USDA NASS Quick Stats: stale::" in out          # core source stale = error
    assert "::error title=Cropland Data Layer: failed::" in out
    assert "::warning title=RAP: partial::" in out
    assert "| U.S. Drought Monitor | ✅ OK | 2026-11-17 |" in summary.read_text()


def test_report_never_fetched_and_annual_years():
    r = RunReport()
    rows = {x["key"]: x for x in r.rows({
        "cdl": {"name": "CDL", "as_of": None, "stale": True},
        "census": {"name": "Census", "as_of": "2022-01-01", "stale": False},
        "usdm": {"name": "USDM", "as_of": "2026-11-17", "stale": False}})}
    assert rows["cdl"]["status"] == "no_data"
    assert rows["census"]["as_of"] == "2022" and rows["census"]["status"] == "not_fetched"
