# 0025: Stories fit one desktop screen; the daily rain map is dropped

- **Status:** Accepted
- **Date:** 2026-11-22

## Context
On a desktop screen each story's controls sat 200–650 px below the fold: the heading, a full-width visual,
the caption panel and the timeline were stacked. Play, the slider and the chapters, which make a story work,
needed a scroll. The daily county rain map ("Every rainy day of …") had lots of motion but read as noise:
a day of rain says little on its own, and the dashboard already covers rain this week and since Jan. 1.

## Decision
- From 1000 px wide, the player is two columns. The visual and its timeline go on the left. The date,
  caption, readout (map stories) and controls go on the right. The page heading is compact.
- Visuals cap their height with `--vis-max`, which the player sets from `100svh`. On short screens
  (up to 860 px tall) the map readouts shrink and the census lists show their top three. The full table
  below has every figure.
- A Playwright test checks that each story's controls end within a 1280×800 viewport.
- The daily rain map story, its visual and its `stories.json` entry are removed.
- The Stories index shows featured stories two across and the rest as a compact card grid.
- The Stories header link is an accent pill with a play mark, so it reads as my own take on the data
  rather than another data view.

## Why
- Map stories are height-limited, so the right column gets half the width (`1fr 1fr`). Their chapter
  buttons then fit in two rows instead of three. Wide visuals keep about 64% of the width.
- Capping the SVG height (not the width) keeps every visual's aspect ratio. Extra space letterboxes inside
  the visual's own background.
- Below 1000 px the stacked layout stays: one column already reads well on phones and tablets.

## Consequences
- A new visual should honor `--vis-max` (falling back to no cap) and keep its readout compact, or the
  laptop-fit test fails.
- 1024×768 is the smallest size that was checked. The drought story ends about 12 px past the fold there.
