"""USDA APHIS's public New World screwworm confirmed-detections export."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from .. import http, store
from ..config import Region

FIELDS = {"Animal ID", "State", "County", "Confirmed Date", "Case Type", "Species", "Status"}
CASE_TYPES = {"Domestic", "Wildlife & Feral", "Fly Trap"}


def parse(region: Region, content: str, fetched_at: datetime) -> dict:
    """Validate the full export before accepting it as a new snapshot."""
    reader = csv.DictReader(StringIO(content.lstrip("\ufeff"), newline=""), strict=True)
    if not FIELDS.issubset(reader.fieldnames or []):
        raise ValueError("USDA screwworm CSV is missing required columns")
    counties = {county.name.casefold(): county.fips for county in region.counties}
    today = fetched_at.astimezone(ZoneInfo(region.timezone)).date()
    ids, detections = set(), []
    for row in reader:
        if None in row or any(not (row[field] or "").strip() for field in FIELDS):
            raise ValueError("USDA screwworm CSV has an incomplete detection row")
        case_type, status = row["Case Type"].strip(), row["Status"].strip()
        confirmed = datetime.strptime(row["Confirmed Date"].strip(), "%m/%d/%Y").date()
        animal_id = row["Animal ID"].strip()
        if case_type not in CASE_TYPES or status not in {"Active", "Inactive"} or confirmed > today:
            raise ValueError("USDA screwworm CSV has an unexpected case type, status or date")
        if animal_id in ids:
            raise ValueError("USDA screwworm CSV has a duplicate detection ID")
        ids.add(animal_id)
        if row["State"].strip().casefold() == region.name.casefold():
            fips = counties.get(row["County"].strip().casefold())
            if fips is None:
                raise ValueError("USDA screwworm CSV contains an unknown county for the region")
            detections.append({"fips": fips, "date": confirmed.isoformat(), "fly_trap": case_type == "Fly Trap",
                               "active": status == "Active"})
    if not ids:
        raise ValueError("USDA screwworm CSV is empty")
    return {"fetched_at": fetched_at.isoformat(timespec="seconds"), "detections": detections}


def refresh(region: Region) -> None:
    with http.session() as session:
        response = session.get(region.source("screwworm")["csv_url"], timeout=20)
        response.raise_for_status()
        snapshot = parse(region, response.content.decode("utf-8-sig"), datetime.now(timezone.utc))
    store.write_snapshot(region, "screwworm", snapshot)
