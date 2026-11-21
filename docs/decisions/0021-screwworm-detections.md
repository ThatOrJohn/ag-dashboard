# 0021. New World screwworm detections

- **Status** Accepted
- **Date** 2026-11-21

The Texas overview uses the official [USDA APHIS detections dashboard][dashboard] and its public
[Tableau CSV export][csv]. The Texas Animal Health Commission points to USDA for individual detections.
The national export includes confirmation dates, county and state names, case types, statuses and
record IDs. The adapter validates the export, maps Texas counties to FIPS and replaces the saved
snapshot only after validation. A full replacement lets corrections, reclassifications and changes
in case status carry through. The public site shows statewide totals and the latest confirmation day
in each of the five most recently affected counties. Wild-fly trap detections have their own count.

The CSV has no publication timestamp, and Texas can go weeks between detections. Freshness measures
the last successful download and validation. After three Texas calendar days the card flags the saved
figures as stale. At 14 days the build omits the card, and the browser applies the same deadlines to a
previously built page. A successful refresh clears the warning. An unchanged but valid USDA export
still counts as a successful refresh.

The card links to the Texas Animal Health Commission movement restriction map and the USDA weekly
planned sterile fly dispersal map. USDA also gives release volumes in agency updates, sometimes across
multiple jurisdictions. No structured record of completed Texas releases was verified.

[dashboard]: https://www.aphis.usda.gov/animals/animal-health/livestock-and-poultry-disease/stop-screwworm/current-status/confirmed
[csv]: https://publicdashboards.dl.usda.gov/t/MRP_PUB/views/NewWorldScrewwormPublicReporting_17805168329840/ExportToCSV.csv?:showVizHome=no
