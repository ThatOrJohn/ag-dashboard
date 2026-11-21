# 0009: Share images drawn at build time, showing only drought figures

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
Links shared to social or messaging apps show an Open Graph image. Images travel without the page footer,
which is where the required NASS notice lives.

## Decision
One 1200×630 PNG per page (`og/<name>.png`), drawn at build time with satori + sharp, as ms-sound-check
does. Each shows the page title and the drought sentence from the headline (Drought Monitor data, credited
with its map date), plus "Not an official source". Colors are the site's light tokens converted from OKLCH
to hex in `web/src/lib/og.ts`; fonts are the static @fontsource woff files.

## Why
Keeping NASS figures off the images means no image needs the NASS notice, and drought is the most
universally relevant figure. No burn-ban graphics, so the TFS logo requirement doesn't apply.

## Consequences
The images change every run; `?v=<build time>` on the URL keeps share caches honest. Adding crop numbers to
an image would require putting the NASS notice on it.
