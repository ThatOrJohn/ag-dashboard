# 0027: Flyovers are zoom-and-pan tours over the build-time map

- **Status:** Accepted
- **Date:** 2026-11-22

## Context
The animated stories (0024) replay one measure over time. They don't show a place: where the cotton is, how a
district's counties compare this week, or what makes one district different from its neighbor. The site's zoom
(US → state → district → county stop with a card) already suggests a way to tell a story about a place: move
through those levels and stop at the places worth stopping on.

A true 3D flyover (terrain, tilted camera) would need a tiled map and terrain tiles. That would reverse 0005
(static SVG, no map JavaScript, works without JS), add a large library, and use tile and basemap terms that
often fail 0014's "any use, no permission" rule.

## Decision
Add a story visual, `kind: "flyover"`. A flyover is a sequence of **stops** drawn on the existing build-time
county SVG. The camera eases between stops by animating the SVG `viewBox`. Each stop is a chapter.

- **Layout:** the 0025 two-column player. On the left, the map with the current stop's area highlighted and
  icons pinned at county centroids (cotton boll, cattle, water drop, well, rain gauge). On the right, the stop's
  name, two to four stat tiles (each with its source and as-of date), and a caption. Below 1000 px wide, the
  layout stacks.
- **Route strip:** the timeline under the map lists the stop names in order. Tapping one flies there. Playback
  holds on each stop for `chapterHoldMs`.
- **Built for any area (0026):** a US flyover stops at states, a state flyover at districts, a district
  flyover at counties. One visual covers all three levels.
- **Stops come from the data, as in 0024.** For example: the district whose drought changed most this week,
  the wettest county against normal, the county with the largest CDL cotton share. The tour always starts on
  the whole area and ends back on it.
- **Two kinds:**
  - **This week:** built from `latest.json` on every build. A stop whose source is stale is dropped. A
    seasonal measure shows "out of season" instead of last season's numbers. If too few stops remain, the
    tour hides like any other section.
  - **Profile:** from the annual sources (CDL crop mix, RAP rangeland cover, Census farms and cattle,
    normals). These rarely change, and they say what a district is rather than what happened this week.
- **Where they appear:** each district page links to its tour ("Take the tour"). The state tour and the
  featured districts' tours go on the Stories index. The other districts' tours are reachable from their
  district pages and from a pick-a-district map on the index.

## Why
- Zooming the SVG gives most of the feel of a flyover. It keeps 0005's static, accessible, indexable map and
  adds only a small amount of player JavaScript.
- A tour is the dashboard's own zoom, narrated, so it adds no new way to think about place. It also makes the
  county "map stop with a card" (seed.md) something a reader can follow without hunting for it.
- Data-chosen stops keep captions accurate as the weeks change, like the drought and harvest chapters.
- Stat tiles with a source and as-of date on every stop follow the rule that every figure shows both.

## Consequences
- **Strokes:** county outlines need `vector-effect: non-scaling-stroke`, or borders thicken as the camera
  zooms in.
- **Labels:** each stop has its own label set, placed at build time for that zoom with the 0005 addendum's
  rules (largest first, shrink, then drop). Labels placed for the whole state would be oversized or crowded
  once the camera is on a district.
- **Reduced motion:** stops cut instead of flying, and icons appear without entrance animation.
- **Without JavaScript,** the page shows the whole-area map and every stop's card in order. The stops table
  lists every figure, so no fact depends on the animation.
- **Icons** are a small inline SVG set drawn in ink or the data colors from `tokens.css`. Each one sits next to a
  text label or title, never color or shape alone. No agency logos are used as icons. The TFS logo stays only
  on burn-ban graphics.
- **The 1280×800 fit test (0025)** covers flyovers, including the stat tiles.
- **A US flyover** waits for the national data set in 0026. It is the natural way to deliver the ROADMAP's
  "national context on the US map".
- **District figures** on tiles keep their labels: my own totals, a lower bound where counties are
  unpublished, and "satellite-classified" for CDL.
- **Revisit** if a profile needs raster detail, such as field-level CDL or RAP pixels instead of county
  summaries. 0005 already says that would need its own decision.
- **Suggested order:**
  1. The flyover visual and a Texas "this week" tour across the 15 districts.
  2. Profile tours for the five featured districts, then all 15.
  3. The US tour.

## Implementation

Texas has a statewide weekly route across all districts with enough current figures. Districts have a
weekly route and an annual profile, each with up to five county stops. The Stories index features the
statewide tour and the five featured district profiles. Its district map and link list cover available
tours for all districts. Each district dashboard's **Take the tour** link opens its profile when available.

The player uses the same build-time boundaries for each stop and places labels against the stop's own
view. It holds for 2.6 seconds per chapter. The whole-area map, ordered stop cards and figures table
are rendered in HTML and SVG. The national tour remains pending the national data set in 0026.
See the [architecture guide](../ARCHITECTURE.md#from-json-to-pages) for the data inputs and freshness rules.
