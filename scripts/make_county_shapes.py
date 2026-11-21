#!/usr/bin/env python3
"""One-time: regions/tx-counties.geojson, simplified Texas county outlines (EPSG:4326) for RAP queries.

From the Census TIGERweb service, simplified to ~500 m (maxAllowableOffset 0.005°), 4 decimal places.
Commit the output. Re-run only if county lines change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kad.http import session  # noqa: E402

URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"


def main() -> int:
    j = session().get(URL, params={"where": "STATE='48'", "outFields": "GEOID,NAME", "f": "geojson", "outSR": 4326,
                                   "maxAllowableOffset": 0.005, "geometryPrecision": 4}, timeout=180).json()
    feats = sorted(({"type": "Feature", "id": f["properties"]["GEOID"], "properties": {"name": f["properties"]["NAME"]},
                     "geometry": f["geometry"]} for f in j["features"]), key=lambda f: f["id"])
    assert len(feats) == 254, len(feats)
    out = ROOT / "regions" / "tx-counties.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    print(f"wrote {out.relative_to(ROOT)}: {len(feats)} counties, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
