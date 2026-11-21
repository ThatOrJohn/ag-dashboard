"""Plain-language "this week" headlines for Texas and each home district.

Each sentence comes from one source and is left out when that source is stale. Wording is factual and calm
(CLAUDE.md: plain, non-alarmist language): "eased", "expanded", "held steady", never "crisis" or "severe
threat". Thresholds are small on purpose so a 1-point wobble reads as steady.
"""
from __future__ import annotations

STEADY_PTS = 2          # drought share change (points) that still counts as "held steady"
YEAR_PTS = 10           # mention a year ago only when it differs this much
AHEAD_PTS = 3           # crop progress vs 5-year average
STAGE_VERB = {"planted": "planted", "emerged": "emerged", "harvested": "harvested", "headed": "headed",
              "silking": "silking", "bolls_opening": "with bolls opening", "squaring": "squaring",
              "setting_bolls": "setting bolls", "mature": "mature", "coloring": "coloring", "dented": "dented",
              "dough": "in dough"}
CROP_NAME = {"corn": "Corn", "sorghum": "Sorghum", "cotton": "Cotton", "wheat": "Winter wheat"}


def _p(v: float) -> str:
    return f"{round(v)}%"


def _inches(v: float) -> str:
    if v < 0.05:
        return "almost no rain"
    return f"{v:.1f} inch" if abs(v - 1) < 0.05 else f"{v:.1f} inches"


def drought_sentence(where: str, d: dict | None) -> str | None:
    """`where` reads inside a sentence: "Texas", "the Blacklands"."""
    if not d or not d.get("now"):
        return None
    now, week, year = d["now"]["d1"], (d.get("week_ago") or {}).get("d1"), (d.get("year_ago") or {}).get("d1")
    d0 = d["now"]["d0"]
    if now < 1:
        s = (f"None of {where} is in drought this week" if now == 0
             else f"Less than 1% of {where} is in drought this week")
        s += f", though {_p(d0)} is abnormally dry." if d0 >= 20 else "."
        if week is not None and week >= STEADY_PTS:
            s = s[:-1] + f" (a week ago {_p(week)} was in drought)."
        return s
    if week is None or abs(now - week) < STEADY_PTS:
        s = f"Drought held steady in {where} this week: {_p(now)} is in drought (D1 or worse)."
    elif now < week:
        s = f"Drought eased in {where} this week: {_p(now)} is in drought (D1 or worse), down from {_p(week)}."
    else:
        s = f"Drought expanded in {where} this week: {_p(now)} is in drought (D1 or worse), up from {_p(week)}."
    if year is not None and abs(now - year) >= YEAR_PTS:
        s += f" A year ago, {_p(year)} was in drought."
    worst = d["now"]["d3"]
    if worst >= 25:
        s += f" About {_p(worst)} is in extreme or exceptional drought (D3 or worse)."
    return s


def rain_sentence(past: float | None, vs_normal: dict | None = None, through: str | None = None) -> str | None:
    """NOAA's latest week of rain and, with normals, its latest 30 days against the 1991–2020 normal.
    NOAA runs about a week behind, so the sentence names the day it runs through."""
    if past is None:
        return None
    when = f"the week through {_md(through)}" if through else "the past week"
    s = f"Rain in {when} averaged {_inches(past)}." if past >= 0.05 else f"{when[0].upper()}{when[1:]} brought almost no rain."
    if vs_normal and vs_normal.get("pct") is not None:
        pct = vs_normal["pct"]
        amount = "about normal rain" if 90 <= pct <= 110 else f"about {pct}% of normal rain"
        s += f" The {vs_normal['days']} days through {_md(vs_normal['through'])} brought {amount}."
    return s


def estimate_sentence(est: dict | None) -> str | None:
    """Stage IV rain for the days since NOAA's newest day (decision 0017): said to be an estimate, every time."""
    if not est:
        return None
    if est["in"] < 0.05:
        return f"Radar and rain gauge estimates show almost no rain since then, through {_md(est['through'])}."
    return f"Radar and rain gauge estimates add about {_inches(est['in'])} since then, through {_md(est['through'])}."


def forecast_sentence(ahead: float | None) -> str | None:
    if ahead is None:
        return None
    if ahead < 0.25:
        return "The National Weather Service forecast for the next 7 days looks mostly dry."
    return f"The National Weather Service forecast calls for about {_inches(ahead)} over the next 7 days."


def _md(iso: str) -> str:
    """"2026-11-14" → "Nov. 14" (AP style months, as on the site)."""
    months = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{months[m - 1]} {d}"


