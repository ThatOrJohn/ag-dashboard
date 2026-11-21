"""Import the published trapping and treatment totals from TBWEF's weekly report."""
from __future__ import annotations

import re
import subprocess
from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from .. import http, store
from ..config import Region

ZONES = {
    "LRGV": "Lower Rio Grande Valley",
    "ETMA": "East Texas Maintenance Area",
    "WTMA": "West Texas Maintenance Area",
}
DATE = r"\d{1,2}/\d{1,2}/\d{4}"
NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"


class ReportLinks(HTMLParser):
    def __init__(self, homepage: str):
        super().__init__()
        self.homepage = homepage
        self.urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        link = dict(attrs).get("href") if tag == "a" else None
        if not link:
            return
        url = urljoin(self.homepage, link)
        parts = urlsplit(url)
        if (parts.scheme == "https" and parts.netloc == urlsplit(self.homepage).netloc
                and re.fullmatch(r"Weekly-Report-[\d-]+\.pdf", parts.path.rsplit("/", 1)[-1], re.I)):
            self.urls.add(url)


def report_url(homepage: str, html: str) -> str:
    links = ReportLinks(homepage)
    links.feed(html)
    if len(links.urls) != 1:
        raise ValueError("expected one weekly report PDF on the TBWEF homepage")
    return next(iter(links.urls))


def _value(section: str, label: str) -> Decimal:
    values = re.findall(rf"\b{label}[ \t]+({NUMBER})[ \t]*$", section, flags=re.M)
    if len(values) != 1:
        raise ValueError(f"expected one TBWEF value for {label}")
    return Decimal(values[0].replace(",", ""))


def parse(content: str, today: date) -> dict:
    weeks = re.findall(rf"For Week Beginning[ \t]+({DATE})\b", content)
    if len(weeks) != 1:
        raise ValueError("expected one TBWEF report week")
    week = datetime.strptime(weeks[0], "%m/%d/%Y").date()
    if week > today:
        raise ValueError("TBWEF report week is in the future")

    names = {f"{name} ({code})": name for code, name in ZONES.items()}
    headings = "|".join(map(re.escape, names))
    sections = re.split(rf"^[ \t]*({headings})[ \t]*$", content.replace("\f", "\n"), flags=re.M)
    zones = {}
    for heading, section in zip(sections[1::2], sections[2::2]):
        dates = re.findall(rf"^[ \t]*(?:Report Date:[ \t]*)?({DATE})\b", section, flags=re.M)
        if heading in zones or not dates or any(datetime.strptime(d, "%m/%d/%Y").date() != week for d in dates):
            raise ValueError(f"unexpected TBWEF section or report date for {heading}")
        traps = _value(section, "Total Traps Inspected")
        captures = _value(section, "Total Weevils Captured")
        ytd = _value(section, "YTD Weevils Captured")
        acres = _value(section, "Number of Acres Treated")
        if (any(n != n.to_integral_value() for n in (traps, captures, ytd))
                or captures > ytd or (captures and not traps)):
            raise ValueError(f"invalid TBWEF trapping totals for {heading}")
        zones[heading] = {"name": names[heading], "traps": int(traps), "captures": int(captures),
                          "captures_ytd": int(ytd), "acres_treated": float(acres)}
    if zones.keys() != names.keys():
        raise ValueError("TBWEF report is missing a reporting area")
    return {"week": week.isoformat(), "zones": list(zones.values())}


def refresh(region: Region) -> None:
    homepage = region.source("boll_weevil")["url"]
    with http.session() as session:
        index = session.get(homepage, timeout=20)
        index.raise_for_status()
        url = report_url(homepage, index.text)
        response = session.get(url, timeout=20)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF-"):
            raise ValueError("TBWEF weekly report download is not a PDF")
    pdf = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"], input=response.content,
                         capture_output=True, check=True, timeout=20)
    now = datetime.now(timezone.utc)
    snapshot = parse(pdf.stdout.decode("utf-8"), now.astimezone(ZoneInfo(region.timezone)).date())
    previous = store.read_snapshot(region, "boll_weevil")
    if previous and snapshot["week"] < previous["week"]:
        raise ValueError("TBWEF homepage links to a report older than the saved report")
    snapshot.update(url=url, fetched_at=now.isoformat(timespec="seconds"))
    store.write_snapshot(region, "boll_weevil", snapshot)
