# Changelog

User-visible changes, newest first.

## Unreleased
- Flyovers: map tours that fly between places and stop where the data picks out something worth seeing.
  Texas has a tour of this week's conditions across its districts, and every district has a profile tour of
  its counties and a this-week tour. A dotted route links numbered stops; the camera pulls back between
  stops and settles in, a small plane inks each leg as it goes, and each stop lights up with its figures.
- The Stories page splits flyovers from replays. Flyovers sit in their own band with a route map on each card
  and a pick-a-district map whose labels no longer get covered by neighboring districts.
- New Stories section with animated replays, each with chapters, a table of every figure and its sources:
  - Two years of weekly Drought Monitor maps recoloring every Texas county.
  - Every Texas cotton harvest since 2021, raced side by side with a harvester in each season's lane.
  - Texas reservoirs month by month since 1950, as a lake that fills and drains.
  - Three Ogallala monitoring wells, one winter at a time.
  - The Brazos at Richmond through floods and droughts since 1991.
  - A year of feeder steer prices, with price tags and a pen of cattle sold each week.
  - Texas farms by county, 2017 to 2022 Census of Agriculture.
  - Five weeks of fall rain filling three district rain gauges.
- On desktop, each story's animation, caption and controls fit on one screen: the visual sits on the left,
  with the date, caption, readout and playback controls beside it.
- The Stories page shows featured stories two across and the rest as a compact grid of cards.
- The header's Stories link stands out as my own take on the data, and the More districts menu closes when
  you click outside it or press Escape.
- Fixed dark-mode drought colors: abnormally dry and moderate drought showed as green and exceptional
  drought as purple. The scale now runs from amber through orange to red as intended.
- About the data explains how to identify published figures, dashboard summaries, and dashboard forecasts.
  The cotton outlook links to its forecasting and scoring methods.
- The cotton card labels the USDA report and shows the outlook in a separate inset with a scale for
  reported progress, the forecast, and its estimated range.
- Cotton shows an estimate for the next statewide harvest report in season. The accuracy panel compares
  past estimates and their ranges with USDA results and a typical-week baseline.
- Cotton shows weekly boll weevil trapping and treatment by reporting area. Cotton, Corn & Sorghum,
  and Wheat & Small Grains link to crop-specific pest alerts and scouting guides.
- The Texas overview shows confirmed New World screwworm cases and recent county detections, with
  links to movement restrictions and planned sterile fly releases. The card flags stale figures
  after three days without a refresh and disappears after 14 days.
- Cattle & Hay and Edwards Plateau show weekly San Angelo auction prices for slaughter hair lambs and
  goat kids in the 50–69 lb class, with a comparison to the prior reported sale where available.
- County cards show the largest satellite-classified crop categories, their share of county land, and
  acres from an earlier year where available. Rangeland cover shows all published cover types alongside
  the 1986–1995 average where available.
- Every Texas district now has its own page with a card for every county: the ten districts beyond the
  five featured ones are in a "More districts" menu, the Texas map links every county, and the district
  table links each name. Forecasts and land cover for the new counties fill in over the next few updates.
- The Texas drought map names all 15 districts, multi-word names on two lines.
- Persona pages list drought, rain and burn bans for all 15 districts, featured ones first.

## 0.1.0 (first public version)
- Texas overview, five featured NASS districts and a card for every county: drought (U.S. Drought Monitor),
  crop progress and condition (NASS), feeder cattle prices (AMS), burn bans (Texas A&M Forest Service),
  observed weather and 1991–2020 normals (NOAA nClimGrid-Daily), Stage IV rain estimates and the 7-day
  forecast (NWS).
- Rain since Jan. 1 against normal and typical range; rain vs normal for each district and county.
- Annual context: Census of Agriculture, NASS county estimates, Cropland Data Layer land cover and
  Rangeland Analysis Platform cover and forage.
- Views by what you raise (Corn & Sorghum, Cotton, Wheat & Small Grains, Cattle & Hay, Land, Water &
  Weather), share images, light and dark themes.
