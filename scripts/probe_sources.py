#!/usr/bin/env python3
"""Feasibility probe: what do the candidate sources actually return for the Blacklands?

Stdlib only. Reads NASS_QUICK_STATS_API_KEY from .env.local (or the environment).
Writes data/probe/feasibility.json (gitignored) and prints a summary.
The API key is never printed or written.

    python3 scripts/probe_sources.py                 # everything
    python3 scripts/probe_sources.py burn_bans rap   # just the named probes
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "probe" / "feasibility.json"  # a partial run (named probes) writes feasibility-<names>.json
YEAR = date.today().year

# Featured-district seed counties (FIPS). The NASS district probe below reports the real district roster.
COUNTIES = {"48491": "Williamson", "48331": "Milam", "48027": "Bell", "48145": "Falls", "48309": "McLennan"}
CENTER = (30.65, -97.43)  # roughly Taylor, TX


def load_key() -> str:
    key = os.environ.get("NASS_QUICK_STATS_API_KEY", "")
    env = ROOT / ".env.local"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("NASS_QUICK_STATS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key


def ctx() -> ssl.SSLContext:
    try:
        import certifi  # python.org macOS builds often lack system certs
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL = ctx()
KEY = load_key()


def redact(s: str) -> str:
    return s.replace(KEY, "<key>") if KEY else s


def get(url: str, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "ag-dashboard probe", **(headers or {})})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL) as r:
            body = r.read()
            return {"status": r.status, "secs": round(time.time() - t, 1), "bytes": len(body),
                    "ctype": r.headers.get("Content-Type", ""), "body": body}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "secs": round(time.time() - t, 1), "error": redact(str(e)),
                "body": e.read()[:500]}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "secs": round(time.time() - t, 1), "error": redact(repr(e))}


def nass(params: dict, endpoint: str = "api_GET") -> dict:
    q = urllib.parse.urlencode({"key": KEY, "format": "JSON", **params})
    r = get(f"https://quickstats.nass.usda.gov/api/{endpoint}/?{q}")
    out = {"params": params, "status": r["status"], "secs": r["secs"]}
    if r.get("error"):
        out["error"] = r["error"]
        out["detail"] = r.get("body", b"")[:300].decode("utf-8", "replace")
        return out
    data = json.loads(r["body"])
    if endpoint != "api_GET":
        out["result"] = data
        return out
    rows = data.get("data", [])
    vals = [x.get("Value", "").strip() for x in rows]
    out.update({
        "rows": len(rows),
        "suppressed": sum(v in ("(D)", "(Z)", "(NA)", "(X)", "(S)") for v in vals),
        "years": sorted({x.get("year") for x in rows})[-6:],
        "latest_week": max((x.get("week_ending", "") for x in rows), default=""),
        "geos": dict(Counter(x.get("county_name") or x.get("asd_desc") or x.get("state_alpha") for x in rows).most_common(40)),
        "short_desc": sorted({x.get("short_desc") for x in rows})[:12],
        "sample": [{k: x.get(k) for k in ("year", "reference_period_desc", "week_ending", "county_name",
                                          "asd_desc", "short_desc", "Value")} for x in rows[:5]],
    })
    return out


def probe_nass() -> dict:
    if not KEY:
        return {"skipped": "no NASS_QUICK_STATS_API_KEY"}
    base = {"source_desc": "SURVEY", "state_alpha": "TX"}
    res = {}
    res["asd_names"] = nass({"param": "asd_desc", "state_alpha": "TX"}, "get_param_values")
    for crop in ("CORN", "COTTON", "SORGHUM", "WHEAT"):
        res[f"progress_state_{crop}"] = nass({**base, "commodity_desc": crop, "statisticcat_desc": "PROGRESS",
                                             "agg_level_desc": "STATE", "year": YEAR})
        res[f"condition_state_{crop}"] = nass({**base, "commodity_desc": crop, "statisticcat_desc": "CONDITION",
                                              "agg_level_desc": "STATE", "year": YEAR})
        res[f"planted_district_{crop}"] = nass({**base, "commodity_desc": crop, "statisticcat_desc": "AREA PLANTED",
                                               "agg_level_desc": "AGRICULTURAL DISTRICT", "year__GE": YEAR - 5})
        res[f"planted_county_blacklands_{crop}"] = nass({**base, "commodity_desc": crop,
                                                        "statisticcat_desc": "AREA PLANTED",
                                                        "agg_level_desc": "COUNTY", "asd_desc": "BLACKLANDS",
                                                        "year__GE": YEAR - 5})
    res["cattle_inventory_county_blacklands"] = nass({**base, "commodity_desc": "CATTLE",
                                                     "statisticcat_desc": "INVENTORY", "agg_level_desc": "COUNTY",
                                                     "asd_desc": "BLACKLANDS", "year__GE": YEAR - 5})
    res["hay_production_county_blacklands"] = nass({**base, "commodity_desc": "HAY",
                                                   "statisticcat_desc": "PRODUCTION", "agg_level_desc": "COUNTY",
                                                   "asd_desc": "BLACKLANDS", "year__GE": YEAR - 5})
    res["pasture_condition_state"] = nass({**base, "commodity_desc": "PASTURELAND",
                                          "statisticcat_desc": "CONDITION", "agg_level_desc": "STATE",
                                          "year": YEAR})
    res["census_farms_county_williamson"] = nass({"source_desc": "CENSUS", "state_alpha": "TX",
                                                 "county_name": "WILLIAMSON", "commodity_desc": "FARM OPERATIONS",
                                                 "agg_level_desc": "COUNTY"})
    return res


def probe_cdl() -> dict:
    res = {}
    for fips, name in list(COUNTIES.items())[:2]:
        for yr in (YEAR - 1, YEAR - 2):
            r = get(f"https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLStat?year={yr}&fips={fips}&format=json")
            res[f"{name}_{yr}"] = {k: v for k, v in r.items() if k != "body"} | {
                "preview": r.get("body", b"")[:400].decode("utf-8", "replace")}
    return res


def probe_usdm() -> dict:
    end = date.today()
    start = end - timedelta(days=60)
    res = {}
    for fips, name in list(COUNTIES.items())[:2]:
        url = ("https://usdmdataservices.unl.edu/api/CountyStatistics/GetDroughtSeverityStatisticsByAreaPercent"
               f"?aoi={fips}&startdate={start:%-m/%-d/%Y}&enddate={end:%-m/%-d/%Y}&statisticsType=1")
        r = get(url, {"Accept": "application/json"})
        res[name] = {k: v for k, v in r.items() if k != "body"} | {
            "preview": r.get("body", b"")[:600].decode("utf-8", "replace")}
    return res


def probe_ams() -> dict:
    # MyMarketNews API needs its own free key (basic auth); unauthenticated status tells us it's reachable.
    r = get("https://marsapi.ams.usda.gov/services/v1.2/reports")
    return {k: v for k, v in r.items() if k != "body"} | {
        "note": "needs a MyMarketNews API key (basic auth) for real pulls",
        "preview": r.get("body", b"")[:200].decode("utf-8", "replace")}


def probe_weather() -> dict:
    """NOAA nClimGrid-Daily (observed, ~a week behind) and the NWS API (forecast); decision 0014."""
    lat, lon = CENTER
    month = date.today().strftime("%Y%m")
    nc = get(f"https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/{date.today().year}/ncdd-{month}-version.txt")
    nws = get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
    return {"nclimgrid": {k: v for k, v in nc.items() if k != "body"} | {
                "version": nc.get("body", b"")[:120].decode("utf-8", "replace")},
            "nws_points": {k: v for k, v in nws.items() if k != "body"} | {
                "preview": nws.get("body", b"")[:300].decode("utf-8", "replace")}}


def probe_pages() -> dict:
    # Burn bans / fire danger: confirm reachability; the machine-readable feed still has to be found.
    return {u: {k: v for k, v in get(u).items() if k != "body"} for u in (
        "https://tfsweb.tamu.edu/",
        "https://texasforestservice.tamu.edu/",
        "https://rangelands.app/",
    )}


def probe_burn_bans() -> dict:
    # TFS publishes the daily burn-ban map as a KMZ (zipped KML); counties under a ban are filled red.
    import io, re, zipfile
    r = get("https://tfsfrp.tamu.edu/WILDFIRES/Burn_Ban.kmz")
    out = {k: v for k, v in r.items() if k != "body"}
    try:
        z = zipfile.ZipFile(io.BytesIO(r["body"]))
        kml = z.read([n for n in z.namelist() if n.endswith(".kml")][0]).decode("utf-8", "replace")
        out["placemarks"] = kml.count("<Placemark")
        out["names_sample"] = re.findall(r"<name>(.*?)</name>", kml)[:15]
        out["styles"] = sorted(set(re.findall(r"<styleUrl>(.*?)</styleUrl>", kml)))[:10]
        out["head"] = kml[:800]
    except Exception as e:  # noqa: BLE001
        out["parse_error"] = repr(e)
    return out


def probe_rap() -> dict:
    # Rangeland Analysis Platform time-series API: POST a GeoJSON Feature, get a weighted-mean table back.
    box = [[-98.95, 30.20], [-98.80, 30.20], [-98.80, 30.32], [-98.95, 30.32], [-98.95, 30.20]]  # near Fredericksburg
    res = {}
    for ep in ("coverV3", "production16dayV3"):
        body = json.dumps({"type": "Feature", "properties": {"mask": True, "year": None},
                           "geometry": {"type": "Polygon", "coordinates": [box]}}).encode()
        req = urllib.request.Request(f"https://us-central1-rap-data-365417.cloudfunctions.net/{ep}", data=body,
                                     headers={"Content-Type": "application/json", "User-Agent": "ag-dashboard probe"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180, context=SSL) as r:
                props = json.loads(r.read())["properties"]
            table = next(v for v in props.values() if isinstance(v, list))
            res[ep] = {"status": 200, "secs": round(time.time() - t, 1), "rows": len(table) - 1,
                       "header": table[0], "last": table[-3:]}
        except Exception as e:  # noqa: BLE001
            res[ep] = {"status": None, "secs": round(time.time() - t, 1), "error": repr(e)}
    return res


def main() -> int:
    probes = {"nass": probe_nass, "cropland_data_layer": probe_cdl, "drought_monitor": probe_usdm,
              "ams_market_news": probe_ams, "weather": probe_weather, "pages": probe_pages,
              "burn_bans": probe_burn_bans, "rap": probe_rap}
    only = set(sys.argv[1:])
    if only:
        probes = {k: v for k, v in probes.items() if k in only}
    results = {"run_at": date.today().isoformat(), "year": YEAR}
    for name, fn in probes.items():
        print(f"probing {name} ...", flush=True)
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001  one bad source never stops the run
            results[name] = {"error": redact(repr(e))}
    out = OUT if not only else OUT.with_name(f"feasibility-{'-'.join(sorted(only))}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(redact(json.dumps(results, indent=2, default=str)))
    print(f"\nwrote {out.relative_to(ROOT)}")
    nr = results.get("nass", {})
    for k, v in nr.items():
        if isinstance(v, dict) and "rows" in v:
            print(f"  nass {k:42s} rows={v['rows']:<5} suppressed={v['suppressed']:<4} years={v['years']} latest_week={v['latest_week']}")
        elif isinstance(v, dict):
            print(f"  nass {k:42s} status={v.get('status')} {v.get('error', '')}")
    for name in ("cropland_data_layer", "drought_monitor", "ams_market_news", "weather", "pages", "burn_bans", "rap"):
        if name not in results:
            continue
        v = results.get(name, {})
        items = v.items() if isinstance(v, dict) and all(isinstance(x, dict) for x in v.values()) else [(name, v)]
        for k, x in items:
            print(f"  {name:20s} {str(k)[:40]:40s} status={x.get('status')} secs={x.get('secs')} {x.get('error', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
