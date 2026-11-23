# 0028: One-row header everywhere; Stories shows flyovers and replays side by side

- **Status:** Accepted
- **Date:** 2026-11-22

## Context
The header was a wrapping flex row. On a 1440 px screen the brand and nav needed exactly the 1240 px
available, so most pages wrapped to two rows. The Stories page didn't, because its bold current link made
the nav 2 px narrower. Between 1101 and 1279 px every page wrapped, and phones always did. The Stories link
had a small play triangle that read as a dropdown caret, but the link doesn't expand.
On the Stories page the flyover band, with six large route cards and the district picker, filled about
two screens. Replays started below the fold, so a desktop visitor could miss them.

## Decision
- The header never wraps (`nowrap`). As the screen narrows, items fold away at fixed breakpoints, and a
  Playwright test checks for one row at 11 widths on four pages:
  - from 1280 px: featured districts inline; the brand's "Texas" tag shows from 1440 px;
  - up to 1279 px: every district folds into the Districts menu;
  - up to 699 px: the brand's "Texas" tag drops;
  - up to 539 px: the brand is the mark alone (the wordmark stays as screen-reader text), and the "Texas"
    link moves to the top of the Districts menu as "All of Texas".
- The nav says "About" instead of "About the data". The page itself is still titled About the data.
- Stories is a rounded accent pill with no icon. A pill reads as a destination, not a menu toggle.
- From 1024 px the Stories page puts flyovers and replays in two equal columns. Flyover cards wider than
  24rem (a container query) switch to a compact sideways layout with a small thumbnail. The district picker
  moves to its own full-width flyover band below both columns.
- Each band heading has a small looping vignette in place of the static icon (`BandArt.astro`). Flyovers
  show a camera frame hopping between waypoints as the route draws. Replays show a play button giving way to
  a playhead that draws a line chart. With reduced motion it shows the finished frame and doesn't move.

## Why
Breakpoints measured against the real nav width make the header predictable. The old wrap depended on
which link was bold. Two columns put both kinds of story above the fold at 1280×800 and cut the page from
about 2,800 px to 2,400 px at 1440 px wide. The two columns come out nearly the same height.

## Consequences
Adding a sixth featured district or a new top-level nav item needs the breakpoints re-measured. The header
test fails if it no longer fits. The narrow-screen menu now carries the Texas link on phones.
