# 0023. Forecast the next Texas cotton harvest report

- **Status** Accepted
- **Date** November 21, 2026

## Decision

Use the fall statewide NASS cotton harvest series to estimate the percent harvested as of the following
week ending. The baseline adds the median gain from the same or adjacent calendar week in prior seasons.
Ridge regression estimates the gain from calendar week, current harvest progress, and the previous
week's gain. If the previous report is missing, the forecast uses the baseline. Estimates stay between
the latest reported percentage and 100%.

## Evidence

The retrospective backtest trained on earlier seasons and predicted consecutive report weeks in each
test season. The saved USDA observations can include historical revisions. Mean absolute error is in
percentage points.

| Season | Scored weeks | Typical weekly gain | Ridge regression |
| --- | ---: | ---: | ---: |
| 2023 | 12 | 1.83 | 1.74 |
| 2024 | 13 | 1.54 | 1.15 |
| 2025 | 6 | 2.42 | 2.30 |
| 2026 through Nov. 15 | 11 | 2.95 | 2.64 |
| All | 42 | 2.12 | 1.87 |

The dashboard issues the ridge estimate. It uses the 80th percentile of the absolute replay errors
from prior seasons to form an estimated range once 20 such errors are available. Bounds are rounded
outward and limited to the reported progress and 100%. Observed coverage is tracked in the live history.

## Live operation

The scheduled run saves both predictions, the selected method, inputs, and the issue time when
the latest fall report still has a future target week. Retries keep the original prediction.
Once the exact target week is available, the run saves the first result it observes and its timestamp.
Forecasts for missing weeks stay in the history without contributing to accuracy. The data branch
stores the history in `snapshots/cotton_harvest.json`.

New seasons add training data automatically. Compare changes on the same report weeks using the
baseline and current forecast before changing the issued model. Reproduce the retrospective scores
with `python -m kad harvest-backtest` against a store with the NASS weekly observations.
