# 0020: Weekly sheep and goat auction prices from San Angelo

- **Status:** Accepted
- **Date:** 2026-11-21

## Source

USDA AMS publishes one [weekly San Angelo sheep and goat auction report](https://mymarketnews.ams.usda.gov/viewReport/2014)
for both species. The [November 17, 2026 sale](https://mymarketnews.ams.usda.gov/filerepo/sites/default/files/2014/2026-11-17/1366325/ams_2014_00360.pdf)
includes both series. [Report 2013](https://mymarketnews.ams.usda.gov/viewReport/2013) covers a special feeder calf auction.

## Decision

Use the same AMS refresh and price units as the cattle markets. For each sale, show head-weighted
prices for slaughter hair lambs and slaughter goat kids, using lots whose average weight is 50–69 lb
and whose reported price is per hundredweight. The band includes lots published for both species and
keeps the weight range consistent between sales. The mix of grades can vary by sale.

Cattle & Hay and the Edwards Plateau district page have a separate section for this auction. If a sale
has no matching prices, show a source link and the sale date. Hide prices after 14 days, the same
limit as the other auctions.
