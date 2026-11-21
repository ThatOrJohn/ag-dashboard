#!/usr/bin/env python3
"""One-time: build regions/tx-counties.csv (all 254 Texas counties → NASS agricultural statistics district).

District comes from NASS Census of Agriculture 2022 county rows (every county is published there, with its
asd_code). Centroid and land area come from the Census Gazetteer county file, passed as an argument:

    python scripts/make_county_table.py path/to/2025_Gaz_counties_national.txt

Commit the output. Re-run only if NASS redraws districts or a county changes.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kad.adapters.nass import query  # noqa: E402
from kad.config import load_env, slugify  # noqa: E402


def main(gazetteer: str) -> int:
    load_env()
    rows = query({"source_desc": "CENSUS", "year": 2022, "state_alpha": "TX", "agg_level_desc": "COUNTY",
                  "short_desc": "FARM OPERATIONS - NUMBER OF OPERATIONS", "domain_desc": "TOTAL"})
    nass = {r["state_fips_code"] + r["county_code"]: r for r in rows}
    gaz = {}
    with open(gazetteer, newline="") as f:
        for r in csv.DictReader(f, delimiter="|"):
            r = {k.strip(): v.strip() for k, v in r.items()}
            if r["USPS"] == "TX":
                gaz[r["GEOID"]] = r
    assert len(nass) == 254 and len(gaz) == 254, (len(nass), len(gaz))
    out = ROOT / "regions" / "tx-counties.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fips", "county", "district", "district_code", "lat", "lon", "land_sqmi"])
        for fips in sorted(gaz):
            g, n = gaz[fips], nass[fips]
            name = re.sub(r" County$", "", g["NAME"])
            w.writerow([fips, name, slugify(n["asd_desc"]), n["asd_code"], g["INTPTLAT"], g["INTPTLONG"],
                        g["ALAND_SQMI"]])
    print(f"wrote {out.relative_to(ROOT)}: 254 counties")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
