# 0006: Cattle prices are head-weighted averages of Medium and Large No. 1 lots, in 100 lb classes

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
AMS auction reports give one row per lot group: class, frame, muscle grade, average weight, average price
per cwt and head. The weight-break fields are usually blank.

## Decision
`steers:500` = feeder steers, Medium and Large frame No. 1 muscle, averaging 500–599 lb: the head-weighted
average of those rows' prices. The same goes for heifers. Slaughter cows are one series (all grades). The
site shows four series per report, compared with the previous sale, and quotes the AMS reporter's narrative
as written.

## Why
M&L No. 1 is the most-reported feeder grade in all three reports (1955, 3724, 2015), so the series is
comparable week to week. 100 lb classes are how producers talk about calves.

## Consequences
These are our averages of the reported lots, not AMS's own weighted averages, and the card says so. Thin
sales can swing; the head count is stored (`:head`) for when we want to hide thin classes.
