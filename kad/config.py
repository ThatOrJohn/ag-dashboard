"""Region config. Texas is one YAML file plus a county table in regions/."""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ROOT / "regions"
DATA = Path(os.environ.get("KAD_DATA_DIR", ROOT / "data"))   # pipeline store (data branch in CI)
SITE_OUT = ROOT / "web" / "public" / "data"                  # read by the Astro build, served as-is


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_env() -> None:
    """Read .env.local into the environment if present (never overrides real env vars, e.g. CI secrets)."""
    p = ROOT / ".env.local"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class County:
    fips: str
    name: str
    district: str        # district slug, e.g. "blacklands"
    lat: float
    lon: float
    land_sqmi: float


@dataclass
class Region:
    id: str
    name: str
    state_fips: str
    timezone: str
    districts: list[dict]
    counties: list[County]
    personas: list[dict]
    sources: dict
    extras: dict = field(default_factory=dict)

    @property
    def data_dir(self) -> Path:
        return DATA / self.id

    @property
    def home_districts(self) -> list[dict]:
        return [d for d in self.districts if d.get("home")]

    def district(self, slug: str) -> dict:
        return next(d for d in self.districts if d["slug"] == slug)

    def counties_in(self, slug: str) -> list[County]:
        return [c for c in self.counties if c.district == slug]

    def source(self, key: str) -> dict:
        return self.sources.get(key, {})


def load_region(region_id: str) -> Region:
    raw = yaml.safe_load((REGIONS / f"{region_id}.yaml").read_text())
    with (REGIONS / f"{region_id}-counties.csv").open(newline="") as f:
        counties = [County(r["fips"], r["county"], r["district"], float(r["lat"]), float(r["lon"]),
                           float(r["land_sqmi"])) for r in csv.DictReader(f)]
    known = {d["slug"] for d in raw["districts"]}
    unknown = {c.district for c in counties} - known
    if unknown:
        raise ValueError(f"counties reference districts missing from {region_id}.yaml: {sorted(unknown)}")
    return Region(id=raw["id"], name=raw["name"], state_fips=raw["state_fips"], timezone=raw["timezone"],
                  districts=raw["districts"], counties=counties, personas=raw.get("personas", []),
                  sources=raw.get("sources", {}),
                  extras={k: v for k, v in raw.items() if k not in
                          ("id", "name", "state_fips", "timezone", "districts", "personas", "sources")})
