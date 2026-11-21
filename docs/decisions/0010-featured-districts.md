# 0010: Five featured districts get the full district view, and the site says why

- **Status:** Accepted
- **Date:** 2026-11-20 (reworded 2026-11-21)

## Context
The site gives five NASS districts the full district view and treats the rest of Texas as context.
Readers outside those districts would reasonably ask why theirs gets less.

## Decision
The featured districts are Blacklands, South Central, Edwards Plateau, East Texas North and East Texas
South: the ones the site started with. District names follow Quick Stats, the first source (NASS's district
map page calls the last two "North East Texas" and "South East Texas"). The Texas page heads that section
"Featured districts", district pages carry "featured district" in their eyebrow, and About has a "Why these
districts" section saying the rest will get the same view in time. The list is a config edit (`home:` in
`regions/tx.yaml`); the wording counts and lists districts from config.

## Why
It answers the "why not my district" question plainly and honestly, without promising a date.

## Consequences
On narrow screens five district links don't fit in the header, so they fold into a "Districts" menu
below 1100 px. Opening every district needs a different navigation (a picker or the map) rather than
more header links; that is on the roadmap.
