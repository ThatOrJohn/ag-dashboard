from kad import headline as h


def D(now, week=None, year=None, d0=None, d3=0):
    lv = lambda x, z=0: {"d0": d0 if d0 is not None else x, "d1": x, "d2": 0, "d3": z, "d4": 0}
    return {"now": lv(now, d3), "week_ago": lv(week) if week is not None else None,
            "year_ago": lv(year) if year is not None else None}


def test_drought_wording():
    assert h.drought_sentence("Texas", D(43, 54, 65)).startswith("Drought eased in Texas this week: 43%")
    assert "up from 40%" in h.drought_sentence("Texas", D(45, 40))
    assert h.drought_sentence("Texas", D(41, 40)).startswith("Drought held steady")     # 1 pt is steady
    assert "A year ago" not in h.drought_sentence("Texas", D(41, 40, 45))               # within 10 pts
    s = h.drought_sentence("the district", D(100, 100, 80, d3=57))
    assert s.index("A year ago, 80% was in drought.") < s.index("About 57%")


def test_no_drought_says_dry_and_less_than_one():
    assert h.drought_sentence("X", D(0, 0, d0=5)) == "None of X is in drought this week."
    assert h.drought_sentence("X", D(0.2, 12, d0=22)).startswith("Less than 1% of X is in drought this week, though 22%")


def test_rain_and_bans():
    assert h.rain_sentence(0.81, through="2026-11-14") == "Rain in the week through Nov. 14 averaged 0.8 inches."
    assert h.rain_sentence(0.0, through="2026-11-14") == "The week through Nov. 14 brought almost no rain."
    assert h.rain_sentence(None) is None
    assert h.forecast_sentence(0.1) == "The National Weather Service forecast for the next 7 days looks mostly dry."
    assert "about 1.0 inch over" in h.forecast_sentence(1.02)
    assert h.forecast_sentence(None) is None
    assert h.burn_ban_sentence(0, 25) == "No counties have a burn ban."
    assert h.burn_ban_sentence(None, 25) is None


def test_stale_sources_drop_out():
    tx = {"drought": None, "burn_bans": None, "crops": {}}
    out = h.texas(tx, {"stale": True})
    assert out == {"sentences": [], "sources": [], "items": []}


def test_crop_pace_picks_biggest_gap_and_skips_done_stages():
    crops = {"cotton": {"progress": {"status": "fresh", "stages": [
                {"stage": "harvested", "pct": 68, "avg_5yr": 62},
                {"stage": "bolls_opening", "pct": 91, "avg_5yr": None}]}},
             "corn": {"progress": {"status": "fresh", "stages": [{"stage": "harvested", "pct": 100, "avg_5yr": 99}]}},
             "wheat": {"progress": {"status": "fresh", "stages": [{"stage": "planted", "pct": 84, "avg_5yr": 87}]}}}
    assert [t for _, t in h.crop_sentences(crops)] == ["Cotton is 68% harvested, ahead of the 5-year average of 62%.",
                                                      "Winter wheat is 84% planted, behind the 5-year average of 87%."]


def test_items_carry_topics():
    tx = {"drought": D(43, 54), "burn_bans": {"count": 2, "of": 254}, "crops": {}}
    out = h.texas(tx, None)
    assert [(i["topic"], i["source"]) for i in out["items"]] == [("drought", "usdm"), ("burn_bans", "burn_bans")]


def test_multi_stage_crop_is_one_sentence_and_done_harvest_on_request():
    crops = {"wheat": {"progress": {"status": "fresh", "stages": [
                {"stage": "emerged", "pct": 74, "avg_5yr": 71}, {"stage": "planted", "pct": 84, "avg_5yr": 87}]}},
             "corn": {"progress": {"status": "fresh", "stages": [{"stage": "harvested", "pct": 100, "avg_5yr": None}]}}}
    assert h.crop_sentences(crops) == [("wheat", "Winter wheat is 84% planted and 74% emerged, against 5-year averages of 87% and 71%.")]
    assert ("corn", "Corn harvest is complete.") in h.crop_sentences(crops, 99, done=True)


def test_rain_sentence_adds_percent_of_normal_only_with_normals():
    from kad.headline import rain_sentence
    assert "normal" not in rain_sentence(0.4)
    v = {"through": "2026-11-14", "days": 30, "pct": 61}
    assert rain_sentence(0.4, v, "2026-11-14").endswith("The 30 days through Nov. 14 brought about 61% of normal rain.")
    assert rain_sentence(0.4, {**v, "pct": 104}).endswith("brought about normal rain.")
    assert "normal" not in rain_sentence(0.4, {**v, "pct": None})


def test_estimate_sentence_always_says_estimate():
    assert h.estimate_sentence({"from": "2026-11-15", "through": "2026-11-19", "in": 1.08}) == \
        "Radar and rain gauge estimates add about 1.1 inches since then, through Nov. 19."
    assert "almost no rain" in h.estimate_sentence({"from": "2026-11-15", "through": "2026-11-19", "in": 0.01})
    assert h.estimate_sentence(None) is None


def test_district_estimate_follows_the_rain_sentence_only():
    entry = {"counties": 2, "rain_estimate": {"from": "2026-11-15", "through": "2026-11-19", "in": 0.5}}
    assert not any(i["source"] == "stage4" for i in h.district(entry, "x", None)["items"])
    entry["rain_7d_in"] = 0.2
    entry["rain_through"] = "2026-11-14"
    texts = h.district(entry, "x", None)["sentences"]
    assert texts[0].startswith("Rain in the week through Nov. 14") and texts[1].startswith("Radar and rain gauge")
