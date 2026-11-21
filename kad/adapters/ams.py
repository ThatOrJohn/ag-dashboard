"""USDA AMS Market News (MyMarketNews / MARS API). Basic auth: key as user, blank password.

Auction reports come back as clean rows (class, frame, muscle grade, avg weight, avg price per cwt, head).
Weight breaks are usually blank, so we bucket by average weight into 100 lb classes and head-weight the
prices: "steers:500" = Medium and Large No. 1 feeder steers averaging 500-599 lb, $/cwt.
Slaughter cows are one series ("cows:slaughter"), all grades and dressings together.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import pandas as pd
from requests import RequestException

from ..config import Region
from ..http import session
from ..report import plain_error

log = logging.getLogger(__name__)
API = "https://marsapi.ams.usda.gov/services/v1.2/reports"
SOURCE = "ams"
FEEDER_GRADE = ("Medium and Large", "1")
WEIGHT_CLASSES = range(300, 1000, 100)
SHEEP_GOAT_SERIES = {
    "hair_lambs:50": ("slaughter sheep/lambs", "hair breeds"),
    "goat_kids:50": ("slaughter goats", "kids"),
}
SHEEP_GOAT_FIELDS = {"report_date", "commodity", "class", "price_unit", "avg_price", "avg_weight", "head_count"}


def _get(slug: int, start: date, end: date, *, section: str = "") -> list[dict]:
    key = os.environ.get("AMS_MMN_API_KEY")
    if not key:
        raise RuntimeError("AMS_MMN_API_KEY is not set")
    s = session()
    s.auth = (key, "")
    path = f"{slug}/{section}" if section else str(slug)
    r = s.get(f"{API}/{path}", params={"q": f"report_begin_date={start:%m/%d/%Y}:{end:%m/%d/%Y}"}, timeout=180)
    r.raise_for_status()
    j = r.json()
    return j.get("results", []) if isinstance(j, dict) else j


def fetch(region: Region, *, weeks: int = 6, start: date | None = None, today: date | None = None):
    """Returns (obs rows, {slug: latest narrative snapshot})."""
    end = today or date.today()
    start = start or end - timedelta(weeks=weeks)
    frames, notes = [], {}
    for rep in region.source("ams").get("reports", []):
        slug = rep["slug"]
        sheep_goats = rep.get("kind") == "sheep_goats"
        try:
            rows = _get(slug, start, end)
            report_rows = rows
            if sheep_goats and not any(SHEEP_GOAT_FIELDS <= row.keys() for row in rows):
                rows = _get(slug, start, end, section="Details")
                report_rows = report_rows + rows
        except RequestException as exc:
            if not sheep_goats:
                raise
            log.warning("AMS report %s: %s", slug, plain_error(exc))
            continue
        frames.append(parse_sheep_goats(slug, rows) if sheep_goats else parse(slug, rows))
        dated = [row for row in report_rows if row.get("report_date")]
        if dated:
            notes[str(slug)] = narrative(rep, dated)
    obs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return obs, notes


def parse(slug: int, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    need = {"report_date", "class", "commodity", "avg_price", "head_count"}
    if df.empty or not need <= set(df.columns):
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["report_date"], format="%m/%d/%Y")
    df = df[(df["price_unit"].fillna("Per Cwt") == "Per Cwt") & df["avg_price"].notna() & (df["head_count"] > 0)]
    geo = f"ams:{slug}"
    out = []

    feeders = df[(df["commodity"] == "Feeder Cattle") & df["class"].isin(["Steers", "Heifers"])
                 & (df["frame"] == FEEDER_GRADE[0]) & (df["muscle_grade"] == FEEDER_GRADE[1])
                 & df["avg_weight"].notna()].copy()
    feeders["wclass"] = (feeders["avg_weight"] // 100 * 100).astype(int)
    feeders = feeders[feeders["wclass"].isin(WEIGHT_CLASSES)]
    for (d, cls, w), g in feeders.groupby(["date", "class", "wclass"]):
        out.append({"geo": geo, "var": f"{cls.lower()}:{w}", "date": d,
                    "value": round((g["avg_price"] * g["head_count"]).sum() / g["head_count"].sum(), 2)})
        out.append({"geo": geo, "var": f"{cls.lower()}:{w}:head", "date": d, "value": float(g["head_count"].sum())})

    cows = df[(df["commodity"] == "Slaughter Cattle") & (df["class"] == "Cows")]
    for d, g in cows.groupby("date"):
        out.append({"geo": geo, "var": "cows:slaughter", "date": d,
                    "value": round((g["avg_price"] * g["head_count"]).sum() / g["head_count"].sum(), 2)})

    # Receipts are repeated per row and vary by report section; the largest is the whole sale's count.
    if "receipts" in df.columns:
        for d, g in df.groupby("date"):
            if g["receipts"].notna().any():
                out.append({"geo": geo, "var": "receipts", "date": d, "value": float(g["receipts"].max())})
    res = pd.DataFrame(out)
    if not res.empty:
        res["source"] = SOURCE
    return res


def parse_sheep_goats(slug: int, rows: list[dict]) -> pd.DataFrame:
    """Head-weight $/cwt lots with an average weight from 50 through 69 lb."""
    df = pd.DataFrame(rows)
    if not SHEEP_GOAT_FIELDS <= set(df.columns):
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["report_date"], format="%m/%d/%Y", errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    for key in ("avg_price", "avg_weight", "head_count"):
        df[key] = pd.to_numeric(df[key], errors="coerce")
    geo = f"ams:{slug}"
    # Keep the sale date even when none of its lots matched, so older prices aren't carried forward.
    out = [{"geo": geo, "var": "reported", "date": d, "value": 1} for d in df["date"].unique()]
    priced = df[df["price_unit"].astype("string").str.strip().str.casefold().eq("per cwt")
                & df["avg_price"].gt(0) & df["head_count"].gt(0) & df["avg_weight"].between(50, 70, inclusive="left")]
    commodity = priced["commodity"].astype("string").str.strip().str.casefold()
    animal_class = priced["class"].astype("string").str.strip().str.casefold()
    for series, (group, cls) in SHEEP_GOAT_SERIES.items():
        for d, lots in priced[commodity.eq(group) & animal_class.eq(cls)].groupby("date"):
            head = lots["head_count"].sum()
            price = (lots["avg_price"] * lots["head_count"]).sum() / head
            out.extend([
                {"geo": geo, "var": series, "date": d, "value": round(price, 2)},
                {"geo": geo, "var": f"{series}:head", "date": d, "value": float(head)},
            ])
    return pd.DataFrame(out).assign(source=SOURCE) if out else pd.DataFrame()


def narrative(rep: dict, rows: list[dict]) -> dict:
    latest = max(rows, key=lambda x: (pd.Timestamp(x["report_date"]), bool(x.get("report_narrative"))))
    return {"slug": rep["slug"], "name": latest.get("report_title") or rep["name"],
            "report_date": pd.Timestamp(latest["report_date"]).date().isoformat(),
            "published": latest.get("published_date"),
            "narrative": (latest.get("report_narrative") or "").strip() or None,
            "url": f"https://mymarketnews.ams.usda.gov/viewReport/{rep['slug']}"}
