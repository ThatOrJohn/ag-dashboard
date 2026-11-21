# 0003: Burn bans read from the TFS KMZ; #PolyStyle02 means "ban"

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
The Texas A&M Forest Service burn-ban KMZ has one placemark per county with one of two style ids, and
feasibility left open which one means "ban".

## Decision
`#PolyStyle02` = ban, `#PolyStyle00` = no ban (set in `regions/tx.yaml`). Any other style makes the adapter
fail, so the section hides instead of guessing.

## Why
In the KML, `#PolyStyle02` fills opaque red (`ff0000ff`, KML's aabbggrr) and `#PolyStyle00` has a fully
transparent fill. On 2026-11-20 TFS's own list (`BURNBAN.txt`, UTF-16, "89 Texas Burn Bans - 11/19/2026")
named exactly the 89 counties styled `#PolyStyle02`, and none of the others.

## Consequences
If TFS rebuilds the map file with new style ids, the burn-ban card hides and the run logs the failure.
Re-check against `BURNBAN.txt` and update the config. TFS asks for its logo on burn-ban graphics; we show
only text and a county map without TFS branding, crediting TFS by name. Revisit if we publish an image.
