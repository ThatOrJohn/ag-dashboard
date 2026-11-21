"""USDA AMS Market News (MyMarketNews / MARS API). Basic auth: key as user, blank password.

Auction reports come back as clean rows (class, frame, muscle grade, avg weight, avg price per cwt, head).
Weight breaks are usually blank, so we bucket by average weight into 100 lb classes and head-weight the
prices: "steers:500" = Medium and Large No. 1 feeder steers averaging 500-599 lb, $/cwt.
Slaughter cows are one series ("cows:slaughter"), all grades and dressings together.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd

from ..config import Region
from ..http import session

API = "https://marsapi.ams.usda.gov/services/v1.2/reports"
SOURCE = "ams"
FEEDER_GRADE = ("Medium and Large", "1")
WEIGHT_CLASSES = range(300, 1000, 100)


def _get(slug: int, start: date, end: date) -> list[dict]:
    key = os.environ.get("AMS_MMN_API_KEY")
    if not key:
        raise RuntimeError("AMS_MMN_API_KEY is not set")
    s = session()
    s.auth = (key, "")
    r = s.get(f"{API}/{slug}", params={"q": f"report_begin_date={start:%m/%d/%Y}:{end:%m/%d/%Y}"}, timeout=180)
    r.raise_for_status()
    j = r.json()
    return j.get("results", []) if isinstance(j, dict) else j


def fetch(region: Region, *, weeks: int = 6, start: date | None = None, today: date | None = None):
    """Returns (obs rows, {slug: latest narrative snapshot})."""
    end = today or date.today()
    start = start or end - timedelta(weeks=weeks)
    frames, notes = [], {}
    for rep in region.source("ams").get("reports", []):
        rows = _get(rep["slug"], start, end)
        if not rows:
            continue
        frames.append(parse(rep["slug"], rows))
        notes[str(rep["slug"])] = narrative(rep, rows)
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


def narrative(rep: dict, rows: list[dict]) -> dict:
    latest = max(rows, key=lambda x: pd.Timestamp(x["report_date"]))
    return {"slug": rep["slug"], "name": latest.get("report_title") or rep["name"],
            "report_date": pd.Timestamp(latest["report_date"]).date().isoformat(),
            "published": latest.get("published_date"),
            "narrative": (latest.get("report_narrative") or "").strip() or None,
            "url": f"https://mymarketnews.ams.usda.gov/viewReport/{rep['slug']}"}
