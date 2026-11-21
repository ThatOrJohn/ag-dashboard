# 0019: Satellite summaries on county cards

- **Status:** Accepted
- **Date:** 2026-11-21

## Context
County cards already listed leading Cropland Data Layer (CDL) classes, which could be dominated by
non-crop cover, and showed four of the six Rangeland Analysis Platform (RAP) cover types.

## Decision
- Show up to six CDL crop categories, ranked by their largest acreage in either the newest or earliest
  available county year. This keeps formerly prominent crops visible. The share uses all county land
  in the newest year. A crop with no classified acres in a published year is shown as zero.
- Show all available RAP cover types as percentages of rangeland, with the 1986–1995 average where
  available. Evaluate cover and forage freshness independently so cover can appear as soon as it arrives.

## Consequences
The tables use the county observations already in the pipeline. Historical columns appear as data
becomes available county by county. The publisher links let readers explore the underlying maps.
