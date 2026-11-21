"""Texas A&M Forest Service county burn bans, from the daily KMZ behind their burn-ban map.

254 placemarks, one per county, each named by its 3-digit county FIPS padded with spaces ("001       ").
A style URL marks ban / no ban; the two style ids are set in regions/tx.yaml (docs/decisions/0003).
Any other style means TFS changed the file, so we fail rather than guess.
"""
from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone

from ..config import Region
from ..http import session

SOURCE = "burn_bans"
_PLACEMARK = re.compile(r"<Placemark\b.*?</Placemark>", re.S)
_NAME = re.compile(r"<name>\s*(.*?)\s*</name>", re.S)
_STYLE = re.compile(r"<styleUrl>\s*(.*?)\s*</styleUrl>", re.S)


def fetch(region: Region) -> dict:
    cfg = region.source("burn_bans")
    r = session().get(cfg["kmz"], timeout=120)
    r.raise_for_status()
    return parse(r.content, region.state_fips, cfg["ban_style"], cfg["no_ban_style"],
                 last_modified=r.headers.get("Last-Modified"))


def parse(kmz: bytes, state_fips: str, ban_style: str, no_ban_style: str, last_modified: str | None = None) -> dict:
    z = zipfile.ZipFile(io.BytesIO(kmz))
    kml = z.read(next(n for n in z.namelist() if n.lower().endswith(".kml"))).decode("utf-8", "replace")
    counties = {}
    for pm in _PLACEMARK.findall(kml):
        name, style = _NAME.search(pm), _STYLE.search(pm)
        if not name or not style or not name.group(1).strip().isdigit():
            continue
        fips = state_fips + name.group(1).strip().zfill(3)
        counties[fips] = style.group(1)
    if len(counties) < 250:
        raise ValueError(f"burn-ban KMZ has only {len(counties)} counties; format may have changed")
    styles = Counter(counties.values())
    unknown = set(styles) - {ban_style, no_ban_style}
    if unknown:
        raise ValueError(f"burn-ban KMZ has unknown styles {sorted(unknown)}; check docs/decisions/0003")
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_modified": last_modified,
        "counties": {f: s == ban_style for f, s in counties.items()},
    }