def burn_ban_sentence(count: int | None, of: int) -> str | None:
    if count is None:
        return None
    if count == 0:
        return "No counties have a burn ban."
    if count == of:
        return f"All {of} counties have a burn ban."
    return f"{count} of {of} counties have a burn ban."


def crop_sentences(crops: dict, limit: int = 2, *, done: bool = False) -> list[tuple[str, str]]:
    """One sentence per crop with stages under way (5-95%) that have a 5-year average; crops with the biggest
    gap from the average first. `done`: also say when a crop's harvest is complete (persona pages)."""
    picks = []
    for crop, c in crops.items():
        p = c.get("progress") or {}
        if p.get("status") != "fresh":
            continue
        name = CROP_NAME.get(crop, crop.title())
        live = [st for st in p.get("stages", [])
                if st["avg_5yr"] is not None and 5 <= st["pct"] <= 95 and st["stage"] in STAGE_VERB]
        if live:
            gap = max(abs(st["pct"] - st["avg_5yr"]) for st in live)
            if len(live) == 1:
                st = live[0]
                diff = st["pct"] - st["avg_5yr"]
                pace = "ahead of" if diff >= AHEAD_PTS else "behind" if diff <= -AHEAD_PTS else "in line with"
                text = (f"{name} is {_p(st['pct'])} {STAGE_VERB[st['stage']]}, "
                        f"{pace} the 5-year average of {_p(st['avg_5yr'])}.")
            else:
                live = sorted(live, key=lambda st: -st["pct"])[:2]   # the earlier stage first (planted, emerged)
                a, b = live
                text = (f"{name} is {_p(a['pct'])} {STAGE_VERB[a['stage']]} and {_p(b['pct'])} {STAGE_VERB[b['stage']]}, "
                        f"against 5-year averages of {_p(a['avg_5yr'])} and {_p(b['avg_5yr'])}.")
            picks.append((gap, crop, text))
        elif done and any(st["stage"] == "harvested" and st["pct"] >= 100 for st in p.get("stages", [])):
            picks.append((-1, crop, f"{name} harvest is complete."))
    return [(crop, text) for _, crop, text in sorted(picks, key=lambda x: -x[0])[:limit]]


def cattle_sentence(market: dict | None, where: str = "Texas auctions") -> str | None:
    if not market or market.get("stale"):
        return None
    s = next((x for x in market.get("series", []) if x["id"] == "steers:500"), None)
    if not s or s["price_cwt"] is None:
        return None
    out = f"Feeder steers (500–599 lb) averaged ${s['price_cwt']:.2f}/cwt at {where}"
    if s["prev"] is not None:
        d = s["price_cwt"] - s["prev"]
        out += (", about the same as the sale before." if abs(d) < 1 else
                f", {'up' if d > 0 else 'down'} ${abs(d):.2f} from the sale before.")
    else:
        out += "."
    return out


def texas(tx: dict, statewide_market: dict | None, *, all_crops: bool = False) -> dict:
    """`all_crops`: one sentence per crop under way (persona pages pick theirs); otherwise the two with the
    biggest gap from the average."""
    parts = [("usdm", "drought", drought_sentence("Texas", tx.get("drought")))]
    parts += [("nass", f"crop:{c}", s) for c, s in crop_sentences(tx.get("crops", {}), limit=99 if all_crops else 2, done=all_crops)]
    parts.append(("ams", "cattle", cattle_sentence(statewide_market)))
    bb = tx.get("burn_bans")
    parts.append(("burn_bans", "burn_bans", burn_ban_sentence(bb["count"], bb["of"]) if bb else None))
    return _pack(parts)


def district(entry: dict, where: str, market: dict | None) -> dict:
    parts = [("usdm", "drought", drought_sentence(where, entry.get("drought"))),
             ("nclimgrid", "rain", rain_sentence(entry.get("rain_7d_in"), entry.get("rain_vs_normal"),
                                                     entry.get("rain_through"))),
             ("stage4", "rain", estimate_sentence(entry.get("rain_estimate")) if entry.get("rain_7d_in") is not None else None),
             ("nws", "forecast", forecast_sentence(entry.get("rain_next_7d_in"))),
             ("burn_bans", "burn_bans", burn_ban_sentence(entry.get("burn_bans"), entry["counties"])),
             ("ams", "cattle", cattle_sentence(market, market["name"]) if market else None)]
    return _pack(parts)


def _pack(parts: list[tuple[str, str, str | None]]) -> dict:
    """items carry source and topic so a page can keep only the sentences it's about (persona pages)."""
    kept = [{"source": k, "topic": t, "text": s} for k, t, s in parts if s]
    return {"sentences": [x["text"] for x in kept], "sources": sorted({x["source"] for x in kept}), "items": kept}
