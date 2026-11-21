"""CLI.

  python -m kad backfill   one-time history pull (drought 2 years, auctions 60 weeks) so "a year ago" works
  python -m kad ingest     pull recent data from every weekly/daily source
  python -m kad annual     run the annual sources that are due (--force: all; --only census,cdl)
  python -m kad build      write web/public/data/<region>/*.json from the local store only (fast)
  python -m kad run        ingest + annual (when due) + build + run report (what CI runs)
  python -m kad check      health check CI runs: fail if the core weekly sources have gone stale

Every source is independent: if one is down, the rest still update, and the page hides that source's
section rather than showing old numbers. Each run ends with a per-source report (kad/report.py).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from . import annual, store
from .config import load_env, load_region
from .report import REPORT, plain_error

log = logging.getLogger("kad")


def _try(key, fn, *a, **kw):
    """Run one source step. A failure is logged, reported under `key`, and never stops the run."""
    try:
        res = fn(*a, **kw)
        REPORT.record(key, "ok")
        return res
    except Exception as e:  # keep going; report at the end
        msg = plain_error(e)
        log.warning("%s failed: %s", key, msg)
        REPORT.record(key, "failed", msg)
        _try.failures.append(key)
        return None
_try.failures = []


def _save(region, source, df):
    if df is not None:
        n = store.upsert_obs(region, source, df)
        store.log_fetch(region, source)
        log.info("%s: %d rows", source, n)


def cmd_backfill(region, args):
    from .adapters import ams, usdm
    _save(region, "usdm", _try("usdm", usdm.fetch, region, start=date.today() - timedelta(days=740)))
    res = _try("ams", ams.fetch, region, start=date.today() - timedelta(weeks=60))
    if res is not None:
        _save(region, "ams", res[0])


def cmd_ingest(region, args):
    from .adapters import ams, burnbans, nass, nclimgrid, nws, screwworm, stage4, usdm
    if region.source("screwworm"):
        _try("screwworm", screwworm.refresh, region)
    _save(region, "usdm", _try("usdm", usdm.fetch, region))
    _save(region, "nass", _try("nass", nass.weekly, region, years_back=5 if args.force else None))
    res = _try("ams", ams.fetch, region)
    if res is not None:
        obs, notes = res
        _save(region, "ams", obs)
        store.write_snapshot(region, "ams_notes", notes)
    snap = _try("burn_bans", burnbans.fetch, region)
    if snap is not None:
        store.write_snapshot(region, "burn_bans", snap)
        store.log_fetch(region, "burn_bans")
    observed = _try("nclimgrid", nclimgrid.recent, region)
    if observed is not None:
        obs, finalized = observed
        _save(region, "nclimgrid", obs)
        store.write_snapshot(region, "nclimgrid_final_rain", finalized)
    _save(region, "stage4", _try("stage4", stage4.recent, region))
    fc = _try("nws", nws.fetch, region)
    if fc is not None and not fc.empty:
        region.data_dir.mkdir(parents=True, exist_ok=True)
        fc.to_parquet(region.data_dir / "forecast.parquet", index=False)
        store.log_fetch(region, "nws")


def cmd_annual(region, args):
    annual.run_due(region, budget_s=args.budget, force=args.force,
                   only=args.only.split(",") if args.only else None, try_=_try)


def cmd_build(region, args):
    from .build import build
    out = build(region, asof=date.fromisoformat(args.asof) if args.asof else None, failures=_try.failures)
    stale = [k for k, v in out["sources"].items() if v["stale"]]
    log.info("built %s as of %s; stale or missing: %s", region.id, out["asof"], ", ".join(stale) or "none")
    return out


def cmd_check(region, args) -> int:
    """Fail if a core weekly source (drought, NASS crop progress) is stale: the schedule or a source stalled."""
    import json
    import os
    from .config import SITE_OUT
    latest = json.loads((SITE_OUT / region.id / "latest.json").read_text())
    core = ("usdm", "nass")
    bad = [f"{latest['sources'][k]['name']} (newest {latest['sources'][k]['as_of'] or 'none'})"
           for k in core if latest["sources"][k]["stale"]]
    healthy = not bad
    msg = "core weekly sources are current" if healthy else "stale: " + "; ".join(bad)
    (log.info if healthy else log.error)("health: %s", msg)
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"healthy={'true' if healthy else 'false'}\nmessage={msg}\n")
    return 0 if healthy else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kad")
    ap.add_argument("command", choices=["backfill", "ingest", "annual", "build", "run", "check"])
    ap.add_argument("--region", default="tx")
    ap.add_argument("--asof", help="build as of this date (testing), YYYY-MM-DD")
    ap.add_argument("--force", action="store_true", help="refresh annual sources even if not due and reload NASS history on ingest")
    ap.add_argument("--only", help="annual: comma-separated source keys (census,nass_county,cdl,rap)")
    ap.add_argument("--budget", type=float, default=480, help="annual: seconds this run may spend")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_env()
    region = load_region(args.region)
    if args.command == "check":
        return cmd_check(region, args)
    out = None
    if args.command == "run":
        cmd_ingest(region, args)
        cmd_annual(region, args)
        out = cmd_build(region, args)
    elif args.command == "build":
        out = cmd_build(region, args)
    else:
        {"backfill": cmd_backfill, "ingest": cmd_ingest, "annual": cmd_annual}[args.command](region, args)
    if out is not None:
        REPORT.write(out["sources"])
    elif REPORT.events:
        REPORT.write({k: {"name": region.source(k).get("name", k)} for k in REPORT.events})
    return 0


if __name__ == "__main__":
    sys.exit(main())
