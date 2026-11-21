"""What happened this run, per source, readable at a glance (docs/decisions/0011).

Written three ways at the end of every run:
- a table in the GitHub Actions run summary ($GITHUB_STEP_SUMMARY): source, status, newest figure, note
- annotations (::error / ::warning), which GitHub lists on the run's overview page without opening logs
- the same table on the console, for local runs

Statuses: ok, failed (fetch raised), stale (no new figure within its max age: hidden on the site),
partial (an incremental backfill stopped at its time budget or some items failed), not_due (annual source
fetched recently), deferred (due, but this run's time budget was spent).
"""
from __future__ import annotations

import os
import re


def plain_error(e: BaseException) -> str:
    """Network errors in words a glance can parse; anything else, its first line."""
    text = str(e)
    m = re.search(r"too many (\d{3}) error", text)
    if m:
        code = m.group(1)
        return f"service unavailable (HTTP {code}, still failing after retries)" if code in ("502", "503", "504") \
            else f"HTTP {code}, still failing after retries"
    m = re.search(r"(\d{3}) (Client|Server) Error", text)
    if m:
        return f"HTTP {m.group(1)} ({m.group(2).lower()} error)"
    if "Read timed out" in text or "ReadTimeout" in type(e).__name__ or "timed out" in text:
        return "timed out waiting for the service"
    if "NameResolution" in text or "Failed to resolve" in text:
        return "couldn't look up the server's address (DNS)"
    if "ConnectionError" in type(e).__name__ or "Connection refused" in text or "Max retries exceeded" in text:
        return "couldn't connect to the service"
    return (text.splitlines()[0] if text else type(e).__name__)[:200]

ICON = {"ok": "✅ OK", "failed": "❌ Failed", "stale": "⚠️ Stale (hidden)", "partial": "🔄 Partial",
        "not_due": "⏭️ Not due", "deferred": "⏳ Deferred", "between": "💤 Between reports",
        "no_data": "📭 No data yet", "not_fetched": "· Not fetched this run"}


class RunReport:
    def __init__(self):
        self.events: dict[str, dict] = {}

    def record(self, key: str, status: str, note: str = "") -> None:
        prev = self.events.get(key)
        # A failure in any step for a source wins over an ok from another step.
        if prev and prev["status"] == "failed" and status == "ok":
            return
        self.events[key] = {"status": status, "note": note}

    def rows(self, sources: dict) -> list[dict]:
        """Merge fetch outcomes with the build's freshness (sources from latest.json)."""
        out = []
        for key in dict.fromkeys([*sources, *self.events]):
            src = sources.get(key, {})
            ev = self.events.get(key)
            status, note = (ev["status"], ev["note"]) if ev else ("not_fetched", "")
            if status in ("ok", "not_fetched", "not_due") and not src.get("as_of") and "as_of" in src:
                status, note = "no_data", note or "nothing in the store yet; its section stays hidden until a fetch succeeds"
            elif status in ("ok", "not_fetched", "not_due") and src.get("stale"):
                why = "fetched fine, but" if status == "ok" else "no new fetch, and"
                status, note = "stale", f"{why} the newest figure ({src.get('as_of')}) is past its max age · hidden on the site"
            elif status == "ok" and src.get("between_reports"):
                status = "between"
            elif status == "failed" and src.get("stale"):
                note += " · section hidden on the site"
            as_of = src.get("as_of") or ""
            out.append({"key": key, "name": src.get("name", key), "status": status,
                        "as_of": as_of[:4] if as_of.endswith("-01-01") else as_of, "note": note})
        return out

    def write(self, sources: dict, core: tuple[str, ...] = ("usdm", "nass")) -> None:
        rows = self.rows(sources)
        lines = ["| Source | Status | Newest figure | Note |", "|---|---|---|---|"]
        lines += [f"| {r['name']} | {ICON.get(r['status'], r['status'])} | {r['as_of']} | {r['note'].replace('|', '/')} |"
                  for r in rows]
        bad = [r for r in rows if r["status"] in ("failed", "stale", "partial", "deferred", "no_data")]
        head = (f"**{len(bad)} source(s) need a look:** " + ", ".join(f"{r['name']} ({r['status']})" for r in bad)
                if bad else "**All sources OK.**")
        md = "## Data sources this run\n\n" + head + "\n\n" + "\n".join(lines) + "\n"
        print(md)
        if os.environ.get("GITHUB_ACTIONS"):
            for r in bad:
                level = "error" if r["status"] == "failed" or (r["status"] == "stale" and r["key"] in core) else "warning"
                msg = (r["note"] or r["status"]).replace("\n", " ").replace("%", "%25")
                print(f"::{level} title={r['name']}: {r['status']}::{msg}")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(md + "\n")


REPORT = RunReport()
