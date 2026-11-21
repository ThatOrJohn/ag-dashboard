# 0022. Crop pest monitoring

- **Status** Accepted
- **Date** 2026-11-21

The Texas Boll Weevil Eradication Foundation publishes trapping and treatment counts in a weekly
PDF linked from its [homepage](https://tbwef.org/). The importer follows that link and uses Poppler
to extract the published figures. The homepage sometimes links to files in a different month’s
upload directory. The importer validates the report week and all three reporting areas before
replacing the saved snapshot. Failed or older reports leave the previous snapshot in place.

Cotton displays counts by the foundation’s reporting areas and links to its zone finder and the
source report. The figures expire once the report’s week-beginning date is more than 14 days old, regardless of
when the PDF was downloaded. An area with no trap inspections is labeled accordingly.

The crop persona configuration holds links to Texas A&M AgriLife Extension pest alerts and scouting
guides. These resources include cotton jassid and corn leafhopper alerts and scouting information
for sorghum aphid and small-grain pests.
